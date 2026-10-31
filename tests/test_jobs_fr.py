"""France-Travail-Adapter: Feld-Mapping, Token-URL, harte Grenze ohne Credentials."""
from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

_spec_agent = importlib.util.spec_from_file_location("jobs_agent", SCRIPTS / "jobs_agent.py")
_agent = importlib.util.module_from_spec(_spec_agent)
sys.modules["jobs_agent"] = _agent
_spec_agent.loader.exec_module(_agent)

_spec_fr = importlib.util.spec_from_file_location("jobs_fr", SCRIPTS / "jobs_fr.py")
fr = importlib.util.module_from_spec(_spec_fr)
sys.modules["jobs_fr"] = fr
_spec_fr.loader.exec_module(fr)


def test_token_url_mit_realm():
    assert "realm=%2Fpartenaire" in fr.TOKEN_URL
    assert fr.TOKEN_URL.startswith("https://entreprise.francetravail.fr/")


def test_scope_enthaelt_offres_v2():
    assert "api_offresdemploiv2" in fr.SCOPE
    assert "o2dsoffre" in fr.SCOPE


def test_fr_job_mappt_felder():
    t = {
        "id": "207CNDJ",
        "intitule": "Infirmier (H/F)",
        "entreprise": {"nom": "Clinique Lyon"},
        "lieuTravail": {"libelle": "69 - Lyon"},
        "origineOffre": {"urlOrigine": "https://candidat.francetravail.fr/offres/recherche/detail/207CNDJ"},
        "contact": {"courriel": "RH@Clinique.fr"},
    }
    job = fr.fr_job(t)
    assert job.title == "Infirmier (H/F)"
    assert job.employer == "Clinique Lyon"
    assert job.location == "69 - Lyon"
    assert job.country == "FR"
    assert job.contact_email == "rh@clinique.fr"
    assert "francetravail.fr" in job.url


def test_fr_job_fallback_url_aus_id():
    t = {"id": "ABC123", "intitule": "Cuisinier"}
    job = fr.fr_job(t)
    assert job.url.endswith("/ABC123")


def test_ohne_credentials_exit_3(monkeypatch):
    monkeypatch.delenv("FT_CLIENT_ID", raising=False)
    monkeypatch.delenv("FT_CLIENT_SECRET", raising=False)
    assert fr.run(Namespace(max_jobs=1, min_jobs=1, per_query=1, min_score=40, mock=False)) == 3


def test_suchkonfiguration_deckt_vier_branchen():
    branchen = {b for b, _ in fr.SUCHEN}
    assert branchen == {"Krankenpflege", "LKW", "Handwerk", "Hotellerie"}
