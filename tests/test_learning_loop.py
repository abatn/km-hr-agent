"""Lern-Loop (02.11.2026): HR-Entscheidung → gewichtung_historie.

Die i18n-Schicht wird durch ein Minimal-Modul ersetzt (kein NiceGUI im
Testprozess nötig); der Connector-Aufruf wird auf {} gepatcht (kein
Subprozess, deterministische Schwellen 80/70).
"""
import json
import sys
import types

from webui import db, logic


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "learn.db")
    # Agent-Queue hat einen eigenen Modulpfad; in Produktion identisch zu DB_PATH.
    monkeypatch.setattr(db, "AGENT_TASKS_DB", tmp_path / "learn.db")
    fake = types.ModuleType("webui.i18n")
    fake._ = lambda m: m
    monkeypatch.setitem(sys.modules, "webui.i18n", fake)
    monkeypatch.setattr(logic, "_static_connector_call", lambda *a, **k: {})
    conn = db.get_conn()
    db.init_agent_tasks_table()
    conn.execute("""CREATE TABLE IF NOT EXISTS gewichtung_historie (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        datum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        kategorie TEXT NOT NULL,
        alte_gewichtung INTEGER NOT NULL,
        neue_gewichtung INTEGER NOT NULL,
        grund TEXT NOT NULL,
        feedback_anzahl INTEGER NOT NULL)""")
    return conn


def _match_task(conn, app_id, score):
    conn.execute(
        "INSERT INTO agent_tasks (task_type, status, payload, result_json) "
        "VALUES ('match_candidate','done',?,?)",
        (json.dumps({"application_id": app_id}),
         json.dumps({"text": f"Match-Score: {score}"})))
    conn.commit()


def test_last_match_score_aus_result_json(tmp_path, monkeypatch):
    conn = _setup(tmp_path, monkeypatch)
    try:
        _match_task(conn, 7, 85)
        assert logic.last_match_score(conn, 7) == 85
        assert logic.last_match_score(conn, 8) is None
    finally:
        conn.close()


def test_einladung_passt_erfahrung_an(tmp_path, monkeypatch):
    conn = _setup(tmp_path, monkeypatch)
    try:
        _match_task(conn, 7, 85)
        msg = logic.record_hr_decision(conn, 7, "eingeladen")
        row = conn.execute(
            "SELECT kategorie, alte_gewichtung, neue_gewichtung, grund, feedback_anzahl "
            "FROM gewichtung_historie").fetchone()
        assert row is not None
        assert row[0] == "Berufserfahrung"
        assert row[2] == row[1] + 5
        assert "hr_entscheidung:eingeladen" in row[3]
        assert row[4] == 1
        assert msg  # Anzeige-Text (deutsch im Test-Fake)
    finally:
        conn.close()


def test_ablehnung_ohne_score_aendert_nichts_aber_ist_neutral(tmp_path, monkeypatch):
    conn = _setup(tmp_path, monkeypatch)
    try:
        # Kein Match-Task → Score-Fallback 60; "Nein" + 60 ist kein < 70?
        # 60 < 70 → Sprache +10 (gewollter Regler).
        logic.record_hr_decision(conn, 99, "abgelehnt")
        row = conn.execute(
            "SELECT kategorie, neue_gewichtung FROM gewichtung_historie").fetchone()
        assert row[0] == "Sprache"
        assert row[1] == 10
    finally:
        conn.close()


def test_unbekannter_status_ist_no_op(tmp_path, monkeypatch):
    conn = _setup(tmp_path, monkeypatch)
    try:
        assert logic.record_hr_decision(conn, 1, "angesehen") == ""
        assert conn.execute(
            "SELECT COUNT(*) FROM gewichtung_historie").fetchone()[0] == 0
    finally:
        conn.close()
