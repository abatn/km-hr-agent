"""P4 (05.10.2026): Offizieller MCP-Client (`mcp.ClientSession`, stdio).

Spec: knowledge/system/event-loop-blockieren.md §Phase 4.

Nachweis:
  1. Integration: echte Subprozesse (hr-benchmark / salary-data /
     prescreen-config) liefern nicht-leere dicts mit plausiblen Werten.
  2. Event-Loop-Kern: der SYNCHRONE `_mcp_connector_call` aus einer laufenden
     Event-Loop darf NICHT `RuntimeError: asyncio.run() cannot be called from
     a running event loop` werfen (Thread-Offload via `_run_coro_blocking`).
  3. DRY-RUN-Guard `KMHR_MCP_DRY_RUN=1` → `{}` OHNE Subprozess (Monkeypatch-
     Nachweis: `_run_coro_blocking` wird nicht betreten).
  4. Fehlerpfad: nicht existierende Serverdatei → `{}`.
"""
import asyncio

from webui import logic


# ─── 1. Integration (echte stdio-Subprozesse) ───────────────────────────────

def test_hr_benchmark_get_score_category():
    r = logic._mcp_connector_call(
        logic.HR_BENCHMARK_SERVER, "get_score_category", {"score": 85})
    assert isinstance(r, dict) and r
    assert r.get("score") == 85
    assert r.get("category") == "Strong"


def test_salary_data_tolerance():
    r = logic._mcp_connector_call(
        logic.SALARY_DATA_SERVER, "calculate_salary_tolerance", {"midpoint": 50000})
    assert isinstance(r, dict) and r
    assert r.get("tolerance_min") == 42500.0
    assert r.get("tolerance_percent") == 0.15


def test_prescreen_config_optimal_duration():
    r = logic._mcp_connector_call(
        logic.PRESCREEN_CONFIG_SERVER, "get_optimal_duration", {})
    assert isinstance(r, dict) and r


# ─── 2. Event-Loop-Kern (P4) ───────────────────────────────────────────────

def test_sync_call_aus_laufender_event_loop():
    async def _wrapper():
        # Der sync-Aufruf erfolgt INNERHALB einer laufenden Event-Loop.
        # Ohne Thread-Offload → RuntimeError aus asyncio.run.
        return logic._mcp_connector_call(
            logic.HR_BENCHMARK_SERVER, "get_score_category", {"score": 55})

    r = asyncio.run(_wrapper())
    assert isinstance(r, dict) and r
    assert r.get("category") == "Weak"


# ─── 3. DRY-RUN-Guard (kein Subprozess) ────────────────────────────────────

def test_dry_run_guard_ohne_subprozess(monkeypatch):
    monkeypatch.setenv("KMHR_MCP_DRY_RUN", "1")

    def _darf_nicht_aufgerufen_werden(*a, **k):
        raise AssertionError("DRY-RUN-Guard griff nicht — Subprozess gestartet")

    monkeypatch.setattr(logic, "_run_coro_blocking", _darf_nicht_aufgerufen_werden)
    r = logic._mcp_connector_call(
        logic.HR_BENCHMARK_SERVER, "get_score_category", {"score": 85})
    assert r == {}


# ─── 4. Fehlerpfad ─────────────────────────────────────────────────────────

def test_fehlende_serverdatei_liefert_leeres_dict():
    r = logic._mcp_connector_call(
        logic.BASE_DIR / "connectors" / "gibt-es-nicht.py", "x", {})
    assert r == {}
