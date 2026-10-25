"""Fehlversuch-Transparenz im Modellpfad (22.10.2026, Auftrag „jeden
Fehlversuch mit Grund loggen, auch dort, wo heute ein stilles break steht").

`scripts/agent-runner.py::_llm_complete` hatte drei stille Stellen:
  1. HTTP 200, aber leere Antwort — nur last_error, kein Log-Eintrag,
  2. HTTP != 200/503 -> break OHNE Log (Beleg: HTTP 410 von
     moonshotai/kimi-k3 am 22.10.2026 war im Runner-Log nicht auffindbar,
     nur im Task-Fehler von Bewerbung #42),
  3. Exception -> break OHNE Log.

Isolation: requests.post gemockt (KEIN Netz), Backoff-Sleep ausgeschaltet —
die volle Modellkette (3 Modelle x 3 Versuche) laeuft in Millisekunden.
"""
import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "agent-runner.py"


def _load_runner():
    """Runner per importlib laden (Muster tests/test_compliance_writer.py)."""
    spec = importlib.util.spec_from_file_location("agent_runner_llm_log_unit", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Resp:
    """Minimaler requests.Response-Ersatz (nur status_code/text/json)."""

    def __init__(self, status_code: int, text: str = "", content: str | None = None):
        self.status_code = status_code
        self.text = text
        self._content = content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def _kette(mod, antworten):
    """Zaehlt die POST-Aufrufe; liefert dieselbe Antwort, bis `antworten`
    erschoepft ist (danach die letzte — die Kette laeuft sonst ins Leere)."""
    calls = {"n": 0}

    def _post(*args, **kwargs):
        i = calls["n"]
        calls["n"] += 1
        a = antworten[i] if i < len(antworten) else antworten[-1]
        return _Resp(*a)

    return calls, _post


def _run(mod, _post):
    with patch.object(mod.requests, "post", _post), \
            patch.dict(os.environ, {"NVIDIA_API_KEY": "test-key-notig"}), \
            patch.object(mod.time, "sleep", lambda *_: None):
        return mod._llm_complete("Test-Prompt")


# ─── 1) HTTP-Fehler (frueher stilles break) ────────────────────────────────

def test_http_410_wird_mit_status_geloggt(capsys):
    """Vorfall 22.10.2026: HTTP 410 landete nur im Task-Fehler."""
    mod = _load_runner()
    calls, _post = _kette(mod, [(410, '{"title":"Gone","detail":"model retired"}')])

    with pytest.raises(RuntimeError, match="Alle Modelle fehlgeschlagen"):
        _run(mod, _post)

    out = capsys.readouterr().out
    assert "HTTP 410 von" in out, f"HTTP-Status fehlt im Log: {out[-400:]!r}"
    assert "model retired" in out, "Body-Ausschnitt fehlt im Log"
    assert "Versuch 1/3" in out
    # HTTP-Fehler bricht den Versuch pro Modell ab (Design: „nächstes Modell")
    # => 1 Aufruf je Modell, die KETTE laeuft durch alle 3 Modelle:
    assert calls["n"] == 3, f"Modellkette brach ab: {calls['n']} Aufrufe"
    for _m in ("nemotron-3-super-120b", "lightning-30b", "kimi-k3"):
        assert _m in out, f"Modell {_m} ohne Fehlversuch-Logzeile"


def test_http_410_erste_model_hilft_der_kette_aus(capsys):
    """Fehlschlag Modell 1 (410) -> Modell 2 antwortet: Log zeigt beides."""
    mod = _load_runner()
    calls, _post = _kette(mod, [
        (410, '{"title":"Gone"}'),
        (200, "", "Profil extrahiert."),
    ])

    text = _run(mod, _post)

    out = capsys.readouterr().out
    assert "HTTP 410 von" in out
    assert "✅ Erfolg mit" in out
    assert text == "Profil extrahiert."
    assert calls["n"] == 2, "Kette muss nach dem Erfolg stoppen"


# ─── 2) Leere Antwort (frueher still) ──────────────────────────────────────

def test_leere_antwort_wird_geloggt(capsys):
    mod = _load_runner()
    calls, _post = _kette(mod, [(200, "", "")])

    with pytest.raises(RuntimeError, match="Alle Modelle fehlgeschlagen"):
        _run(mod, _post)

    out = capsys.readouterr().out
    assert "Leere Antwort von" in out, f"leere Antwort fehlt im Log: {out[-400:]!r}"
    assert "HTTP 200" in out
    assert calls["n"] == 9


# ─── 3) Exception (frueher stilles break) ──────────────────────────────────

def test_exception_wird_mit_typ_geloggt(capsys):
    mod = _load_runner()

    def _post_boom(*args, **kwargs):
        raise ConnectionError("Verbindungsabbruch zum NIM-Endpoint")

    with pytest.raises(RuntimeError, match="Alle Modelle fehlgeschlagen"):
        _run(mod, _post_boom)

    out = capsys.readouterr().out
    assert "ConnectionError bei" in out, f"Exception fehlt im Log: {out[-400:]!r}"
    assert "Verbindungsabbruch zum NIM-Endpoint" in out


# ─── 4) Regression: Erfolgspfad unveraendert ───────────────────────────────

def test_erfolg_loggt_modell_und_gibt_text():
    mod = _load_runner()
    calls, _post = _kette(mod, [(200, "", "Antwort des Agenten")])

    assert _run(mod, _post) == "Antwort des Agenten"
    assert calls["n"] == 1, "erstes Modell reicht -> kein Fallback-Aufruf"
