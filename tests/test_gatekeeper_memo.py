"""R6-1 (30.09.2026): Gatekeeper-Merkbuch, Variante A — getestet gegen Spiegel-DB.

Befund: `sweep_gatekeeper` wertete jede fertige Kette bei JEDEM Runner-Zyklus
neu aus; NEIN liess keinen Marker → 336-419 Pförtner-Zeilen/Stunde,
34.186 hr-benchmark-Subprozess-Starts, logs/agent-errors.log 10,2 MB.

Variante A (Nutzer-GO 30.09.2026): Entscheidung je (application_id, gen,
Zustandssignatur der drei Berichte) merken; NEIN wird als Task-Typ
`gatekeeper_eval` (status='done') protokolliert; get_score_category läuft
lokal statt als Subprozess.

Faelle:
1. Zweiter Sweep ohne Aenderung → KEINE neue Log-Zeile, KEIN gatekeeper_decision-Aufruf.
2. JA-Fall → notify_hr genau EINMAL je Generation (auch bei erneuter Auswertung).
3. Aenderung der Berichte (neue task-ids) → NEUe Auswertung + neuer Marker.
4. Subprozess-Ersatz: gatekeeper_decision nutzt get_score_category_lokal,
   kein mcp_connector_call mehr (statischer Quellnachweis).

Isolation: conftest leitet data/feedback.db in einen prozesseigenen Spiegel
um — die Live-DB wird NIE beschrieben (fail-closed, Muster
tests/test_send_rejection_guard.py).

Ausfuehren: .venv-streamlit/bin/python3 -m pytest tests/test_gatekeeper_memo.py -v
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest

BASE = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "agent_runner_r6", BASE / "scripts" / "agent-runner.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

APP = 999_999          # synthetic Bewerbungs-Id (existiert nirgends echten)
KETTE = ("match_candidate", "check_compliance", "assess_culture_fit")


# ─── Isolation-Guard: nie ohne Spiegel arbeiten ──────────────────────────────

@pytest.fixture()
def conn():
    c = sqlite3.connect(str(mod.DB_PATH), timeout=10)
    # fail-closed: conftest leitet data/feedback.db in den Spiegel um — hier
    # der ECHTE Verbindungspfad nachweisen (PRAGMA database_list), nicht nur
    # den Eingabepfad (DB_PATH bleibt trotz Uleitung der Live-Pfad).
    real_file = c.execute("PRAGMA database_list").fetchone()[2]
    assert "kmhr-mirror" in real_file, f"KEIN Spiegel — Verbindung zeigt auf: {real_file}"
    try:
        yield c
    finally:
        try:
            for t in ("gatekeeper_eval", "notify_hr"):
                c.execute("DELETE FROM agent_tasks WHERE task_type = ? "
                          "AND json_extract(payload, '$.application_id') = ?",
                          (t, APP))
            c.execute("DELETE FROM agent_tasks "
                      "WHERE json_extract(payload, '$.application_id') = ?", (APP,))
            c.commit()
        finally:
            c.close()


def _add_chain(conn, gen: int = 0) -> None:
    """Drei done-Kette-Tasks fuer APP + gen anlegen (neue task-ids)."""
    for t in KETTE:
        conn.execute(
            "INSERT INTO agent_tasks (task_type, status, payload) "
            "VALUES (?, 'done', ?)",
            (t, json.dumps({"application_id": APP, "gen": gen})))
    conn.commit()


def _count(conn, task_type: str) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM agent_tasks WHERE task_type = ? "
        "AND json_extract(payload, '$.application_id') = ?",
        (task_type, APP)).fetchone()[0]


# ─── 1. Zweiter Sweep = still ────────────────────────────────────────────────

def test_zweiter_sweep_ohne_aenderung_ist_still(conn):
    _add_chain(conn)
    logs: list[str] = []
    with patch.object(mod, "gatekeeper_decision",
                      return_value=(False, 8, "Weak")) as dec, \
         patch.object(mod, "log", side_effect=logs.append):
        mod.sweep_gatekeeper(conn)
        erste = (len(logs), dec.call_count)
        assert _count(conn, "gatekeeper_eval") >= 1, "erste Bewertung ohne Marker"
        logs.clear(); dec.reset_mock()
        # ZWEITER Sweep, unveraenderte Berichte:
        mod.sweep_gatekeeper(conn)
        zweite = (len(logs), dec.call_count)
    assert erste[1] >= 1, "erster Sweep muss mindestens die eigene Kette bewerten"
    assert zweite == (0, 0), (
        f"zweiter Sweep ohne Aenderung war NICHT still: "
        f"Log-Zeilen={zweite[0]}, gatekeeper_decision={zweite[1]}")


# ─── 2. JA-Fall: notify_hr genau einmal je Generation ───────────────────────

def test_ja_queued_notify_hr_genau_einmal(conn):
    _add_chain(conn)
    with patch.object(mod, "gatekeeper_decision",
                      return_value=(True, 75, "Strong")), \
         patch.object(mod, "log", side_effect=lambda m: None):
        mod.sweep_gatekeeper(conn)
        assert _count(conn, "notify_hr") == 1, "erster JA-Sweep queued notify_hr"
        # Signatur unveraendert → stiller Return, kein zweites notify_hr:
        mod.sweep_gatekeeper(conn)
        assert _count(conn, "notify_hr") == 1, "zweiter Sweep doppelte JA-Mail!"
        # Signatur geaendert (neue Berichts-ids, gleiche gen):
        _add_chain(conn)
        mod.sweep_gatekeeper(conn)
        assert _count(conn, "notify_hr") == 1, \
            "erneuter JA in GLEICHER Generation darf notify_hr nicht verdoppeln"
        assert _count(conn, "gatekeeper_eval") == 2, \
            "neue Signatur muss neu bewertet und protokolliert worden sein"


# ─── 3. Berichtsaenderung loest NEUBEWERTUNG aus ─────────────────────────────

def test_berichtsaenderung_loest_neubewertung_aus(conn):
    _add_chain(conn)
    logs: list[str] = []
    with patch.object(mod, "gatekeeper_decision",
                      return_value=(False, 8, "Weak")) as dec, \
         patch.object(mod, "log", side_effect=logs.append):
        mod.sweep_gatekeeper(conn)
        assert dec.call_count >= 1
        dec.reset_mock(); logs.clear()
        _add_chain(conn)          # neue task-ids → neue Signatur
        mod.sweep_gatekeeper(conn)
        assert dec.call_count >= 1, "neue Berichts-Ids wurden NICHT neu bewertet"
        assert any("Pförtner-Regel" in m for m in logs), \
            "keine Pförtner-Log-Zeile trotz neuer Auswertung"
        assert _count(conn, "gatekeeper_eval") == 2, "zweiter Marker fehlt"


# ─── 4. Subprozess-Ersatz (statischer Quellnachweis) ─────────────────────────

def test_gatekeeper_decision_nutzt_lokale_kategorie():
    src = inspect.getsource(mod.gatekeeper_decision)
    assert "get_score_category_lokal" in src, \
        "gatekeeper_decision nutzt nicht logic.get_score_category_lokal"
    assert "mcp_connector_call" not in src, \
        "gatekeeper_decision ruft weiterhin den hr-benchmark-Subprozess"


def test_kategorie_lokal_gleich_connector():
    """M-16-Fix: gleiche Werte wie hr-benchmark-server (80/60-Schwellen)."""
    from webui.logic import get_score_category_lokal
    assert get_score_category_lokal(85) == "Strong"
    assert get_score_category_lokal(70) == "Consider"
    assert get_score_category_lokal(8) == "Weak"
