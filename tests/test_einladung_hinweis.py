"""Einladungs-Hinweis „Einladung wird vorbereitet" (22.10.2026, Auftrag:
„Ist der Status 'eingeladen', aber der create_invitation-Task noch nicht
fertig, den Hinweis anzeigen").

Vorfall (Bewerbung #42, 22.10.2026): Der Task wartete 63 min in der Queue;
die Employer-Seite zeigte weder Termin noch Link noch Hinweis, weil
`get_invitation_artifacts` NUR `status='done'` liest und in allen anderen
Faellen None liefert.

Teil 1: db.get_invitation_task_status (Temp-DB, kein Spiegel).
Teil 2: Rendering der Einladungs-Seite ueber das NiceGUI-User-Plugin
        (Routen in tests/nicegui_main.py: /p3-inv-pending, /p3-inv-kein-hinweis).
"""
import sqlite3
from pathlib import Path

from webui import db


def _task_db(tmp_path, zeilen: list) -> Path:
    dbf = tmp_path / "tasks.db"
    conn = sqlite3.connect(str(dbf))
    conn.execute("""CREATE TABLE agent_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_type TEXT, status TEXT, payload TEXT)""")
    for task_type, status, app_id in zeilen:
        conn.execute("INSERT INTO agent_tasks (task_type, status, payload) VALUES (?, ?, ?)",
                     (task_type, status, f'{{"application_id": {app_id}}}'))
    conn.commit()
    conn.close()
    return dbf


# ─── Teil 1: Status-Leser ──────────────────────────────────────────────────

def test_status_je_task_status(tmp_path, monkeypatch):
    dbf = _task_db(tmp_path, [
        ("create_invitation", "pending", 1),
        ("create_invitation", "running", 2),
        ("create_invitation", "failed", 3),
        ("create_invitation", "done", 4),
    ])
    monkeypatch.setattr(db, "AGENT_TASKS_DB", dbf)
    assert db.get_invitation_task_status(1) == "pending"
    assert db.get_invitation_task_status(2) == "running"
    assert db.get_invitation_task_status(3) == "failed"
    assert db.get_invitation_task_status(4) == "done"


def test_juengster_task_gewinnt(tmp_path, monkeypatch):
    """Zwei Tasks zur selben Bewerbung: der juengste bestimmt die Anzeige."""
    dbf = _task_db(tmp_path, [
        ("create_invitation", "pending", 42),
        ("create_invitation", "done", 42),
    ])
    monkeypatch.setattr(db, "AGENT_TASKS_DB", dbf)
    assert db.get_invitation_task_status(42) == "done"


def test_nur_create_invitation_zaehlt(tmp_path, monkeypatch):
    dbf = _task_db(tmp_path, [("match_candidate", "pending", 9)])
    monkeypatch.setattr(db, "AGENT_TASKS_DB", dbf)
    assert db.get_invitation_task_status(9) is None


def test_ohne_task_liefert_none(tmp_path, monkeypatch):
    dbf = _task_db(tmp_path, [("create_invitation", "done", 4)])
    monkeypatch.setattr(db, "AGENT_TASKS_DB", dbf)
    assert db.get_invitation_task_status(999) is None


def test_kaputte_db_liefert_none_ohne_absturz(tmp_path, monkeypatch):
    """Tabelle fehlt (Muster R6-3: defekte DB) -> None, kein Exception-Absturz."""
    dbf = tmp_path / "leer.db"
    sqlite3.connect(str(dbf)).close()
    monkeypatch.setattr(db, "AGENT_TASKS_DB", dbf)
    assert db.get_invitation_task_status(42) is None


# ─── Teil 2: Rendering ─────────────────────────────────────────────────────

async def test_hinweis_bei_pending_task(user):
    """pending Task -> Hinweis; done-Bewerbung zeigt weiterhin die volle Karte."""
    await user.open('/p3-inv-pending')
    await user.should_see('Kandidat Pending')
    await user.should_see('Einladung wird vorbereitet')
    # done-Fall unveraendert: Karte mit Termin + Director-Link
    await user.should_see('Kandidat Fertig')
    await user.should_see('2026-10-23 10:00')
    await user.should_see('https://vdo.ninja/?director=prescreeningtest1')


async def test_hinweis_auch_bei_running_task(user):
    """running haengt wie pending unter 'noch nicht fertig'."""
    await user.open('/p3-inv-running')
    await user.should_see('Kandidat Pending')
    await user.should_see('Einladung wird vorbereitet')
