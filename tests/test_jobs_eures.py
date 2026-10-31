"""EURES-Adapter: Mapping, NUTS-Nullwerte, Länderabdeckung (ohne Netz)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

_spec_agent = importlib.util.spec_from_file_location("jobs_agent", SCRIPTS / "jobs_agent.py")
_agent = importlib.util.module_from_spec(_spec_agent)
sys.modules["jobs_agent"] = _agent
_spec_agent.loader.exec_module(_agent)

_spec = importlib.util.spec_from_file_location("jobs_eures", SCRIPTS / "jobs_eures.py")
eu = importlib.util.module_from_spec(_spec)
sys.modules["jobs_eures"] = eu
_spec.loader.exec_module(eu)

TREFFER = {
    "id": "MTM1MjAtMDA2ODQ3MTAwNy1T",
    "title": "Pflegefachkraft (m/w/d)",
    "description": "Visum und Anerkennung werden unterstuetzt. " * 20,
    "employer": {"name": "Alloheim Senioren-Residenzen SE"},
    "locationMap": {"DE": ["DE717"]},
}


def test_eures_job_mappt_felder():
    job = eu.eures_job(TREFFER, "de")
    assert job.title == "Pflegefachkraft (m/w/d)"
    assert job.employer == "Alloheim Senioren-Residenzen SE"
    assert job.country == "DE"
    assert "jv-details" in job.url and "MTM1MjAtMDA2ODQ3MTAwNy1T" in job.url


def test_location_map_mit_none_wird_toleriert():
    t = dict(TREFFER, locationMap={"DE": [None, "DE717"]})
    assert eu.eures_job(t, "de").location == "DE717"


def test_location_map_leer_faellt_auf_land():
    t = dict(TREFFER, locationMap={})
    assert eu.eures_job(t, "de").location == "DE"


def test_suchkonfiguration_deckt_drei_laender_und_vier_branchen():
    laender = {land for land, _, _ in eu.SUCHEN}
    branchen = {b for _, b, _ in eu.SUCHEN}
    assert laender == {"de", "fr", "ch"}
    assert branchen == {"Krankenpflege", "LKW", "Handwerk", "Hotellerie"}


def test_endpunkt_ist_oeffentlich():
    assert eu.URL.startswith("https://europa.eu/")
    assert "jv-search" in eu.URL
