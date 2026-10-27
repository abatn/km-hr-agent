"""Tests für den Ads-Agenten (scripts/ads_agent.py). Nur Dry-Run, keine Netzwerkaufrufe."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

import importlib.util

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "tests" / "fixtures" / "seed.db"
_spec = importlib.util.spec_from_file_location("ads_agent_mod", ROOT / "scripts" / "ads_agent.py")
ads = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ads)  # type: ignore[union-attr]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("KMHR_ADS_DAILY_CAP_EUR", raising=False)
    monkeypatch.delenv("KMHR_ADS_APPROVAL_FILE", raising=False)


def test_kleinzellen_schutz():
    assert ads.suppress(4) == "<5"
    assert ads.suppress(5) == 5


def test_zielgruppe_nur_aus_aggregaten():
    signals = ads.read_signals(SEED)
    segs = {s["segment"]: s for s in ads.derive_segments(signals)}
    assert set(segs) == {"employers_eu", "candidates_north_africa"}
    # Kandidaten-Nordafrika hat keinen eigenen Messwert -> None, nicht geschätzt
    assert segs["candidates_north_africa"]["audience_size"] is None
    assert "candidate" not in json.dumps(signals).lower()


def test_creatives_vier_sprachen_und_pflichtteile():
    creatives = ads.build_creatives()
    assert {(c["segment"], c["language"]) for c in creatives} == {
        (s, l) for s in ads.CREATIVES for l in ("de", "en", "fr", "ar")}
    for c in creatives:
        assert ads.SITE in c["text"]
        ads.social.assert_no_pii(c["text"])


def test_verbotene_werbeaussage_wird_blockiert():
    with pytest.raises(ads.AdsError, match="verboten"):
        ads.check_creative("Stellen garantiert in 2 Tagen. jobs.hanibal-ai.com KI-Hinweis")


def test_fehlender_ki_hinweis_wird_blockiert():
    with pytest.raises(ads.AdsError, match="Pflichtbestandteile"):
        ads.check_creative("Stellen in Europa. jobs.hanibal-ai.com")


def test_personenbezug_wird_blockiert():
    with pytest.raises(ads.social.SocialError):
        ads.check_creative("Kandidat #12 jobs.hanibal-ai.com KI-Hinweis")


def test_budget_cap_null_blockiert_alles(tmp_path):
    result = ads.run_once(date(2026, 10, 27), SEED, out_dir=tmp_path,
                          dmp_path=tmp_path / "dmp.jsonl")
    assert result["cap_eur"] == 0
    assert result["planned_budget_eur"] == 0
    assert all(c["status"] == "blocked" for c in result["campaigns"])


def test_freigabe_wirkt_nur_innerhalb_cap(tmp_path, monkeypatch):
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({"campaigns": {"employers_eu": 3.0, "candidates_north_africa": 3.0}}))
    monkeypatch.setenv("KMHR_ADS_DAILY_CAP_EUR", "2")
    monkeypatch.setenv("KMHR_ADS_APPROVAL_FILE", str(approval))
    result = ads.run_once(date(2026, 10, 27), SEED, out_dir=tmp_path,
                          dmp_path=tmp_path / "dmp.jsonl")
    assert result["planned_budget_eur"] <= 2.0
    assert all(c["daily_budget_eur"] <= 2.0 for c in result["campaigns"])
    ready = [c for c in result["campaigns"] if c["status"] == "paused_ready"]
    blocked = [c for c in result["campaigns"] if c["status"] == "blocked"]
    assert len(ready) == 1 and ready[0]["daily_budget_eur"] == 2.0
    assert len(blocked) == 1 and "Tages-Cap" in blocked[0]["reason"]


def test_ohne_freigabe_trotz_cap_blockiert(tmp_path, monkeypatch):
    monkeypatch.setenv("KMHR_ADS_DAILY_CAP_EUR", "10")
    result = ads.run_once(date(2026, 10, 27), SEED, out_dir=tmp_path,
                          dmp_path=tmp_path / "dmp.jsonl")
    assert result["planned_budget_eur"] == 0
    assert all("keine Freigabe" in c["reason"] for c in result["campaigns"])


def test_gebot_nie_ueber_obergrenze(tmp_path):
    result = ads.run_once(date(2026, 10, 27), SEED, out_dir=tmp_path,
                          dmp_path=tmp_path / "dmp.jsonl")
    for c in result["campaigns"]:
        sim = c["bid_simulation"]
        assert sim["simulated"] is True
        assert sim["bid_cpm_eur"] <= sim["max_cpm_eur"]


def test_targeting_beschaeftigungsregeln_immer(tmp_path):
    for seg in ads.SEGMENTS:
        t = ads.targeting_for(seg)
        assert (t["age_min"], t["age_max"], t["genders"]) == (18, 65, "all")
        assert t["lookalikes"] is False and t["zip_codes"] == [] and t["exclusions"] == []


def test_meta_payload_nur_per_opt_in_und_paused(tmp_path, monkeypatch):
    monkeypatch.setenv("KMHR_ADS_DAILY_CAP_EUR", "0")
    monkeypatch.setenv("KMHR_ADS_CHANNELS", "meta_ads")
    result = ads.run_once(date(2026, 10, 27), SEED, out_dir=tmp_path,
                          dmp_path=tmp_path / "dmp.jsonl")
    for c in result["campaigns"]:
        assert "meta_ads" in result["channels"]
        for payload in c["platform_payloads"].values():
            if "special_ad_categories" in payload.get("data", {}):
                assert payload["data"]["status"] == "PAUSED"
                assert payload["data"]["special_ad_categories"] == ["EMPLOYMENT"]


def test_live_ist_gesperrt(tmp_path):
    with pytest.raises(ads.AdsError, match="nicht implementiert"):
        ads.run_once(date(2026, 10, 27), SEED, live=True, out_dir=tmp_path,
                     dmp_path=tmp_path / "dmp.jsonl")


def test_dmp_enthaelt_nur_aggregate(tmp_path):
    dmp = tmp_path / "dmp.jsonl"
    ads.run_once(date(2026, 10, 27), SEED, out_dir=tmp_path, dmp_path=dmp)
    rows = [json.loads(l) for l in dmp.read_text(encoding="utf-8").splitlines()]
    assert rows, "DMP leer"
    for row in rows:
        assert set(row) == {"date", "signal", "value"}
        assert not any(k in row["signal"] for k in ("candidate_id", "application_id", "_id", "#"))
        assert isinstance(row["value"], (int, str))


def test_lauf_schreibt_run_json(tmp_path):
    ads.run_once(date(2026, 10, 27), SEED, out_dir=tmp_path, dmp_path=tmp_path / "dmp.jsonl")
    run = json.loads((tmp_path / "2026-10-27" / "run.json").read_text(encoding="utf-8"))
    assert run["mode"] == "dry_run"
    assert len(run["creatives"]) == 8
    assert len(run["campaigns"]) == 2
