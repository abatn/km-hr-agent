"""Alternative Kanäle des Werbe-Agenten (ohne Meta). Dry-Run, keine Netzwerkaufrufe.

Beleg: Der Agent erreicht beide Zielgruppen über Suchanzeigen (Google Ads, Microsoft
Advertising), ohne dass Meta konfiguriert ist. Die Schutzregeln bleiben gleich.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "tests" / "fixtures" / "seed.db"
_spec = importlib.util.spec_from_file_location("ads_agent_ch", ROOT / "scripts" / "ads_agent.py")
ads = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ads)  # type: ignore[union-attr]


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for var in ("KMHR_ADS_CHANNELS", "KMHR_ADS_APPROVAL_FILE", "KMHR_ADS_DAILY_CAP_EUR"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def approved(tmp_path, monkeypatch):
    f = tmp_path / "approval.json"
    f.write_text(json.dumps({"campaigns": {"employers_eu": 3.0, "candidates_north_africa": 2.0}}))
    monkeypatch.setenv("KMHR_ADS_DAILY_CAP_EUR", "5")
    monkeypatch.setenv("KMHR_ADS_APPROVAL_FILE", str(f))
    return f


def _run(tmp_path, **kw):
    return ads.run_once(date(2026, 10, 28), SEED, out_dir=tmp_path,
                        dmp_path=tmp_path / "dmp.jsonl", **kw)


def test_standardkanaele_ohne_meta():
    assert ads.DEFAULT_CHANNELS == ["google_ads", "microsoft_ads"]
    assert "meta_ads" not in ads.DEFAULT_CHANNELS


def test_lauf_ohne_meta_nutzt_nur_suchkanaele(tmp_path, approved):
    result = _run(tmp_path)
    assert result["channels"] == ["google_ads", "microsoft_ads"]
    for c in result["campaigns"]:
        assert set(c["platform_payloads"]) <= {"google_ads", "microsoft_ads"}
        assert "meta_ads" not in c["platform_payloads"]
        assert "graph.facebook.com" not in json.dumps(c["platform_payloads"])


def test_zielgruppe_nordafrika_erreicht_ueber_suche(tmp_path, approved):
    result = _run(tmp_path)
    camp = {c["campaign_key"]: c for c in result["campaigns"]}["candidates_north_africa"]
    g = camp["platform_payloads"]["google_ads"]
    geo = set(g["geo_targets"])
    assert {"geoTargetConstants/2504", "geoTargetConstants/2012",
            "geoTargetConstants/2788", "geoTargetConstants/2818"} <= geo  # MA, DZ, TN, EG
    assert {"languageConstants/1002", "languageConstants/1019"} <= set(g["languages"])  # FR, AR
    ms = camp["platform_payloads"]["microsoft_ads"]
    assert set(ms["body"]["Campaigns"][0]["GeoTargets"]) >= {"MA", "DZ", "TN", "EG"}


def test_arbeitgeber_eu_ueber_suche(tmp_path, approved):
    result = _run(tmp_path)
    camp = {c["campaign_key"]: c for c in result["campaigns"]}["employers_eu"]
    g = camp["platform_payloads"]["google_ads"]
    assert {"geoTargetConstants/2276", "geoTargetConstants/2250", "geoTargetConstants/2756"} <= set(g["geo_targets"])


def test_alle_suchkampagnen_paused_und_kein_geld(tmp_path, approved):
    result = _run(tmp_path)
    for c in result["campaigns"]:
        g = c["platform_payloads"]["google_ads"]
        op = g["campaign"]["json"]["operations"][0]["create"]
        assert op["status"] == "PAUSED"
        assert op["advertisingChannelType"] == "SEARCH"
        assert op["networkSettings"]["targetSearchNetwork"] is False
        ms_op = c["platform_payloads"]["microsoft_ads"]["body"]["Campaigns"][0]
        assert ms_op["Status"] == "Paused"
        assert ms_op["DailyBudget"] <= result["cap_eur"]
    assert result["planned_budget_eur"] <= 5.0


def test_google_budget_in_micros(tmp_path, approved):
    result = _run(tmp_path)
    camp = {c["campaign_key"]: c for c in result["campaigns"]}["employers_eu"]
    op = camp["platform_payloads"]["google_ads"]["budget"]["json"]["operations"][0]["create"]
    assert op["amountMicros"] == str(int(3.0 * 1_000_000))


def test_suchanzeigen_laengen_und_pflichtteile(tmp_path, approved):
    result = _run(tmp_path)
    assets = result["search_assets"]
    assert len(assets) == 8
    for a in assets:
        assert len(a["headline"]) <= 30
        assert len(a["description"]) <= 90
        assert a["final_url"] == ads.SITE
        ads.check_search_asset({k: a[k] for k in ("headline", "description")})


def test_suchanzeige_zu_lang_wird_blockiert():
    with pytest.raises(ads.AdsError, match="zu lang"):
        ads.check_search_asset({"headline": "x" * 31, "description": "KI-Hinweis"})
    with pytest.raises(ads.AdsError, match="zu lang"):
        ads.check_search_asset({"headline": "Ok", "description": "x" * 91})


def test_unbekannter_kanal_wird_abgelehnt(monkeypatch):
    monkeypatch.setenv("KMHR_ADS_CHANNELS", "google_ads,tiktok")
    with pytest.raises(ads.AdsError, match="Unbekannte Kanäle"):
        ads.selected_channels()


def test_meta_nur_als_opt_in(tmp_path, approved, monkeypatch):
    monkeypatch.setenv("KMHR_ADS_CHANNELS", "google_ads,meta_ads")
    result = _run(tmp_path)
    assert result["channels"] == ["google_ads", "meta_ads"]
    for c in result["campaigns"]:
        assert "microsoft_ads" not in c["platform_payloads"]
        assert set(c["platform_payloads"]) <= {"google_ads", "meta_ads"}


def test_regeln_bleiben_bei_kanalwechsel(tmp_path, monkeypatch):
    """Cap 0 und fehlende Freigabe blockieren auch über Suchkanäle."""
    result = _run(tmp_path)
    assert result["planned_budget_eur"] == 0
    assert all(c["status"] == "blocked" for c in result["campaigns"])
    for c in result["campaigns"]:
        op = c["platform_payloads"]["google_ads"]["campaign"]["json"]["operations"][0]["create"]
        assert op["status"] == "PAUSED"


def test_dmp_enthaelt_keine_kanal_personen(tmp_path, approved):
    dmp = tmp_path / "dmp.jsonl"
    ads.run_once(date(2026, 10, 28), SEED, out_dir=tmp_path, dmp_path=dmp)
    for line in dmp.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        assert set(row) == {"date", "signal", "value"}
