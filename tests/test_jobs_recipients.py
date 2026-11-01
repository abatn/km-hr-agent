"""Empfängerliste: Quellen-Mapping, Priorisierung, Mock-Ausschluss."""
from __future__ import annotations

import importlib.util
import pytest
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

_spec_agent = importlib.util.spec_from_file_location("jobs_agent", SCRIPTS / "jobs_agent.py")
_agent = importlib.util.module_from_spec(_spec_agent)
sys.modules["jobs_agent"] = _agent
_spec_agent.loader.exec_module(_agent)

_spec = importlib.util.spec_from_file_location("jobs_recipients", SCRIPTS / "jobs_recipients.py")
rec = importlib.util.module_from_spec(_spec)
sys.modules["jobs_recipients"] = rec
_spec.loader.exec_module(rec)


def test_quellen_mapping():
    assert rec._quelle(Path("x/2026-10-31-eures-fr/index.md")) == "EURES"
    assert rec._quelle(Path("x/2026-10-31-lhr/index.md")) == "LHR"
    assert rec._quelle(Path("x/2026-10-31-jdp/index.md")) == "Journal des Palaces"
    assert rec._quelle(Path("x/2026-10-31-ch/index.md")) == "Job-Room"
    assert rec._quelle(Path("x/2026-10-31/index.md")) == "Bundesagentur"


def test_sammle_liefert_priorisierte_zeilen():
    rows = rec.sammle()
    if not rows:
        pytest.skip("keine Belege im Checkout (gitignored)")
    assert len(rows) >= 20
    for r in rows:
        assert r["prioritaet"] in (1, 2)
        if r["prioritaet"] == 1:
            assert "@" in r["email"]
        else:
            assert r["email"] == ""


def test_keine_mock_eintraege():
    rows = rec.sammle()
    assert not any(r["arbeitgeber"].upper().startswith("MOCK") for r in rows)
    assert not any("mock" in r["email"].lower() for r in rows if r["email"])


def test_dedupe_pro_arbeitgeber_und_mail():
    rows = rec.sammle()
    keys = [(r["arbeitgeber"].lower(), r["email"]) for r in rows]
    assert len(keys) == len(set(keys))


def test_csv_hat_kopfzeile(tmp_path, monkeypatch):
    ziel = tmp_path / "emp.csv"
    monkeypatch.setattr(rec, "CSV", ziel)
    rec.schreibe_csv(rec.sammle())
    kopf = ziel.read_text(encoding="utf-8").splitlines()[0]
    assert kopf.startswith("prioritaet,arbeitgeber,stelle")
