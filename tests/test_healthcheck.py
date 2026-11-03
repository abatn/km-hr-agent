"""Uptime-Check (02.11.2026): reine Bewertung + Alarm-Dedupe.

Kein Netzwerk: `evaluate_health` und `should_alert` sind reine Funktionen.
"""
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "healthcheck_mod", _ROOT / "scripts" / "healthcheck.py")
hc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hc)


def _ok_payload():
    return {"status": "ok", "db": {"ok": True},
            "runner": {"alive": True}, "audit": {"ok": True}}


def test_gesund():
    ok, reasons = hc.evaluate_health(200, _ok_payload())
    assert ok is True
    assert reasons == []


def test_http_503_ist_alarm():
    ok, reasons = hc.evaluate_health(503, {"status": "error", "db": {"ok": False}})
    assert ok is False
    assert "HTTP 503" in reasons


def test_degraded_ist_alarm():
    p = _ok_payload()
    p["status"] = "degraded"
    p["runner"] = {"alive": False}
    ok, reasons = hc.evaluate_health(200, p)
    assert ok is False
    assert any("status=degraded" in r for r in reasons)
    assert "runner.alive=false" in reasons


def test_audit_gebrochen_ist_alarm():
    p = _ok_payload()
    p["audit"] = {"ok": False}
    ok, reasons = hc.evaluate_health(200, p)
    assert ok is False
    assert "audit.ok=false" in reasons


def test_kein_json_objekt_ist_alarm():
    ok, reasons = hc.evaluate_health(200, None)
    assert ok is False
    assert "Antwort ist kein JSON-Objekt" in reasons


def test_dedupe_erster_alarm():
    assert hc.should_alert(1000.0, {}, ok=False, repeat=1800) is True


def test_dedupe_kein_zweiter_alarm_innerhalb_repeat():
    state = {"last_ok": False, "last_alert_ts": 1000.0}
    assert hc.should_alert(1100.0, state, ok=False, repeat=1800) is False


def test_dedupe_nach_repeat_wieder_alarm():
    state = {"last_ok": False, "last_alert_ts": 1000.0}
    assert hc.should_alert(2800.0, state, ok=False, repeat=1800) is True


def test_gesund_loest_keinen_alarm_aus():
    assert hc.should_alert(1000.0, {"last_ok": False}, ok=True, repeat=1800) is False
