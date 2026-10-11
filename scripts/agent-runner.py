#!/usr/bin/env python3
"""
KM-HR-Agent – Agent-Runner (Phase 5, Spec v3)
=============================================
Hintergrund-Runner für die agent_tasks-Queue (data/feedback.db).

Kernprinzip (knowledge/system/agent-automation.md v3):
- Ausführung A – MCP-direct (deterministisch, kein LLM):
    create_invitation → Meeting-Raum (Projektstandard seit 27.09.2026: VDO.Ninja, KEIN Google Meet, KEIN Jitsi)
                       + meeting-tools.generate_screening_questions
                       + meeting-tools.generate_ics_file (meet_url = VDO.Ninja)
                       + email-sender.send_pre_screen_invitation
    send_confirmation / send_rejection / notify_hr → email-sender.send_email
    onboarding_release → Marker (bestehender 7️⃣-Mechanismus zeigt die Checkliste)
- Ausführung B – LLM-Tasks via opencode run (NVIDIA NIM, live getestet 12.09.2026):
    extract_profile, match_candidate, check_compliance, assess_culture_fit
- Pförtner-Regel (User-Entscheidung 12.09.2026):
    Score >= 60 UND Compliance = COMPLIANT → JA → notify_hr-Mail an HR
    sonst → NEIN → KEINE Mail, Ergebnisse bleiben für HR sichtbar (Suche/Talentpool)
- Variante A (Mensch-in-der-Schleife): Der Runner versendet Einladung/Absage NUR
  nach HR-Klick im Portal (Trigger-Feld im Payload). Er lädt/lehnt nie selbst ab.

Start:  python3 scripts/agent-runner.py [--once] [--dry-run]
Env:    KMHR_RUNNER_AUTOSTART=0 (App-Start-Hook respektiert das)
PID:    data/agent-runner.pid
"""

import json
import os
import random
import re
import signal
import sqlite3
import string
import subprocess
import sys
import time
import requests
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from ansvar_gateway import ansvar_search, get_ansvar_token

# ─── i18n (Variante B, P2/P3 07.10.2026) ────────────────────────────────
# Spec: knowledge/system/i18n-runner-chain.md §7.1 Punkt 3–5. NUR die
# framework-freie Kernschicht (gettext, kein NiceGUI) importieren — der Runner
# läuft in einem eigenen Prozess ohne NiceGUI-Session.
from webui.i18n_core import tr, SUPPORTED

# ISO-Kürzel → Klarname für die LLM-Prompt-Anweisung (§7.1 Punkt 5).
LANG_NAMES = {"de": "Deutsch", "en": "Englisch", "fr": "Französisch", "ar": "Arabisch"}


def _lang(payload: dict) -> str:
    """Payload-Sprache (Variante B): nur Werte aus SUPPORTED, sonst Default 'de'.

    Alt-Tasks ohne `language` → `de` (Spec §7.1 Punkt 4, keine Rück-Übersetzung).
    """
    lang = (payload or {}).get("language")
    return lang if lang in SUPPORTED else "de"


def _ki_hinweis(lang: str) -> str:
    """Signatur-Fußzeile aller Kandidaten-/HR-Mails (EU AI Act Art. 50)."""
    return "\n\n--\n" + tr(
        "Diese Nachricht wurde im Rahmen des Bewerbungsverfahrens "
        "mit Unterstützung eines KI-Systems (EU AI Act Art. 50) erstellt.", lang)


def _pdf_forensic_pre_scan(cand_id: int) -> str:
    """ pdf-verify-mcp Pre-Scan für verify_documents (SKILL.md Schritt 4a).
    Führt evaluate_policy + verify_integrity auf dem ersten PDF des Kandidaten aus.
    Gibt Trust-Verdict + Integritäts-Info als String zurück. Quelle: npm @shuji-bonji/pdf-verify-mcp v0.26.0.
    """
    # PDF-Pfad finden (candidate_documents oder Fallback testdaten/)
    pdf_pfad = None
    try:
        conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
        c.execute("""SELECT datei_pfad FROM candidate_documents
                     WHERE candidate_id = ? AND datei_pfad LIKE '%.pdf'
                     ORDER BY hochgeladen_am DESC LIMIT 1""", (cand_id,))
        row = c.fetchone(); conn.close()
        if row and row[0] and Path(row[0]).exists():
            pdf_pfad = row[0]
    except Exception:
        pass
    if not pdf_pfad:
        # Fallback: glob testdaten/
        for p in sorted(Path(PROJECT_ROOT).glob(f"testdaten/kandidat-{cand_id}-*.pdf")):
            pdf_pfad = str(p); break
    if not pdf_pfad:
        return "(kein PDF gefunden für forensischen Pre-Scan)"
    # pdf-verify-mcp aufrufen (npx, kein pip nötig)
    ergebnisse_parts = []
    for tool_name in ("evaluate_policy", "verify_integrity"):
        try:
            cmd = ["npx", "-y", "@shuji-bonji/pdf-verify-mcp"]
            input_json = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                     "params": {"name": tool_name,
                                                "arguments": {"file_path": pdf_pfad,
                                                               "response_format": "markdown"}}})
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, cwd=str(PROJECT_ROOT))
            stdout, stderr = proc.communicate(input=(input_json + "\n").encode("utf-8"), timeout=60)
            stdout_str = stdout.decode("utf-8", errors="replace")
            if proc.returncode == 0 and stdout_str.strip():
                for line in stdout_str.strip().splitlines():
                    if line.startswith("{"):
                        resp = json.loads(line)
                        content = resp.get("result", {}).get("content", [])
                        text = "\n".join(c.get("text", "") for c in content)
                        if text:
                            ergebnisse_parts.append(f"### {tool_name}\n{text[:800]}")
                        break
        except subprocess.TimeoutExpired:
            log(f"   pdf-verify-mcp Timeout bei {tool_name}")
        except Exception as e:
            log(f"   pdf-verify-mcp Fehler ({tool_name}): {e}")
    if ergebnisse_parts:
        return "\n\n".join(ergebnisse_parts)
    return "(pdf-verify-mcp nicht verfügbar – forensischer Pre-Scan übersprungen)"

DB_PATH = PROJECT_ROOT / "data" / "feedback.db"
PID_FILE = PROJECT_ROOT / "data" / "agent-runner.pid"
LOG_FILE = PROJECT_ROOT / "logs" / "agent-errors.log"
# R6-1 (30.09.2026): Logrotation (Design-Entscheidung): 5 MB × 3 Altdateien
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUPS = 3
ERGEBNISSE = PROJECT_ROOT / "ergebnisse"

# .env-runner laden (falls Umgebungsvariable nicht gesetzt)
_env_runner = PROJECT_ROOT / ".env-runner"
if _env_runner.exists():
    for _line in _env_runner.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# LLM-Modell (direkte API, keine Provider-Präfixe nötig)
LLM_MODEL = os.environ.get("KMHR_LLM_MODEL", "nvidia/nemotron-3-super-120b-a12b")

# Connector-Server (gleiche wie opencode.json – direkter stdio JSON-RPC)
VENV_PY = PROJECT_ROOT / ".venv-pdf" / "bin" / "python3"
EMAIL_SERVER = PROJECT_ROOT / "mcp-email-server.py"
MEETING_SERVER = PROJECT_ROOT / "mcp-meeting-server.py"

# HR-Connectoren (Phase 1, verifiziert 15.09.2026)
HR_BENCHMARK_SERVER = PROJECT_ROOT / "connectors" / "hr-benchmark-server.py"
SALARY_DATA_SERVER = PROJECT_ROOT / "connectors" / "salary-data-server.py"
PRESCREEN_CONFIG_SERVER = PROJECT_ROOT / "connectors" / "prescreen-config-server.py"

LOOP_SECONDS = 60
MAX_TASKS_PER_LOOP = 5
MCP_TIMEOUT = 60          # Sekunden pro MCP-Tool-Aufruf
LLM_TIMEOUT = 600         # 10 min pro LLM-Task (Spec §4)
MAX_ATTEMPTS = 3

DRY_RUN = "--dry-run" in sys.argv
RUN_ONCE = "--once" in sys.argv

# ─── Logging ─────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        # R6-1 (30.09.2026): Logrotation — Design-Entscheidung (keine externe
        # Quelle): max 5 MB je Datei, 3 Altdateien (.1 = neueste).
        # Die Datei war ohne Rotation auf 10,2 MB gewachsen (34.609 NEIN-Zeilen
        # aus der Gatekeeper-Schleife, ~8-10 Tsd. Zeilen/Tag).
        if LOG_FILE.exists() and LOG_FILE.stat().st_size >= LOG_MAX_BYTES:
            _l1 = LOG_FILE.with_name(LOG_FILE.name + ".1")
            _l2 = LOG_FILE.with_name(LOG_FILE.name + ".2")
            _l3 = LOG_FILE.with_name(LOG_FILE.name + ".3")
            if _l2.exists():
                _l2.replace(_l3)
            if _l1.exists():
                _l1.replace(_l2)
            LOG_FILE.replace(_l1)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ─── MCP-Connector-Aufrufe (stdio JSON-RPC, Muster: Handshake-Test) ─────

def mcp_call(server_py: Path, tool: str, args: dict) -> str:
    """Ruft ein Tool eines lokalen FastMCP-Servers auf (initialize + call + exit)."""
    if DRY_RUN:
        log(f"[DRY-RUN] MCP {server_py.name}::{tool} args={json.dumps(args, ensure_ascii=False)[:120]}")
        return "DRY-RUN"
    if not server_py.exists():
        raise FileNotFoundError(f"MCP-Server fehlt: {server_py}")
    py = str(VENV_PY) if VENV_PY.exists() else "python3"
    init_req = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05",
                           "capabilities": {},
                           "clientInfo": {"name": "km-hr-agent-runner", "version": "1.0"}}}
    # MCP-Protokoll: initialized-Notification ist PFLICHT nach initialize,
    # sonst schließt FastMCP die Verbindung ("Connection closed", Live-Befund 12.09.2026)
    initialized_note = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    call_req = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": tool, "arguments": args}}
    # stdin offen halten bis Antwort da (FastMCP bricht bei EOF ab – Live-Befund 12.09.2026)
    proc = subprocess.Popen([py, str(server_py)], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(PROJECT_ROOT))
    for r in (init_req, initialized_note, call_req):
        proc.stdin.write((json.dumps(r) + "\n").encode("utf-8"))
    proc.stdin.flush()
    import threading as _th
    _buf = {"lines": [], "resp": None}
    def _read():
        for line in proc.stdout:
            line = line.decode("utf-8", errors="replace").strip()
            if line.startswith("{"):
                _buf["lines"].append(line)
                try:
                    e = json.loads(line)
                    if e.get("id") == 2:
                        _buf["resp"] = e; return
                except json.JSONDecodeError:
                    pass
    _t = _th.Thread(target=_read, daemon=True)
    _t.start(); _t.join(timeout=MCP_TIMEOUT)
    try:
        proc.stdin.close(); proc.terminate(); proc.wait(timeout=5)
    except Exception:
        pass
    if _t.is_alive():
        raise RuntimeError(f"MCP-Timeout nach {MCP_TIMEOUT}s: {server_py.name}::{tool}")
    if not _buf.get("resp"):
        try:
            _err = proc.stderr.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            _err = ""
        raise RuntimeError(f"Keine Antwort von {server_py.name}::{tool}: {_err}")
    resp = _buf["resp"]
    if "error" in resp:
        raise RuntimeError(f"MCP-Fehler {tool}: {json.dumps(resp['error'], ensure_ascii=False)[:300]}")
    content = resp.get("result", {}).get("content", [])
    return "\n".join(c.get("text", "") for c in content)


def extract_meet_url(meeting_text: str) -> str | None:
    for line in meeting_text.splitlines():
        if line.strip().startswith("Link:"):
            url = line.split("Link:", 1)[1].strip()
            if url.startswith("http"):
                return url
    return None


def mcp_connector_call(server_py: Path, tool: str, args: dict) -> dict:
    """Ruft ein Tool eines HR-Connectors auf (stdio JSON-RPC). Gibt dict zurück."""
    try:
        result_text = mcp_call(server_py, tool, args)
        if result_text.startswith("FEHLER") or result_text.startswith("DRY-RUN"):
            return {}
        return json.loads(result_text)
    except Exception as e:
        log(f"   Connector-Fehler ({server_py.name}::{tool}): {e}")
        return {}

# ─── E-Mail-Aktionen (deterministisch via email-sender) ─────────────────

def send_confirmation(payload: dict) -> dict:
    cid = payload.get("candidate_id")
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    c.execute("SELECT email, name FROM candidates WHERE id = ?", (cid,))
    row = c.fetchone(); conn.close()
    if not row or not row[0]:
        raise RuntimeError(f"Kandidat #{cid} nicht gefunden / keine E-Mail")
    email, name = row
    lang = _lang(payload)
    body = "\n\n".join([
        tr("Guten Tag {name},", lang, name=name),
        tr("vielen Dank für Ihre Bewerbung. Sie ist bei uns eingegangen und wird "
           "in Kürze geprüft (Lebenslauf-Analyse, Match- und Compliance-Prüfung).", lang),
        tr("Wir melden uns, sobald ein Ergebnis vorliegt.", lang),
        tr("Ihr KM-HR-Agent-Team", lang),
    ]) + _ki_hinweis(lang)
    out = mcp_call(EMAIL_SERVER, "send_email",
                   {"to": email,
                    "subject": tr("Ihre Bewerbung ist eingegangen", lang),
                    "body": body})
    return {"mail": out[:200], "to": email}


def _dokumente_block(cand_id: int) -> str:
    """Spec v6.1: Sammelt die Dokumente des Kandidaten — TYPED aus candidate_documents
    (Tab 🗂️ Dokumente), Fallback: Glob testdaten/kandidat-N-* (v6-Verhalten)."""
    teile = []
    quelle = "candidate_documents"
    try:
        conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
        c.execute("""SELECT datei_pfad, dokumententyp FROM candidate_documents
                     WHERE candidate_id = ? ORDER BY hochgeladen_am DESC""", (cand_id,))
        doks = c.fetchall(); conn.close()
    except Exception:
        doks = []
    if doks:
        eintraege = [(pfad, typ) for pfad, typ in doks]
    else:
        # Fallback (v6): blindes Glob ohne Typ-Kontext
        quelle = "glob (untypisiert)"
        eintraege = [(str(p), "") for p in sorted(PROJECT_ROOT.glob(f"testdaten/kandidat-{cand_id}-*"))]
    for pfad, typ in eintraege:
        p = Path(pfad)
        try:
            if not p.exists():
                teile.append(f"--- {typ or p.name} --- (Datei fehlt)")
                continue
            if p.suffix.lower() == ".pdf":
                # pdf-reader-Connector (live getestet 12.09.2026)
                txt = mcp_call(PROJECT_ROOT / "mcp-pdf-server.py", "read_pdf_text",
                               {"file_path": str(p)})
                if txt.startswith("FEHLER"):
                    txt = f"(unlesbar: {txt[:120]})"
            else:
                txt = p.read_text(encoding="utf-8", errors="replace")
            label = f"{typ}: {p.name}" if typ else p.name
            teile.append(f"--- {label} ---\n{txt[:1800]}")
        except Exception as e:
            teile.append(f"--- {typ or p.name} --- (Fehler: {e})")
    log(f"   Dokumenten-Quelle: {quelle} ({len(teile)} Dokumente)")
    return "\n\n".join(teile) if teile else "(keine Dokumente gefunden)"


def _visum_auswertung_from_ergebnisse(cand_id: int) -> dict | None:
    """Spec v6: Liest die Visum-Auswertung (WAS/WIE/WO) aus dem letzten
    verify_documents-Bericht. None = nicht relevant / kein Bericht."""
    for p in sorted(ERGEBNISSE.glob(f"verify_documents-kandidat-{cand_id}-*.md")):
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:
            continue
        bedarf_zeile = next((l for l in txt.splitlines() if "Visum-Bedarf:" in l), "")
        if "ja" not in bedarf_zeile.lower():
            continue  # nicht relevant
        def _zeile(praefix: str) -> str:
            for l in txt.splitlines():
                if l.strip().startswith(praefix):
                    return l.split(":", 1)[-1].strip()[:200]
            return "–"
        return {"was": _zeile("WAS:"), "wie": _zeile("WIE:"), "wo": _zeile("WO:")}
    return None


def notify_hr(payload: dict, score: int, kategorie: str) -> dict:
    hr_mail = _hr_email_from_db(payload.get("job_id"))
    if not hr_mail:
        raise RuntimeError("Keine HR-Empfänger-E-Mail gefunden (employers.kontakt_email)")
    app_id = payload.get("application_id"); cid = payload.get("candidate_id")
    lang = _lang(payload)
    # Spec v6: Visum-INFO erst beim JA-Pfad (User-Entscheidung) – aus verify_documents-Bericht
    visum = _visum_auswertung_from_ergebnisse(cid)
    visum_block = ""
    if visum:
        visum_block = ("\n" + tr("Visum-Hinweis (aus der Dokumenten-Prüfung, agent-generiert):", lang) + "\n"
                       + tr("WAS: {0}", lang).format(visum.get('was', '–')) + "\n"
                       + tr("WIE: {0}", lang).format(visum.get('wie', '–')) + "\n"
                       + tr("WO: {0}", lang).format(visum.get('wo', '–')) + "\n"
                       + tr("Der Agent stellt keinen Antrag – die Antragstellung obliegt dem Kandidaten.", lang) + "\n")
    body = "\n\n".join([
        tr("Guten Tag,", lang),
        tr("der Agent hat die Bewerbung von Kandidat #{0} geprüft (Bewerbung #{1}).", lang).format(cid, app_id),
        tr("Match-Score: {0}/100 ({1})", lang).format(score, tr(kategorie, lang)),
        tr("Compliance: {0}", lang).format("COMPLIANT"),
        tr("Dokumente: siehe Bericht verify_documents-kandidat-{0}.md", lang).format(cid),
        visum_block.strip(),
        tr("Die ausführlichen Berichte (Match / Compliance / Culture-Fit / Dokumente) finden Sie "
           "im Portal: 2️⃣ Match-Ergebnis · 3️⃣ Compliance-Ergebnis.", lang),
        tr("Entscheiden Sie im Portal (💼 Stellenangebote), ob Sie den Kandidaten "
           "einladen möchten – der Agent versendet keine Einladung von sich aus.", lang),
        tr("Ihr KM-HR-Agent (automatische Benachrichtigung)", lang),
    ]) + _ki_hinweis(lang)
    out = mcp_call(EMAIL_SERVER, "send_email",
                   {"to": hr_mail,
                    "subject": tr("Neues Agent-Ergebnis: Kandidat #{0} – Score {1}/100", lang).format(cid, score),
                    "body": body})
    return {"mail": out[:200], "to": hr_mail, "score": score,
            **({"visum": visum} if visum else {})}


def visa_confirmation(payload: dict) -> dict:
    """Spec v6: Nach HR-Klick '📩 Visum-Antrag bestätigen' – sendet dem Kandidaten
    die Visum-Schritte (WAS/WIE/WO) aus der verify_documents-Auswertung.
    Variante-A-Guard wie create_invitation/send_rejection."""
    if payload.get("trigger") not in ("hr_klick_portal", "hr_klick_hr_seite", "admin_klick"):
        raise RuntimeError("Variante A verletzt: visa_confirmation nur nach HR-Klick")
    cid = payload.get("candidate_id")
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    c.execute("SELECT email, name FROM candidates WHERE id = ?", (cid,))
    row = c.fetchone(); conn.close()
    if not row:
        raise RuntimeError(f"Kandidat #{cid} nicht gefunden")
    email, name = row
    lang = _lang(payload)
    visum = _visum_auswertung_from_ergebnisse(cid)
    if not visum:
        raise RuntimeError("Keine Visum-Auswertung vorhanden (verify_documents: nicht relevant oder fehlt)")
    body = "\n\n".join([
        tr("Guten Tag {name},", lang, name=name),
        tr("Ihre Bewerbung war erfolgreich – für Ihren Arbeitsantritt benötigt Ihre "
           "Aufenthaltsgenehmigung Ihre Aufmerksamkeit. Hier die Schritte (agent-generiert, "
           "bitte verifizieren Sie die Angaben bei der zuständigen Stelle):", lang),
        tr("WAS: {0}", lang).format(visum.get('was', '–')) + "\n"
        + tr("WIE: {0}", lang).format(visum.get('wie', '–')) + "\n"
        + tr("WO: {0}", lang).format(visum.get('wo', '–')),
        tr("Der Agent stellt keinen Antrag – die Antragstellung obliegt Ihnen.", lang),
        tr("Ihr KM-HR-Agent", lang),
    ]) + _ki_hinweis(lang)
    out = mcp_call(EMAIL_SERVER, "send_email",
                   {"to": email,
                    "subject": tr("Ihre Visum-Schritte zur Arbeitsaufnahme", lang),
                    "body": body})
    return {"mail": out[:200], "to": email, "visum": visum}


def send_onboarding_mail(payload: dict) -> dict:
    """Mail #6: Onboarding-Begrüßung nach Status 'eingestellt' (Spec v6, NB6).
    Variante-A-Guard wie create_invitation/send_rejection/visa_confirmation."""
    # Guard 1: Variante A – nur nach HR/Admin-Klick
    if payload.get("trigger") not in ("hr_klick_portal", "hr_klick_hr_seite", "admin_klick"):
        raise RuntimeError("Variante A verletzt: send_onboarding_mail nur nach HR-Klick")
    # Guard 2 + 3: Status-Check via applications-Lookup; candidate_id DARAUS
    # (payload.candidate_id kann fehlen, z.B. alter Task #104)
    app_id = payload.get("application_id")
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    c.execute("SELECT status, candidate_id FROM applications WHERE id = ?", (app_id,))
    arow = c.fetchone()
    if not arow:
        conn.close()
        raise RuntimeError(f"Bewerbung #{app_id} nicht gefunden")
    status, cid = arow[0], arow[1]
    if status != "eingestellt":
        conn.close()
        raise RuntimeError(f"send_onboarding_mail nur bei Status 'eingestellt', ist '{status}'")
    # Kandidat + Job-Titel (JOIN, nice-to-have) in EINEM Lookup
    c.execute("""SELECT cd.email, cd.name, j.titel FROM applications a
                 JOIN candidates cd ON a.candidate_id = cd.id
                 JOIN jobs j ON a.job_id = j.id WHERE a.id = ?""", (app_id,))
    row = c.fetchone()
    # Mentoring (Phase D P10, Spec §5): aktiver Mentor → Zeile, sonst auslassen
    # (Lookup VOR conn.close())
    mentor_block = ""
    try:
        c.execute("SELECT mentor_name FROM mentoring WHERE candidate_id = ? "
                  "AND status = 'aktiv' ORDER BY changed_at DESC LIMIT 1", (cid,))
        _mrow = c.fetchone()
        if _mrow and _mrow[0]:
            mentor_block = _mrow[0]  # Name; Anzeige unten sprachabhängig
    except sqlite3.Error:
        mentor_block = ""  # Tabelle evtl. noch nicht angelegt – Mail trotzdem
    conn.close()
    if not row or not row[0]:
        raise RuntimeError(f"Kandidat #{cid} nicht gefunden / keine E-Mail")
    email, name, titel = row
    lang = _lang(payload)
    if not titel:
        titel = tr("Ihre neue Position", lang)  # Fallback (Design-Entscheidung)
    # Visum-Abschnitt (optional, wie visa_confirmation/notify_hr)
    visum = _visum_auswertung_from_ergebnisse(cid)
    visum_block = ""
    if visum:
        visum_block = ("\n" + tr("📋 Visum-Schritte (aus der Dokumenten-Prüfung, agent-generiert):", lang) + "\n"
                       + tr("WAS: {0}", lang).format(visum.get('was', '–')) + "\n"
                       + tr("WIE: {0}", lang).format(visum.get('wie', '–')) + "\n"
                       + tr("WO: {0}", lang).format(visum.get('wo', '–')) + "\n"
                       + tr("Der Agent stellt keinen Antrag – die Antragstellung obliegt Ihnen.", lang) + "\n")
    # Mentor-Zeile (Phase D P10) – Anzeige, übersetzt
    mentor_txt = tr("Dein Ansprechpartner (Mentor): {0}", lang).format(mentor_block) if mentor_block else ""
    # Onboarding-Kernpunkte kompakt (aus knowledge/onboarding-default.md)
    body = "\n\n".join([
        tr("Guten Tag {name},", lang, name=name),
        tr("wir freuen uns, Sie offiziell bei uns begrüßen zu dürfen – "
           "herzlichen Glückwunsch zu Ihrer Einstellung!", lang),
        tr("Stelle: {0}", lang).format(titel),
        mentor_txt.strip(),
        tr("Ihr Onboarding im Überblick:", lang),
        tr("- Vertragliche Dokumente: Arbeitsvertrag (vor Eintritt), "
           "Datenschutzeinwilligung und Arbeitszeitkonto (Tag 1)", lang),
        tr("- IT-Ausstattung: Laptop, E-Mail-Account, VPN und Chat-Zugang "
           "(bereitgestellt von der IT-Abteilung)", lang),
        tr("- Einarbeitung Woche 1: Tag 1 Begrüßung & IT-Übergabe → Tag 2 Tools und "
           "Team-Vorstellung → Tag 3 Prozess-Überblick → Tag 5 Rückfragen und erstes Feedback", lang),
        visum_block.strip(),
        tr("Die vollständige Onboarding-Checkliste erhalten Sie über das "
           "Candidate-Portal (Tab Onboarding).", lang),
        tr("Wir freuen uns auf die Zusammenarbeit!", lang),
        tr("Ihr KM-HR-Agent-Team", lang),
    ]) + _ki_hinweis(lang)
    out = mcp_call(EMAIL_SERVER, "send_email",
                   {"to": email, "subject": tr("Willkommen im Team – Ihre Einstellung", lang), "body": body})
    return {"mail": out[:200], "to": email, "app_id": app_id, "job": titel,
            **({"visum": visum} if visum else {})}


def send_rejection(payload: dict) -> dict:
    if payload.get("trigger") not in ("hr_klick_portal", "hr_klick_hr_seite", "admin_klick"):
        raise RuntimeError("Variante A verletzt: send_rejection nur nach HR-Klick")
    app_id = payload.get("application_id")
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    c.execute("SELECT status FROM applications WHERE id = ?", (app_id,))
    arow = c.fetchone(); conn.close()
    if not arow:
        raise RuntimeError(f"Bewerbung #{app_id} nicht gefunden")
    if arow[0] != "abgelehnt":
        raise RuntimeError(f"Variante A verletzt: send_rejection nur bei Status 'abgelehnt', ist '{arow[0]}'")
    cid = payload.get("candidate_id")
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    c.execute("SELECT email, name FROM candidates WHERE id = ?", (cid,))
    row = c.fetchone(); conn.close()
    if not row or not row[0]:
        raise RuntimeError(f"Kandidat #{cid} nicht gefunden / keine E-Mail")
    email, name = row
    lang = _lang(payload)
    # AGG-sicher: neutral, dankend, ohne Begründung, ohne Diskriminierungsmerkmale
    body = "\n\n".join([
        tr("Guten Tag {name},", lang, name=name),
        tr("vielen Dank für Ihre Bewerbung und Ihr Interesse.", lang),
        tr("Nach sorgfältiger Prüfung aller Unterlagen haben wir uns entschlossen, "
           "in diesem Verfahren anderenorts fortzufahren. Dies ist keine Bewertung "
           "Ihrer Fähigkeiten und Persönlichkeit.", lang),
        tr("Wir wünschen Ihnen für Ihre berufliche und persönliche Zukunft alles Gute.", lang),
        tr("Ihr KM-HR-Agent-Team", lang),
    ]) + _ki_hinweis(lang)
    out = mcp_call(EMAIL_SERVER, "send_email",
                   {"to": email,
                    "subject": tr("Rückmeldung zu Ihrer Bewerbung", lang),
                    "body": body})
    return {"mail": out[:200], "to": email}


def _hr_email_from_db(job_id) -> str | None:
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    if job_id:
        c.execute("""SELECT e.kontakt_email FROM jobs j JOIN employers e ON j.employer_id = e.id
                     WHERE j.id = ?""", (job_id,))
        row = c.fetchone()
        if row and row[0]:
            conn.close(); return row[0]
    c.execute("SELECT kontakt_email FROM employers ORDER BY id LIMIT 1")
    row = c.fetchone(); conn.close()
    return row[0] if row and row[0] else None

# ─── Einladung (MCP-direct Kette, Spec §5) ───────────────────────────────

def create_invitation(payload: dict) -> dict:
    app_id = payload.get("application_id")
    if payload.get("trigger") not in ("hr_klick_portal", "hr_klick_hr_seite", "admin_klick"):
        raise RuntimeError("Variante A verletzt: create_invitation nur nach HR-Klick")
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    c.execute("""SELECT cd.email, cd.name, j.titel FROM applications a
                 JOIN candidates cd ON a.candidate_id = cd.id
                 JOIN jobs j ON a.job_id = j.id WHERE a.id = ?""", (app_id,))
    row = c.fetchone(); conn.close()
    if not row:
        raise RuntimeError(f"Bewerbung #{app_id} nicht gefunden")
    email, name, titel = row
    lang = _lang(payload)
    # 1) Meeting-Raum (Projektstandard seit 27.09.2026: VDO.Ninja, KEIN Google Meet,
    #    KEIN Jitsi – Jitsi-Aufzeichnung brauchte Jibri auf eigenem Server.
    #    Spec: knowledge/system/vdo-ninja-migration.md
    #    KEIN aufnahme-aktivierender Parameter (&record/&autorecord zum Einschalten)
    #    – Aufzeichnung nur manuell nach bestätigter Einwilligung (§ 26 Abs. 2 BDSG).
    #    HÄRTUNG seit 28.09.2026 (Gate 8, recording-consent.md): der GAST-Link des
    #    Kandidaten trägt `&record=off` (Anbieterdoku and-record: Aufnahme disabled,
    #    „the director won't even be able to trigger it remotely"); der HR/Director-
    #    Link bleibt parameterfrei. HR-Prozessregel = Gate 9 (UI-Hinweis employer.py).
    #    Feldname (Ergebnis-JSON) = `vdo_ninja_url` seit 27.09.2026 (war `jitsi_url`);
    #    Konsumenten candidate.py/employer.py lesen neu, mit Legacy-Fallback auf den
    #    alten Schlüssel, damit bereits erzeugte Einladungen sichtbar bleiben.
    code = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    # Raumname alphanumerisch, OHNE Bindestrich seit 04.10.2026 (Lab Schritt 3):
    # Quelle docs.vdo.ninja/advanced-settings/setup-parameters/room — „1 to 49-characters
    # long: aLphaNumEric-characters; case sensitive." VDO ersetzte `pre-screening-` sonst
    # durch `pre_screening_` (Warnung im Control Room, geprüft 04.10.2026);
    # Spec: knowledge/system/vdo-ninja-migration.md §2.5.
    vdo_ninja_url = f"https://vdo.ninja/?director=prescreening{code}"
    # Gast-Link (Kandidat, Gate 8): `?room=` + `&record=off` – Quellen:
    # docs.vdo.ninja/getting-started/rooms („Guests have their own link") + and-record.
    vdo_ninja_gast_url = f"https://vdo.ninja/?room=prescreening{code}&record=off"
    # Termin: HR-gewählt (payload, seit Feature 'HR-Terminauswahl') mit Validierung;
    # Fallback: morgen 10:00, 20 Min (CareerPlug-Connector)
    datum = (datetime.now() + __import__("datetime").timedelta(days=1)).strftime("%Y-%m-%d")
    uhrzeit = "10:00"
    # Connector: prescreen-config → get_optimal_duration()
    dauer = 20  # Fallback (CareerPlug optimal)
    try:
        dur_result = mcp_connector_call(PRESCREEN_CONFIG_SERVER, "get_optimal_duration", {})
        if dur_result and "optimal_minutes" in dur_result:
            dauer = dur_result["optimal_minutes"]
            log(f"   Connector: prescreen-config → optimale Dauer = {dauer} Min.")
    except Exception as e:
        log(f"   Connector-Fallback: prescreen-config → 20 Min ({e})")
    _hr_datum = payload.get("termin_datum")
    _hr_zeit = payload.get("termin_uhrzeit")
    _hr_dauer = payload.get("termin_dauer_min")
    if _hr_datum:
        try:
            from datetime import datetime as _dt
            _d = _dt.strptime(str(_hr_datum), "%Y-%m-%d")
            if _d.date() >= _dt.now().date():  # nicht in der Vergangenheit
                datum = str(_hr_datum)
            else:
                log(f"   HR-Termin {_hr_datum} liegt in der Vergangenheit → Fallback {datum}")
        except ValueError:
            log(f"   HR-Termin-Datum ungültig ({_hr_datum}) → Fallback {datum}")
    if _hr_zeit:
        try:
            from datetime import datetime as _dt
            _dt.strptime(str(_hr_zeit), "%H:%M")
            uhrzeit = str(_hr_zeit)
        except ValueError:
            log(f"   HR-Termin-Uhrzeit ungültig ({_hr_zeit}) → Fallback {uhrzeit}")
    if _hr_dauer:
        try:
            dauer = max(10, min(int(_hr_dauer), 180))
        except (ValueError, TypeError):
            log(f"   HR-Dauer ungültig ({_hr_dauer}) → Fallback {dauer}")
    if _hr_datum or _hr_zeit:
        log(f"   Einladungstermin (HR-gewählt): {datum} {uhrzeit} ({dauer} Min.)")
    # 2) Screening-Fragen (mit echtem Match-Score aus der DB, Spec: Lücke aus Phase-A-Analyse)
    score = _last_match_score(app_id)
    fragen = mcp_call(MEETING_SERVER, "generate_screening_questions",
                      {"candidate_name": tr("Kandidat #{0}", lang).format(payload.get('candidate_id')),
                       "position": titel, "match_score": score, "cultural_fit_score": 75,
                       "strengths": tr("siehe Match-Bericht", lang),
                       "gaps": tr("siehe Match-Bericht", lang),
                       "language": lang})
    # 3) ICS (meet_url = VDO.Ninja-GAST-Raum, Gate 8)
    ics_text = mcp_call(MEETING_SERVER, "generate_ics_file",
                        {"topic": tr("Vorstellungsgespräch: {0}", lang).format(titel), "date": datum,
                         "time": uhrzeit, "duration_minutes": dauer, "meet_url": vdo_ninja_gast_url,
                         "description": tr("Online-Interview im Rahmen des Bewerbungsverfahrens.", lang)})
    ics_path = ERGEBNISSE / f"einladung-ics-bewerbung-{app_id}.ics"
    if not DRY_RUN and not ics_text.startswith("FEHLER"):
        ics_path.write_text(ics_text, encoding="utf-8")
    # 3b) ICS für HR – enthält den DIRECTOR-Link (Rollentrennung, seit 28.09.2026);
    #     HR lädt die Datei über den Button „Termin in Kalender speichern (.ics) – HR“.
    ics_hr_text = mcp_call(MEETING_SERVER, "generate_ics_file",
                        {"topic": tr("Vorstellungsgespräch: {0} (HR)", lang).format(titel), "date": datum,
                         "time": uhrzeit, "duration_minutes": dauer, "meet_url": vdo_ninja_url,
                         "description": tr("Online-Interview (HR/Director-Ansicht).", lang)})
    ics_path_hr = ERGEBNISSE / f"einladung-ics-hr-bewerbung-{app_id}.ics"
    if not DRY_RUN and not ics_hr_text.startswith("FEHLER"):
        ics_path_hr.write_text(ics_hr_text, encoding="utf-8")
    # 4) Einladungs-Mail
    mail_out = mcp_call(EMAIL_SERVER, "send_pre_screen_invitation",
                        {"to": email, "candidate_name": name, "position": titel,
                         "meet_url": vdo_ninja_gast_url, "date": datum, "time": uhrzeit,
                         "questions_summary": fragen[:400], "language": lang})
    return {"vdo_ninja_url": vdo_ninja_url, "vdo_ninja_gast_url": vdo_ninja_gast_url,
            "recording": False,  # Gate 10 (recording-consent.md): explizites Feld
            "ics_path": str(ics_path), "ics_path_hr": str(ics_path_hr),
            "termin": tr("{0} Uhr ({1} Min.)", lang).format(f"{datum} {uhrzeit}", dauer),
            "mail": mail_out[:200], "to": email}


def _last_match_score(app_id: int) -> int:
    """Echter Match-Score der Bewerbung aus dem letzten Match-Bericht (Spec §5)."""
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    c.execute("SELECT candidate_id, job_id FROM applications WHERE id = ?", (app_id,))
    row = c.fetchone(); conn.close()
    if not row:
        # ⚠️ Design-Entscheidung (15.09.2026): Fallback 70 hat keine externe Quelle.
        # Alternative: Neutralen Wert (50) oder keinen Fallback ( Fehler werfen)
        return 70
    cand, job = row
    score, _ = _score_from_ergebnisse(cand, job)
    return score if score and score > 0 else 70


# ─── LLM-Tasks (Ausführung B: opencode run + NVIDIA NIM) ────────────────
# WICHTIG (Live-Befund 12.09.2026): opencode run ist nicht-interaktiv –
# Permission "bash"/"edit" = "ask" wird AUTO-REJECTET. Daher:
#   1. Der Runner bettet die Daten (CV-Text, Profil-/Job-Felder) direkt in den
#      Prompt ein (Lesen von knowledge/*/*.md ist erlaubt: read "*": "allow").
#   2. Der Agent liefert TEXT; der Runner schreibt die Berichtsdatei SELBST
#      ("LLM denkt, Runner persistiert") und verifiziert sie vor status=done.

def _collect_text_events(stdout: str) -> str:
    """Sammelt alle 'text'-Events aus opencode run --format json."""
    texts = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("type") == "text":
            t = e.get("part", {}).get("text", "")
            if t:
                texts.append(t)
    return "\n\n".join(texts).strip()



def _db_candidate_context(cid) -> dict:
    """Liest Kandidaten-Kontext aus der DB (Runner-Seite, keine Agent-Tools nötig)."""
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    c.execute("SELECT name, hard_skills, soft_skills, berufserfahrung_jahre, abschluss, deutsch, englisch, standort, lebenslauf_text FROM candidates WHERE id = ?", (cid,))
    row = c.fetchone(); conn.close()
    if not row:
        return {}
    keys = ("name", "hard_skills", "soft_skills", "erfahrung_jahre", "abschluss", "deutsch", "englisch", "standort", "lebenslauf_text")
    return dict(zip(keys, row))


def _db_job_context(jid) -> dict:
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    c.execute("SELECT titel, hard_skills, soft_skills, berufserfahrung_jahre, deutsch_level, standort, land, stellentyp FROM jobs WHERE id = ?", (jid,))
    row = c.fetchone(); conn.close()
    if not row:
        return {}
    keys = ("titel", "hard_skills", "soft_skills", "erfahrung_jahre", "deutsch_level", "standort", "land", "stellentyp")
    return dict(zip(keys, row))


def _update_candidate_from_extract(cid: int, agent_text: str) -> None:
    """Parst die extract_profile LLM-Ausgabe und schreibt die extrahierten
    Daten in die candidates-Tabelle (Lab-Prinzip: MD-first, aber DB-Update
    ist nötig weil Streamlit die extrahierten Daten nie in die DB schrieb)."""
    try:
        import re
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        updates = {}
        # --- Hard-Skills (aus "Kernkompetenzen" Sektion) ---
        km_match = re.search(r'##\s*Kernkompetenzen\s*\n(.*?)(?=\n##\s|$)', agent_text, re.DOTALL)
        if km_match:
            skills_raw = km_match.group(1)
            hard = [l.strip().lstrip('- ') for l in skills_raw.strip().split('\n') if l.strip().startswith('-')]
            if hard:
                updates['hard_skills'] = ', '.join(hard)
        # --- Soft-Skills: werden aus hard_skills separat extrahiert ---
        known_soft = {'freundlichkeit', 'belastbarkeit', 'flexibilit', 'teamf',
                      'zuverl', 'interkulturell'}
        if 'hard_skills' in updates:
            all_skills = [s.strip() for s in updates['hard_skills'].split(',')]
            soft = [s for s in all_skills if any(k in s.lower() for k in known_soft)]
            hard = [s for s in all_skills if s not in soft]
            if soft:
                updates['soft_skills'] = ', '.join(soft)
            if hard:
                updates['hard_skills'] = ', '.join(hard)
        # --- Berufserfahrung (Jahre berechnen aus Datumsangaben) ---
        exp_match = re.findall(r'\*(\d{2}/\d{4})\s*[–\-]\s*(\d{2}/\d{4})\*', agent_text)
        total_months = 0
        for start_s, end_s in exp_match:
            try:
                sm, sy = map(int, start_s.split('/'))
                em, ey = map(int, end_s.split('/'))
                total_months += (ey * 12 + em) - (sy * 12 + sm)
            except Exception:
                pass
        if total_months > 0:
            updates['berufserfahrung_jahre'] = round(total_months / 12)
        # --- Abschluss (aus "Bildung" Sektion) ---
        abschluss_match = re.search(r'##\s*Bildung\s*\n(.*?)(?=\n##\s|$)', agent_text, re.DOTALL)
        if abschluss_match:
            abschluss_text = abschluss_match.group(1).strip().split('\n')[0]
            abschluss_text = re.sub(r'^[-*]\s*', '', abschluss_text).strip()
            abschluss_text = re.sub(r'\|.*$', '', abschluss_text).strip()
            abschluss_text = re.sub(r'\*\*', '', abschluss_text).strip()  # Markdown bold entfernen
            if abschluss_text and '[' not in abschluss_text:
                updates['abschluss'] = abschluss_text
        # --- Sprachkenntnisse (Deutsch/Englisch Level) ---
        for lang, col in [('Deutsch', 'deutsch'), ('Englisch', 'englisch')]:
            lvl_match = re.search(rf'{lang}\s*:\s*(A[12]|B[12]|C[12])', agent_text)
            if lvl_match:
                updates[col] = lvl_match.group(1)
        # --- Nationalität + Visum-Status (aus Lebenslauf oder Profil) ---
        # Achte auf Markdown-Bold (**Text**)
        nat_match = re.search(r'\*\*Staatsangeh[öo]rigkeit:\*\*\s*(\w+)', agent_text)
        if not nat_match:
            nat_match = re.search(r'Staatsangeh[öo]rigkeit:\s*(\w+)', agent_text)
        if not nat_match:
            nat_match = re.search(r'\*\*Nationalit[äa]t:\*\*\s*(\w+)', agent_text)
        if not nat_match:
            nat_match = re.search(r'Nationalit[äa]t:\s*(\w+)', agent_text)
        if not nat_match:
            nat_match = re.search(r'Geburtsdatum.*?\n.*?(Tunesien|Marokko|Algerien|Libyen|Ägypten|Türkei|Syrien|Irak|Iran|China|Indien|\w+)', agent_text)
        if nat_match:
            nat = nat_match.group(1).strip()
            updates['nationalitaet'] = nat
            # EU/EFTA-Länder = kein Visum nötig
            eu_efta = {'deutschland', 'österreich', 'schweiz', 'frankreich', 'italien', 'spanien',
                       'portugal', 'niederlande', 'belgien', 'luxemburg', 'irland', 'polen',
                       'tschechien', 'slowakei', 'ungarn', 'slowenien', 'kroatien', 'bulgarien',
                       'rumänien', 'griechenland', 'estland', 'lettland', 'litauen', 'finnland',
                       'schweden', 'dänemark', 'malta', 'zypern', 'island', 'norwegen', 'liechtenstein'}
            if nat.lower() in eu_efta:
                updates['visum_status'] = 'EU-Bürger'
            else:
                updates['visum_status'] = 'Visum erforderlich'
        if not updates:
            log(f"   extract_profile: Keine strukturierten Daten extrahiert (Kandidat #{cid})")
            conn.close()
            return
        # --- DB-Update ---
        set_clause = ', '.join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [cid]
        c.execute(f"UPDATE candidates SET {set_clause}, aktualisiert_am = CURRENT_TIMESTAMP WHERE id = ?", vals)
        conn.commit()
        conn.close()
        log(f"   extract_profile → DB-Update Kandidat #{cid}: {', '.join(updates.keys())}")
    except Exception as e:
        log(f"   extract_profile DB-Update fehlgeschlagen (Kandidat #{cid}): {e}")


def _gewichts_prompt_zeile(lang: str = "de") -> str:
    """Baut die Gewichtszeile für den match_candidate-Prompt aus den LIVE-Werten.

    Quelle der Wahrheit: `gewichtung_historie` via `webui.logic.get_current_weights()`
    (webui/logic.py:338) – derselbe Wert, den das Portal-Score verwendet. Ersetzt die
    bisher harte Baseline-Kopie im Prompt (Phase-E Runde 2, Nutzerentscheidung A').
    Design-Entscheidungen: Rundung auf 1 Nachkommastelle; Fallback = Baseline
    (webui/logic.py:182-185), wenn Historie leer/DB nicht erreichbar.
    """
    fallback = {"kern": 30, "erfahrung": 25, "bildung": 15, "standort": 10,
                "branche": 10, "soft": 10, "sprache": 0}
    try:
        from webui.logic import get_current_weights
        w = get_current_weights() or {}
        if len(w) < len(fallback):
            raise ValueError(f"unvollständige Gewichte: {list(w)}")
    except Exception as exc:
        log(f"   Gewichtsquelle fallback ({exc}) – nutze Baseline")
        w = fallback
    return " / ".join(f"{tr(k, lang)} {round(float(v), 1)}" for k, v in w.items())


def _parse_compliance_status(text: str) -> str | None:
    """Status-Token aus dem check_compliance-Bericht (None = kein Token).

    Reihenfolge wie `employer._compliance_status`: NICHT_COMPLIANT ZUERST prüfen,
    sonst faellt "COMPLIANT" als Teilstring den Negativ-Status auf.
    """
    m = re.search(r"^Compliance-Status:\s*(.*)$", text or "", re.M)
    if not m:
        return None
    roh = m.group(1).strip()
    if roh.startswith("NICHT_COMPLIANT") or roh.startswith("NICHT COMPLIANT"):
        return "NICHT_COMPLIANT"
    if roh.startswith("COMPLIANT"):
        return "COMPLIANT"
    return roh.split()[0] if roh else "UNBEKANNT"


def _write_compliance_protokoll(payload: dict, agent_text: str, jid, cid, job_land) -> str:
    """N-K (01.10.2026): check_compliance-Ergebnis zusaetzlich ins compliance_protokoll.

    User-Entscheidung 01.10.2026 „Beides: Writer + Berichte“: die MD-Berichte
    bleiben Primaerquelle (Compliance-Seite R3-3), das Protokoll wird wieder
    aktiv befuellt. match_id-Schema `employer-job-<job>-cand-<cand>-<datum>` ist
    genau das Muster, das `_compliance_rows` (employer.py) zur Arbeitgeber-
    Zurechnung liest. Idempotent ueber (match_id, pruefpunkt); OHNE Status-Token
    wird NICHTS geschrieben (kein stilles Erfinden).
    """
    from webui import db as _db  # lazy: Runner laeuft auch ohne App-Boot
    _db.init_compliance_protokoll_table()
    status = _parse_compliance_status(agent_text)
    if status is None:
        return "kein Status-Token -> kein Schreiben"
    m = re.search(r"^Compliance-Status:\s*(.*)$", agent_text or "", re.M)
    roh = m.group(1).strip()
    datum = datetime.now().strftime("%Y-%m-%d")
    match_id = (f"employer-job-{jid}-cand-{cid}-{datum}"
                if jid and cid else f"cand-{cid}-{datum}")
    aktion = _db.record_compliance_protokoll(
        match_id, job_land or "DE",
        "Gesamt (AGG §1 / DSGVO Art. 6 / EU AI Act Art. 26)",
        status, roh, payload.get("application_id"))
    return f"{aktion} ({match_id}, status={status})"


def llm_report_header(task_type: str, cid, jid, datum: str, lang: str) -> str:
    """Berichts-Header fuer LLM-Tasks in der Payload-Sprache (P9.5b, 07.10.2026).

    Design-Entscheidung (Nutzer-GO 07.10.2026): der Task-Titel bleibt
    englisch (Identifier = task_type.title(), entspricht Dateiname-Prefix und
    Badge-Key), die Prosa-Zeile laeuft ueber tr(). Bei lang='de' byte-identisch
    mit dem Altbestand (Regression: tests/e2e_admin_downloads.py erwartet
    "Extract Profile").

    Korrektur P9.5b fuer parse-kritische Marker (Design-Entscheidung 09.10.2026):
    die Titel-Struktur-Marker "Kandidat #<id>" / "Stelle #<id>" sind
    sprachstabile Identifier (maschinell geparst von
    webui/pages/employer.py::_BERICHT_STELLE + tests/test_r33_compliance_reports.py)
    und werden IMMER deutsch geschrieben — nur die Prosa-Zeile uebersetzt.
    """
    titel = task_type.replace("_", " ").title()
    zeile = "# " + titel + " – " + "Kandidat #{0}".format(cid)
    if jid:
        zeile += " / " + "Stelle #{0}".format(jid)
    return (zeile + "\n\n> " +
            tr("Agent-Task (Phase 5, live {0}), Modell: {1}", lang).format(datum, LLM_MODEL) +
            "\n\n")


def run_llm_task(task_type: str, payload: dict) -> dict:
    cid = payload.get("candidate_id"); jid = payload.get("job_id"); lang = _lang(payload)
    datum = datetime.now().strftime("%Y-%m-%d")
    kand = _db_candidate_context(cid)
    job = _db_job_context(jid)
    cv_text = (kand.get("lebenslauf_text") or "").strip()
    kand_block = (f"Name: {kand.get('name', '?')}\n"
                  f"Hard-Skills: {kand.get('hard_skills') or '–'}\n"
                  f"Soft-Skills: {kand.get('soft_skills') or '–'}\n"
                  f"Berufserfahrung: {kand.get('erfahrung_jahre') or 0} Jahre\n"
                  f"Abschluss: {kand.get('abschluss') or '–'}\n"
                  f"Deutsch: {kand.get('deutsch') or '–'} · Englisch: {kand.get('englisch') or '–'}\n"
                  f"Standort: {kand.get('standort') or '–'}")
    job_block = (f"Titel: {job.get('titel', '?')}\n"
                 f"Must-Have-Skills: {job.get('hard_skills') or '–'}\n"
                 f"Soft-Skills: {job.get('soft_skills') or '–'}\n"
                 f"Min. Erfahrung: {job.get('erfahrung_jahre') or 0} Jahre\n"
                 f"Deutsch-Level: {job.get('deutsch_level') or '–'}\n"
                 f"Standort: {job.get('standort') or '–'} · Typ: {job.get('stellentyp') or '–'}")
    # ─── pdf-verify-mcp Pre-Scan (nur für verify_documents) ─────────────
    # Quelle: skills/verify-documents/SKILL.md Schritt 4a
    # Führt technische Prüfung durch BEVOR das LLM die inhaltliche Prüfung macht.
    forensic_verdict = ""
    if task_type == "verify_documents":
        forensic_verdict = _pdf_forensic_pre_scan(cid)
    # ─── Visa-Check: Variablen für 3-Länder-Routing ─────────────────
    kand_nat = kand.get('nationalitaet', '') or ''
    kand_visa = kand.get('visum_status', '') or ''
    job_land = job.get('land') or 'DE'
    herkunft = kand_nat.lower() if kand_nat else ''
    eu_efta = {'deutschland', 'österreich', 'schweiz', 'frankreich', 'italien', 'spanien',
               'portugal', 'niederlande', 'belgien', 'luxemburg', 'irland', 'polen',
               'tschechien', 'slowakei', 'ungarn', 'slowenien', 'kroatien', 'bulgarien',
               'rumänien', 'griechenland', 'estland', 'lettland', 'litauen', 'finnland',
               'schweden', 'dänemark', 'malta', 'zypern', 'island', 'norwegen', 'liechtenstein'}
    ist_eu = herkunft in eu_efta
    # Country-specific rules for LLM prompt
    if job_land == 'FR':
        land_regeln = (
            f"FRANKREICH (CESEDA):\n"
            f"- Titre de séjour travail: Art. L313-10 bis L313-27 CESEDA\n"
            f"- Carte bleue européenne: Art. L313-20 CESEDA (Mindestgehalt 1.5x SMIC)\n"
            f"- Autorisation provisoire de travail: Art. L5221-4 Code du travail\n"
            f"- DPM: Demande préalable de main-d'œuvre (Arbeitgeber muss nachweisen)\n"
            f"- Bearbeitungszeit: 2–8 Wochen (primaire), 1–3 Monate (saisonier)\n"
            f"- Anerkennung: ENIC-NARIC (für Bildungsabschlüsse)\n")
    elif job_land == 'CH':
        land_regeln = (
            f"SCHWEIZ (AuG/ArG):\n"
            f"- Ausländerbewilligung: Art. 10-12 AuG (Verhältnismässigkeit)\n"
            f"- Arbeitsbewilligung: Art. 21 AVV (cantonal beantragen)\n"
            f"- EU/EFTA: Freizügigkeitsabkommen (kein Visum, nur Registrierung)\n"
            f"- Nicht-EU: Art. 10 Abs. 3 AuG (Quotenregelung, Index B)\n"
            f"- Bearbeitungszeit: 2–4 Wochen (EU/EFTA), 3–6 Monate (nicht-EU)\n"
            f"- Anerkennung: BBK/CRB (Bundesamt für Berufsbildung)\n")
    else:
        land_regeln = (
            f"DEUTSCHLAND (AufenthG):\n"
            f"- §18a Fachkraft mit Berufsausbildung\n"
            f"- §18b Blaue Karte EU: Mindestgehalt 50.700€ (45.934€ Mangelberufe, Stand 2026)\n"
            f"- §19c Selbständig, §20 Forscher\n"
            f"- ZAV-Zustimmung (§39 AufenthG) für Nicht-EU\n"
            f"- Anerkennung (AnerkG): IT = freiwillig; reglementiert = Pflicht\n"
            f"- Bearbeitungszeit: Visum 4–12 Wochen, Anerkennung 3–4 Monate\n")
    eu_hinweis = "" if ist_eu else (
        f"\nACHTUNG: Kandidat ist Nicht-EU-Bürger ({kand_nat or 'unbekannt'}). "
        f"Visum + Arbeitserlaubnis sind IMMER erforderlich.\n")
    prompts = {
        "extract_profile": (f"Extrahiere ein strukturiertes HR-Profil aus dem folgenden Lebenslauf.\n"
                            f"Du darfst bei Bedarf knowledge/*/*.md im Projekt lesen (erlaubt).\n"
                            f"Antworte NUR mit dem strukturierten Profil (Markdown, Sektionen: {tr('Profil', lang)},\n"
                            f"{tr('Kernkompetenzen', lang)}, {tr('Berufserfahrung', lang)}, {tr('Bildung', lang)}, {tr('Sprache', lang)}, {tr('Standort', lang)}).\n\n"
                            f"=== LEBENSLAUF (Kandidat #{cid}) ===\n"
                            f"{(cv_text or kand_block)[:4500]}\n"),
        "match_candidate": (f"Führe ein Matching nach folgenden Gewichten durch: "
                            f"{_gewichts_prompt_zeile(lang)} "
                            f"(Summe 100, Quelle: Live-DB `gewichtung_historie` über "
                            f"webui.logic.get_current_weights; Spezifikation: "
                            f"knowledge/lifecycle/matching-criteria.md). Verwende KEINE Werkzeuge, antworte "
                            f"nur aus dem gegebenen Kontext. Kandidat #{cid}:\n{kand_block}\nCV (Auszug):\n"
                            f"{cv_text[:2500]}\n\nStelle #{jid}:\n{job_block}\n\n"
                            f"Antworte mit: einer Zeile 'Match-Score: N/100', einer Zeile "
                            f"'{tr('Kategorie', lang)}: <Name>', dann Begründung je Kategorie (kurz)."),
        "check_compliance": (f"Du bist ein HR-Compliance-Prüfer. Verwende KEINE Werkzeuge und lies "
                             f"KEINE Dateien – antworte ausschließlich aus dem gegebenen Kontext und "
                             f"den hier genannten Regeln (Live-Fix: Tool-Calls truncieren den Stream).\n"
                             f"Relevante Regeln: AGG §1 (keine Benachteiligung wegen Geschlecht, Herkunft, "
                             f"Alter etc.), DSGVO Art. 5/6/17 (Datenminimierung, Rechtsgrundlage, Löschung), "
                             f"EU AI Act Art. 26 (menschliche Aufsicht).\n\n"
                             f"Kandidat #{cid}:\n{kand_block}\n\nStelle #{jid}:\n{job_block}\n\n"
                             f"Antworte mit genau einer Zeile 'Compliance-Status: COMPLIANT' oder "
                             f"'Compliance-Status: NICHT_COMPLIANT', dann kurze Begründung (AGG, DSGVO, "
                             f"Diskriminierungsfreiheit)."),
        "assess_culture_fit": (f"Bewerte den Kultur-Fit (0-100) zwischen Kandidat #{cid} und Stelle "
                               f"#{jid}. Verwende KEINE Werkzeuge, antworte nur aus dem Kontext.\n"
                               f"Kriterien: knowledge/lifecycle/cultural-fit-criteria.md, Abschnitt 'DE-TN-Spezialisierung (Phase-E Runde 2, 24.09.2026)'.\n"
                               f"Kandidat:\n{kand_block}\n\nStelle:\n{job_block}\n\n"
                               f"Antworte mit einer Zeile 'Culture-Fit-Score: N/100' + kurzer Begründung."),
        # Spec v6: Dokumenten-Verifizierung (Zeugnisse/Sprachzeugnisse, Herkunft Kandidat)
        "verify_documents": (f"Du bist ein Dokumenten-Prüfer (Skill verify-documents, Regeln unten). "
                             f"Verwende KEINE Werkzeuge und lies KEINE Dateien – antworte nur aus dem "
                             f"gegebenen Kontext (Live-Fix: Tool-Calls truncieren den Stream).\n\n"
                             f"=== TECHNISCHER PRE-SCAN (pdf-verify-mcp, 16.09.2026) ===\n"
                             f"{forensic_verdict}\n\n"
                             f"=== REGELN (skills/verify-documents/SKILL.md) ===\n"
                             f"1. Dokumenttyp erkennen (Arbeitszeugnis, Abschluss, Berufszertifikat, "
                             f"Sprachzertifikat, Pass, Visum/Aufenthaltstitel)\n"
                             f"2. Pflichtfelder + Datumslogik + Profil-Konsistenz prüfen (Indizien)\n"
                             f"3. Skala: PLAUSIBEL / AUFFAELLIG / UNBEKANNT – KEIN echtes/falsch-Urteil\n"
                             f"4. Berücksichtige das technische Trust-Verdict: "
                             f"use_with_caution = keine Signatur (technisch nicht verifizierbar), "
                             f"reject = AUFFAELLIG setzen\n"
                             f"5. Visum-Auswertung (ansvar-law-Wissen): Wenn der Kandidat keinen "
                             f"unbefristeten Aufenthaltstitel für das Stellenland hat → Visum-Bedarf, "
                             f"sonst 'nicht relevant'. Für den Bedarf: WAS = Aufenthaltstitel-Art, "
                             f"WIE = typische Schritte/Unterlagen/Fristen, WO = zuständige Behörde "
                             f"(DE: Ausländerbehörde/Auslandsvertretung; FR: Préfecture; CH: Kantonales "
                             f"Migrationsamt). Land der Stelle: {job.get('land') or 'DE'}\n\n"
                             f"=== DOKUMENTE (Kandidat #{cid}, mit Bewerbung hochgeladen) ===\n"
                             f"{_dokumente_block(cid)}\n\n"
                             f"=== KANDIDAT (aus Profil) ===\n{kand_block}\n\n"
                             f"Antworte mit: (1) einer Zeile 'Gesamtstatus: PLAUSIBEL' oder "
                             f"'Gesamtstatus: AUFFAELLIG' oder 'Gesamtstatus: UNBEKANNT', (2) einer "
                             f"Tabelle je Dokument (Typ | Pflichtfelder | Indizien | Status | Technisch), (3) einem "
                              f"Abschnitt 'Visum-Auswertung' mit den Zeilen 'Visum-Bedarf: ja/nein', "
                              f"'WAS: ...', 'WIE: ...', 'WO: ...' (je 1 Zeile)."),
        # Skill 17: notify-user – Benachrichtigung bei Top-Matches
        "notify_user": (f"Du bist ein HR-Benachrichtigungs-Agent (Skill notify-user). "
                        f"Erstelle eine E-Mail-Benachrichtigung für einen Top-Match. "
                        f"Score-Bereich: >=90 SOFORT, 80-89 SOFT, <80 keine Benachrichtigung. "
                        f"Format: Betreff + Empfänger-Name + Kategorie + Top-3 Stärken.\n\n"
                        f"Kandidat #{cid}: {kand_block}\n"
                        f"Stelle #{jid}: {job_block}\n"
                        f"Match-Score: {payload.get('score', '?')}/100\n\n"
                        f"Antworte mit: Betreff (1 Zeile), Empfänger-Name, Kategorie, "
                        f"Top-3 Stärken (je 1 Zeile), Empfehlung (1-2 Sätze)."),
        # Skill 13: check-gdpr – DSGVO-Compliance-Prüfung
        "check_gdpr": (f"Du bist ein DSGVO-Compliance-Prüfer (Skill check-gdpr). "
                        f"Prüfe ob die Datenverarbeitung für diesen Kandidaten DSGVO-konform ist. "
                        f"Relevante Regeln: Art. 5 (Datenminimierung), Art. 6 (Rechtsgrundlage), "
                        f"Art. 15-20 (Betroffenenrechte), Art. 17 (Recht auf Löschung).\n\n"
                        f"Kandidat #{cid}: {kand_block}\n"
                        f"Stelle #{jid}: {job_block}\n\n"
                        f"Antworte mit genau einer Zeile 'DSGVO-Status: KONFORM' oder "
                        f"'DSGVO-Status: NICHT_KONFORM', dann kurze Begründung (Art. 5/6/17)."),
        # Skill 9: explain-match – Detaillierte Begründung für Match-Score
        "explain_match": (f"Du bist ein HR-Matching-Erklärer (Skill explain-match). "
                           f"Erstelle eine detaillierte Begründung für den Match-Score. "
                           f"Kategorien: Erfahrung, Skills, Standort, Kultur-Fit, Gehaltserwartung. "
                           f"Für jede Kategorie: Stärke oder Schwäche erklären.\n\n"
                           f"Kandidat #{cid}: {kand_block}\nCV (Auszug): {cv_text[:2000]}\n\n"
                           f"Stelle #{jid}: {job_block}\n"
                           f"Match-Score: {payload.get('score', '?')}/100\n\n"
                           f"Antworte mit: Score-Zusammenfassung (1 Zeile), dann pro Kategorie "
                           f"(Erfahrung, Skills, Standort, Kultur-Fit, Gehalt) jeweils 1-2 Sätze "
                           f"mit Stärke/Schwäche und konkretem Beispiel."),
        # Spec v6.2: Visum-Check (Aufenthaltstitel, Anerkennung, nächste Schritte)
        # Erweitert: 3-Länder-Routing (DE/FR/CH) mit variablen aus Zeile 678-715
        "check_visa": (f"Du bist ein Visum-Check-Prüfer (Skill check-visa). Verwende KEINE "
                       f"Werkzeuge und lies KEINE Dateien – antworte nur aus dem gegebenen "
                       f"Kontext.\n\n"
                       f"=== REGELN (skills/check-visa/SKILL.md + knowledge/legal/visa-rules.md) ===\n"
                       f"{land_regeln}"
                       f"{eu_hinweis}"
                       f"8. Blue Card: Prüfe ob Stellengehalt ≥ Mindestgehalt (DE: 50.700€, FR: 1.5x SMIC)\n"
                       f"9. HR-Pflichten: ZAV-Zustimmung (DE), DPM (FR), Arbeitsbewilligung (CH)\n\n"
                       f"Land der Stelle: {job_land}\n"
                       f"Nationalität des Kandidaten: {kand_nat or 'nicht angegeben'}\n"
                       f"Visum-Status (DB): {kand_visa}\n\n"
                       f"=== KANDIDAT #{cid} ===\n{kand_block}\n\n"
                       f"=== STELLE #{jid} ===\n{job_block}\n\n"
                       f"Antworte mit: (1) einer Zeile 'Visum-Status: ERFORDERLICH' oder "
                       f"'Visum-Status: NICHT ERFORDERLICH' oder 'Visum-Status: UNGEWISS'. "
                       f"ACHTUNG: Nicht-EU-Bürger brauchen IMMER ein Visum — die Frage ist "
                       f"nur OB sie die Voraussetzungen erfüllen, nicht OB sie ein Visum brauchen. "
                       f"(2) einer Tabelle (Prüfpunkt | Ergebnis | Rechtsgrundlage), "
                       f"(3) einem Abschnitt 'Nächste Schritte — Kandidat' (nur Kandidaten-Hausaufgaben), "
                       f"(4) einem Abschnitt 'Nächste Schritte — HR/Arbeitgeber' (ZAV/DPM, Vertrag, "
                       f"Timeline, Kosten). NICHT mischen."),
    }
    prompt = prompts.get(task_type)
    if not prompt:
        raise RuntimeError(f"Unbekannter LLM-Task: {task_type}")
    # §7.1 Punkt 5: dem LLM sagen, in der Payload-Sprache zu antworten
    # (nur Prompt-Instruktion, KEINE Nachbearbeitung der LLM-Ausgabe). Der
    # Prompt ist deutsch → Anweisung mit deutschem Klarnamen (LANG_NAMES).
    _langval = _lang(payload)
    prompt += "\n\n" + f"Antworte in {LANG_NAMES.get(_langval, 'Deutsch')}."
    # P9.5b (07.10.2026, Nutzer-GO "Prompt-Haertung"): die Status-Tokens sind
    # das Fundament von _badge_icon (employer.py, 🔴/🟢/🟡) und duerfen bei
    # FR/AR-Antwort nicht mituebersetzt werden. Interne Prompt-Regel wie
    # "Antworte in <Klarname>" — fest deutsch, KEINE msgid (nicht nutzersichtbar).
    prompt += ("\n\nAchtung: Die Status-Tokens COMPLIANT, NICHT_COMPLIANT, "
               "KONFORM, NICHT_KONFORM, PLAUSIBEL, AUFFAELLIG, UNBEKANNT, "
               "UNGEWISS, ERFORDERLICH und NICHT ERFORDERLICH gibst du IMMER "
               "unveraendert aus (genau so, lateinische Buchstaben) — auch wenn "
               "der Rest deiner Antwort eine andere Sprache ist.")
    result_path = str(ERGEBNISSE / f"{task_type}-kandidat-{cid}-{datum}.md")
    # ─── Hybrid: ansvar-Law als Rechtsquelle für check_visa/check_compliance ───
    if task_type in ("check_visa", "check_compliance"):
        try:
            token = get_ansvar_token()
            land = job.get("land") or "DE"
            suchbegriffe = {
                "check_visa": {
                    "DE": [
                        ("AufenthG 18a Fachkraft", ["DE"]),
                        ("AufenthG 18b Blaue Karte EU", ["DE"]),
                        ("BeschV Mangelberufe Mindestgehalt", ["DE"]),
                        ("AufenthG 19c Selbständig", ["DE"]),
                        ("AufenthG 20 Forscher", ["DE"]),
                        ("ZAV Zustimmung Arbeitsmarkt", ["DE"]),
                        ("AnerkG Berufsanerkennung IT", ["DE"]),
                    ],
                    "FR": [
                        ("CESEDA titre séjour travail", ["FR"]),
                        ("CESEDA carte bleue européenne", ["FR"]),
                        ("Code du travail étranger France", ["FR"]),
                        ("ONISEP travail étranger France", ["FR"]),
                    ],
                    "CH": [
                        ("AuG Ausländergesetz Bewilligung", ["CH"]),
                        ("ArG Arbeitsgesetz Ausländer", ["CH"]),
                        ("Büro für Zuwanderung Schweiz", ["CH"]),
                        ("SECO Arbeitsbewilligung Ausländer", ["CH"]),
                    ],
                },
                "check_compliance": {
                    "DE": [("AGG Diskriminierung", ["DE"]), ("DSGVO Datenschutz", ["DE"])],
                    "FR": [("Code du travail discrimination", ["FR"])],
                    "CH": [("ArG Gleichbehandlung", ["CH"])],
                },
            }
            ansvar_results = []
            for query, j in suchbegriffe.get(task_type, {}).get(land, []):
                try:
                    r = ansvar_search(query, j, token)
                    hits = r.get("results", [])
                    if hits:
                        snippet = hits[0].get("text", "")[:300]
                        source = hits[0].get("citation", {}).get("source_full_name", "")
                        article = hits[0].get("citation", {}).get("article", "")
                        url = hits[0].get("citation", {}).get("source_url", "")
                        ansvar_results.append(f"[{query}] {source} {article}: {snippet} ({url})")
                except Exception as e:
                    log(f"   ansvar-Suche fehlgeschlagen ({query}): {e}")
            if ansvar_results:
                ansvar_block = "\n".join(ansvar_results)
                prompt = (f"=== AKTUELLE RECHTSTEXTE (ansvar-live, {len(ansvar_results)} Quellen) ===\n"
                          f"{ansvar_block}\n\n"
                          f"Antworte BASED ON these legal texts, NOT from memory.\n\n"
                          f"{prompt}")
                log(f"   Hybrid: {len(ansvar_results)} ansvar-Suchergebnisse eingebettet")
        except Exception as e:
            log(f"   Hybrid-Fallback: ansvar nicht verfügbar ({e}) – LLM nutzt Trainingswissen")
    if DRY_RUN:
        log(f"[DRY-RUN] NVIDIA API direct :: {task_type} (Kontext eingebettet, {len(prompt)} Zeichen)")
        return {"result_path": result_path}
    # Direkter API-Aufruf mit Exponential Backoff + Fallback-Modellen
    api_url = "https://integrate.api.nvidia.com/v1/chat/completions"
    api_key = os.environ.get("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY nicht gesetzt – prüfe .env-runner oder Umgebungsvariable")
    api_headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    # Fallback-Modellkette: nemotron-120b → lightning-30b → kimi-k3
    model_chain = [
        (LLM_MODEL, LLM_TIMEOUT),                              # nemotron-120b, 600s
        ("nvidia/nemotron-3.5-lightning-30b-a3b", LLM_TIMEOUT), # lightning-30b, 600s
        ("moonshotai/kimi-k3", 120),                             # kimi-k3, 120s (Timeout)
    ]
    last_error = None
    for model_name, model_timeout in model_chain:
        api_payload = {
            "messages": [{"role": "user", "content": prompt}],
            "model": model_name,
            "max_tokens": 4096,
            "stream": False,
            "temperature": 1,
        }
        for attempt in range(3):  # 3 Versuche pro Modell mit Backoff
            try:
                wait = [5, 10, 20][attempt]  # Exponential Backoff: 5s → 10s → 20s
                if attempt > 0:
                    log(f"   Backoff: {wait}s vor Versuch {attempt+1}/3 ({model_name})")
                    time.sleep(wait)
                resp = requests.post(api_url, headers=api_headers, json=api_payload, timeout=model_timeout)
                if resp.status_code == 200:
                    agent_text = resp.json()["choices"][0]["message"].get("content") or ""
                    if agent_text.strip():
                        log(f"   ✅ Erfolg mit {model_name} (Versuch {attempt+1}/3)")
                        break
                    else:
                        last_error = f"Agent ohne Text-Antwort ({model_name}, HTTP 200, content leer)"
                elif resp.status_code == 503:
                    last_error = f"HTTP 503 ({model_name}, Versuch {attempt+1}/3)"
                    log(f"   ⚠️ 503 von {model_name} (Versuch {attempt+1}/3)")
                else:
                    last_error = f"HTTP {resp.status_code} ({model_name}): {resp.text[:100]}"
                    break  # Bei anderen Fehlern: nächstes Modell
            except requests.Timeout:
                last_error = f"Timeout nach {model_timeout}s ({model_name})"
                log(f"   ⚠️ Timeout bei {model_name} (Versuch {attempt+1}/3)")
            except Exception as e:
                last_error = f"{type(e).__name__}: {e}"
                break
        else:
            log(f"   ❌ Alle 3 Versuche für {model_name} fehlgeschlagen")
            continue  # Nächstes Modell in der Kette
        if agent_text.strip():
            break  # Erfolg – Schleife verlassen
    else:
        raise RuntimeError(f"Alle Modelle fehlgeschlagen. Letzter Fehler: {last_error}")
    if not agent_text.strip():
        raise RuntimeError(f"Agent ohne Text-Antwort: {last_error}")
    # Runner persistiert (Permission-frei): Bericht selbst schreiben
    header = llm_report_header(task_type, cid, jid, datum, _langval)
    report_text = header + agent_text + "\n"
    Path(result_path).write_text(report_text, encoding="utf-8")
    size = Path(result_path).stat().st_size
    if size < 100:
        raise RuntimeError(f"Bericht zu klein ({size} Bytes) – gilt als fehlgeschlagen")
    log(f"   Bericht geschrieben: {result_path} ({size} Bytes, {len(agent_text)} Zeichen Agent-Text)")
    # ─── N-K (01.10.2026): check_compliance -> compliance_protokoll-Writer ──
    if task_type == "check_compliance":
        try:
            _akt = _write_compliance_protokoll(payload, agent_text, jid, cid, job_land)
            log(f"   compliance_protokoll: {_akt}")
        except Exception as e:
            log(f"   ⚠️ compliance_protokoll-Write fehlgeschlagen: {type(e).__name__}: {e}")
    # ─── extract_profile → DB-Update: Extrahierte Daten in candidates-Tabelle schreiben ──
    if task_type == "extract_profile" and cid:
        _update_candidate_from_extract(cid, agent_text)
        # ─── Auto-Refresh: match_candidate für aktive Bewerbungen auslösen ──
        # (damit Tab 2 Match-Ergebnis immer aktuell ist)
        try:
            _conn_ar = sqlite3.connect(str(DB_PATH))
            _c_ar = _conn_ar.cursor()
            _c_ar.execute("""SELECT id, job_id FROM applications
                WHERE candidate_id = ? AND status NOT IN ('zurückgezogen', 'abgelehnt', 'eingestellt')""", (cid,))
            _active_apps = _c_ar.fetchall()
            for _app_id, _job_id in _active_apps:
                import json as _json
                _c_ar.execute("INSERT INTO agent_tasks (task_type, payload) VALUES (?, ?)",
                    ("match_candidate", _json.dumps({
                        "application_id": _app_id,
                        "candidate_id": cid,
                        "job_id": _job_id
                    })))
                log(f"   Auto-Refresh: match_candidate für Bewerbung #{_app_id} (Job #{_job_id}) ausgelöst")
            _conn_ar.commit()
            _conn_ar.close()
        except Exception as e:
            log(f"   Auto-Refresh Fehler: {e}")
    # Berichtstext zusätzlich in `result_json` ablegen, damit die UI (Agent-Details)
    # ihn aus der DB lesen kann — `ergebnisse/` ist gitignored. ADDITIV:
    # `result_path`/`agent_chars` bleiben erhalten (keine Aufrufer brechen).
    # UNGEKAPPT (Plan(ii) 11.10.2026): vollständiger Text, keine Obergrenze.
    # Spec: knowledge/system/agent-automation.md §2/§7.1
    return {"result_path": result_path, "agent_chars": len(agent_text),
            "text": report_text}

# ─── Pförtner-Regel (Spec §3, User-Entscheidung 12.09.2026) ─────────────

def gatekeeper_decision(app_id: int) -> tuple[bool, int, str]:
    """JA wenn Score >= 60 UND Compliance = COMPLIANT; sonst NEIN.
    Returns (ja, score, kategorie)."""
    conn = sqlite3.connect(str(DB_PATH)); c = conn.cursor()
    c.execute("SELECT candidate_id, job_id FROM applications WHERE id = ?", (app_id,))
    row = c.fetchone(); conn.close()
    if not row:
        return False, 0, "unbekannt"
    cand, job = row
    score, kategorie = _score_from_ergebnisse(cand, job)
    compliant = _compliance_from_ergebnisse(cand)
    # Connector-Ersatz (R6-1, 30.09.2026): `logic.get_score_category_lokal`
    # liefert dieselben Werte wie hr-benchmark-server.py::get_score_category
    # (80+ Strong / 60-79 Consider / <66 Weak — beide Quellen identisch,
    # M-16-Fix in webui/logic.py:577-582). Ohne Subprozess: die Gatekeeper-
    # Schleife hatte 34.186 hr-benchmark-Subprozess-Starts verursacht.
    pförtner_schwelle = 60  # Fallback (Design-Entscheidung)
    try:
        from webui.logic import get_score_category_lokal
        cat = get_score_category_lokal(score)
        # ZYTHR: "Consider" ab 60 → Pförtner-Schwelle = 60
        if cat == "Weak":
            pförtner_schwelle = 61  # Score muss mindestens 60 sein (Consider)
        elif cat == "Consider":
            pförtner_schwelle = 60
        else:  # Strong
            pförtner_schwelle = 0  # immer JA
        log(f"   Lokal: score_category {score} = {cat}, Schwelle = {pförtner_schwelle}")
    except Exception as e:
        log(f"   Lokal-Fallback: score_category → Schwelle 60 ({e})")
    # ⚠️ Design-Entscheidung (15.09.2026): Pförtner-Schwelle 60 hat keine externe Quelle.
    return (score >= pförtner_schwelle and compliant), score, kategorie


def _gatekeeper_signature(c, app_id: int, gen: int) -> str:
    """Zustandssignatur der drei Kette-Berichte (R6-1, Variante A).

    task_id+status je task_type (neuester Stand = hoechste id): Aenderung einer
    Berichts-Generierung (neue task-ids oder status) erzeugt eine neue
    Signatur → der Pförtner bewertet erneut; unveraenderte Signatur → Merkbuch
    greift, KEINE Neubewertung, KEINE Log-Zeile, KEIN Subprozess."""
    c.execute("""SELECT task_type, id, status FROM agent_tasks
                 WHERE json_extract(payload, '$.application_id') = ?
                   AND COALESCE(json_extract(payload, '$.gen'), 0) = ?
                   AND task_type IN
                 ('match_candidate', 'check_compliance', 'assess_culture_fit')
                 ORDER BY id""", (app_id, gen))
    latest: dict = {}
    for t, tid, st in c.fetchall():
        latest[t] = (tid, st)  # ORDER BY id → spaeter = neuester Stand
    return "|".join(f"{t}:{latest[t][0]}:{latest[t][1]}" for t in sorted(latest))


def _maybe_gatekeeper(conn, app_id, payload: dict) -> None:
    """Evaluiert die Pförtner-Regel, sobald alle 3 Kette-Berichte done sind.

    R3-1 (30.09.2026): Beide Abfragen lesen die Bewerbung per
    `json_extract(payload, '$.application_id') = ?` (exakter Zahlenvergleich)
    statt per LIKE-Präfix-Muster `%"application_id": N%` — das traf auch
    10/11/160, wenn N=1 war (Präfix-Kollision, s. tests/test_application_id_match.py).
    Ketten-Zustände kommen mit `ORDER BY id` und werden in Abfrage-Reihenfolge
    eingespeist: der LETZTE Eintrag je task_type gewinnt, also der mit der
    höchsten id = neuester Stand (vorher: `dict()` aus unsortierten Zeilen →
    bei mehreren Tasks desselben Typs gewann zufällig einer).

    R3-2 (Generation): Es gilt immer die höchste Generation der Bewerbung
    (`payload.gen`). Altbestand ohne `gen`-Feld wird via COALESCE als 0 gelesen
    → Verhalten für Bestandsdaten unverändert. Ein alter notify_hr-Marker einer
    früheren Generation blockiert die Auswertung einer neuen Generation NICHT.
    JA → queue notify_hr (einmalig je Generation, idempotent via notify_hr-Count).
    NEIN → keine Mail (Ergebnisse bleiben für HR sichtbar, Spec v3)."""
    c = conn.cursor()
    # R3-2: höchste Generation dieser Bewerbung (Altbestand ohne gen → 0)
    c.execute("""SELECT COALESCE(MAX(COALESCE(json_extract(payload, '$.gen'), 0)), 0)
                 FROM agent_tasks
                 WHERE json_extract(payload, '$.application_id') = ?""", (app_id,))
    current_gen = c.fetchone()[0]
    c.execute("""SELECT task_type, status FROM agent_tasks
                 WHERE json_extract(payload, '$.application_id') = ?
                   AND COALESCE(json_extract(payload, '$.gen'), 0) = ?
                   AND task_type IN
                 ('match_candidate', 'check_compliance', 'assess_culture_fit')
                 ORDER BY id""",
              (app_id, current_gen))
    states = {}
    for task_type, status in c.fetchall():
        states[task_type] = status  # ORDER BY id → späterer Eintrag = neuester Stand
    if set(states) != {"match_candidate", "check_compliance", "assess_culture_fit"} \
            or any(s != "done" for s in states.values()):
        return  # Kette noch nicht vollständig
    # ── R6-1 (30.09.2026, Variante A): Merkbuch je (app, gen, Signatur) ──
    # Vorher bewertete dieser Sweep JEDE fertige Bewerbung bei JEDEM Loop neu
    # (NEIN liess keinen Marker → 336-419 Pförtner-Zeilen/Stunde, 34.186
    # hr-benchmark-Subprozess-Starts). Jetzt: gleiche Signatur → stiller Return.
    sig = _gatekeeper_signature(c, app_id, current_gen)
    c.execute("""SELECT payload FROM agent_tasks
                 WHERE task_type = 'gatekeeper_eval'
                   AND json_extract(payload, '$.application_id') = ?
                   AND COALESCE(json_extract(payload, '$.gen'), 0) = ?
                 ORDER BY id DESC LIMIT 1""",
              (app_id, current_gen))
    mrow = c.fetchone()
    if mrow:
        try:
            _marker_sig = json.loads(mrow[0]).get("signature")
        except (json.JSONDecodeError, AttributeError):
            _marker_sig = None
        if _marker_sig == sig:
            return  # seit der letzten Auswertung unverändert → nichts zu tun
    ja, score, kategorie = gatekeeper_decision(app_id)
    # Marker (status='done', nie pending → fetch_pending/Prozessierung ausgeschlossen)
    c.execute("INSERT INTO agent_tasks (task_type, status, payload) VALUES ('gatekeeper_eval', 'done', ?)",
              (json.dumps({"application_id": app_id, "gen": current_gen,
                           "signature": sig, "ja": bool(ja), "score": score,
                           "kategorie": kategorie}, ensure_ascii=False),))
    log(f"   Pförtner-Regel Bewerbung #{app_id} (Gen {current_gen}): Score {score} ({kategorie}), "
        f"Compliance {'OK' if 'check_compliance' in states else '?'} → {'JA' if ja else 'NEIN'}")
    if ja:
        # "gen" am Ende: current_gen ist maßgeblich (payload kann aus einem
        # älteren Task ohne gen stammen, z.B. Auto-Refresh-Match ohne Generation)
        c.execute("""SELECT COUNT(*) FROM agent_tasks
                     WHERE json_extract(payload, '$.application_id') = ?
                       AND COALESCE(json_extract(payload, '$.gen'), 0) = ?
                       AND task_type = 'notify_hr'""",
                  (app_id, current_gen))
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO agent_tasks (task_type, payload) VALUES ('notify_hr', ?)",
                      (json.dumps({**payload, "score": score, "kategorie": kategorie,
                                   "gen": current_gen},
                                  ensure_ascii=False, sort_keys=True),))
            log(f"   → notify_hr-Task #{c.lastrowid} gequeued (HR-Mail mit Score)")
        else:
            log("   → JA (Bereits gemeldet, Marker erneuert — kein zweites notify_hr)")
    else:
        log("   → NEIN: keine HR-Mail, Ergebnisse bleiben für HR sichtbar (Suche/Talentpool)")
    conn.commit()


def _score_from_ergebnisse(cand: int, job: int) -> tuple[int, str]:
    for p in sorted(ERGEBNISSE.glob(f"match_candidate-kandidat-{cand}-*.md")):
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:
            continue
        score = None
        for line in txt.splitlines():
            if "Match-Score" in line and "/100" in line:
                for tok in line.replace("**", " ").split():
                    tok = tok.strip("/")
                    # Live-Fix 12.09.2026: Token kann '8/100' sein (nicht nur '8')
                    if "/100" in tok:
                        tok = tok.split("/")[0]
                    if tok.isdigit() and 0 <= int(tok) <= 100:
                        score = int(tok); break
            if score:
                break
        if score is not None:
            kategorie = "passend"
            for line in txt.splitlines():
                if "Kategorie" in line:
                    kategorie = line.split(":", 1)[-1].strip()[:40]; break
            return score, kategorie
    # Fallback: kein Bericht -> Pförtner bleibt zu (sicherer Default)
    return 0, "kein Bericht"


def _compliance_from_ergebnisse(cand: int) -> bool:
    for p in sorted(ERGEBNISSE.glob(f"check_compliance-kandidat-{cand}-*.md")):
        try:
            txt = p.read_text(encoding="utf-8").lower()
        except Exception:
            continue
        if "nicht_compliant" in txt or "non-compliant" in txt:
            return False
        if "compliant" in txt:
            return True
    return False  # kein Bericht -> NICHT compliant (sicherer Default, Pförtner bleibt zu)


# ─── Skill 16: export-report (deterministisch) ────────────────────────

def export_report(payload: dict) -> dict:
    """Exportiert Match-Ergebnisse als MD-Datei nach ergebnisse/."""
    cid = payload.get("candidate_id")
    jid = payload.get("job_id")
    lang = _lang(payload)
    datum = datetime.now().strftime("%Y-%m-%d")
    # Match-Bericht lesen
    score, kategorie = _score_from_ergebnisse(cid, jid)
    compliant = _compliance_from_ergebnisse(cid)
    # Kultur-Fit lesen
    kultur_score = None
    for p in sorted(ERGEBNISSE.glob(f"assess_culture_fit-kandidat-{cid}-*.md")):
        try:
            txt = p.read_text(encoding="utf-8")
            for line in txt.splitlines():
                if "Culture-Fit-Score" in line and "/100" in line:
                    for tok in line.replace("**", " ").split():
                        tok = tok.strip("/")
                        if "/100" in tok:
                            tok = tok.split("/")[0]
                        if tok.isdigit() and 0 <= int(tok) <= 100:
                            kultur_score = int(tok)
                            break
        except Exception:
            continue
    # Bericht erstellen (P4c 07.10.2026: nutzersichtbare Strings via tr(), Spec §7)
    siehe = tr("siehe Match-Bericht", lang)
    zeilen = "\n".join(
        tr("| {0} | {1} |", lang).format(tr(kat, lang), siehe)
        for kat in ("Kernkompetenzen", "Berufserfahrung", "Bildung", "Standort",
                    "Branchenkenntnis", "Soft Skills", "Sprache"))
    compliance_token = "COMPLIANT" if compliant else "NICHT COMPLIANT"
    bericht = (tr("# Match-Export – Kandidat #{0} / Stelle #{1}", lang).format(cid, jid) + "\n\n"
               + tr("**Datum:** {0}", lang).format(datum) + "\n"
               + tr("**Score:** {0}/100 ({1})", lang).format(score, tr(kategorie, lang)) + "\n"
               + tr("**Compliance:** {0}", lang).format(compliance_token) + "\n"
               + tr("**Kultur-Fit:** {cultural_fit_score}/100", lang,
                    cultural_fit_score=kultur_score) + "\n\n"
               + "---\n\n"
               + tr("## Kategorien", lang) + "\n\n"
               + tr("| Kategorie | Status |", lang) + "\n"
               + "|---|---|\n"
               + zeilen + "\n\n"
               + tr("*Exportiert am {0} von Skill export-report.*", lang).format(datum) + "\n")
    pfad = ERGEBNISSE / f"export-kandidat-{cid}-job-{jid}-{datum}.md"
    pfad.write_text(bericht, encoding="utf-8")
    return {"result_path": str(pfad), "score": score, "kategorie": kategorie}


# ─── Skill 18: handle-errors (deterministisch) ────────────────────────

def handle_errors(payload: dict) -> dict:
    """Protokolliert einen Fehler in logs/agent-errors.log und knowledge/error-statistics.md."""
    fehler_typ = payload.get("typ", "TECHNISCH")
    schwere = payload.get("schwere", "MITTEL")
    skill = payload.get("skill", "unbekannt")
    meldung = payload.get("meldung", "keine Details")
    kontext = payload.get("kontext", "")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # In Error-Log schreiben
    log_eintrag = f"[{timestamp}] [{schwere}] [{fehler_typ}] {skill}: {meldung}"
    if kontext:
        log_eintrag += f" | Kontext: {kontext}"
    try:
        LOG_FILE.parent.mkdir(exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_eintrag + "\n")
    except Exception:
        pass
    # In error-statistics.md aktualisieren
    stats_pfad = PROJECT_ROOT / "knowledge" / "error-statistics.md"
    try:
        if stats_pfad.exists():
            stats = stats_pfad.read_text(encoding="utf-8")
        else:
            stats = "# Fehlerstatistik\n\n| Datum | Typ | Schwere | Skill | Meldung |\n"
            stats += "|---|---|---|---|---|\n"
        stats += f"| {timestamp} | {fehler_typ} | {schwere} | {skill} | {meldung[:80]} |\n"
        stats_pfad.parent.mkdir(exist_ok=True)
        stats_pfad.write_text(stats, encoding="utf-8")
    except Exception:
        pass
    return {"logged": True, "typ": fehler_typ, "schwere": schwere, "skill": skill}


# ─── Skill 23: contract-management – Contract Preflight (Phase D P8) ────
# USER-GO 24.09.2026: Recherche-Pflicht erfuellt (ergebnisse/phase-d-p8-contract-
# recherche.md); KEINE hartkodierten Links – alle URLs aus knowledge/legal/
# contract-sources.md (MD-first, Lab-Prinzip 2/3). Deterministisch, kein LLM,
# kein Mailversand, keine Signatur (Optionen A–F bleiben beim User).

def _load_contract_sources() -> tuple[dict, dict]:
    """Parst knowledge/legal/contract-sources.md → ({key: url}, {key: row_text}).

    Kein https-Literal in diesem File – die URL kommt ausschliesslich aus dem MD.
    """
    src = PROJECT_ROOT / "knowledge" / "legal" / "contract-sources.md"
    if not src.exists():
        raise FileNotFoundError(f"Link-Katalog fehlt: {src}")
    urls: dict = {}
    rows: dict = {}
    link_re = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")
    key_re = re.compile(r"\|\s*`([a-z0-9_]+)`\s*\|")
    for line in src.read_text(encoding="utf-8").splitlines():
        m_key = key_re.search(line)
        if not m_key:
            continue
        key = m_key.group(1)
        rows[key] = line
        m_link = link_re.search(line)
        if m_link:
            urls[key] = m_link.group(2)
    return urls, rows


def contract_preflight(payload: dict) -> dict:
    """Contract-Pre-Flight (Skill 23): Gehalt vs. Mindestlohn (Wert aus Link-
    Katalog), Formfall-Hinweise (§14/§126a/§623), NachwG-Checkliste-Verweis.
    Nur pruefen + berichten – nie Vertrag erstellen/signieren (Variante A)."""
    # Variante-A-Guard: nur nach HR-Klick (Muster visa_confirmation/send_rejection)
    trigger = payload.get("trigger", "")
    if trigger not in ("hr_klick_portal", "hr_klick_hr_seite", "admin_klick",
                       "hr_onboarding_klick"):
        raise RuntimeError(
            f"Variante A verletzt: contract_preflight nur nach HR-Klick (trigger={trigger!r})")
    app_id = payload.get("application_id")
    cand_id = payload.get("candidate_id")
    job_id = payload.get("job_id")
    lang = _lang(payload)
    # job_id fehlt ggf. (Button ohne Lookup) → aus applications nachziehen
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    if app_id is not None and job_id is None:
        row = c.execute("SELECT candidate_id, job_id FROM applications WHERE id = ?",
                        (app_id,)).fetchone()
        if row:
            cand_id = cand_id or row[0]
            job_id = row[1]
    if job_id is None:
        conn.close()
        raise FileNotFoundError(f"contract_preflight: kein job_id/app_id in payload {payload}")
    c.execute("""SELECT titel, land, gehaltsrahmen_min, gehaltsrahmen_max, stellentyp
                 FROM jobs WHERE id = ?""", (job_id,))
    job = c.fetchone()
    cand_name = None
    if cand_id is not None:
        crow = c.execute("SELECT name FROM candidates WHERE id = ?", (cand_id,)).fetchone()
        cand_name = crow[0] if crow else tr("Kandidat #{0}", lang).format(cand_id)
    conn.close()
    if not job:
        raise FileNotFoundError(f"contract_preflight: Job #{job_id} nicht gefunden")
    titel, land, gmin, gmax, stellentyp = job

    # ── Quellen + Mindestlohn-WERT aus dem Link-Katalog (kein Hartkodieren) ──
    urls, rows = _load_contract_sources()
    ml_row = rows.get("mindestlohn_2026", "")
    # Wert wie »13,90 €/h« / »13.90 €/h« aus der Key-Zeile ziehen
    m_val = re.search(r"(\d{1,2}[.,]\d{2})\s*(?:€|EUR)\s*/\s*h", ml_row)
    if not m_val:
        raise FileNotFoundError(
            "contract_preflight: Mindestlohn-Wert nicht in contract-sources.md "
            "(Key mindestlohn_2026) gefunden – MD aktualisieren")
    mindestlohn = float(m_val.group(1).replace(",", "."))
    # Quellenstatus (sekundär/amtlich) aus der Zeile mitschleppen
    quellen_status = tr("⚠️ sekundär belegt", lang) if "sekund" in ml_row.lower() else tr("siehe Katalog", lang)

    # ── Gehalts-Check (DE, Stundenlohn) ──
    # Design-Entscheidung (24.09.2026): Vollzeit-Basis 40 h/Woche × 52 = 2080 h
    # für Jahresgehalt→Stundenlohn; keine externe Quelle, im Report ausgewiesen.
    JAHRES_STUNDEN = 2080
    land_norm = (land or "").strip().upper()
    if land_norm in ("DE", "DEUTSCHLAND") or (land or "").startswith("Deutsch"):
        if gmin:
            stundenlohn = float(gmin) / JAHRES_STUNDEN
            if stundenlohn >= mindestlohn:
                gehalt_status = "✅"
                gehalt_txt = tr("Mindestgehalt {0} €/Jahr ≈ {1:.2f} €/h "
                                "≥ {2:.2f} €/h Mindestlohn (Stand 2026)",
                                lang).format(gmin, stundenlohn, mindestlohn)
            else:
                gehalt_status = "❌"
                gehalt_txt = tr("Mindestgehalt {0} €/Jahr ≈ {1:.2f} €/h "
                                "< {2:.2f} €/h Mindestlohn (Stand 2026) – "
                                "VOR Vertragsübergabe korrigieren",
                                lang).format(gmin, stundenlohn, mindestlohn)
        else:
            gehalt_status = "⚠️"
            gehalt_txt = tr("Kein Gehaltsrahmen in der Stelle hinterlegt – HR ergänzt "
                            "Gehalt vor Vertragsübergabe (HINWEIS, kein FEHLER, Parität "
                            "app.py MiLoG-Logik)", lang)
    else:
        gehalt_status = "–"
        gehalt_txt = tr("Stellenland {0} – Mindestlohn-Check DE (MiLoG) "
                        "nicht anwendbar; Landesrecht prüfen", lang).format(land or '?')

    # ── Formfall-Tabelle (statisch aus Spec contract-management.md §4) ──
    # URLs kommen aus dem Katalog-Dict, NICHT aus Literalen.
    def _u(key: str) -> str:
        return urls.get(key, tr("(Katalog-Key {0} ohne URL)", lang).format(key))

    formfallen = [
        (tr("Unbefristet, unstrittig", lang),
         tr("formfrei; Nachweis Textform (§ 2 NachwG, E-Mail genügt)", lang),
         f"[§ 611a BGB]({_u('bgb_611a')}) · [§ 2 NachwG]({_u('nachwg_2')})"),
        (tr("Befristet", lang),
         tr("Schriftform; elektronisch nur mit QES", lang),
         f"[§ 14 Abs. 4 TzBfG]({_u('tzbg_14')}) · [§ 126a BGB]({_u('bgb_126a')})"),
        (tr("Kündigung / Aufhebungsvertrag", lang),
         tr("Schriftform, elektronische Form ausgeschlossen", lang),
         f"[§ 623 BGB]({_u('bgb_623')})"),
        (tr("QES allgemein", lang),
         tr("qualifizierte elektronische Signatur = handschriftliche Wirkung", lang),
         f"[eIDAS Art. 25]({_u('eidas_2014')}) " + tr("(Volltext prüfen)", lang)),
    ]

    datum = datetime.now().strftime("%Y-%m-%d")
    nachwg_url = _u("nachwg_2")
    vorlage = "knowledge/templates/contract-templates/arbeitsvertrag-de-skeleton.md"
    ml_url = _u("mindestlohn_2026")

    lines = [
        tr("# Contract Preflight – Bewerbung #{0}", lang).format(app_id),
        "",
        "**" + tr("Datum:", lang) + f"** {datum}",
        "**" + tr("Kandidat:", lang) + f"** {cand_name or '–'} (#{cand_id})",
        "**" + tr("Stelle:", lang) + f"** {titel} (Job #{job_id}, {land or '?'}, {stellentyp or '–'})",
        "**" + tr("Trigger:", lang) + f"** {payload.get('trigger')} ({tr('Variante A: HR-Klick', lang)})",
        "",
        tr("## 1. Gehalts-Check (MiLoG)", lang),
        "",
        "| " + tr("Status", lang) + " | " + tr("Befund", lang) + " |",
        "|---|---|",
        f"| {gehalt_status} | {gehalt_txt} |",
        "",
        "- **" + tr("Mindestlohn-Wert (Stand 2026):", lang) + f"** {mindestlohn:.2f} €/h "
        f"– {tr('Quellenstatus:', lang)} {quellen_status}",
        "- **" + tr("Quelle (aus Link-Katalog):", lang) + f"** {ml_url}",
        "- **" + tr("Vergleichsbasis (Design-Entscheidung, 24.09.2026):", lang) + "** "
        + tr("Jahresgehalt ÷ {0} h (40 h/Woche × 52) → Stundenlohn", lang).format(JAHRES_STUNDEN),
        "- " + tr("Stellenrahmen: min={0} max={1} €/Jahr", lang).format(gmin, gmax),
        "",
        tr("## 2. Formfall-Hinweise (HR wählt vor Versand)", lang),
        "",
        "| " + tr("Fall", lang) + " | " + tr("Form", lang) + " | " + tr("Rechtsgrundlage", lang) + " |",
        "|---|---|---|",
    ]
    for fall, form, basis in formfallen:
        lines.append(f"| {fall} | {form} | {basis} |")
    lines += [
        "",
        tr("## 3. NachwG-Pflichtangaben (§ 2 Abs. 1 Nr. 1–15) – HR prüft", lang),
        "",
        tr("Volltext: {0} (Key `nachwg_2` im Link-Katalog)", lang).format(nachwg_url),
        "",
        tr("- [ ] 1 Name/Anschrift · 2 Beginn/Dauer · 3 Arbeitsort · 4 Tätigkeit", lang),
        tr("- [ ] 5 Einstufung (tarifgebunden) · 6 Vergütung · 7 Arbeitszeit", lang),
        tr("- [ ] 8 Urlaub · 9 Kündigungsfristen · 10 Tarifvertrag/BV", lang),
        tr("- [ ] 11 Vorrang-Regeln · 12 E-Kommunikation · 13 Genehmigung", lang),
        tr("- [ ] 14 Entsendung/Auslandsrecht · 15 besondere Vertragsbestandteile", lang),
        "",
        tr("## 4. Vertragsskelett", lang),
        "",
        tr("- Vorlage: `{0}` (Skelett, HR füllt aus – Agent erstellt NICHT den Vertrag)", lang).format(vorlage),
        "",
        tr("## 5. Quellen (aus knowledge/legal/contract-sources.md, keine Hartkodierung)", lang),
        "",
        "| " + tr("Key", lang) + " | URL |",
        "|---|---|",
    ]
    for key in ("bgb_126a", "bgb_623", "bgb_611a", "nachwg_2", "milog_1",
                "tzbg_14", "mindestlohn_2026"):
        if key in urls:
            lines.append(f"| `{key}` | {urls[key]} |")
    lines += [
        "",
        "---",
        "",
        tr("*Erstellt von Skill contract-management (Preflight). Der Agent prüft und "
           "berichtet – er erstellt keinen Vertrag und signiert nicht (Variante A). "
           "Signatur-Optionen A–F: knowledge/legal/contract-management.md §4.*", lang),
        "",
    ]
    rep = ERGEBNISSE / f"contract-preflight-bewerbung-{app_id}.md"
    rep.write_text("\n".join(lines), encoding="utf-8")
    return {"result_path": str(rep), "gehalt_status": gehalt_status,
            "mindestlohn": mindestlohn, "quellen": len(urls)}


# ─── Task-Ausführung + Queue-Verwaltung ─────────────────────────────────

def fetch_pending(conn) -> list:
    c = conn.cursor()
    c.execute("""SELECT id, task_type, payload, attempts FROM agent_tasks
                 WHERE status = 'pending' ORDER BY id LIMIT ?""", (MAX_TASKS_PER_LOOP,))
    return c.fetchall()


def claim_task(conn, task_id: int) -> bool:
    c = conn.cursor()
    c.execute("""UPDATE agent_tasks SET status = 'running', started_at = CURRENT_TIMESTAMP,
                 attempts = attempts + 1 WHERE id = ? AND status = 'pending'""", (task_id,))
    conn.commit()
    return c.rowcount == 1


def finish_task(conn, task_id: int, ok: bool, result: dict | None = None,
                result_path: str | None = None, error: str | None = None) -> None:
    c = conn.cursor()
    c.execute("SELECT attempts FROM agent_tasks WHERE id = ?", (task_id,))
    attempts = (c.fetchone() or [1])[0]
    if ok:
        c.execute("""UPDATE agent_tasks SET status = 'done', finished_at = CURRENT_TIMESTAMP,
                     result_path = ?, result_json = ?, error_text = NULL WHERE id = ?""",
                  (result_path, json.dumps(result or {}, ensure_ascii=False) if result else None, task_id))
    else:
        if attempts >= MAX_ATTEMPTS:
            c.execute("""UPDATE agent_tasks SET status = 'failed', finished_at = CURRENT_TIMESTAMP,
                         error_text = ? WHERE id = ?""", (error, task_id))
        else:
            c.execute("UPDATE agent_tasks SET status = 'pending', error_text = ? WHERE id = ?", (error, task_id))
    conn.commit()


def _relocation_txt(bewerbung: dict) -> str:
    """Relocation-Abschnitt im Onboarding-Freigabe-Report (Phase E, P6-Option C, User-GO 25.09.2026).
    Nur-Text aus knowledge/lifecycle/relocation.md (§2 Prozess, §5 Lücken, §6 DSGVO) – keine
    Adressen, keine URLs, keine erfundenen Zahlen; `bewerbung` = Task-Payload ohne Personenauswertung.
    Sprache aus dem Payload (Variante B, P3 07.10.2026)."""
    lang = _lang(bewerbung)
    return (
        "\n" + tr("## 🏛️ Relocation / Umzug, Behörden, Anmeldung", lang) + "\n\n"
        + tr("- **Reihenfolge (bindend, Spec §2):** 1 Visum/Aufenthalt (`check_visa`) → 2 Wohnung suchen/beziehen → 3 Bürgeramt-Anmeldung (Meldebehörde) → 4 Steuer-ID → 5 Krankenkasse → 6 ELStAM.", lang) + "\n"
        + tr("- **Schritt 3 Bürgeramt (Spec §2):** Anmeldung **innerhalb von 2 Wochen nach Einzug**; Unterlagen: Meldeschein + Personalausweis/Pass/Passersatz + Wohnungsgeberbestätigung (Mietvertrag ersetzt sie NICHT); Nicht-EU: Anmeldung **vor** dem Aufenthaltstitel, eAT mit Nationalpass (BMG § 17/§ 23).", lang) + "\n"
        + tr("- **Schritte 4–6 (Spec §2):** Steuer-ID erst **nach** Schritt 3 (IdNr bei Zuzug aus dem Ausland zwingend) · Krankenkasse: Kandidat wählt GKV, Arbeitgeber meldet Beschäftigung spätestens 6 Wochen nach Beginn · ELStAM: IdNr + Geburtsdatum, ohne IdNr Steuerklasse VI (max. 3 Monate).", lang) + "\n"
        + tr("- **FR/CH (Design-Entscheidung, Spec §2):** FR Mairie → numéro fiscal → sécurité sociale; CH Einwohnerkontrolle/Gemeinde → AHV-Nummer → Krankenkasse – Details nicht recherchiert.", lang) + "\n"
        + tr("- **Variante A (Spec §3):** Der Agent lädt, meldet und beantragt nie bei einer Behörde – nur Information, Checkliste, E-Mail-Hinweis nach HR-Freigabe.", lang) + "\n"
        + "\n" + tr("**Offen (Spec §5 – was NEU kommen müsste, noch nicht umgesetzt):**", lang) + "\n"
        + tr("- §5.1 Behörden-Infos live & kostenlos (Fristen/Öffnungen/Formulare) via `fetch` + `anysearch` → knowledge-MD – **offen**.", lang) + "\n"
        + tr("- §5.2 Relocation-Abschnitt in `knowledge/onboarding-default.md` + den 3 Land-Templates – **offen**.", lang) + "\n"
        + tr("- §5.3 Skill `relocation` (Agent-Ebene, analog `check-visa`) – **offen**.", lang) + "\n"
        + tr("- §5.4 ansvar-Query-Test `search(\"Bundesmeldegesetz Anmeldung 17\")` – **offen**.", lang) + "\n"
        + tr("- §5.5 MD-Korrektur `knowledge/legal/visa-rules.md:144` – **offen**.", lang) + "\n"
        + tr("- §5.6 Trigger/Task-Zeitpunkt des relocation-Checks (Design-Entscheidung) – **offen**.", lang) + "\n"
        + "\n" + tr("**DSGVO (Spec §6):** Meldebestätigung/Meldeschein enthält die vollständige Wohnanschrift = Stammdaten "
                    "(Löschfrist 6 Monate, `gdpr-policy.md:48`); in Agent-Berichten nur Status speichern („Meldebestätigung: "
                    "ja/nein/Offen“, „Wohnungsgeberbestätigung: vorliegend/ja“), **keine** Adresse, **keine** Meldeschein-/"
                    "Pass-/eAT-Nummern (Art. 5 Abs. 1 c DSGVO); Meldeadresse nie in E-Mails an Dritte.", lang) + "\n"
    )


def process_task(conn, task_id: int, task_type: str, payload_json: str, attempts: int) -> None:
    if not claim_task(conn, task_id):
        return
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        finish_task(conn, task_id, False, error="payload ungültig (JSONDecodeError)")
        return
    app_id = payload.get("application_id")
    log(f"→ Task #{task_id} ({task_type}) startet (Versuch {attempts + 1}/{MAX_ATTEMPTS})")
    result, result_path, ok, error = {}, None, True, None
    try:
        if task_type == "send_confirmation":
            result = send_confirmation(payload)
        elif task_type == "send_rejection":
            result = send_rejection(payload)
        elif task_type == "create_invitation":
            result = create_invitation(payload)
            # Einladungs-Bericht ablegen (Nachweispflicht, Spec §9)
            _langval = _lang(payload)
            rep = ERGEBNISSE / f"einladung-bewerbung-{app_id}.md"
            rep.write_text(tr("# Einladung – Bewerbung #{0}", _langval).format(app_id) + "\n\n"
                           + tr("- Meeting (HR/Director): {0}", _langval).format(result['vdo_ninja_url']) + "\n"
                           + tr("- Meeting (Kandidat/Gast, Gate 8): {0}", _langval).format(
                               result.get('vdo_ninja_gast_url', result['vdo_ninja_url'])) + "\n"
                           + tr("- Termin: {0}", _langval).format(result['termin']) + "\n"
                           + tr("- ICS (Kandidat/Gast): {0}", _langval).format(result['ics_path']) + "\n"
                           + tr("- ICS (HR/Director): {0}", _langval).format(
                               result.get('ics_path_hr', result['ics_path'])) + "\n"
                           + tr("- Mail: {0}", _langval).format(result['mail']) + "\n\n"
                           + tr("*Ausgelöst durch HR-Klick ({0}) – Variante A.*", _langval).format(payload.get('trigger'))
                           + "\n",
                           encoding="utf-8")
            result_path = str(rep)
        elif task_type == "onboarding_release":
            # 7️⃣-Mechanismus zeigt die Checkliste automatisch bei Status 'eingestellt'
            # (app.py:1689); der Task dokumentiert die Freigabe (Spec §3).
            _langval = _lang(payload)
            # Spec v6: Wenn Visum-Bedarf → Freigabe-Bericht enthält Visum-Abschnitt (WAS/WIE/WO)
            _visum = _visum_auswertung_from_ergebnisse(payload.get("candidate_id"))
            _visum_txt = ""
            if _visum:
                _visum_txt = ("\n" + tr("## 📋 Visum-Schritt (agent-generiert)", _langval) + "\n\n"
                              + tr("- **WAS:** {0}", _langval).format(_visum.get('was', '–')) + "\n"
                              + tr("- **WIE:** {0}", _langval).format(_visum.get('wie', '–')) + "\n"
                              + tr("- **WO:** {0}", _langval).format(_visum.get('wo', '–')) + "\n\n"
                              + tr("Der Agent stellt keinen Antrag – die Antragstellung obliegt dem Kandidaten.", _langval) + "\n")
            # Mentoring (Phase D P10, Spec §5): aktiver Mentor im Freigabe-Report
            _mentor_txt = ""
            _mcid = payload.get("candidate_id")
            if _mcid:
                try:
                    _mconn = sqlite3.connect(str(DB_PATH))
                    _mrow = _mconn.execute(
                        "SELECT mentor_name FROM mentoring WHERE candidate_id = ? "
                        "AND status = 'aktiv' ORDER BY changed_at DESC LIMIT 1",
                        (_mcid,),
                    ).fetchone()
                    _mconn.close()
                    if _mrow and _mrow[0]:
                        _mentor_txt = ("\n" + tr("## 🤝 Patenschaft (Mentoring)", _langval) + "\n\n"
                                       + tr("- **Mentor/Ansprechpartner:** {0}", _langval).format(_mrow[0]) + "\n")
                except sqlite3.Error:
                    _mentor_txt = ""
            # Wohnungssuche (Phase D P6, Spec §5): Checkliste + freie Quellen
            # im Freigabe-Report (analog _visum_txt, KEIN Scraping/Listing-API)
            _wohnung_txt = ("\n" + tr("## 🏠 Wohnungssuche (Checkliste + freie Quellen)", _langval) + "\n\n"
                            + tr("- **Checkliste:** Zielstadt + Einzugstermin festlegen → Bewerbungsmappe "
                                 "(Selbstauskunft, SCHUFA, Einkommensnachweise) → Mietpreis-Range via "
                                 "Open-Data-Mietspiegel prüfen → freie Quellen nutzen → Angebote manuell "
                                 "auf Portalen (Browser) ansehen", _langval) + "\n"
                            + tr("- **Freie Quellen:** BMWSB-Ratgeber »Auf Wohnungssuche in Deutschland« · "
                                 "Handbook Germany (9 Sprachen) · Statistikportal/Destatis Open Data · "
                                 "kommunale Wohnungsämter", _langval) + "\n"
                            + tr("- **Portale (nur Link, manuell):** ImmoScout24 · Kleinanzeigen · "
                                 "wg-gesucht · immowelt (AGB untersagt automatisiertes Scraping)", _langval) + "\n"
                            + tr("- Der Agent sucht keine Angebote und stellt keine Mietanfragen "
                                 "(Variante A).", _langval) + "\n")
            # Relocation (Phase E P6-Option C, User-GO 25.09.2026): behördenrechtlicher
            # Abschnitt im Freigabe-Report (analog _wohnung_txt, Nur-Text Spec relocation.md)
            _relocation = _relocation_txt(payload)
            result = {"released": True,
                      "hinweis": tr("Checkliste via 7️⃣ Generate Onboarding freigeben (HR)", _langval),
                      **({"visum": _visum} if _visum else {})}
            rep = ERGEBNISSE / f"onboarding-freigabe-bewerbung-{app_id}.md"
            rep.write_text(tr("# Onboarding-Freigabe – Bewerbung #{0}", _langval).format(app_id) + "\n\n"
                           + tr("Kandidat #{0} eingestellt – HR erstellt die "
                                "Checkliste mit 7️⃣ Generate Onboarding und gibt sie frei.",
                                _langval).format(payload.get('candidate_id'))
                           + _mentor_txt
                           + _visum_txt
                           + _wohnung_txt
                           + _relocation
                           + "\n" + tr("*Task automatisch erzeugt beim Statuswechsel 'eingestellt'.*", _langval) + "\n",
                           encoding="utf-8")
            # Mail #6 (NB6, 23.09.2026): Onboarding-Begrüßungsmail an Kandidat
            _mail_res = send_onboarding_mail(payload)
            result["mail"] = _mail_res.get("mail", "")
            result["mail_to"] = _mail_res.get("to", "")
            result_path = str(rep)
        elif task_type in ("extract_profile", "match_candidate", "check_compliance", "assess_culture_fit",
                           "verify_documents", "check_visa", "notify_user", "check_gdpr",
                           "explain_match"):
            result = run_llm_task(task_type, payload)
            result_path = result.get("result_path")
        elif task_type == "visa_confirmation":
            result = visa_confirmation(payload)
        elif task_type == "notify_hr":
            result = notify_hr(payload, payload.get("score", 0), payload.get("kategorie", "–"))
        # Skill 16: export-report – Ergebnisse als MD-Datei exportieren
        elif task_type == "export_report":
            result = export_report(payload)
            result_path = result.get("result_path")
        # Skill 18: handle-errors – Fehler protokollieren
        elif task_type == "handle_errors":
            result = handle_errors(payload)
            result_path = result.get("result_path") if isinstance(result, dict) else None
        # Skill 23: contract-management – Contract Preflight (Phase D P8, 24.09.2026)
        # Deterministisch (kein LLM), HR-Klick-Guard, URLs aus Link-Katalog
        elif task_type == "contract_preflight":
            result = contract_preflight(payload)
            result_path = result.get("result_path")
        else:
            ok, error = False, f"unbekannter task_type: {task_type}"
    except FileNotFoundError as e:
        ok, error = False, str(e)
    except subprocess.TimeoutExpired:
        ok, error = False, f"Timeout ({LLM_TIMEOUT if task_type in ('extract_profile','match_candidate','check_compliance','assess_culture_fit','verify_documents','check_visa','notify_user','check_gdpr','explain_match') else MCP_TIMEOUT} s)"
    except Exception as e:
        ok, error = False, f"{type(e).__name__}: {e}"
    finish_task(conn, task_id, ok, result=result, result_path=result_path, error=error)
    log(f"✓ Task #{task_id} ({task_type}) {'done' if ok else 'FEHLER: ' + (error or '?')[:120]}")
    # Pförtner-Regel (v3): NACH finish_task evaluieren, sobald alle 3 Kette-Berichte
    # done sind (idempotent via notify_hr-Marker); JA → notify_hr-Task, NEIN → still
    if ok and task_type in ("match_candidate", "check_compliance", "assess_culture_fit"):
        try:
            _maybe_gatekeeper(conn, app_id, payload)
        except Exception as e:
            log(f"   Pförtner-Auswertung fehlgeschlagen (App/Runner läuft weiter): {e}")

# ─── Main-Loop ───────────────────────────────────────────────────────────

def write_pid() -> None:
    PID_FILE.write_text(str(os.getpid()))


def cleanup_pid(*_) -> None:
    try:
        if PID_FILE.exists() and PID_FILE.read_text().strip() == str(os.getpid()):
            PID_FILE.unlink()
    except Exception:
        pass
    sys.exit(0)


def sweep_gatekeeper(conn) -> None:
    """Selbstheilung: evaluiert die Pförtner-Regel für alle Bewerbungen, deren
    Kette fertig ist, aber noch kein notify_hr-Marker existiert (v3, idempotent)."""
    try:
        c = conn.cursor()
        c.execute("""SELECT DISTINCT payload FROM agent_tasks
                     WHERE task_type IN ('match_candidate', 'check_compliance', 'assess_culture_fit')""")
        seen = set()
        for (pj,) in c.fetchall():
            try:
                p = json.loads(pj)
            except json.JSONDecodeError:
                continue
            app_id = p.get("application_id")
            if app_id is None or app_id in seen:
                continue
            seen.add(app_id)
            _maybe_gatekeeper(conn, app_id, p)
    except Exception as e:
        log(f"Gatekeeper-Sweep fehlgeschlagen (Runner läuft weiter): {e}")


def main() -> None:
    write_pid()
    signal.signal(signal.SIGTERM, cleanup_pid)
    signal.signal(signal.SIGINT, cleanup_pid)
    log(f"Agent-Runner gestartet (PID {os.getpid()}, Modell {LLM_MODEL}, "
        f"{'DRY-RUN' if DRY_RUN else 'live'}, {'einmalig' if RUN_ONCE else 'Loop'})")
    while True:
        try:
            conn = sqlite3.connect(str(DB_PATH), timeout=10)
            sweep_gatekeeper(conn)
            tasks = fetch_pending(conn)
            for task_id, task_type, payload, attempts in tasks:
                process_task(conn, task_id, task_type, payload, attempts)
            conn.close()
        except Exception as e:
            log(f"Loop-Fehler (Runner läuft weiter): {e}")
        if RUN_ONCE:
            break
        time.sleep(LOOP_SECONDS)


if __name__ == "__main__":
    main()
