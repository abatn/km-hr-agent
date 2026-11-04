"""BA-Jobsuche-Adapter: Feld-Mapping, Detail-URL, Ort (ohne Netz).

Spec: knowledge/system/jobs-agent.md §Datenquellen
"""
from __future__ import annotations

import base64
import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

# jobs_agent zuerst registrieren (jobs_api importiert es als Modul)
_spec_agent = importlib.util.spec_from_file_location("jobs_agent", SCRIPTS / "jobs_agent.py")
_agent = importlib.util.module_from_spec(_spec_agent)
sys.modules["jobs_agent"] = _agent
_spec_agent.loader.exec_module(_agent)

_spec_api = importlib.util.spec_from_file_location("jobs_api", SCRIPTS / "jobs_api.py")
api = importlib.util.module_from_spec(_spec_api)
sys.modules["jobs_api"] = api
_spec_api.loader.exec_module(api)

TREFFER = {
    "stellenangebotsTitel": "Pflegefachkraft (m/w/d)",
    "firma": "Permacon GmbH",
    "referenznummer": "10001-1003940671-S",
    "stellenlokationen": [{"adresse": {"ort": "Berlin", "plz": "10115"}}],
    "beruf": "Pflegefachkraft",
}


def test_ba_job_mappt_felder():
    job = api.ba_job(TREFFER)
    assert job.title == "Pflegefachkraft (m/w/d)"
    assert job.employer == "Permacon GmbH"
    assert job.location == "Berlin"
    assert job.country == "DE"
    assert job.url.endswith("/10001-1003940671-S")
    assert "arbeitsagentur.de/jobsuche/jobdetail/" in job.url


def test_ba_job_ohne_lokation():
    t = dict(TREFFER)
    t.pop("stellenlokationen")
    assert api.ort(t) == ""


def test_ort_region_wird_ignoriert():
    """Regionalcodes (DEG03, DE252 …) sind kein Ort; lieber leer lassen."""
    t = {"stellenlokationen": [{"adresse": {"region": "DEG03"}}]}
    assert api.ort(t) == ""


def test_detail_url_base64_und_padding():
    url = api.detail_url("10001-1003940671-S")
    b64 = url.rsplit("/", 1)[-1]
    assert "%3D" in b64 or not b64.endswith("=")
    wieder = base64.b64decode(b64.replace("%3D", "=")).decode()
    assert wieder == "10001-1003940671-S"


def test_suchkonfiguration_deckt_vier_branchen_und_beide_arten():
    branchen = {b for b, _, _, _ in api.SUCHEN}
    assert branchen == {"Krankenpflege", "LKW", "Handwerk", "Hotellerie"}
    arten = {a for _, _, _, a in api.SUCHEN}
    assert arten == {"1", "4"}, "Arbeit und Ausbildung muessen abgedeckt sein"


def test_api_key_ist_der_oeffentliche_jobsuche_key():
    assert api.BA_KEY == "jobboerse-jobsuche"
    assert api.BA_BASE.startswith("https://rest.arbeitsagentur.de/")
