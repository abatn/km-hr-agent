"""P1-1 (30.09.2026): Reaktivierung einer zurückgezogenen Bewerbung.

Nutzerentscheid 30.09.2026: „Zurückziehen hebt die Sperre auf“.

Kern: `applications` hat UNIQUE(candidate_id, job_id). Eine zurückgezogene
Bewerbung belegt diese Zeile. `db.apply_to_job` reaktiviert sie deshalb, statt
mit sqlite3.IntegrityError abzubrechen. ALLE ANDEREN Status bleiben gesperrt.

Getestet wird die REINE DB-Logik. tests/conftest.py leitet jeden Zugriff auf
data/feedback.db in einen frischen /tmp-Spiegel um — die Live-DB wird nur gelesen
und nie beschrieben.
"""
import sqlite3

import pytest

from webui import db


@pytest.fixture(scope="module")
def cand_id():
    """Ein Kandidat auf CV-Pflicht-Status im Spiegel (Status-Gate in apply_to_job).

    modulweit, weil candidates.email UNIQUE ist. Die STELLE legt jeder Test
    selbst an (applications hat UNIQUE(candidate_id, job_id), also braucht jeder
    Test eine eigene job_id).
    """
    conn = db.get_conn()
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO candidates (name, email, status, password_hash) "
            "VALUES ('P1-1 Test', 'p1-1-reapply@example.invalid', "
            "'lebenslauf_hochgeladen', 'x')")
        conn.commit()
        return c.lastrowid
    finally:
        conn.close()


def _job(conn, n: int) -> int:
    """Eigene Stelle pro Test (UNIQUE(candidate_id, job_id) verlangt das)."""
    c = conn.cursor()
    # employer_id, titel, beschreibung, standort, stellentyp, hard_skills = NOT NULL
    # (read-only an PRAGMA table_info(jobs) verifiziert)
    c.execute("INSERT INTO jobs (employer_id, titel, beschreibung, standort, "
              "stellentyp, hard_skills, status) "
              "VALUES (1, ?, 'P1-1 Teststelle', 'Berlin', 'Vollzeit', 'Python', 'aktiv')",
              (f"P1-1 Job {n}",))
    return c.lastrowid


def _bewerbung(conn, cid, jid, status, text=None):
    c = conn.cursor()
    c.execute(
        "INSERT INTO applications (candidate_id, job_id, status, bewerbungstext) "
        "VALUES (?, ?, ?, ?)", (cid, jid, status, text))
    aid = c.lastrowid
    c.execute("INSERT INTO application_status_history (application_id, status, changed_by) "
              "VALUES (?, ?, 'kandidat')", (aid, status))
    conn.commit()
    return aid


def _status(app_id):
    conn = db.get_conn()
    try:
        return conn.execute("SELECT status FROM applications WHERE id=?", (app_id,)).fetchone()[0]
    finally:
        conn.close()


def _anzahl(cid, jid):
    conn = db.get_conn()
    try:
        return conn.execute("SELECT COUNT(*) FROM applications WHERE candidate_id=? AND job_id=?",
                            (cid, jid)).fetchone()[0]
    finally:
        conn.close()


# ─── Reaktivierung: das gewaehlte Verhalten ────────────────────────────────

def test_zurueckgezogen_wird_reaktiviert_statt_blockiert(cand_id):
    cid = cand_id
    conn = db.get_conn()
    try:
        jid = _job(conn, 1)
        alt = _bewerbung(conn, cid, jid, "zurückgezogen", "alter Text")
    finally:
        conn.close()

    neue_id = db.apply_to_job(cid, jid, "neuer Text")

    assert neue_id == alt, "muss DIESE Zeile wiederverwenden, keine neue anlegen"
    assert _status(alt) == "eingegangen"
    assert _anzahl(cid, jid) == 1, "keine Doppelzeile trotz erneutem Bewerben"


def test_reaktivierung_ueberschreibt_text_und_zeitstempel(cand_id):
    cid = cand_id
    conn = db.get_conn()
    try:
        jid = _job(conn, 2)
        alt = _bewerbung(conn, cid, jid, "zurückgezogen", "alter Text")
    finally:
        conn.close()
    db.apply_to_job(cid, jid, "neuer Text")
    conn = db.get_conn()
    try:
        text, ts = conn.execute(
            "SELECT bewerbungstext, aktualisiert_am FROM applications WHERE id=?",
            (alt,)).fetchone()
    finally:
        conn.close()
    assert text == "neuer Text"
    assert ts, "aktualisiert_am muss gesetzt sein"


def test_reaktivierung_protokolliert_einen_neuen_uebergang(cand_id):
    cid = cand_id
    conn = db.get_conn()
    try:
        jid = _job(conn, 3)
        alt = _bewerbung(conn, cid, jid, "zurückgezogen")
    finally:
        conn.close()
    db.apply_to_job(cid, jid)
    conn = db.get_conn()
    try:
        hist = conn.execute(
            "SELECT status FROM application_status_history WHERE application_id=? ORDER BY id",
            (alt,)).fetchall()
    finally:
        conn.close()
    assert [h[0] for h in hist] == ["zurückgezogen", "eingegangen"], \
        "alte Historie bleibt erhalten, neuer Uebergang wird ergaenzt"


def test_cv_pflicht_gilt_auch_fuer_die_reaktivierung(cand_id):
    """Kein Bypass am Status-Gate: ohne Lebenslauf weiterhin ValueError."""
    cid = cand_id
    conn = db.get_conn()
    try:
        jid = _job(conn, 4)
        alt = _bewerbung(conn, cid, jid, "zurückgezogen")
        conn.execute("UPDATE candidates SET status='neu' WHERE id=?", (cid,))
        conn.commit()
    finally:
        conn.close()
    try:
        with pytest.raises(ValueError, match="CV-Pflicht"):
            db.apply_to_job(cid, jid)
        assert _status(alt) == "zurückgezogen", "darf bei gesperrtem Status nicht aendern"
    finally:
        # Kandidatenstatus ist modulweit geteilt -> zuruecksetzen
        conn = db.get_conn()
        try:
            conn.execute("UPDATE candidates SET status='lebenslauf_hochgeladen' WHERE id=?", (cid,))
            conn.commit()
        finally:
            conn.close()


# ─── Alles andere bleibt gesperrt (Gegenprobe) ─────────────────────────────

@pytest.mark.parametrize("status", ["eingegangen", "angesehen", "eingeladen",
                                    "eingestellt", "abgelehnt"])
def test_andere_status_blockieren_weiterhin(cand_id, status):
    cid = cand_id
    conn = db.get_conn()
    try:
        jid = _job(conn, 10 + len(status))
        _bewerbung(conn, cid, jid, status)
    finally:
        conn.close()
    with pytest.raises(sqlite3.IntegrityError):
        db.apply_to_job(cid, jid)
    assert _anzahl(cid, jid) == 1
    assert _status(_first_app(cid, jid)) == status, "unveraendert"


def _first_app(cid, jid):
    conn = db.get_conn()
    try:
        return conn.execute("SELECT id FROM applications WHERE candidate_id=? AND job_id=?",
                            (cid, jid)).fetchone()[0]
    finally:
        conn.close()


def test_mehrfaches_reaktivieren_bleibt_eine_zeile(cand_id):
    cid = cand_id
    conn = db.get_conn()
    try:
        jid = _job(conn, 5)
        alt = _bewerbung(conn, cid, jid, "zurückgezogen")
    finally:
        conn.close()
    assert db.apply_to_job(cid, jid) == alt
    # zweite Runde: jetzt ist sie 'eingegangen' -> muss sperren
    with pytest.raises(sqlite3.IntegrityError):
        db.apply_to_job(cid, jid)
    assert _anzahl(cid, jid) == 1


# ─── Quelltext-Nachweis fuer die UI (kein DB-Zugriff) ─────────────────────

def test_ui_bietet_erneutes_bewerben_an():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "webui" / "pages" / "candidate.py"
           ).read_text(encoding="utf-8")
    assert "zurueckgezogen = bool(applied) and applied[1] == \"zurückgezogen\"" in src
    assert "Erneut bewerben" in src
