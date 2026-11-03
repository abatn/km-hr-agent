#!/usr/bin/env python3
"""
KM-HR-Agent – Uptime-Check (02.11.2026)
=======================================
Ruft `/healthz` ab und alarmiert bei HTTP != 200 oder `status != "ok"`.

Betrieb:
  * systemd-Timer `kmhr-healthcheck.timer` (alle 30 s), oder
  * Cron `deploy/cron/kmhr-healthcheck.cron` (zwei Zeilen pro Minute).

Alarmkanäle (optional, per Env):
  * Log:        logs/healthcheck.log (immer)
  * Webhook:    KMHR_ALERT_WEBHOOK  (JSON-POST)
  * E-Mail:     KMHR_ALERT_EMAIL + SMTP_* (aus .env-email)

Dedupe: derselbe Fehler wird höchstens alle `KMHR_ALERT_REPEAT` Sekunden
(Default 1800) erneut gemeldet. Eine Erholung wird einmalig gemeldet.

Exit: 0 = gesund, 1 = Alarm (systemd/Cron macht den Fehlschlag sichtbar).
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import smtplib
import ssl
import sys
import time
import urllib.error
import urllib.request
from email.message import EmailMessage
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_URL = "https://jobs.hanibal-ai.com/healthz"
LOG_DIR = PROJECT_ROOT / "logs"


def _load_env_file(path: Path) -> None:
    """Liest KEY=VALUE aus einer .env (ohne bereits gesetzte Werte zu überschreiben).

    Cron startet ohne EnvironmentFile; damit funktionieren Webhook/E-Mail auch
    dort. Kommentare und Leerzeilen werden ignoriert.
    """
    if not path.is_file():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())
    except OSError:
        pass


def evaluate_health(http_status: int, payload: dict) -> tuple[bool, list[str]]:
    """Reine Bewertungsfunktion (testbar): (ok, Gründe).

    Alarm bei HTTP != 200 ODER status != "ok" ODER einer der Teilbefunde
    (db/runner/audit) ist negativ. `degraded` ist bewusst ein Alarm: die App
    antwortet zwar, aber der Runner oder die Audit-Kette ist gestört.
    """
    reasons: list[str] = []
    if http_status != 200:
        reasons.append(f"HTTP {http_status}")
    if not isinstance(payload, dict):
        reasons.append("Antwort ist kein JSON-Objekt")
        return False, reasons
    status = str(payload.get("status") or "")
    if status != "ok":
        reasons.append(f"status={status or 'fehlt'}")
    db = payload.get("db") or {}
    if not db.get("ok"):
        reasons.append("db.ok=false")
    runner = payload.get("runner") or {}
    if not runner.get("alive"):
        reasons.append("runner.alive=false")
    audit = payload.get("audit") or {}
    if not audit.get("ok"):
        reasons.append("audit.ok=false")
    return (len(reasons) == 0), reasons


def should_alert(now: float, state: dict, ok: bool, repeat: float) -> bool:
    """Dedupe: Alarm nur bei Zustandswechsel oder nach `repeat` Sekunden."""
    last_ok = state.get("last_ok")
    last_ts = float(state.get("last_alert_ts") or 0)
    if ok:
        return False
    if last_ok is False and (now - last_ts) < repeat:
        return False
    return True


def _post_webhook(url: str, text: str, payload: dict) -> None:
    body = json.dumps({"text": text, "source": "kmhr-healthcheck",
                       "payload": payload}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read(1)


def _send_email(to_addr: str, subject: str, text: str) -> None:
    host = os.environ.get("SMTP_HOST", "").strip()
    if not host:
        return
    port = int(os.environ.get("SMTP_PORT", "587") or 587)
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    sender = os.environ.get("SMTP_FROM", user or "no-reply@hanibal-ai.com")
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(text)
    starttls = os.environ.get("SMTP_STARTTLS", "1").strip().lower() not in ("0", "false", "no")
    with smtplib.SMTP(host, port, timeout=15) as smtp:
        if starttls:
            smtp.starttls(context=ssl.create_default_context())
        if user:
            smtp.login(user, password)
        smtp.send_message(msg)


def _alert(text: str, payload: dict) -> list[str]:
    """Sendet über alle konfigurierten Kanäle; Rückgabe: genutzte Kanäle."""
    used: list[str] = []
    webhook = os.environ.get("KMHR_ALERT_WEBHOOK", "").strip()
    if webhook:
        try:
            _post_webhook(webhook, text, payload)
            used.append("webhook")
        except Exception as ex:
            print(f"[healthcheck] Webhook fehlgeschlagen: {ex!r}", file=sys.stderr)
    mail = os.environ.get("KMHR_ALERT_EMAIL", "").strip()
    if mail:
        try:
            _send_email(mail, "[KM-HR-Agent] ALARM: /healthz", text)
            used.append("email")
        except Exception as ex:
            print(f"[healthcheck] E-Mail fehlgeschlagen: {ex!r}", file=sys.stderr)
    return used


def _read_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_state(path: Path, state: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=1),
                        encoding="utf-8")
    except OSError:
        pass


def run(url: str, timeout: float, repeat: float) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "healthcheck.log"
    state_path = LOG_DIR / "healthcheck-state.json"
    state = _read_state(state_path)
    now = time.time()

    http_status = 0
    payload: dict = {}
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            http_status = int(resp.status)
            payload = json.loads(resp.read().decode("utf-8", "replace") or "{}")
    except urllib.error.HTTPError as ex:
        http_status = int(ex.code)
        try:
            payload = json.loads(ex.read().decode("utf-8", "replace") or "{}")
        except (ValueError, TypeError):
            payload = {}
    except (urllib.error.URLError, TimeoutError, OSError,
            http.client.HTTPException) as ex:
        payload = {"status": "unreachable", "error": repr(ex)}
    except ValueError as ex:
        payload = {"status": "unreachable", "error": repr(ex)}

    prev_ok = state.get("last_ok")
    ok, reasons = evaluate_health(http_status, payload)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    base = (f"http={http_status} status={payload.get('status')} "
            f"gruende={';'.join(reasons) or '-'}")

    if ok:
        line = f"{stamp} OK {base}"
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        if prev_ok is False:
            recovery = f"{stamp} RECOVERY {base}"
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(recovery + "\n")
            _alert(recovery, payload)
        state.update({"last_ok": True, "last_alert_ts": 0, "last_reason": ""})
        _write_state(state_path, state)
        print(line)
        return 0

    # Dedupe: nur bei Zustandswechsel oder nach `repeat` erneut benachrichtigen.
    # Die Log-Zeile unterscheidet ALARM (Benachrichtigung) von STILL (weiterhin
    # kaputt, aber innerhalb des Wiederholungsfensters).
    alerted = should_alert(now, {"last_ok": prev_ok,
                                 "last_alert_ts": state.get("last_alert_ts", 0)},
                           ok, repeat)
    state["last_ok"] = False
    state["last_reason"] = ";".join(reasons)
    if alerted:
        used = _alert(f"{stamp} ALARM {base}", payload)
        state["last_alert_ts"] = now
        state["last_channels"] = used
    line = f"{stamp} {'ALARM' if alerted else 'STILL'} {base}"
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    _write_state(state_path, state)
    print(line, file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="KM-HR-Agent Uptime-Check")
    parser.add_argument("--url", default=os.environ.get("KMHR_HEALTH_URL", DEFAULT_URL))
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--repeat", type=float,
                        default=float(os.environ.get("KMHR_ALERT_REPEAT", "1800")))
    parser.add_argument("--env-file", default=os.environ.get("KMHR_ENV_FILE",
                                                             str(PROJECT_ROOT / ".env")))
    args = parser.parse_args()
    _load_env_file(Path(args.env_file))
    _load_env_file(PROJECT_ROOT / ".env-email")
    return run(args.url, args.timeout, args.repeat)


if __name__ == "__main__":
    raise SystemExit(main())
