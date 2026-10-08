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
import asyncio
import threading
from pathlib import Path

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


# ─── (f) Option 1: Per-Key-Lock — verschiedene Keys parallel, gleicher Key
#          serialisiert (08.10.2026) ──────────────────────────────────────────
#
# Beweist, dass Session-Starts UNTERSCHIEDLICHER Server nicht durch einen
# globalen Lock gegenseitig blockieren, während DERSELBE Key serialisiert
# bleibt. Deterministisch, ohne echte Subprozesse: Fake-Handle, Dummy-Loop und
# ein Worker, der an einem expliziten Start-Gate (threading.Event) parkt.

class _FakeMcpSession:
    """Minimal-Ersatz für `logic._McpServerSession` (kein Subprozess)."""

    def __init__(self, server_py, python_path, loop):
        self.server_py = server_py
        self.python_path = python_path
        self.loop = loop
        self.queue = None
        self.ready = threading.Event()
        self.done = threading.Event()
        self.alive = True
        self.error = None
        self.tools = None


class _FakeAsyncio:
    """Ersatz für `logic.asyncio`: führt die Worker-Coroutine in eigenem
    Thread aus (der reale Event-Loop wird hier nur durch eine Attrappe
    vertreten)."""

    @staticmethod
    def run_coroutine_threadsafe(coro, loop):
        threading.Thread(target=lambda: asyncio.run(coro),
                         daemon=True).start()


def test_f_per_key_lock_parallel_starts(monkeypatch):
    monkeypatch.delenv("KMHR_MCP_SESSION", raising=False)

    starts = {"n": 0}
    starts_lock = threading.Lock()
    state = {
        "gate": threading.Event(),
        "one_started": threading.Event(),
        "two_started": threading.Event(),
    }

    async def fake_worker(handle):
        # Parkt am Start-Gate und wird erst danach „bereit" — so lässt sich
        # beobachten, wie viele Starts gleichzeitig im Lock hängen.
        with starts_lock:
            starts["n"] += 1
            n = starts["n"]
        if n >= 1:
            state["one_started"].set()
        if n >= 2:
            state["two_started"].set()
        assert state["gate"].wait(10), "Start-Gate nicht rechtzeitig gelöst"
        handle.ready.set()

    monkeypatch.setattr(logic, "_McpServerSession", _FakeMcpSession)
    monkeypatch.setattr(logic, "_get_session_loop", lambda: object())
    monkeypatch.setattr(logic, "_mcp_session_worker", fake_worker)
    monkeypatch.setattr(logic, "asyncio", _FakeAsyncio)

    logic._SESSIONS.clear()
    logic._SESSION_LOCKS.clear()

    def _start(store, key):
        try:
            store[key] = logic._get_or_start_handle(Path(key), None)
        except BaseException as ex:  # noqa: BLE001
            store[key] = ex

    # ── Teil 1: verschiedene Keys → Starts laufen parallel ─────────────────
    out = {}
    ta = threading.Thread(target=_start, args=(out, "A.py"))
    tb = threading.Thread(target=_start, args=(out, "B.py"))
    ta.start()
    tb.start()

    # Beide Worker parken am Gate, obwohl der jeweils erste Aufruf noch im
    # Per-Key-Lock steht → kein gegenseitiges Blockieren.
    assert state["two_started"].wait(10), "verschiedene Keys nicht parallel"
    assert ta.is_alive() and tb.is_alive()
    assert out == {} and not state["gate"].is_set()
    state["gate"].set()

    ta.join(10)
    tb.join(10)
    assert not ta.is_alive() and not tb.is_alive()
    assert out["A.py"] is not out["B.py"]
    assert out["A.py"].server_py == Path("A.py")
    assert out["B.py"].server_py == Path("B.py")

    # ── Teil 2: gleicher Key → serialisiert, lebende Session wiederverwendet
    logic._SESSIONS.clear()
    logic._SESSION_LOCKS.clear()
    state["gate"] = threading.Event()
    state["one_started"].clear()
    state["two_started"].clear()
    with starts_lock:
        starts["n"] = 0

    res1, res2 = {}, {}
    t1 = threading.Thread(target=_start, args=(res1, "A.py"))
    t2 = threading.Thread(target=_start, args=(res2, "A.py"))
    t1.start()
    t2.start()

    assert state["one_started"].wait(10), "kein Worker für Key A gestartet"
    # Zweiter Start darf nicht parallel laufen (gleicher Per-Key-Lock) …
    assert not state["two_started"].wait(0.5), "gleicher Key parallel gestartet"
    state["gate"].set()

    t1.join(10)
    t2.join(10)
    assert not t1.is_alive() and not t2.is_alive()
    # … und die bereits lebende Session wird statt eines Neustarts verwendet.
    assert starts["n"] == 1, "gleicher Key startete mehr als einmal"
    assert res1["A.py"] is res2["A.py"], "Session nicht wiederverwendet"
