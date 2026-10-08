"""Plan A (08.10.2026): Warm-up der MCP-Sessions beim App-Start.

Spec: knowledge/system/mcp-tool-lazy-gating.md §Warm-up der MCP-Sessions.
Der erste Match-Render öffnete die MCP-Sessions synchron im Event-Loop
(Lag-Monitor: 2,97 s Block). `warm_mcp_connectors()` startet dafür einen
Daemon-Thread. Rollback: Env `KMHR_MCP_WARMUP=0`.

Nachweise:
  (1) `_warm_mcp_connectors_blocking()` ruft `_mcp_connector_call` genau 3×
      (die 3 `_MCP_WARMUP_JOBS`).
  (2) Fehler werden geschluckt (kein Raise).
  (3) `KMHR_MCP_WARMUP=0` → `warm_mcp_connectors()` liefert None, kein Thread.
  (4) ohne Env → Thread-Objekt; `thread.join(5)` beendet.

Keine Live-DB, kein Netz nötig (`_mcp_connector_call` wird gestubbt).
"""
from webui import logic


def test_1_blocking_warms_exactly_three_jobs(monkeypatch):
    calls = []

    def _recorder(server_py, tool, args, python_path=None):
        calls.append((server_py, tool, args))
        return {"__warm__": True}

    monkeypatch.setattr(logic, "_mcp_connector_call", _recorder)

    out = logic._warm_mcp_connectors_blocking()

    assert len(calls) == 3
    assert len(out) == 3
    pairs = [(server_py, tool) for server_py, tool, _ in calls]
    assert (logic.HR_BENCHMARK_SERVER, "get_score_category") in pairs
    assert (logic.SALARY_DATA_SERVER, "calculate_salary_tolerance") in pairs
    assert (logic.PRESCREEN_CONFIG_SERVER, "get_optimal_duration") in pairs
    assert sorted(pairs) == sorted([
        (srv, tool) for srv, tool, _ in logic._MCP_WARMUP_JOBS
    ])


def test_2_errors_are_swallowed(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("connector down")

    monkeypatch.setattr(logic, "_mcp_connector_call", _boom)

    out = logic._warm_mcp_connectors_blocking()

    assert out == [None, None, None]


def test_3_env_rollback_returns_none_without_thread(monkeypatch):
    monkeypatch.setenv("KMHR_MCP_WARMUP", "0")

    def _no_thread(*a, **k):
        raise AssertionError("Thread trotz KMHR_MCP_WARMUP=0 gestartet")

    monkeypatch.setattr(logic.threading, "Thread", _no_thread)

    assert logic.warm_mcp_connectors() is None


def test_4_returns_thread_and_join_finishes(monkeypatch):
    monkeypatch.delenv("KMHR_MCP_WARMUP", raising=False)

    def _fast(server_py, tool, args, python_path=None):
        return {}

    monkeypatch.setattr(logic, "_mcp_connector_call", _fast)

    th = logic.warm_mcp_connectors()

    assert th is not None
    th.join(5)
    assert not th.is_alive()
