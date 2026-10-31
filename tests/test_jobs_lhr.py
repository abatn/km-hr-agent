"""LHR-Adapter: Karten-Parsing, Métier-Liste, JSON-LD-Auswertung (ohne Netz)."""
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

_spec = importlib.util.spec_from_file_location("jobs_lhr", SCRIPTS / "jobs_lhr.py")
lhr = importlib.util.module_from_spec(_spec)
sys.modules["jobs_lhr"] = lhr
_spec.loader.exec_module(lhr)

HTML = """
<a href="/emploi/9ecc9963/restaurant-ortensia-paris/7e3d954f"
   class="d-block list-group-item job-item flex-column" id="1688898">
  <div><h3 class="mb-1">Cuisinier H/F</h3></div>
  <p class="location"><i class="icon-map"></i>75 - PARIS 16</p>
  <small class="date">Posté le 31/10/2026</small>
</a>
"""


def test_liste_parst_karte(monkeypatch):
    monkeypatch.setattr(lhr, "_get", lambda url, timeout=30: HTML)
    karten = lhr.liste("cuisinier")
    assert len(karten) == 1
    k = karten[0]
    assert k["title"] == "Cuisinier H/F"
    assert k["location"] == "75 - PARIS 16"
    assert k["date"] == "Posté le 31/10/2026"
    assert k["href"].startswith("/emploi/")


def test_metiers_decken_hotellerie():
    metiers = {m for _, m in lhr.METIERS}
    assert {"cuisinier", "serveur", "chef-de-partie"} <= metiers
    assert all(b == "Hotellerie" for b, _ in lhr.METIERS)


def test_base_ist_lhr():
    assert lhr.BASE == "https://www.lhotellerie-restauration.fr"


def test_detail_ohne_jsonld_liefert_leer(monkeypatch):
    monkeypatch.setattr(lhr, "_get", lambda url, timeout=30: "<html>kein ld+json</html>")
    assert lhr.detail("/emploi/x/y/z") == {}
