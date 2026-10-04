"""N-K (01.10.2026): compliance_protokoll — Writer + Zurechnung.

User-Entscheidung 01.10.2026 (question-Tool) „Beides: Writer + Berichte":
die MD-Berichte bleiben Primärquelle (Compliance-Seite, R3-3); zusätzlich wird
`compliance_protokoll` wieder aktiv befüllt (mit `application_id`).

Beweis-Kanäle:
  * Berichts-Seite  : `tests/test_r33_compliance_reports.py` + `tests/e2e_compliance_reports.py`
  * Writer-Seite    : DIESE Datei (Parser + db-Writer + Zurechnung)

Alles ohne Live-DB: temporäre DB-Datei bzw. In-Memory-Verbindung.
"""
import importlib.util
import sqlite3
from pathlib import Path

from webui import db
from webui.pages import employer as emp

ROOT = Path(__file__).resolve().parents[1]


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "agent_runner_mod", str(ROOT / "scripts" / "agent-runner.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RUNNER = _load_runner()


# ─── Parser ───────────────────────────────────────────────────────────────

def test_parser_status_token():
    p = RUNNER._parse_compliance_status
    assert p("Compliance-Status: COMPLIANT\nGrund...") == "COMPLIANT"
    assert p("Compliance-Status: NICHT_COMPLIANT\nGrund...") == "NICHT_COMPLIANT"
    # Leerzeichen-Variante
    assert p("Compliance-Status: NICHT COMPLIANT - AGG") == "NICHT_COMPLIANT"
    # NICHT_COMPLIANT darf nicht als COMPLIANT durchgehen
    assert p("Compliance-Status: NICHT_COMPLIANT - DSGVO") == "NICHT_COMPLIANT"
    assert p("ohne Token") is None
    assert p("") is None


# ─── db-Writer ─────────────────────────────────────────────────────────────

def _tmp(tmp_path) -> Path:
    p = tmp_path / "cproto.db"
    db.init_compliance_protokoll_table(p)
    return p


def test_init_legt_tabelle_mit_application_id(tmp_path):
    p = _tmp(tmp_path)
    conn = sqlite3.connect(str(p))
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(compliance_protokoll)")}
    finally:
        conn.close()
    assert "application_id" in cols


def test_init_migriert_altbestand_ohne_application_id(tmp_path):
    p = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(p))
    conn.execute("""CREATE TABLE compliance_protokoll (
        id INTEGER PRIMARY KEY AUTOINCREMENT, match_id TEXT NOT NULL, land TEXT NOT NULL,
        pruefpunkt TEXT NOT NULL, status TEXT NOT NULL, details TEXT,
        datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()
    conn.close()
    db.init_compliance_protokoll_table(p)  # Migration
    conn = sqlite3.connect(str(p))
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(compliance_protokoll)")}
    finally:
        conn.close()
    assert "application_id" in cols


def test_writer_insert_dann_update_idempotent(tmp_path):
    p = _tmp(tmp_path)
    a = db.record_compliance_protokoll(
        "employer-job-5-cand-1-2026-10-01", "DE", "Gesamt", "COMPLIANT", "Grund", 42, p)
    assert a == "inserted"
    b = db.record_compliance_protokoll(
        "employer-job-5-cand-1-2026-10-01", "DE", "Gesamt", "NICHT_COMPLIANT", "neu", 42, p)
    assert b == "updated"
    conn = sqlite3.connect(str(p))
    try:
        rows = conn.execute(
            "SELECT status, details, application_id FROM compliance_protokoll").fetchall()
    finally:
        conn.close()
    assert rows == [("NICHT_COMPLIANT", "neu", 42)]


# ─── Zurechnung: _compliance_rows liest den neuen Writer-Eintrag ───────────

def _con_with_job(employer_id, job_id):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY, employer_id INTEGER)")
    conn.execute("INSERT INTO jobs (id, employer_id) VALUES (?, ?)", (job_id, employer_id))
    return conn


def test_writer_eintrag_wird_zugerechnet():
    conn = _con_with_job(1, 5)
    conn.execute("""CREATE TABLE compliance_protokoll (
        id INTEGER PRIMARY KEY AUTOINCREMENT, match_id TEXT NOT NULL, land TEXT NOT NULL,
        pruefpunkt TEXT NOT NULL, status TEXT NOT NULL, details TEXT,
        datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP, application_id INTEGER)""")
    conn.execute("INSERT INTO compliance_protokoll (match_id, land, pruefpunkt, status, "
                 "details, application_id) VALUES (?, ?, ?, ?, ?, ?)",
                 ("employer-job-5-cand-1-2026-10-01", "DE", "Gesamt", "COMPLIANT", "ok", 42))
    # Legacy-Zeile ohne job-Bezug → nicht zurechenbar
    conn.execute("INSERT INTO compliance_protokoll (match_id, land, pruefpunkt, status) "
                 "VALUES ('anna-schuster-devops-2026', 'DE', 'AGG §1', 'COMPLIANT')")
    zugeordnet, nicht = emp._compliance_rows(conn, 1)
    conn.close()
    assert nicht == 1
    assert len(zugeordnet) == 1
    r = zugeordnet[0]
    assert r["job_id"] == 5 and r["cand_id"] == 1
    assert r["application_id"] == 42
    assert r["status"] == "COMPLIANT"


def test_write_compliance_protokoll_voller_pfad(tmp_path, monkeypatch):
    p = tmp_path / "w.db"
    monkeypatch.setattr(db, "DB_PATH", p)
    akt = RUNNER._write_compliance_protokoll(
        {"application_id": 7, "candidate_id": 1, "job_id": 5},
        "# Check Compliance\nCompliance-Status: COMPLIANT - ok\n", 5, 1, "DE")
    assert "inserted" in akt
    conn = sqlite3.connect(str(p))
    try:
        row = conn.execute(
            "SELECT match_id, status, application_id FROM compliance_protokoll").fetchone()
    finally:
        conn.close()
    assert row[0].startswith("employer-job-5-cand-1-")
    assert row[1] == "COMPLIANT" and row[2] == 7


def test_write_compliance_protokoll_ohne_token_schreibt_nicht(tmp_path, monkeypatch):
    p = tmp_path / "w2.db"
    monkeypatch.setattr(db, "DB_PATH", p)
    akt = RUNNER._write_compliance_protokoll(
        {"application_id": 7}, "kein Status hier", 5, 1, "DE")
    assert "kein Status-Token" in akt
    conn = sqlite3.connect(str(p))
    try:
        n = conn.execute("SELECT COUNT(*) FROM compliance_protokoll").fetchone()[0]
    finally:
        conn.close()
    assert n == 0


def test_fremder_arbeitgeber_sieht_nichts():
    conn = _con_with_job(1, 5)
    conn.execute("""CREATE TABLE compliance_protokoll (
        id INTEGER PRIMARY KEY AUTOINCREMENT, match_id TEXT NOT NULL, land TEXT NOT NULL,
        pruefpunkt TEXT NOT NULL, status TEXT NOT NULL, details TEXT,
        datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP, application_id INTEGER)""")
    conn.execute("INSERT INTO compliance_protokoll (match_id, land, pruefpunkt, status, "
                 "application_id) VALUES (?, ?, ?, ?, ?)",
                 ("employer-job-5-cand-1-2026-10-01", "DE", "Gesamt", "COMPLIANT", 42))
    zugeordnet, nicht = emp._compliance_rows(conn, 999)  # fremder Arbeitgeber
    conn.close()
    assert zugeordnet == []
