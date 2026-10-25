"""Runner-Persistenz: ehrlicher Status statt Erfolgsversprechen (E1, 21.10.2026).

Hypothese (Teil 0): „logs/agent-errors.log meldet wiederkehrend ‚gatekeeper_eval-Nachweis-UPDATE
fehlgeschlagen (Schema ohne Spalten?): no such column: started_at' ⇒ der Runner persistiert
nicht mehr."

**Ergebnis der Verifikation:** Die 540 Logtreffer stammen **ausschließlich** aus
pytest-Läufen gegen ein bewusst minimales `:memory:`-Schema
(`tests/test_r32_gatekeeper_gen.py::def _mem()`), **0** Treffer im Produktivbetrieb
(VPS-Log). Live-DB, Seed-DB und VPS-DB besitzen `started_at` (11 Spalten, identisch).

Der echte Befund: `handle_errors` meldete `{"logged": True}`, obwohl beide Schreibvorgänge
per `except: pass` verschluckt wurden (**Erfolgsversprechen**). Dieser Test sichert ab:
(1) der Nachweis-UPDATE meldet keinen Erfolg bei fehlenden Spalten,
(2) `handle_errors` meldet den **echten** Status,
(3) `claim_task`/`finish_task` brechen den Runner bei Schema-Lücken **nicht** ab.
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _runner():
    spec = importlib.util.spec_from_file_location("runner_persist", ROOT / "scripts" / "agent-runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_logdatei_zeigt_nicht_in_das_produktionslog():
    """V-17 (21.10.2026): der Runner schreibt im Testlauf NICHT nach
    `logs/agent-errors.log` (Umleitung über `KMHR_LOG_FILE`, tests/conftest.py)."""
    mod = _runner()
    produktionslog = (ROOT / "logs" / "agent-errors.log").resolve()
    assert mod.LOG_FILE.resolve() != produktionslog, (
        f"Runner-Log zeigt auf das Produktionslog: {mod.LOG_FILE}")
    assert "kmhr-testlog-" in str(mod.LOG_FILE), str(mod.LOG_FILE)


def test_db_pfad_von_runner_und_webui_ist_der_gleiche(tmp_path, monkeypatch):
    """V-18 (21.10.2026): Runner und WebUI oeffnen **dieselbe** DB-Datei
    (beide respektieren `KMHR_DB_PATH`)."""
    ziel = tmp_path / "fremde.db"
    monkeypatch.setenv("KMHR_DB_PATH", str(ziel))
    mod = _runner()
    assert mod.DB_PATH == ziel

    # webui/db.py frisch laden, damit die Konstante den Override sieht.
    spec = importlib.util.spec_from_file_location("webdb_pfad", ROOT / "webui" / "db.py")
    webdb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(webdb)
    assert webdb.DB_PATH == ziel
    assert webdb.AGENT_TASKS_DB == ziel
    assert mod.DB_PATH == webdb.DB_PATH


def test_claim_task_eskaliert_nach_maximalen_versuchen():
    """L1 (V-02): `claim_task` markiert den Task nach `MAX_ATTEMPTS` als 'failed'
    — kein stilles Endlos-Retry alle 60 s."""
    mod = _runner()
    conn = sqlite3.connect(":memory:")
    _ohne_started_at(conn)  # `started_at` fehlt ⇒ das UPDATE schlägt fehl
    conn.execute("""INSERT INTO agent_tasks (task_type, status, payload)
                    VALUES ('gatekeeper_eval', 'pending', '{}')""")
    conn.commit()
    for _ in range(mod.MAX_ATTEMPTS - 1):
        assert mod.claim_task(conn, 1) is False
        status = conn.execute("SELECT status FROM agent_tasks WHERE id = 1").fetchone()[0]
        assert status == "pending", status
    # Der MAX_ATTEMPTS-te Versuch eskaliert.
    assert mod.claim_task(conn, 1) is False
    status, attempts = conn.execute(
        "SELECT status, attempts FROM agent_tasks WHERE id = 1").fetchone()
    conn.close()
    assert status == "failed", status
    assert attempts >= mod.MAX_ATTEMPTS, (attempts, mod.MAX_ATTEMPTS)


def test_claim_task_eskaliert_auch_im_extremschema():
    """L1 (V-02): auch ohne `attempts`/`error_text` endet der Task als 'failed'
    (Notnagel) — er darf nicht endlos pending bleiben."""
    mod = _runner()
    conn = sqlite3.connect(":memory:")
    _minimal(conn)
    conn.execute("""INSERT INTO agent_tasks (task_type, status, payload)
                    VALUES ('gatekeeper_eval', 'pending', '{}')""")
    conn.commit()
    assert mod.claim_task(conn, 1) is False
    status = conn.execute("SELECT status FROM agent_tasks WHERE id = 1").fetchone()[0]
    conn.close()
    assert status == "failed", status


def test_finish_task_meldet_erfolg_nur_bei_committed_update():
    """L1 (V-01): `finish_task` liefert den **Status-String** der Datenbank."""
    mod = _runner()
    conn = sqlite3.connect(":memory:")
    _voll(conn)
    conn.execute("""INSERT INTO agent_tasks (task_type, status, payload)
                    VALUES ('gatekeeper_eval', 'running', '{}')""")
    conn.commit()
    assert mod.finish_task(conn, 1, True, result={"a": 1}) == "done"
    conn.close()

    # Minimalschema (ohne started_at/finished_at) ⇒ sqlite3.Error ⇒
    # "nicht_persistiert" (kein 'done').
    conn2 = sqlite3.connect(":memory:")
    _minimal(conn2)
    conn2.execute("""INSERT INTO agent_tasks (task_type, status, payload)
                     VALUES ('gatekeeper_eval', 'running', '{}')""")
    conn2.commit()
    assert mod.finish_task(conn2, 1, True, result={"a": 1}) == "nicht_persistiert"
    conn2.close()


def test_finish_task_behandelt_nicht_serialisierbares_ergebnis():
    """L1 (V-01): ein nicht serialisierbares `result` darf **kein** 'done' werden."""
    mod = _runner()
    conn = sqlite3.connect(":memory:")
    _voll(conn)
    conn.execute("""INSERT INTO agent_tasks (task_type, status, payload)
                    VALUES ('gatekeeper_eval', 'running', '{}')""")
    conn.commit()
    assert mod.finish_task(conn, 1, True, result={"obj": object()}) == "failed"
    status, err = conn.execute(
        "SELECT status, error_text FROM agent_tasks WHERE id = 1").fetchone()
    conn.close()
    assert status != "done", status
    assert err and "serialisierbar" in err, err


def _voll(conn) -> None:
    conn.execute("""CREATE TABLE agent_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, task_type TEXT NOT NULL,
        status TEXT DEFAULT 'pending', payload TEXT NOT NULL, result_path TEXT,
        result_json TEXT, error_text TEXT, attempts INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, started_at TIMESTAMP,
        finished_at TIMESTAMP)""")


def _minimal(conn) -> None:
    """Schema wie tests/test_r32_gatekeeper_gen.py::def _mem() (ohne started_at)."""
    conn.execute("""CREATE TABLE agent_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, task_type TEXT NOT NULL,
        status TEXT DEFAULT 'pending', payload TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")


def _ohne_started_at(conn) -> None:
    """Realistisches Alt-Schema: `attempts`/`error_text` vorhanden, `started_at` fehlt."""
    conn.execute("""CREATE TABLE agent_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, task_type TEXT NOT NULL,
        status TEXT DEFAULT 'pending', payload TEXT NOT NULL, error_text TEXT,
        attempts INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")


def test_nachweis_update_mit_vollschema_ist_erfolgreich():
    # Der Runner muss importierbar sein (Beleg: der Fehlerpfad darf nicht
    # beim Import scheitern).
    assert _runner() is not None
    conn = sqlite3.connect(":memory:")
    _voll(conn)
    conn.execute("""INSERT INTO agent_tasks (task_type, status, payload)
                    VALUES ('gatekeeper_eval', 'done', '{}')""")
    conn.commit()
    cur = conn.cursor()
    cur.execute("""UPDATE agent_tasks SET started_at = CURRENT_TIMESTAMP,
                   finished_at = CURRENT_TIMESTAMP, result_json = ?
                   WHERE id = ? AND task_type = 'gatekeeper_eval'""",
                (json.dumps({"inline": True}), 1))
    conn.commit()
    zeile = conn.execute("SELECT started_at, result_json FROM agent_tasks WHERE id = 1").fetchone()
    conn.close()
    assert zeile[0] is not None
    assert json.loads(zeile[1])["inline"] is True


def test_nachweis_update_mit_minimalschema_wirft_nicht_aus_der_funktion():
    """Der Fehlerpfad darf den Runner nicht sprengen (fehlertolerant, Design D4 13.10.2026)."""
    assert _runner() is not None
    conn = sqlite3.connect(":memory:")
    _minimal(conn)
    conn.execute("""INSERT INTO agent_tasks (task_type, status, payload)
                    VALUES ('gatekeeper_eval', 'done', '{}')""")
    conn.commit()
    cur = conn.cursor()
    with pytest.raises(sqlite3.Error):
        cur.execute("""UPDATE agent_tasks SET started_at = CURRENT_TIMESTAMP
                       WHERE id = ? AND task_type = 'gatekeeper_eval'""", (1,))
    conn.close()


def test_handle_errors_meldet_echten_status(tmp_path, monkeypatch):
    """Kein Erfolgsversprechen: `logged` ist nur True, wenn wirklich geschrieben wurde."""
    mod = _runner()
    monkeypatch.setattr(mod, "LOG_FILE", tmp_path / "logs" / "agent-errors.log")
    monkeypatch.setattr(mod, "ERGEBNISSE", tmp_path / "ergebnisse")
    ergebnis = mod.handle_errors({"typ": "TECHNISCH", "schwere": "HOCH",
                                  "skill": "test", "meldung": "Probe"})
    assert ergebnis["logged"] is True
    assert ergebnis["stats_ok"] is True
    assert ergebnis["result_path"] and Path(ergebnis["result_path"]).is_file()


def test_handle_errors_meldet_fehler_bei_unbeschreibbarem_ziel(tmp_path, monkeypatch):
    """Schreibfehler ⇒ `logged` False + Fehlertext (kein stilles `except: pass`)."""
    mod = _runner()
    monkeypatch.setattr(mod, "LOG_FILE", tmp_path / "logs" / "agent-errors.log")
    monkeypatch.setattr(mod, "ERGEBNISSE", tmp_path / "ergebnisse")
    # Ziel ist ein Verzeichnis ⇒ write_text schlägt fehl.
    # ACHTUNG: der Dateiname trägt das **heutige** Datum (Codemarke
    # `def handle_errors`) — ein festes Datum würde den Test um Mitternacht
    # (Datumswechsel) scheitern lassen (Befund 22.10.2026).
    from datetime import datetime
    zielname = f"error-statistik-{datetime.now().strftime('%Y-%m-%d')}.md"
    (tmp_path / "ergebnisse").mkdir(parents=True, exist_ok=True)
    (tmp_path / "ergebnisse" / zielname).mkdir()
    ergebnis = mod.handle_errors({"typ": "TECHNISCH", "meldung": "Probe"})
    assert ergebnis["logged"] is False
    assert ergebnis["stats_ok"] is False
    assert "error" in ergebnis


def test_claim_task_bricht_bei_schemaluecke_nicht_ab(tmp_path):
    """`claim_task` darf den Runner nicht beenden (Endlosschleife vermeiden)."""
    mod = _runner()
    conn = sqlite3.connect(":memory:")
    _minimal(conn)
    conn.execute("""INSERT INTO agent_tasks (task_type, status, payload)
                    VALUES ('x', 'pending', '{}')""")
    conn.commit()
    assert mod.claim_task(conn, 1) is False
    conn.close()


def test_finish_task_bricht_bei_schemaluecke_nicht_ab(tmp_path):
    mod = _runner()
    conn = sqlite3.connect(":memory:")
    _minimal(conn)
    conn.execute("""INSERT INTO agent_tasks (task_type, status, payload)
                    VALUES ('x', 'running', '{}')""")
    conn.commit()
    mod.finish_task(conn, 1, ok=True, result={"a": 1})  # darf nicht werfen
    conn.close()


def test_init_agent_tasks_table_ergaenzt_fehlende_spalten(tmp_path, monkeypatch):
    """Migrationsweg: `CREATE TABLE IF NOT EXISTS` ergänzt keine Spalten ⇒ ALTER nötig."""
    from webui import db
    monkeypatch.setattr(db, "AGENT_TASKS_DB", tmp_path / "feedback.db")
    conn = sqlite3.connect(str(tmp_path / "feedback.db"))
    conn.execute("""CREATE TABLE agent_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT, task_type TEXT NOT NULL,
        status TEXT DEFAULT 'pending', payload TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    conn.commit()
    conn.close()
    db.init_agent_tasks_table()
    conn = sqlite3.connect(str(tmp_path / "feedback.db"))
    spalten = {r[1] for r in conn.execute("PRAGMA table_info(agent_tasks)")}
    conn.close()
    assert {"started_at", "finished_at", "result_json"} <= spalten
