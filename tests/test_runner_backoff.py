"""Retry mit Backoff und Jitter (30.10.2026), Spec `knowledge/system/agent-automation.md` §3.2.

Belegt:
  * Wartezeiten 60 s und 300 s (plus Jitter bis 20 %) nach Versuch 1 und 2.
  * `claim_task` und `fetch_pending` nehmen nur fällige Tasks.
  * Neue Verbindung (Neustart) verschiebt den Versuch nicht nach vorn.
  * Nach MAX_ATTEMPTS (3) Status `failed`, danach kein Wiederholen (keine Endlosschleife).

Die Uhr ist über `mod._utc_now` injizierbar; die Queue liegt in einer
temporären SQLite-Datei (Live-DB bleibt unberührt).
"""
from __future__ import annotations

import importlib.util
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from webui import db

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "agent_runner_backoff", ROOT / "scripts" / "agent-runner.py")
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

T0 = datetime(2026, 10, 30, 12, 0, 0)


@pytest.fixture
def queue(tmp_path, monkeypatch):
    path = tmp_path / "feedback.db"
    monkeypatch.setattr(db, "AGENT_TASKS_DB", path)
    db.init_agent_tasks_table()
    clock = {"now": T0}
    monkeypatch.setattr(mod, "_utc_now", lambda: clock["now"])
    conn = sqlite3.connect(str(path))
    conn.row_factory = None
    yield conn, clock, path
    conn.close()


def _task(conn) -> int:
    cur = conn.execute(
        "INSERT INTO agent_tasks (task_type, payload) VALUES ('send_confirmation', '{}')")
    conn.commit()
    return cur.lastrowid


def _attempt_fail(conn, clock, tid, at: datetime) -> str:
    clock["now"] = at
    assert mod.claim_task(conn, tid) is True
    return mod.finish_task(conn, tid, ok=False, error="SMTP nicht erreichbar")


def _next_attempt(conn, tid) -> datetime:
    raw = conn.execute("SELECT next_attempt_at FROM agent_tasks WHERE id = ?",
                       (tid,)).fetchone()[0]
    return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")


def test_wartezeiten_mit_jitter_im_erwarteten_bereich():
    for _ in range(200):
        assert 60 <= mod.retry_delay_seconds(1) <= 72
        assert 300 <= mod.retry_delay_seconds(2) <= 360
        assert 900 <= mod.retry_delay_seconds(3) <= 1080


def test_fehlschlag_setzt_naechsten_versuch_und_sperrt_bis_faellig(queue):
    conn, clock, _ = queue
    tid = _task(conn)
    status = _attempt_fail(conn, clock, tid, T0)
    assert status == "pending"
    due = _next_attempt(conn, tid)
    assert T0 + timedelta(seconds=60) <= due <= T0 + timedelta(seconds=72)

    clock["now"] = T0 + timedelta(seconds=30)
    assert mod.fetch_pending(conn) == []
    assert mod.claim_task(conn, tid) is False

    clock["now"] = due + timedelta(seconds=1)
    assert [r[0] for r in mod.fetch_pending(conn)] == [tid]


def test_neustart_verschiebt_versuch_nicht_nach_vorn(queue):
    conn, clock, path = queue
    tid = _task(conn)
    _attempt_fail(conn, clock, tid, T0)
    conn.close()

    neu = sqlite3.connect(str(path))
    try:
        clock["now"] = T0 + timedelta(seconds=30)
        assert mod.fetch_pending(neu) == []
        assert mod.claim_task(neu, tid) is False
    finally:
        neu.close()


def test_nach_drei_versuchen_failed_ohne_endlosschleife(queue):
    conn, clock, _ = queue
    tid = _task(conn)
    t = T0
    assert _attempt_fail(conn, clock, tid, t) == "pending"
    t = _next_attempt(conn, tid) + timedelta(seconds=1)
    assert _attempt_fail(conn, clock, tid, t) == "pending"
    t = _next_attempt(conn, tid) + timedelta(seconds=1)
    assert _attempt_fail(conn, clock, tid, t) == "failed"

    status = conn.execute("SELECT status, attempts FROM agent_tasks WHERE id = ?",
                          (tid,)).fetchone()
    assert status == ("failed", 3)

    clock["now"] = t + timedelta(days=30)
    assert mod.fetch_pending(conn) == []
    assert mod.claim_task(conn, tid) is False


def test_erfolg_ist_kein_backoff(queue):
    conn, clock, _ = queue
    tid = _task(conn)
    clock["now"] = T0
    assert mod.claim_task(conn, tid) is True
    assert mod.finish_task(conn, tid, ok=True, result={"status": "sent"}) == "done"
    status = conn.execute("SELECT status FROM agent_tasks WHERE id = ?", (tid,)).fetchone()[0]
    assert status == "done"
