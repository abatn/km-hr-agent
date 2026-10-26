"""Doppelklick-Schutz beim Stellen-Publish (11.10.2026, Design-Entscheidung).

Beleg: Live-Vorfall 11.10.2026 — Toufe7 (employer_id 3) publizierte dieselbe
Stelle zweimal (jobs #10 17:39:22, #11 17:39:38, identisch, 16 s Abstand):
`create_job` sperrte den Button nicht und leerte das Formular nicht;
`db.insert_job` hatte keinen Duplikat-Schutz.

Spec: knowledge/portal/employer-portal-fields.md „Doppelklick-Schutz".
DB-basiert (tmp_path-Spiegel wie test_compliance_writer.py), keine Eigenanlagen
in /tmp.
"""
import sqlite3
from pathlib import Path

from webui import db

ROOT = Path(__file__).resolve().parents[1]


def _init_jobs_db(path: Path) -> Path:
    conn = sqlite3.connect(str(path))
    conn.execute("""CREATE TABLE jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employer_id INTEGER NOT NULL, titel TEXT NOT NULL, beschreibung TEXT NOT NULL,
        standort TEXT NOT NULL, stellentyp TEXT NOT NULL, hard_skills TEXT NOT NULL,
        soft_skills TEXT, berufserfahrung_jahre INTEGER,
        deutsch_level TEXT, englisch_level TEXT, abschluss TEXT,
        gehaltsrahmen_min INTEGER, gehaltsrahmen_max INTEGER,
        status TEXT DEFAULT 'aktiv',
        erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        land TEXT DEFAULT 'DE',
        bruttojahresgehalt_eur INTEGER)""")
    conn.execute("""CREATE TABLE job_status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER, status TEXT,
        changed_by TEXT)""")
    conn.commit()
    conn.close()
    return path


def _insert(employer_id=3, standort="Zürich, Schweiz", titel="Kraftfahrer (m/w/d)"):
    return db.insert_job(
        employer_id=employer_id, titel=titel,
        beschreibung="Fahreraufgaben in der Schweiz, Lenk- und Ruhezeiten beachten, "
                     "Ladung sichern und Fahrzeug pflegen — mindestens 50 Zeichen.",
        standort=standort, land="CH", stellentyp="Vollzeit",
        hard_skills="Führerschein C/CE, Fahrerkarte", soft_skills="Zuverlässigkeit",
        berufserfahrung_jahre=2, deutsch_level="A1", englisch_level="A1",
        abschluss="Egal", gehaltsrahmen_min=2500, gehaltsrahmen_max=3500)


# ─── DB-Ebene: Dedupe in insert_job ────────────────────────────────────────

def test_zweiter_aufruf_identisch_gibt_bestehende_id(tmp_path, monkeypatch):
    p = _init_jobs_db(tmp_path / "jobs.db")
    monkeypatch.setattr(db, "DB_PATH", p)
    first = _insert()
    second = _insert()  # Doppelklick, identische Werte, < 60 s
    assert first == second
    conn = sqlite3.connect(str(p))
    try:
        n = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        hist = conn.execute("SELECT COUNT(*) FROM job_status_history").fetchone()[0]
    finally:
        conn.close()
    assert n == 1, "identischer Klick innerhalb 60 s darf keine zweite Zeile anlegen"
    assert hist == 1, "kein zweiter Status-History-Eintrag zum Dedupe-Fall"


def test_anderer_standort_ist_kein_duplikat(tmp_path, monkeypatch):
    p = _init_jobs_db(tmp_path / "jobs2.db")
    monkeypatch.setattr(db, "DB_PATH", p)
    a = _insert(standort="Zürich, Schweiz")
    b = _insert(standort="Basel, Schweiz")
    assert a != b
    conn = sqlite3.connect(str(p))
    try:
        n = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    finally:
        conn.close()
    assert n == 2


def test_fenster_vorbei_erlaubt_neue_zeile(tmp_path, monkeypatch):
    p = _init_jobs_db(tmp_path / "jobs3.db")
    monkeypatch.setattr(db, "DB_PATH", p)
    a = _insert()
    conn = sqlite3.connect(str(p))
    try:
        conn.execute(
            "UPDATE jobs SET erstellt_am = datetime('now', '-120 seconds') WHERE id = ?",
            (a,))
        conn.commit()
    finally:
        conn.close()
    b = _insert()  # identisch, aber > 60 s spaeter -> neue Stelle zulaessig
    assert a != b
    conn = sqlite3.connect(str(p))
    try:
        n = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    finally:
        conn.close()
    assert n == 2


def test_andere_employer_id_ist_kein_duplikat(tmp_path, monkeypatch):
    p = _init_jobs_db(tmp_path / "jobs4.db")
    monkeypatch.setattr(db, "DB_PATH", p)
    a = _insert()
    b = _insert(employer_id=1)
    assert a != b


# ─── UI-Ebene: Sperre + Reset in create_job (Quelltext-Assert, Muster P8.2) ─

def test_create_job_quellt_sperre_reset_und_finally():
    src = (ROOT / "webui" / "pages" / "employer.py").read_text(encoding="utf-8")
    fn = src.split("def create_job():", 1)[1].split("btn_stelle = ui.button", 1)[0]
    assert "btn_stelle.disable()" in fn, "Publish-Button muss beim Absenden gesperrt werden"
    assert "finally:" in fn and "btn_stelle.enable()" in fn, \
        "Button muss in finally immer wieder freigegeben werden"
    for feld in ("titel_input", "beschreibung_input", "standort_input", "hard_input"):
        assert f"{feld}.value = None" in fn, f"{feld} muss nach Erfolg zurueckgesetzt werden"
