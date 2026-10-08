"""P6.1 (05.10.2026): persistente MCP-Session + Host-Tool-Cache.

Spec: knowledge/system/mcp-tool-lazy-gating.md §Phase 6.1.
Quelle (offiziell): MCP „Client Best Practices" (abgerufen 05.10.2026) —
„Cache tool definitions … memoize the definition host-side so re-injecting
it later doesn't need another tools/list round trip" + „Dynamic Server
Management". Implementierung = Design-Entscheidung.

Nachweise:
  (a) `KMHR_MCP_SESSION=0` → ausschließlich der alte Ein-Schuss-Pfad.
  (b) Session-Pfad liefert dasselbe Ergebnisformat wie der Altpfad.
  (c) `initialize`/`list_tools`/`spawn` passieren NICHT je Aufruf
      (echter Zähler `logic._MCP_SESSION_STATS`).
  (d) Fehlerpfad: nicht existierende Serverdatei → `{}` ohne Crash.
  (e) Hintergrund-Thread ist `daemon=True`; `_close_all_sessions()` räumt
      auf, ein Folgeaufruf startet die Session lazy neu.

Keine Live-DB, kein Postgres nötig (Connector-Aufrufe berühren keine DB).
"""
from webui import logic


def _reset_stats():
    for key in logic._MCP_SESSION_STATS:
        logic._MCP_SESSION_STATS[key] = 0


# ─── (a) KMHR_MCP_SESSION=0 → Altpfad ───────────────────────────────────────

def test_a_session_disabled_uses_legacy_path(monkeypatch):
    monkeypatch.setenv("KMHR_MCP_SESSION", "0")
    seen = {}

    def _legacy_stub(coro):
        coro.close()  # nicht-awaitete Coroutine sauber schließen
        seen["legacy"] = True
        return {"__legacy__": True}

    def _session_must_not_run(*a, **k):
        raise AssertionError("Session-Pfad lief trotz KMHR_MCP_SESSION=0")

    monkeypatch.setattr(logic, "_run_coro_blocking", _legacy_stub)
    monkeypatch.setattr(logic, "_session_call_blocking", _session_must_not_run)

    r = logic._mcp_connector_call(
        logic.HR_BENCHMARK_SERVER, "get_score_category", {"score": 85})
    assert seen.get("legacy") is True
    assert r == {"__legacy__": True}


# ─── (b) gleiches Ergebnisformat wie Altpfad ────────────────────────────────

def test_b_session_matches_legacy_result(monkeypatch):
    monkeypatch.delenv("KMHR_MCP_SESSION", raising=False)
    legacy = logic._mcp_connector_call_once(
        logic.HR_BENCHMARK_SERVER, "get_score_category", {"score": 85})
    session = logic._session_call_blocking(
        logic.HR_BENCHMARK_SERVER, "get_score_category", {"score": 85})
    assert session == legacy
    assert session.get("category") == "Strong"


# ─── (c) kein initialize/list_tools/spawn je Aufruf ─────────────────────────

def test_c_initialize_and_list_tools_not_per_call(monkeypatch):
    monkeypatch.delenv("KMHR_MCP_SESSION", raising=False)
    # Session vorwärmen (erster Aufruf darf zählen)
    logic._mcp_connector_call(
        logic.HR_BENCHMARK_SERVER, "get_score_category", {"score": 10})
    _reset_stats()

    a = logic._mcp_connector_call(
        logic.HR_BENCHMARK_SERVER, "get_score_category", {"score": 20})
    after_first = dict(logic._MCP_SESSION_STATS)
    b = logic._mcp_connector_call(
        logic.HR_BENCHMARK_SERVER, "get_score_category", {"score": 30})
    after_second = dict(logic._MCP_SESSION_STATS)

    assert a.get("category") == "Weak" and b.get("category") == "Weak"
    # Warme Session: weder Subprozess-Spawn noch initialize/list_tools.
    assert after_first == {"spawn": 0, "initialize": 0, "list_tools": 0,
                           "reconnect": 0}
    assert after_second == after_first


# ─── (d) Fehlerpfad: fehlende Serverdatei → {} ──────────────────────────────

def test_d_missing_server_returns_empty(monkeypatch):
    monkeypatch.delenv("KMHR_MCP_SESSION", raising=False)
    r = logic._mcp_connector_call(
        logic.BASE_DIR / "connectors" / "gibt-es-nicht-p61.py", "x", {})
    assert r == {}


# ─── (e) daemon-Thread + Cleanup + Lazy-Restart ─────────────────────────────

def test_e_daemon_thread_cleanup_and_restart(monkeypatch):
    monkeypatch.delenv("KMHR_MCP_SESSION", raising=False)
    logic._mcp_connector_call(
        logic.HR_BENCHMARK_SERVER, "get_score_category", {"score": 50})

    assert logic._SESSION_THREAD is not None
    assert logic._SESSION_THREAD.daemon is True
    assert logic._SESSION_THREAD.name == "mcp-session-loop"

    logic._close_all_sessions()
    assert logic._SESSIONS == {}

    # Lazy-Restart funktioniert weiterhin (Thread bleibt am Leben).
    r = logic._mcp_connector_call(
        logic.HR_BENCHMARK_SERVER, "get_score_category", {"score": 70})
    assert r.get("category") == "Consider"
