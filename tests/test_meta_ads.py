"""Meta-Marketing-API-Pfad (scripts/meta_ads.py) ohne Netz: Fake-Transport.

Belegt: Vorabprüfung nennt Blocker im Klartext, Anlage ist immer PAUSED mit
Beschäftigungskategorie, Budget in Cent, keine Geschlechter-/PLZ-Ziele,
Aktivierung nur bestätigt, Token erscheint nie in Fehlern. Video-Ads laden über
`act_<id>/advideos` hoch und erzeugen `video_data` (kein `link_data`).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("meta_ads_mod", ROOT / "scripts" / "meta_ads.py")
meta = importlib.util.module_from_spec(_spec)
sys.modules["meta_ads_mod"] = meta  # noetig fuer @dataclass
_spec.loader.exec_module(meta)  # type: ignore[union-attr]


TOKEN = "test-token-not-real"


class FakeTransport:
    def __init__(self, responses: dict[str, dict], status: int = 200):
        self.responses = responses
        self.status = status
        self.calls: list[dict] = []

    def request(self, method, url, params, data=None):
        path = url.split("/v26.0/", 1)[-1]
        self.calls.append({"method": method, "path": path, "url": url,
                           "params": dict(params), "data": dict(data or {})})
        for suffix in sorted(self.responses, key=len, reverse=True):
            if path.startswith(suffix) or path == suffix:
                return self.status, self.responses[suffix]
        return 404, {"error": {"message": f"kein Fake für {path}"}}

    def upload(self, url, params, file_path):
        path = url.split("/v26.0/", 1)[-1]
        self.calls.append({"method": "UPLOAD", "path": path, "url": url,
                           "params": dict(params), "data": {},
                           "file": str(file_path)})
        for suffix in sorted(self.responses, key=len, reverse=True):
            if path.startswith(suffix) or path == suffix:
                return self.status, self.responses[suffix]
        return 404, {"error": {"message": f"kein Fake für {path}"}}

    def find(self, path_fragment: str, method: str = "POST") -> list[dict]:
        return [c for c in self.calls
                if method == c["method"] and c["path"].endswith(path_fragment)]


def _cfg(**kw) -> "meta.MetaConfig":
    base = dict(ad_account_id="act_123", token=TOKEN, page_id="999",
                version="v26.0", currency="EUR",
                dsa_beneficiary="Hanibal AI", dsa_payor="Hanibal AI")
    base.update(kw)
    return meta.MetaConfig(**base)


def _preflight_ok() -> dict[str, dict]:
    return {
        "me": {"id": "42", "name": "Admin"},
        "me/permissions": {"data": [
            {"permission": "ads_management", "status": "granted"},
            {"permission": "ads_read", "status": "granted"},
            {"permission": "pages_read_engagement", "status": "granted"},
        ]},
        "act_123": {"id": "act_123", "name": "KMHR", "account_status": 1,
                    "currency": "EUR", "amount_spent": "0", "spend_cap": "0",
                    "funding_source_details": {"id": "1", "type": "VISA"}},
        "999": {"id": "999", "name": "KMHR Seite"},
    }


def test_preflight_ohne_konfiguration_nennt_fehlende_keys():
    client = meta.MetaAdsClient(meta.MetaConfig(), transport=FakeTransport({}))
    report = client.preflight()
    assert report["ok"] is False
    joined = " ".join(report["blockers"])
    assert "META_AD_ACCOUNT_ID" in joined and "META_ADS_ACCESS_TOKEN" in joined
    assert report["next_steps"]


def test_preflight_gruen_mit_zahlungsmittel_und_seite():
    client = meta.MetaAdsClient(_cfg(), transport=FakeTransport(_preflight_ok()))
    report = client.preflight()
    assert report["ok"] is True, report["blockers"]
    assert report["account"]["status"] == "ACTIVE"
    assert report["account"]["funding_source"] is True
    assert report["permissions"]["ads_management"] == "granted"


def test_preflight_blockiert_ohne_zahlungsmittel():
    responses = _preflight_ok()
    responses["act_123"] = {**responses["act_123"], "funding_source_details": None}
    report = meta.MetaAdsClient(_cfg(), transport=FakeTransport(responses)).preflight()
    assert report["ok"] is False
    assert any("Zahlungsmittel" in b for b in report["blockers"])


def test_preflight_blockiert_fremde_waehrung():
    responses = _preflight_ok()
    responses["act_123"] = {**responses["act_123"], "currency": "USD"}
    report = meta.MetaAdsClient(_cfg(), transport=FakeTransport(responses)).preflight()
    assert any("USD" in b for b in report["blockers"])


def test_preflight_fehlt_dsa_blockiert_eu():
    report = meta.MetaAdsClient(_cfg(dsa_beneficiary="", dsa_payor=""),
                                transport=FakeTransport(_preflight_ok())).preflight()
    assert any("DSA" in b for b in report["blockers"])


def _campaign() -> dict:
    return {"campaign_key": "candidates_north_africa", "daily_budget_eur": 3.0,
            "targeting": {"countries": ["MA", "DZ"], "age_min": 18, "age_max": 65,
                          "genders": "all", "lookalikes": False,
                          "exclusions": [], "zip_codes": []},
            "link": "https://jobs.hanibal-ai.com",
            "headline": "Jobs in Europa",
            "creative": "Stellen in Europa. jobs.hanibal-ai.com KI-Hinweis"}


def test_launch_legt_alles_paused_und_beschaeftigungskategorie_an():
    responses = {
        "act_123/campaigns": {"id": "c1"},
        "act_123/adsets": {"id": "s1"},
        "act_123/adcreatives": {"id": "cr1"},
        "act_123/ads": {"id": "a1"},
        "act_123": {"amount_spent": "0", "spend_cap": "0", "currency": "EUR"},
    }
    transport = FakeTransport(responses)
    result = meta.MetaAdsClient(_cfg(), transport=transport).launch(
        _campaign(), "2026-10-29", "fr")
    assert result["status"] == "paused_created"
    assert (result["campaign_id"], result["adset_id"], result["ad_id"]) == ("c1", "s1", "a1")

    camp = transport.find("campaigns")[0]["data"]
    assert camp["status"] == "PAUSED"
    assert json.loads(camp["special_ad_categories"]) == ["EMPLOYMENT"]
    assert camp["objective"] == meta.OBJECTIVE

    adset = transport.find("adsets")[0]["data"]
    assert adset["status"] == "PAUSED"
    assert adset["daily_budget"] == "300"
    targeting = json.loads(adset["targeting"])
    assert targeting["geo_locations"]["countries"] == ["MA", "DZ"]
    assert (targeting["age_min"], targeting["age_max"]) == (18, 65)
    assert "genders" not in targeting
    assert targeting["targeting_automation"]["advantage_audience"] == 0

    creative = transport.find("adcreatives")[0]["data"]
    story = json.loads(creative["object_story_spec"])
    assert story["page_id"] == "999"
    assert story["link_data"]["link"] == "https://jobs.hanibal-ai.com"

    ad = transport.find("ads")[0]["data"]
    assert ad["status"] == "PAUSED"
    assert ad["dsa_beneficiary"] == "Hanibal AI"
    assert ad["dsa_payor"] == "Hanibal AI"


def _video_responses(video_id: str = "vid1") -> dict[str, dict]:
    return {
        "act_123/advideos": {"id": video_id},
        "act_123/adimages": {"images": {"thumb.jpg": {"hash": "hash1"}}},
        "act_123/campaigns": {"id": "c1"},
        "act_123/adsets": {"id": "s1"},
        "act_123/adcreatives": {"id": "cr1"},
        "act_123/ads": {"id": "a1"},
        "act_123": {"amount_spent": "0", "spend_cap": "0", "currency": "EUR"},
    }


def test_video_url_erzeugt_video_data_creative_und_bleibt_paused():
    transport = FakeTransport(_video_responses())
    cfg = _cfg(video_url="https://cdn.example/reel.mp4",
               video_thumbnail_url="https://cdn.example/thumb.jpg")
    result = meta.MetaAdsClient(cfg, transport=transport).launch(
        _campaign(), "2026-10-29", "fr")

    assert result["status"] == "paused_created"
    assert result["creative_type"] == "video"
    assert result["video_id"] == "vid1"

    upload = transport.find("act_123/advideos")[0]
    assert upload["data"]["file_url"] == "https://cdn.example/reel.mp4"
    assert upload["url"].startswith("https://graph-video.facebook.com/v26.0/")

    creative = json.loads(transport.find("act_123/adcreatives")[0]["data"]["object_story_spec"])
    assert "video_data" in creative
    assert "link_data" not in creative
    video = creative["video_data"]
    assert video["video_id"] == "vid1"
    assert video["message"] == _campaign()["creative"]
    assert video["link_description"] == "jobs.hanibal-ai.com"
    assert video["call_to_action"]["value"]["link"] == "https://jobs.hanibal-ai.com"
    assert video["image_url"] == "https://cdn.example/thumb.jpg"

    camp = transport.find("act_123/campaigns")[0]["data"]
    assert camp["status"] == "PAUSED"
    assert json.loads(camp["special_ad_categories"]) == ["EMPLOYMENT"]
    # Meta 2026: Pflichtfeld bei AdSet-Budget (kein Kampagnenbudget).
    assert camp["is_adset_budget_sharing_enabled"] == "false"
    # Sonderkategorie-Länder müssen die Targeting-Länder enthalten.
    assert json.loads(camp["special_ad_category_country"]) == ["MA", "DZ"]
    adset = transport.find("act_123/adsets")[0]["data"]
    assert adset["status"] == "PAUSED"
    ad = transport.find("act_123/ads")[0]["data"]
    assert ad["status"] == "PAUSED"
    assert ad["dsa_beneficiary"] == "Hanibal AI"
    assert ad["dsa_payor"] == "Hanibal AI"


def test_lokale_video_datei_wird_multipart_hochgeladen(tmp_path):
    video = tmp_path / "reel.mp4"
    video.write_bytes(b"fake-mp4")
    thumb = tmp_path / "thumb.jpg"
    thumb.write_bytes(b"fake-jpg")
    transport = FakeTransport(_video_responses("vid2"))
    cfg = _cfg(video_path=str(video), video_thumbnail_path=str(thumb))
    result = meta.MetaAdsClient(cfg, transport=transport).launch(
        _campaign(), "2026-10-29", "fr")

    assert result["video_id"] == "vid2"
    upload = transport.find("act_123/advideos", "UPLOAD")[0]
    assert upload["file"] == str(video)
    assert upload["params"]["access_token"] == TOKEN
    assert upload["url"].startswith("https://graph-video.facebook.com/v26.0/")
    image_upload = transport.find("act_123/adimages", "UPLOAD")[0]
    assert image_upload["file"] == str(thumb)
    creative = json.loads(transport.find("act_123/adcreatives")[0]["data"]["object_story_spec"])
    assert creative["video_data"]["video_id"] == "vid2"
    assert creative["video_data"]["image_hash"] == "hash1"


def test_video_id_aus_config_ueberspringt_upload():
    transport = FakeTransport(_video_responses())
    result = meta.MetaAdsClient(
        _cfg(video_id="vid9", video_thumbnail_url="https://cdn.example/thumb.jpg"),
        transport=transport).launch(
        _campaign(), "2026-10-29", "fr")

    assert result["video_id"] == "vid9"
    assert transport.find("act_123/advideos") == []
    creative = json.loads(transport.find("act_123/adcreatives")[0]["data"]["object_story_spec"])
    assert creative["video_data"]["video_id"] == "vid9"


def test_ohne_video_bleibt_link_data_creative():
    transport = FakeTransport(_video_responses())
    result = meta.MetaAdsClient(_cfg(), transport=transport).launch(
        _campaign(), "2026-10-29", "fr")

    assert result["creative_type"] == "link"
    assert result["video_id"] is None
    creative = json.loads(transport.find("act_123/adcreatives")[0]["data"]["object_story_spec"])
    assert "link_data" in creative
    assert "video_data" not in creative
    assert transport.find("act_123/advideos") == []


def test_video_ohne_thumbnail_blockiert_vor_kampagne():
    transport = FakeTransport(_video_responses())
    with pytest.raises(meta.MetaAdsError, match="Miniaturbild"):
        meta.MetaAdsClient(
            _cfg(video_url="https://cdn.example/reel.mp4"),
            transport=transport).launch(_campaign(), "2026-10-29")
    assert transport.find("act_123/campaigns") == []


def test_video_upload_fehler_verhindert_kampagne():
    transport = FakeTransport({
        "act_123/advideos": {"error": {"message": "video rejected", "code": 1}},
        "act_123": {"amount_spent": "0", "spend_cap": "0", "currency": "EUR"},
    })
    with pytest.raises(meta.MetaAdsError, match="advideos"):
        meta.MetaAdsClient(
            _cfg(video_url="https://cdn.example/bad.mp4",
                 video_thumbnail_url="https://cdn.example/thumb.jpg"),
            transport=transport).launch(_campaign(), "2026-10-29")
    assert transport.find("act_123/campaigns") == []


def test_preflight_warnung_ohne_video_und_blocker_bei_fehlender_datei(tmp_path):
    report = meta.MetaAdsClient(_cfg(), transport=FakeTransport(_preflight_ok())).preflight()
    assert report["ok"] is True
    assert report["video"]["creative_type"] == "link"
    assert any("Kein Video" in w for w in report["warnings"])

    missing = tmp_path / "fehlt.mp4"
    blocked = meta.MetaAdsClient(
        _cfg(video_path=str(missing),
             video_thumbnail_path=str(tmp_path / "fehlt.jpg")),
        transport=FakeTransport(_preflight_ok())).preflight()
    assert blocked["ok"] is False
    assert any("META_VIDEO_PATH" in b for b in blocked["blockers"])

    no_thumb = meta.MetaAdsClient(
        _cfg(video_id="vid1"), transport=FakeTransport(_preflight_ok())).preflight()
    assert no_thumb["ok"] is False
    assert any("Miniaturbild" in b for b in no_thumb["blockers"])


def test_launch_verweigert_budget_null():
    with pytest.raises(meta.MetaAdsError, match="Budget 0"):
        meta.MetaAdsClient(_cfg(), transport=FakeTransport({})).launch(
            {**_campaign(), "daily_budget_eur": 0}, "2026-10-29")


def test_launch_verweigert_konto_cap_ueberschreitung():
    responses = {"act_123": {"amount_spent": "4900", "spend_cap": "5000",
                             "currency": "EUR"}}
    client = meta.MetaAdsClient(_cfg(), transport=FakeTransport(responses))
    with pytest.raises(meta.MetaAdsError, match="Spend-Cap"):
        client.launch(_campaign(), "2026-10-29")


def test_aktivieren_braucht_bestaetigung():
    client = meta.MetaAdsClient(_cfg(), transport=FakeTransport({}))
    with pytest.raises(meta.MetaAdsError, match="Bestätigung"):
        client.activate({"campaign_id": "c1", "adset_id": "s1", "ad_id": "a1"})


def test_aktivieren_setzt_kampagne_adset_ad():
    transport = FakeTransport({"c1": {"success": True}, "s1": {"success": True},
                               "a1": {"success": True}})
    result = meta.MetaAdsClient(_cfg(), transport=transport).activate(
        {"campaign_id": "c1", "adset_id": "s1", "ad_id": "a1"}, confirm=True)
    assert result["status"] == "active"
    assert len(transport.find("c1")) == 1 and len(transport.find("a1")) == 1
    assert all(c["data"]["status"] == "ACTIVE" for c in transport.calls)


def test_token_erscheint_nicht_in_fehlermeldung():
    transport = FakeTransport(
        {"act_123": {"error": {"message": f"bad token {TOKEN}", "code": 190}}})
    client = meta.MetaAdsClient(_cfg(), transport=transport)
    with pytest.raises(meta.MetaAdsError) as exc:
        client.get("act_123", fields="currency")
    assert TOKEN not in str(exc.value)
    assert "<TOKEN>" in str(exc.value)
