"""Shared E2E harness (F2/F3, 23.09.2026).

F2: Server-Precheck — kein Test ohne liveen Server. Exit 2 statt PASS.
F3: Residue-Zeile — Altlasten (pre_max) vs. Test-Reste (id > pre_max) getrennt.

Nutzung in e2e_*.py (erste Zeilen von main()):
    from e2e_harness import check_server, db_residue_report, pre_max_tasks
    check_server()                       # exit 2, wenn Server nicht HTTP 200
    pre = pre_max_tasks()                # vor dem Test speichern
    ...
    db_residue_report(pre)               # am Ende: F3-Zeile printen
"""
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

# E2E-Isolation (27.09.2026, tests/e2e_isolation.py): Base-URL und DB-Pfad
# sind per Env übersteuerbar.
# R6-0 (30.09.2026): OHNE KMHR_E2E_BASE kein Lauf — der stille Default auf
# http://localhost:8080 traf am 30.09. um 11:50 die LIVE-App (Bewerbung #29
# eingeladen→abgelehnt, Task #286 send_rejection). Isolierte Läufe setzen
# KMHR_E2E_BASE automatisch (e2e_isolation.py:126); bewusst gegen die Live-
# App testen heisst: KMHR_E2E_BASE=http://localhost:8080 explizit setzen.
BASE = os.environ.get("KMHR_E2E_BASE")
if not BASE:
    sys.exit(
        "[e2e_harness] KMHR_E2E_BASE ist NICHT gesetzt — Lauf gegen die "
        "LIVE-App :8080 ist gesperrt (R6-0).\n"
        "  Isoliert (empfohlen): python3 tests/e2e_isolation.py --port <frei> "
        "--only <skript>\n"
        "  Bewusst live:      KMHR_E2E_BASE=http://localhost:8080 python3 tests/<skript>.py"
    )
ROOT = Path(__file__).resolve().parents[1]
DB = Path(os.environ.get("KMHR_DB_PATH") or (ROOT / "data" / "feedback.db"))

# ── CI-Seed-Konten (Option A, 08.10.2026) ────────────────────────────────
# Die E2E-Skripte melden sich mit den LOKALEN Testkonten an (data/feedback.db).
# Das CI-Seed (tests/fixtures/seed.db, erzeugt von scripts/seed_ci_db.py) hat
# dieselben Zeilen/Passwort-Hashes, aber anonymisierte E-Mails (kandidatN@…).
# Mit KMHR_E2E_SEED=1 (CI-Workflow) übersetzt seed_email() den lokalen Wert in
# die Seed-E-Mail; lokal (ohne die Var) bleibt der Wert unverändert.
# Spec: knowledge/system/e2e-ci-seed.md
SEED_MODE = os.environ.get("KMHR_E2E_SEED") == "1"
_SEED_MAP = {
    # Kandidaten: local -> seed (IDs = scripts/seed_ci_db.py::_email)
    "batniniabdelkader@yahoo.com": "kandidat1@example.invalid",
    "test@example.de": "kandidat2@example.invalid",
    "batninitaoufik@gmail.com": "kandidat13@example.invalid",
    "e2e-beweis-phase1@example.com": "kandidat16@example.invalid",
    "recruiting.e2e.2809b@kmailtest.de": "kandidat22@example.invalid",
    # Arbeitgeber
    "hr@techvision.de": "hr1@example.invalid",
    # Admin
    "admin@km-hr-agent.local": "admin@example.invalid",
}


def seed_email(value: str) -> str:
    """Übersetzt eine lokale Login-E-Mail in die Seed-E-Mail (nur KMHR_E2E_SEED=1)."""
    return _SEED_MAP.get(value, value) if SEED_MODE else value


def check_server() -> None:
    """F2-Precheck: meldet 'SERVER DOWN (HTTP xxx)' und beendet mit exit 2."""
    url = f"{BASE}/login"
    code = None
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            code = resp.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception:
        code = 0
    if code != 200:
        print(f"SERVER DOWN (HTTP {code:03d}) — Test nicht aussagekräftig")
        sys.exit(2)


def pre_max_tasks() -> int:
    """Max. agent_tasks.id VOR dem Test (Grenze Altlast vs. Test-Rest)."""
    conn = sqlite3.connect(DB)
    try:
        return conn.execute("SELECT COALESCE(MAX(id), 0) FROM agent_tasks").fetchone()[0]
    finally:
        conn.close()


def db_residue_report(pre_id: int) -> int:
    """F3-Zeile: heutige Altlasten (id <= pre_id) vs. Test-Reste (id > pre_id).

    Test-Reste muessen 0 sein (Restore mueste ggf. noch nachgeholt werden).
    Rueckgabe: Anzahl Test-Reste (0 = ok).
    """
    from datetime import date
    today = date.today().isoformat()
    conn = sqlite3.connect(DB)
    try:
        altlasten = conn.execute(
            "SELECT COUNT(*) FROM agent_tasks "
            "WHERE created_at LIKE ? AND id <= ?",
            (f"{today}%", pre_id),
        ).fetchone()[0]
        residue = conn.execute(
            "SELECT COUNT(*) FROM agent_tasks "
            "WHERE created_at LIKE ? AND id > ?",
            (f"{today}%", pre_id),
        ).fetchone()[0]
    finally:
        conn.close()
    mark = "✓" if residue == 0 else "✗ Test-Reste muessen 0 sein!"
    print(
        f"DB-CHECK: Altlasten heute={altlasten} (erwartet, unverändert), "
        f"Test-Reste={residue} {mark}"
    )
    return residue
