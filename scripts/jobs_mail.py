#!/usr/bin/env python3
"""Versand der Job-Akquise-Mails über den MCP-Mailserver.

Sicherheit:
- Standard ist **Dry-Run** (nur Tabelle, kein Versand).
- `--send` verlangt zusätzlich `--yes`.
- `--to <adresse>` leitet **alle** Mails an eine Testadresse um (Betreff `[TEST]`).
- Echte Arbeitgeberadressen nur mit `--allow-real`.
- Jede Mail braucht eine Abmelde-Option (UWG §7): `Abmelden` / `Unsubscribe` /
  `Désabonner`; sonst wird sie verworfen.

Aufruf:
    python3 scripts/jobs_mail.py                      # Dry-Run
    python3 scripts/jobs_mail.py --send --yes --to du@example.org
    python3 scripts/jobs_mail.py --send --yes --allow-real --limit 5
"""
from __future__ import annotations

import argparse
import json
import os
import re
import select
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTBOX = ROOT / "jobs" / "outbox"
ANSPRACHE = ROOT / "jobs" / "ansprache.jsonl"
EMAIL_SERVER = ROOT / "mcp-email-server.py"
PY = ROOT / ".venv-streamlit" / "bin" / "python3"
ABMELDE = re.compile(r"(abmelden|unsubscribe|d[ée]sabonner)", re.I)


def parse_eml(path: Path) -> dict:
    """Sehr einfacher .eml-Parser (To, Subject, Body, Zusatz-Header)."""
    text = path.read_text(encoding="utf-8")
    kopf, _, body = text.partition("\n\n")
    felder = {}
    for zeile in kopf.splitlines():
        if ":" in zeile:
            k, v = zeile.split(":", 1)
            felder[k.strip().lower()] = v.strip()
    return {"pfad": path, "to": felder.get("to", ""), "subject": felder.get("subject", ""),
            "body": body.strip(), "firma": felder.get("x-kmhr-firma", "").strip(),
            "keys": felder.get("x-kmhr-keys", "").split()}


def merke_ansprache(m: dict, ziel: Path | None = None) -> bool:
    """Schreibt eine erfolgreich versendete Ansprache als JSONL-Zeile (Sperrliste).

    Ohne Firma oder ohne Keys wird nichts geschrieben (False).
    """
    firma = (m.get("firma") or "").strip()
    keys = list(m.get("keys") or [])
    if not firma or not keys:
        return False
    # Modul liegt in scripts/; defensiv, damit ein fehlendes Modul nicht bricht.
    try:
        import jobs_keys as jk
    except ImportError:
        jk = None
    firma_key = ""
    if jk is not None:
        fn = getattr(jk, "firma_key", None)
        if fn is not None:
            firma_key = fn(firma)
    pfad = ziel or ANSPRACHE
    pfad.parent.mkdir(parents=True, exist_ok=True)
    satz = {"datum": datetime.now().strftime("%Y-%m-%d"), "firma": firma,
            "firma_key": firma_key, "keys": keys, "email": m.get("to", ""),
            "betreff": m.get("subject", "")}
    with pfad.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(satz, ensure_ascii=False) + "\n")
    return True


def sammle(outbox: Path | None) -> list[dict]:
    basis = outbox or OUTBOX
    dateien = sorted(basis.rglob("*.eml")) if basis.exists() else []
    return [parse_eml(p) for p in dateien]


def pruefen(mails: list[dict]) -> tuple[list[dict], list[str]]:
    ok, fehler = [], []
    gesehen: set[str] = set()
    for m in mails:
        schluessel = (m["to"] or "").lower()
        if schluessel and schluessel in gesehen:
            continue
        if schluessel:
            gesehen.add(schluessel)
        if not m["to"] or "@" not in m["to"]:
            fehler.append(f"{m['pfad'].name}: keine gültige Empfängeradresse")
            continue
        if not ABMELDE.search(m["body"]):
            fehler.append(f"{m['pfad'].name}: Abmelde-Option fehlt")
            continue
        ok.append(m)
    return ok, fehler


def mcp_send(to: str, subject: str, body: str, timeout: int = 90) -> tuple[bool, str]:
    """Ruft mcp-email-server.py::send_email über das MCP-Protokoll auf."""
    p = subprocess.Popen([str(PY), str(EMAIL_SERVER)], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         cwd=str(ROOT), text=True, bufsize=1)

    def send(obj: dict) -> None:
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()

    def read(t: float) -> dict | None:
        end = time.time() + t
        while time.time() < end:
            r, _, _ = select.select([p.stdout], [], [], 0.5)
            if not r:
                continue
            line = p.stdout.readline()
            if not line:
                return None
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return None

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                         "clientInfo": {"name": "jobs-mail", "version": "1.0"}}})
        if not read(30):
            return False, "kein initialize"
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
              "params": {"name": "send_email",
                         "arguments": {"to": to, "subject": subject, "body": body}}})
        res = read(timeout)
        if not res:
            return False, "keine Antwort"
        if "error" in res:
            return False, str(res["error"])[:160]
        txt = "\n".join(c.get("text", "") for c in res.get("result", {}).get("content", []))
        return txt.startswith("OK"), txt[:160]
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()


def run(args: argparse.Namespace) -> int:
    mails = sammle(Path(args.outbox).resolve() if args.outbox else None)
    ok, fehler = pruefen(mails)
    print(f"Gefunden: {len(mails)} | versandbereit: {len(ok)} | verworfen: {len(fehler)}")
    for f in fehler:
        print("  VERWORFEN:", f)
    if not ok:
        print("Keine versandbereiten Mails.")
        return 2

    ziel = (Path(args.outbox).resolve() if args.outbox
            else (OUTBOX / datetime.now().strftime("%Y-%m-%d")).resolve())
    ziel.mkdir(parents=True, exist_ok=True)
    log = ziel / f"versand-{datetime.now().strftime('%H%M%S')}.md"
    zeilen = [f"# Versand {datetime.now():%Y-%m-%d %H:%M}", "",
              f"Modus: {'SEND' if args.send else 'DRY-RUN'}", ""]

    if not args.send:
        print(f"\n{'Empfänger':42} {'Betreff'}")
        for m in ok[: args.limit]:
            print(f"{m['to'][:42]:42} {m['subject'][:60]}")
            zeilen.append(f"- DRY-RUN: {m['to']} — {m['subject']} ({m['pfad'].name})")
        log.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
        print(f"\nDry-Run: {min(len(ok), args.limit)} Mails wuerden versendet. Log: {log}")
        return 0

    if not args.yes:
        print("--send braucht --yes (Sicherheit).")
        return 2
    stunde = datetime.now().hour
    # Ruhezeit gilt fuer echte Empfaenger. Ein Testversand an --to (Betreiber)
    # ist ausgenommen, weil er niemanden stoert.
    ist_test = bool(args.to)
    if (stunde < 8 or stunde >= 20) and not args.force and not ist_test:
        print(f"Ruhezeit: {stunde:02d}:00 Uhr — Versand nur 08:00-20:00 (--force ueberschreibt).")
        return 2
    allow_real = args.allow_real or os.environ.get("JOBS_ALLOW_REAL") == "1"
    if not args.to and not allow_real:
        print("Echte Arbeitgeberadressen nur mit --allow-real oder JOBS_ALLOW_REAL=1.")
        return 2

    gesendet = 0
    for m in ok[: args.limit]:
        to = args.to or m["to"]
        subject = m["subject"] if not args.to else f"[TEST] {m['subject']}"
        ok_send, info = mcp_send(to, subject, m["body"])
        status = "OK" if ok_send else "FEHLER"
        print(f"{status}: {to} — {subject[:50]} — {info[:60]}")
        zeilen.append(f"- {status}: {to} — {subject} — {info[:80]}")
        gesendet += 1 if ok_send else 0
        # Nur echter Versand an Arbeitgeber wird gesperrt (kein Dry-Run, kein --to).
        if ok_send and not args.to:
            merke_ansprache(m)
        time.sleep(1.2)
    log.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    print(f"\nGesendet: {gesendet}/{min(len(ok), args.limit)} | Log: {log}")
    return 0 if gesendet else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Job-Akquise-Versand über MCP")
    ap.add_argument("--outbox", default="", help="Ordner mit .eml-Dateien")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--to", default="", help="Testadresse (leitet alle Mails um)")
    ap.add_argument("--allow-real", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--force", action="store_true", help="Ruhezeit (20-8 Uhr) ignorieren")
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
