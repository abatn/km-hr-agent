"""P8.2 (08.10.2026): Agent-Details/Badges aus der DB — Verifikation.

Spec: knowledge/system/p8-cloud-datenquellen.md.

Abgedeckt:
  (a) `db.get_candidate_agent_tasks` liefert je `task_type` die LETZTE Task
      (bei mehreren desselben Typs gewinnt die höchste id) und nur Tasks der
      Bewerbungen des angefragten Kandidaten.
  (b) `text` wird aus `result_json["text"]` gelesen.
  (c) fehlendes `result_json`/`text` ⇒ None (Legacy).
  (d) eine übergebene `conn` wird nicht geschlossen und keine eigene geöffnet.
  (e) Badge-Mapping: „AUFFÄLLIG"→🔴, „COMPLIANT"→🟢, Legacy `done`→🟢.
Zusätzlich: Runner speichert den Berichtstext gekappt (Quelltext-Beleg).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from webui import db
from webui.pages import employer


def _seed(tmp_path):
    p = tmp_path / "p82.db"
    conn = sqlite3.connect(str(p))
    conn.executescript(
        "CREATE TABLE applications (id INTEGER PRIMARY KEY, candidate_id INTEGER, job_id INTEGER);"
        "CREATE TABLE agent_tasks (id INTEGER PRIMARY KEY AUTOINCREMENT, task_type TEXT,"
        "  status TEXT, payload TEXT, result_json TEXT, created_at TEXT);"
    )
    # Kandidat 7 hat zwei Bewerbungen (10, 11); App 12 gehört Kandidat 99.
    conn.executemany(
        "INSERT INTO applications (id, candidate_id, job_id) VALUES (?,?,?)",
        [(10, 7, 1), (11, 7, 2), (12, 99, 1)],
    )
    rows = [
        # (a) zwei match_candidate → höchste id (App 11) gewinnt
        ("match_candidate", "done", {"application_id": 10, "gen": 0},
         {"text": "MATCH ALT", "result_path": "/x"}),
        ("match_candidate", "done", {"application_id": 11, "gen": 1},
         {"text": "MATCH NEU COMPLIANT", "result_path": "/y"}),
        # (b) text sauber gelesen
        ("check_compliance", "done", {"application_id": 10, "gen": 0},
         {"text": "Status: COMPLIANT", "agent_chars": 16}),
        # (c) Legacy: kein result_json (check_visa) / result_json ohne text
        ("check_visa", "done", {"application_id": 10, "gen": 0}, None),
        ("verify_documents", "failed", {"application_id": 11, "gen": 1},
         {"result_path": "/z"}),
        # Fremder Kandidat (App 12) → darf NICHT auftauchen
        ("explain_match", "done", {"application_id": 12, "gen": 0},
         {"text": "FREMD"}),
    ]
    for ttype, status, payload, rj in rows:
        conn.execute(
            "INSERT INTO agent_tasks (task_type, status, payload, result_json, created_at)"
            " VALUES (?,?,?,?, '2026-10-05')",
            (ttype, status, json.dumps(payload),
             json.dumps(rj) if rj is not None else None),
        )
    conn.commit()
    return conn


# ─── (a) letzte Task je Typ, nur eigener Kandidat ───────────────────────────

def test_letzte_task_je_typ_hoechste_id(tmp_path):
    conn = _seed(tmp_path)
    by = {t["task_type"]: t for t in db.get_candidate_agent_tasks(7, conn=conn)}
    assert by["match_candidate"]["text"] == "MATCH NEU COMPLIANT"
    assert by["match_candidate"]["application_id"] == 11
    assert by["match_candidate"]["gen"] == 1
    # Fremd-Kandidat (App 12) ausgeschlossen
    assert "explain_match" not in by
    conn.close()


# ─── (b) text aus result_json ───────────────────────────────────────────────

def test_text_aus_result_json(tmp_path):
    conn = _seed(tmp_path)
    by = {t["task_type"]: t for t in db.get_candidate_agent_tasks(7, conn=conn)}
    assert by["check_compliance"]["text"] == "Status: COMPLIANT"
    assert by["check_compliance"]["status"] == "done"
    conn.close()


# ─── (c) Legacy ohne text ⇒ None ────────────────────────────────────────────

def test_fehlender_text_ist_none(tmp_path):
    conn = _seed(tmp_path)
    by = {t["task_type"]: t for t in db.get_candidate_agent_tasks(7, conn=conn)}
    assert by["check_visa"]["text"] is None          # result_json fehlt
    assert by["verify_documents"]["text"] is None    # result_json ohne "text"
    conn.close()


# ─── (d) übergebene conn bleibt offen, keine eigene wird geöffnet ───────────

def test_uebergebene_conn_bleibt_offen(tmp_path, monkeypatch):
    conn = _seed(tmp_path)

    def _boom(*a, **k):
        raise AssertionError("eigene Verbindung geoeffnet")

    monkeypatch.setattr(db.sqlite3, "connect", _boom)
    db.get_candidate_agent_tasks(7, conn=conn)
    assert conn.execute("SELECT 1").fetchone()[0] == 1
    conn.close()


def test_kandidat_ohne_bewerbung_liefert_leer(tmp_path):
    conn = _seed(tmp_path)
    assert db.get_candidate_agent_tasks(4242, conn=conn) == []
    conn.close()


# ─── (e) Badge-Mapping ──────────────────────────────────────────────────────

def test_badge_mapping():
    assert employer._badge_icon("GESAMTSTATUS: AUFFÄLLIG") == "🔴"
    assert employer._badge_icon("STATUS: COMPLIANT") == "🟢"
    assert employer._badge_icon("STATUS: NICHT ERFORDERLICH") == "🟢"
    assert employer._legacy_badge_icon("done") == "🟢"
    assert employer._legacy_badge_icon("failed") == "🔴"
    assert employer._legacy_badge_icon("pending") == "🟡"
    # `_agent_task_icon`: vorhandener Text schlägt den Status
    assert employer._agent_task_icon({"text": "AUFFÄLLIG", "status": "done"}) == "🔴"
    assert employer._agent_task_icon({"text": None, "status": "done"}) == "🟢"
    assert employer._agent_task_icon({"text": "", "status": "failed"}) == "🔴"


# ─── Runner: Berichtstext additiv + gekappt ─────────────────────────────────

def test_runner_speichert_text_gekappt():
    src = (Path(__file__).resolve().parents[1] / "scripts" / "agent-runner.py").read_text("utf-8")
    assert "RESULT_TEXT_MAX = 20000" in src
    assert '"text": report_text[:RESULT_TEXT_MAX]' in src
    # Additiv: die Altfelder bleiben erhalten
    assert '"result_path": result_path, "agent_chars": len(agent_text)' in src
