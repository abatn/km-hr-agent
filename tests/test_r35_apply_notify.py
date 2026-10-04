"""R3-5 (30.09.2026): Neue Bewerbung -> Benachrichtigung des Arbeitgebers.

Auftrag Runde 3, Punkt A („Anbinden") — N-D1.
Quelle der Logik: webui/pages/candidate.py::_notify_neue_bewerbung() +
::_bewerbung_senden() (Rueckgabe von db.apply_to_job wird ausgewertet,
notifications-Zeile NUR bei Erfolg).

Zweiter Teil der Aufgabe (N-D2: Drawer/Badge-Refresh nach „Alle als gelesen
markieren") liegt in webui/components.py::notifications_drawer()/shell() und
wird DOM-seitig in tests/e2e_notifications_flow.py belegt. Diese Datei belegt
die DB-Grundlage der Drawer-Logik: get_unread_count -> 1,
mark_notifications_read -> 0.

Isolation: tests/conftest.py leitet jeden Zugriff auf data/feedback.db in
einen frischen /tmp-Spiegel um — die Live-DB wird nur gelesen. Alle
Fixtures legen EIGENE employers/candidates/jobs an (employers.email und
candidates.email sind UNIQUE, applications hat UNIQUE(candidate_id, job_id)).

Ausfuehren:
  .venv-streamlit/bin/python3 -m pytest -q tests/test_r35_apply_notify.py
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from webui import db
from webui.pages import candidate as candidate_page

ROOT = Path(__file__).resolve().parents[1]


# ─── Fixtures / Helfer (Spiegel-DB) ─────────────────────────────────────

def _setup(prefix: str, status: str = "lebenslauf_hochgeladen",
           titel: str = "R35 Teststelle") -> tuple[int, int, int]:
    """Eigenes employer/candidate/job-Trio je Test (UNIQUE-Constraints)."""
    conn = db.get_conn()
    try:
        c = conn.cursor()
        c.execute(
            "INSERT INTO employers (email, password_hash, firma, kontaktperson) "
            "VALUES (?, 'x', ?, 'R35 HR')",
            (f"{prefix}-hr@example.invalid", f"Firma {prefix}"),
        )
        emp = c.lastrowid
        c.execute(
            "INSERT INTO candidates (email, name, password_hash, status) "
            "VALUES (?, ?, 'x', ?)",
            (f"{prefix}-c@example.invalid", f"Kandidat {prefix}", status),
        )
        cand = c.lastrowid
        c.execute(
            "INSERT INTO jobs (employer_id, titel, beschreibung, standort, "
            "stellentyp, hard_skills, status) "
            "VALUES (?, ?, 'R35 Teststelle', 'Berlin', 'Vollzeit', 'Python', 'aktiv')",
            (emp, titel),
        )
        job = c.lastrowid
        conn.commit()
        return emp, cand, job
    finally:
        conn.close()


def _notifs(user_id: int, role: str) -> list:
    conn = db.get_conn()
    try:
        return conn.execute(
            "SELECT id, titel, nachricht, gelesen FROM notifications "
            "WHERE user_id = ? AND role = ? ORDER BY id",
            (user_id, role),
        ).fetchall()
    finally:
        conn.close()


def _zurueckziehen(app_id: int) -> None:
    """Zurueckziehung wie im Portal (_tab_bewerbungen) — hebt die UNIQUE-Sperre."""
    conn = db.get_conn()
    try:
        conn.execute(
            "UPDATE applications SET status='zurückgezogen', "
            "aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?", (app_id,))
        conn.execute(
            "INSERT INTO application_status_history (application_id, status, changed_by) "
            "VALUES (?, 'zurückgezogen', 'kandidat')", (app_id,))
        conn.commit()
    finally:
        conn.close()


# ─── R3-5a (N-D1): Bewerbung -> notifications des Arbeitgebers ─────────

def test_frischbewerbung_benachrichtigt_arbeitgeber():
    emp, cand, job = _setup("r35-frisch", titel="R35 Frischstelle")
    app_id = candidate_page._bewerbung_senden(cand, job, "Motivation", "Anna R35")
    assert isinstance(app_id, int) and app_id > 0, f"application_id erwartet, war {app_id!r}"

    rows = _notifs(emp, "employer")
    assert len(rows) == 1, f"genau eine notifications-Zeile erwartet, waren {rows}"
    _, titel, nachricht, gelesen = rows[0]
    assert titel == "Neue Bewerbung"
    assert nachricht == "Anna R35 hat sich beworben: R35 Frischstelle"
    assert gelesen == 0

    # Kandidaten-Seite BLEIBT ungelesen-Zeilen-frei (Rolle ist employer)
    assert _notifs(cand, "candidate") == []


def test_reaktivierung_benachrichtigt_erneut():
    """Design-Entscheidung: Reaktivierung = neues Ereignis -> erneute Zeile."""
    emp, cand, job = _setup("r35-reakt", titel="R35 Reaktivierungsstelle")
    app1 = candidate_page._bewerbung_senden(cand, job, "Text 1", "Anna R35")
    assert len(_notifs(emp, "employer")) == 1

    _zurueckziehen(app1)
    app2 = candidate_page._bewerbung_senden(cand, job, "Text 2", "Anna R35")

    assert app2 == app1, "Reaktivierung muss dieselbe application_id liefern"
    rows = _notifs(emp, "employer")
    assert len(rows) == 2, f"Reaktivierung muss erneut benachrichtigen, waren {rows}"
    assert rows[1][2] == "Anna R35 hat sich beworben: R35 Reaktivierungsstelle"
    assert db.get_unread_count(emp, "employer") == 2


def test_blocked_status_keine_benachrichtigung():
    """CV-Pflicht (ValueError VOR dem Insert) -> KEINE notifications-Zeile."""
    emp, cand, job = _setup("r35-blocked", status="registriert",
                            titel="R35 Gesperrte Stelle")
    with pytest.raises(ValueError):
        candidate_page._bewerbung_senden(cand, job, "Text", "Anna R35")

    assert _notifs(emp, "employer") == [], "kein Insert bei gesperrtem Status"
    conn = db.get_conn()
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM applications WHERE candidate_id = ?", (cand,)
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_doppelbewerbung_keine_zweite_benachrichtigung():
    """IntegrityError (UNIQUE) VOR dem Insert -> Zeile bleibt bei 1."""
    emp, cand, job = _setup("r35-doppel", titel="R35 Doppelstelle")
    candidate_page._bewerbung_senden(cand, job, "Text", "Anna R35")
    with pytest.raises(sqlite3.IntegrityError):
        candidate_page._bewerbung_senden(cand, job, "Text", "Anna R35")
    assert len(_notifs(emp, "employer")) == 1


def test_name_fallbacks():
    """Session-Name leer -> candidates.name; unbekannter Kandidat -> „Ein Bewerber"."""
    emp, cand, job = _setup("r35-name", titel="R35 Namensstelle")
    # (a) candidate_id-Lookup
    candidate_page._notify_neue_bewerbung(job, "", cand)
    # (b) Fallback „Ein Bewerber" (candidate_id ohne Zeile)
    emp2, _cand2, job2 = _setup("r35-name2", titel="R35 Namenlos")
    candidate_page._notify_neue_bewerbung(job2, "", 99999999)

    rows = _notifs(emp, "employer")
    assert rows[0][2] == "Kandidat r35-name hat sich beworben: R35 Namensstelle"
    rows2 = _notifs(emp2, "employer")
    assert rows2[0][2] == "Ein Bewerber hat sich beworben: R35 Namenlos"


def test_unbekanntes_job_id_kein_insert(capsys):
    """Kein Job -> kein Employer -> kein Insert, kein Crash (try/except print)."""
    emp, cand, job = _setup("r35-nojob")
    candidate_page._notify_neue_bewerbung(99999999, "Anna R35", cand)
    assert _notifs(emp, "employer") == []


# ─── R3-5b (N-D2) DB-Grundlage: unread -> markiert -> 0 ────────────────

def test_unread_count_und_markieren():
    """get_unread_count 1 -> mark_notifications_read -> 0 (Drawer-Logik)."""
    emp, _cand, _job = _setup("r35-unread")
    assert db.get_unread_count(emp, "employer") == 0

    db.insert_notification(emp, "employer", "Neue Bewerbung",
                           "Anna R35 hat sich beworben: R35 Unread-Stelle")
    assert db.get_unread_count(emp, "employer") == 1

    rows = db.get_notifications(emp, "employer")
    assert len(rows) == 1 and rows[0][1] == "Neue Bewerbung"
    assert rows[0][3] == 0  # gelesen = 0

    db.mark_notifications_read(emp, "employer")
    assert db.get_unread_count(emp, "employer") == 0
    # idempotent: zweiter Aufruf ändert nichts, Zeile bleibt erhalten
    db.mark_notifications_read(emp, "employer")
    assert len(db.get_notifications(emp, "employer")) == 1


# ─── Quelltext-Nachweis der UI-Verdrahtung (kein DB-Zugriff) ───────────

def test_ui_handler_ruft_bewerbung_senden_auf():
    src = (ROOT / "webui" / "pages" / "candidate.py").read_text(encoding="utf-8")
    assert "app_id = _bewerbung_senden(" in src, \
        "_submit() muss die Rueckgabe auswerten (NUR bei Erfolg benachrichtigen)"
    assert "db.apply_to_job(s[\"user_cand_id\"], jid" not in src, \
        "der Bewerbungs-Call muss ueber _bewerbung_senden laufen"
