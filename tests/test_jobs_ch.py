"""Job-Room-Adapter (CH): Parsing, Sprachwahl, HTML-Bereinigung (ohne Netz)."""
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

_spec_ch = importlib.util.spec_from_file_location("jobs_ch", SCRIPTS / "jobs_ch.py")
ch = importlib.util.module_from_spec(_spec_ch)
sys.modules["jobs_ch"] = ch
_spec_ch.loader.exec_module(ch)

EINTRAG = {"jobAdvertisement": {
    "id": "abc-123",
    "jobContent": {
        "externalUrl": "https://example.org/job/1",
        "jobDescriptions": [
            {"languageIsoCode": "fr", "title": "Infirmier (H/F)", "description": "Poste en français"},
            {"languageIsoCode": "de", "title": "<em>Pflegefachfrau</em> HF", "description": "<p>Wir suchen</p>"},
        ],
        "company": {"name": "Stiftung Zion", "city": "Zürich", "email": "jobs@zion.ch"},
        "location": {"city": "Zürich", "cantonCode": "ZH"},
        "applyChannel": {"emailAddress": "bewerbung@zion.ch"},
    },
}}


def test_ch_job_mappt_felder():
    job = ch.ch_job(EINTRAG)
    assert job.employer == "Stiftung Zion"
    assert job.location == "Zürich"
    assert job.country == "CH"
    assert job.url == "https://example.org/job/1"


def test_ch_job_bevorzugt_deutschen_titel_und_entfernt_html():
    job = ch.ch_job(EINTRAG)
    assert job.title == "Pflegefachfrau HF"
    assert "<em>" not in job.title


def test_ch_job_nimmt_firmenmail_vor_applychannel():
    job = ch.ch_job(EINTRAG)
    assert job.contact_email == "jobs@zion.ch"


def test_ch_job_fallback_applychannel():
    e = {"jobAdvertisement": {"id": "x", "jobContent": {
        "externalUrl": "https://example.org/2",
        "jobDescriptions": [{"languageIsoCode": "de", "title": "Koch", "description": "Text " * 50}],
        "company": {"name": "Gurten", "city": "Bern"},
        "location": {"city": "Bern"},
        "applyChannel": {"emailAddress": "hr@gurten.ch"},
    }}}
    assert ch.ch_job(e).contact_email == "hr@gurten.ch"


def test_clean_entfernt_tags():
    assert ch._clean("<p>Hallo <b>Welt</b></p>") == "Hallo Welt"


def test_suchkonfiguration_deckt_vier_branchen():
    branchen = {b for b, _ in ch.SUCHEN}
    assert branchen == {"Krankenpflege", "LKW", "Handwerk", "Hotellerie"}


def test_endpunkt_ist_job_room():
    assert "job-room.ch" in ch.ROOM_URL
    assert "_search" in ch.ROOM_URL
