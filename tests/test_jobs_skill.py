"""Skill-Lattice: Schema, Ladepfad, harte Grenzen (ohne Netz)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

for name in ("jobs_agent", "jobs_api", "jobs_ch"):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)

_spec = importlib.util.spec_from_file_location("jobs_skill", SCRIPTS / "jobs_skill.py")
sk = importlib.util.module_from_spec(_spec)
sys.modules["jobs_skill"] = sk
_spec.loader.exec_module(sk)


def test_mindestens_fuenf_skills():
    assert len(sk.load_skills()) >= 5


def test_jeder_skill_hat_pflichtfelder():
    for sid, s in sk.load_skills().items():
        for feld in ("id", "name", "country", "source", "endpoint", "auth", "industries", "queries"):
            assert s.get(feld), f"{sid}: {feld} fehlt"
        assert s["id"] == sid


def test_alle_vier_branchen_ueber_die_lattice_abgedeckt():
    """Spezialisten (z. B. LHR nur Hotellerie) sind erlaubt; die Summe muss passen."""
    soll = {"Krankenpflege", "LKW", "Handwerk", "Hotellerie"}
    vereinigt = set()
    for s in sk.load_skills().values():
        vereinigt |= set(s["industries"])
    assert soll <= vereinigt, vereinigt


def test_unbekannter_skill_liefert_fehler():
    r = sk.probe({"id": "gibt-es-nicht", "queries": {}}, "Krankenpflege")
    assert r["ok"] is False
    assert "unbekannt" in r["error"]


def test_france_ohne_credentials(monkeypatch):
    monkeypatch.delenv("FT_CLIENT_ID", raising=False)
    monkeypatch.delenv("FT_CLIENT_SECRET", raising=False)
    fr = sk.load_skills()["france-travail-search"]
    r = sk.probe(fr, "Krankenpflege")
    assert r["ok"] is False
    assert r["error"] == "credentials fehlen"


def test_arbeitnow_ist_als_neue_quelle_registriert():
    s = sk.load_skills()["arbeitnow-search"]
    assert s["endpoint"] == "https://www.arbeitnow.com/api/job-board-api"
    assert s["auth"] == "keine"


def test_gelernte_branche_ist_persistiert():
    """Logistik wurde im Form-Designer gelernt und steht in den Skills."""
    skills = sk.load_skills()
    assert "Logistik" in skills["ba-search"]["industries"]
    assert "Logistik" in skills["jobroom-search"]["industries"]
