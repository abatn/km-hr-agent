"""Journal des Palaces RSS: Mapping, Feed-URL, Filter (ohne Netz)."""
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

_spec = importlib.util.spec_from_file_location("jobs_jdp", SCRIPTS / "jobs_jdp.py")
jdp = importlib.util.module_from_spec(_spec)
sys.modules["jobs_jdp"] = jdp
_spec.loader.exec_module(jdp)

EINTRAG = {
    "title": "Hôtel Metropole Monte-Carlo recrute Commis de bar",
    "contract": "CDD",
    "society": "Hôtel Metropole Monte-Carlo",
    "locality": "Monte Carlo",
    "country": "Monaco",
    "link": "https://www.journaldespalaces.com/carriere/offre-1.html",
    "date": "Sat, 31 Oct 2026 05:25:28 +0100",
}


def test_jdp_job_mappt_felder():
    job = jdp.jdp_job(EINTRAG)
    assert job.title.startswith("Hôtel Metropole")
    assert job.employer == "Hôtel Metropole Monte-Carlo"
    assert job.location == "Monte Carlo"
    assert job.country == "FR"
    assert job.industry == "Hotellerie"


def test_feed_url_ist_offen():
    assert jdp.FEED.startswith("https://www.journaldespalaces.com/")
    assert jdp.FEED.endswith(".xml")


def test_rss_parser_liest_items(monkeypatch):
    xml = b"""<?xml version="1.0"?><rss><channel>
    <item><title>T</title><contract-type>CDI</contract-type><society>S</society>
    <locality>L</locality><country-name>France</country-name>
    <link>https://x/1</link><pubDate>Sat, 31 Oct 2026 05:25:28 +0100</pubDate></item>
    </channel></rss>"""
    class _R:
        def read(self): return xml
        def __enter__(self): return self
        def __exit__(self, *a): return False
    monkeypatch.setattr(jdp.urllib.request, "urlopen", lambda *a, **k: _R())
    items = jdp.feed()
    assert len(items) == 1
    assert items[0]["country"] == "France"
    assert items[0]["society"] == "S"
