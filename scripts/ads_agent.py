"""Ads-Agent (Werbe-Komponente, DSP/DMP-ähnlich). Standard: Dry-Run, Budget 0.

Wahrnehmen -> Planen -> Handeln (simuliert) -> Beobachten.
Entscheidung und Grenzen: marketing/ADS_ENTSCHEIDUNG.md.

- Nur Aggregate (social_agent.read_aggregates); keine Personen-, Kandidaten- oder Payload-Daten.
- DMP = Aggregat-Tabelle `ergebnisse/ads/dmp_signals.jsonl` (Kleinzellen < 5 werden unterdrückt).
- Budget: Cap standardmäßig 0; Freigabedatei nötig; Kampagnen immer PAUSED.
- Gebot: simuliert mit Design-Annahmen, nach oben begrenzt, nie selbst erhöht.
- Live (`--live`) nur für Meta/Facebook, nur mit `KMHR_ADS_LIVE_CONFIRM=1`,
  Cap > 0 und Freigabe. Anlegen immer PAUSED; Aktivieren separat mit `--activate`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sqlite3
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "ergebnisse" / "ads"
DMP_FILE = OUT_DIR / "dmp_signals.jsonl"
SMALL_CELL = 5
SITE = "https://jobs.hanibal-ai.com"

_spec = importlib.util.spec_from_file_location("social_agent_ads", ROOT / "scripts" / "social_agent.py")
social = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(social)  # type: ignore[union-attr]

_x402_spec = importlib.util.spec_from_file_location("ads_x402", ROOT / "scripts" / "ads_x402.py")
ads_x402 = importlib.util.module_from_spec(_x402_spec)
sys.modules["ads_x402"] = ads_x402  # noetig fuer @dataclass in ads_x402
_x402_spec.loader.exec_module(ads_x402)  # type: ignore[union-attr]

_meta_spec = importlib.util.spec_from_file_location("meta_ads", ROOT / "scripts" / "meta_ads.py")
meta_ads = importlib.util.module_from_spec(_meta_spec)
sys.modules["meta_ads"] = meta_ads
_meta_spec.loader.exec_module(meta_ads)  # type: ignore[union-attr]

FORBIDDEN_CLAIMS = ("garantiert", "dsgvo-konform", "100 %", "100%", "kostenlos",
                    "visum garantiert", "sofort eingestellt", "guaranteed", "garanti",
                    "gratuit", "مضمون")
DE_COUNTRIES = {"DE", "FR", "CH", "Deutschland", "Frankreich", "Schweiz"}

# Kanäle: Suchanzeigen (Google Ads, Microsoft Advertising) sind Default; Meta nur per Opt-in.
CHANNELS: dict[str, dict[str, Any]] = {
    "google_ads": {"label": "Google Ads (Search)", "default": True},
    "microsoft_ads": {"label": "Microsoft Advertising (Bing Search)", "default": True},
    "meta_ads": {"label": "Meta Ads (Opt-in, Beschäftigungskategorie)", "default": False},
}
DEFAULT_CHANNELS = [k for k, v in CHANNELS.items() if v["default"]]

SEGMENTS: dict[str, dict[str, Any]] = {
    "employers_eu": {
        "label": "Arbeitgeber DE/FR/CH",
        "platforms": ["google_ads", "microsoft_ads"],
        "max_cpm_eur": 15.0,
        # Design-Annahme, nicht gemessen (siehe ADS_ENTSCHEIDUNG.md Punkt 6)
        "assumed_cpm_eur": 12.0,
    },
    "candidates_north_africa": {
        "label": "Kandidaten Nordafrika",
        "platforms": ["google_ads", "microsoft_ads"],
        "max_cpm_eur": 4.0,
        "assumed_cpm_eur": 2.5,
    },
}

SEARCH_ASSETS: dict[str, dict[str, dict[str, str]]] = {
    "employers_eu": {
        "de": {"headline": "Fachkräfte aus Nordafrika",
               "description": "Für Arbeitgeber in der EU. Der Mensch entscheidet. KI-Hinweis: KI-gestützt."},
        "en": {"headline": "Skilled North African talent",
               "description": "For employers in the EU. Humans make the decisions. AI note: AI-assisted."},
        "fr": {"headline": "Talents d'Afrique du Nord",
               "description": "Pour employeurs de l'UE. L'humain décide. Note IA : assisté par IA."},
        "ar": {"headline": "كفاءات من شمال أفريقيا",
               "description": "لأصحاب العمل في الاتحاد الأوروبي. القرار للإنسان. ملاحظة: بدعم من الذكاء الاصطناعي."},
    },
    "candidates_north_africa": {
        "de": {"headline": "Jobs in Europa",
               "description": "Stellen für Fachkräfte aus Nordafrika. Der Mensch entscheidet. KI-Hinweis: KI-gestützt."},
        "en": {"headline": "Jobs in Europe",
               "description": "Jobs for North African talent. Humans make the decisions. AI note: AI-assisted."},
        "fr": {"headline": "Emplois en Europe",
               "description": "Offres pour talents d'Afrique du Nord. L'humain décide. Note IA : assisté par IA."},
        "ar": {"headline": "وظائف في أوروبا",
               "description": "فرص عمل في أوروبا لكفاءات شمال أفريقيا. القرار للإنسان. ملاحظة: بدعم من الذكاء الاصطناعي."},
    },
}

CREATIVES: dict[str, dict[str, str]] = {
    "employers_eu": {
        "de": "Fachkräfte aus Nordafrika für Ihr Unternehmen in der EU. Stellen veröffentlichen, "
              "passende Profile sichten, der Mensch entscheidet. {site} KI-Hinweis: mit KI-Unterstützung erstellt.",
        "en": "Skilled workers from North Africa for your company in the EU. Publish roles, review "
              "matching profiles, humans make the decisions. {site} AI note: created with AI support.",
        "fr": "Main-d'œuvre qualifiée d'Afrique du Nord pour votre entreprise dans l'UE. Publiez vos "
              "offres, l'humain décide. {site} Note IA : créé avec l'aide de l'IA.",
        "ar": "كفاءات مؤهلة من شمال أفريقيا لشركتك في الاتحاد الأوروبي. انشر وظائفك، والقرار للإنسان. "
              "{site} ملاحظة: أُنشئ بدعم من الذكاء الاصطناعي.",
    },
    "candidates_north_africa": {
        "de": "Stellen in Europa für Fachkräfte aus Nordafrika. Jetzt bewerben: {site} Der Mensch "
              "entscheidet. KI-Hinweis: mit KI-Unterstützung erstellt.",
        "en": "Job opportunities in Europe for talent from North Africa. Apply: {site} Humans make the "
              "decisions. AI note: created with AI support.",
        "fr": "Opportunités d'emploi en Europe pour les talents d'Afrique du Nord. Postulez : {site} "
              "L'humain décide. Note IA : créé avec l'aide de l'IA.",
        "ar": "فرص عمل في أوروبا للكفاءات من شمال أفريقيا. قدّم الآن: {site} القرار للإنسان. "
              "ملاحظة: أُنشئ بدعم من الذكاء الاصطناعي.",
    },
}


class AdsError(RuntimeError):
    pass


def log(msg: str) -> None:
    print(f"[ads-agent] {msg}", flush=True)


# ── Wahrnehmen ──────────────────────────────────────────────────────────────

def read_signals(db_path: Path) -> dict[str, Any]:
    """Nur Aggregate: Stellenländer und Trichterzählungen (keine Personen)."""
    agg = social.read_aggregates(db_path)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        land_rows = conn.execute(
            "SELECT land, COUNT(*) FROM jobs WHERE status='aktiv' "
            "AND titel NOT LIKE 'E2E-Beweis%' AND titel NOT LIKE '%Teststelle%' GROUP BY land"
        ).fetchall()
    finally:
        conn.close()
    lands = {land or "unbekannt": n for land, n in land_rows}
    return {"active_jobs": agg["active_jobs"], "applications": agg["applications"],
            "invited": agg["invited"], "hired": agg["hired"], "jobs_by_land": lands}


def suppress(n: int) -> int | str:
    """Kleinzellen-Schutz: Werte unter SMALL_CELL werden nicht als Zahl ausgegeben."""
    return n if n >= SMALL_CELL else f"<{SMALL_CELL}"


# ── Planen ──────────────────────────────────────────────────────────────────

def derive_segments(signals: dict[str, Any]) -> list[dict[str, Any]]:
    eu_jobs = sum(n for land, n in signals["jobs_by_land"].items() if land in DE_COUNTRIES)
    return [
        {"segment": "employers_eu", "label": SEGMENTS["employers_eu"]["label"],
         "audience_size": suppress(eu_jobs), "size_source": "aktive Stellen DE/FR/CH"},
        {"segment": "candidates_north_africa", "label": SEGMENTS["candidates_north_africa"]["label"],
         "audience_size": None, "size_source": "nicht aus eigenen Daten ableitbar (Plattform-Reichweite)"},
    ]


def check_text(text: str) -> None:
    social.assert_no_pii(text)
    low = text.lower()
    for claim in FORBIDDEN_CLAIMS:
        if claim in low:
            raise AdsError(f"Werbeaussage verboten: {claim!r}")


def check_creative(text: str) -> None:
    check_text(text)
    has_ai_note = any(marker in text for marker in ("KI-", "AI note", "Note IA", "الذكاء"))
    if SITE not in text or not has_ai_note:
        raise AdsError("Pflichtbestandteile fehlen (Link oder KI-Hinweis)")


def check_search_asset(asset: dict[str, str]) -> None:
    """Google/Microsoft-Suchanzeige: feste Längen, Ziel-URL und KI-Hinweis in der Beschreibung."""
    if len(asset["headline"]) > 30:
        raise AdsError(f"Headline zu lang ({len(asset['headline'])} > 30)")
    if len(asset["description"]) > 90:
        raise AdsError(f"Beschreibung zu lang ({len(asset['description'])} > 90)")
    check_text(asset["headline"] + " " + asset["description"])
    if not any(m in asset["description"] for m in ("KI-", "AI note", "Note IA", "الذكاء")):
        raise AdsError("KI-Hinweis fehlt in der Suchanzeige")


def build_search_assets() -> list[dict[str, str]]:
    out = []
    for segment, langs in SEARCH_ASSETS.items():
        for lang, asset in langs.items():
            check_search_asset(asset)
            out.append({"segment": segment, "language": lang, "final_url": SITE, **asset})
    return out


def build_creatives() -> list[dict[str, str]]:
    out = []
    for segment, texts in CREATIVES.items():
        for lang, template in texts.items():
            text = template.format(site=SITE)
            check_creative(text)
            out.append({"segment": segment, "language": lang, "text": text})
    return out


def targeting_for(segment: str) -> dict[str, Any]:
    """Beschäftigungs-Regeln immer anwenden (ADS_ENTSCHEIDUNG.md Punkt 4)."""
    countries = ["DE", "FR", "CH"] if segment == "employers_eu" else ["MA", "DZ", "TN", "EG"]
    return {"countries": countries, "age_min": 18, "age_max": 65, "genders": "all",
            "lookalikes": False, "exclusions": [], "zip_codes": []}


# ── Handeln (simuliert) ─────────────────────────────────────────────────────

def load_approvals(path: Path | None) -> dict[str, float]:
    if not path or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): float(v) for k, v in data.get("campaigns", {}).items()}


def plan_campaigns(segments: list[dict[str, Any]], cap_eur: float,
                   approvals: dict[str, float]) -> list[dict[str, Any]]:
    campaigns = []
    remaining = cap_eur  # Cap ist Tagesgesamtbudget über alle Kampagnen
    for seg in segments:
        key = seg["segment"]
        requested = min(5.0, cap_eur)
        approved = approvals.get(key, 0.0)
        if cap_eur <= 0:
            status, reason = "blocked", "Cap 0 (kein Budget freigegeben)"
            budget = 0.0
        elif approved <= 0:
            status, reason = "blocked", "keine Freigabe in KMHR_ADS_APPROVAL_FILE"
            budget = 0.0
        else:
            budget = max(0.0, min(approved, remaining, requested))
            remaining -= budget
            if budget > 0:
                status, reason = "paused_ready", "freigegeben, PAUSED angelegt"
            else:
                status, reason = "blocked", "Tages-Cap bereits durch andere Kampagnen ausgeschöpft"
        campaigns.append({"campaign_key": key, "status": status, "reason": reason,
                          "daily_budget_eur": round(budget, 2),
                          "targeting": targeting_for(key),
                          "languages": ["fr", "ar"] if key == "candidates_north_africa" else ["de", "en", "fr"],
                          "platforms": SEGMENTS[key]["platforms"]})
    return campaigns


def simulate_bid(campaign: dict[str, Any]) -> dict[str, Any]:
    """Gebot = Annahme-CPM + 10 %, nie über max_cpm_eur (Obergrenze, kein Auto-Erhöhen)."""
    seg = SEGMENTS[campaign["campaign_key"]]
    bid = min(seg["assumed_cpm_eur"] * 1.1, seg["max_cpm_eur"])
    budget = campaign["daily_budget_eur"]
    impressions = int(budget / bid * 1000) if budget and bid else 0
    return {"simulated": True, "bid_cpm_eur": round(bid, 2), "max_cpm_eur": seg["max_cpm_eur"],
            "assumed_cpm_eur": seg["assumed_cpm_eur"], "expected_impressions": impressions,
            "note": "Design-Annahme, keine Marktdaten"}


GOOGLE_GEO = {"DE": "2276", "FR": "2250", "CH": "2756", "MA": "2504", "DZ": "2012", "TN": "2788", "EG": "2818"}
GOOGLE_LANG = {"de": "1001", "en": "1000", "fr": "1002", "ar": "1019"}


def google_ads_payloads(campaign: dict[str, Any]) -> dict[str, Any]:
    """Google Ads API (Dry-Run): erst Budget, dann Suchkampagne, beide PAUSED.
    Kriterien-IDs (Geo/Sprache) sind gegen die Google-Ads-Kriterienliste zu prüfen."""
    t = campaign["targeting"]
    base = "https://googleads.googleapis.com/v20/customers/<CUSTOMER_ID>"
    budget_op = {"create": {"name": f"KMHR-budget-{campaign['campaign_key']}",
                            "amountMicros": str(int(campaign["daily_budget_eur"] * 1_000_000)),
                            "deliveryMethod": "STANDARD", "explicitlyShared": False}}
    campaign_op = {"create": {"name": f"KMHR-{campaign['campaign_key']}", "status": "PAUSED",
                              "advertisingChannelType": "SEARCH",
                              "campaignBudget": "<BUDGET_RESOURCE_NAME>",
                              "networkSettings": {"targetGoogleSearch": True,
                                                  "targetSearchNetwork": False,
                                                  "targetContentNetwork": False},
                              "geoTargetTypeSetting": {"positiveGeoTargetType": "PRESENCE"},
                              "manualCpc": {"enhancedCpcEnabled": False}}}
    return {"budget": {"url": f"{base}/campaignBudgets:mutate", "json": {"operations": [budget_op]}},
            "campaign": {"url": f"{base}/campaigns:mutate", "json": {"operations": [campaign_op]}},
            "geo_targets": [f"geoTargetConstants/{GOOGLE_GEO[c]}" for c in t["countries"]],
            "languages": [f"languageConstants/{GOOGLE_LANG[l]}" for l in campaign["languages"]],
            "headers": {"Authorization": "Bearer <OAUTH_ACCESS_TOKEN>",
                        "login-customer-id": "<MANAGER_CUSTOMER_ID>"},
            "note": "Dry-Run: kein Netzwerkaufruf; Google Ads braucht ein Cloud-Projekt mit Explorer-Zugang"}


def microsoft_ads_payload(campaign: dict[str, Any]) -> dict[str, Any]:
    """Microsoft Advertising (Dry-Run): SOAP-Operation AddCampaigns, Status Paused."""
    t = campaign["targeting"]
    return {"service": "CampaignManagement", "operation": "AddCampaigns",
            "body": {"AccountId": "<ACCOUNT_ID>", "Campaigns": [{
                "Name": f"KMHR-{campaign['campaign_key']}", "Status": "Paused",
                "CampaignType": "Search", "BudgetType": "DailyBudgetStandard",
                "DailyBudget": campaign["daily_budget_eur"], "TimeZone": "CentralEuropeanTime",
                "Languages": campaign["languages"], "GeoTargets": t["countries"]}]},
            "headers": {"AuthenticationToken": "<OAUTH_ACCESS_TOKEN>",
                        "DeveloperToken": "<MSADS_DEVELOPER_TOKEN>",
                        "CustomerAccountId": "<ACCOUNT_ID>"},
            "note": "Dry-Run: kein Netzwerkaufruf; Universal-Entwicklertoken aus dem Developer Portal"}


def meta_payload_dry_run(campaign: dict[str, Any]) -> dict[str, Any]:
    t = campaign["targeting"]
    return {"url": "https://graph.facebook.com/v26.0/act_<AD_ACCOUNT_ID>/campaigns",
            "data": {"name": f"KMHR-{campaign['campaign_key']}", "status": "PAUSED",
                     "special_ad_categories": ["EMPLOYMENT"],
                     "countries": t["countries"], "age_min": t["age_min"],
                     "age_max": t["age_max"], "genders": t["genders"]},
            "access_token": "<ADS_ACCESS_TOKEN>", "note": "Dry-Run: kein Netzwerkaufruf"}


def meta_language(campaign_key: str) -> str:
    """Anzeigentext je Segment: Arbeitgeber DE, Kandidaten FR."""
    return "de" if campaign_key == "employers_eu" else "fr"


def meta_spec(campaign: dict[str, Any], language: str | None = None) -> dict[str, Any]:
    """Übergabe an `meta_ads.MetaAdsClient.launch` (nur freigegebene Inhalte)."""
    key = campaign["campaign_key"]
    lang = language or meta_language(key)
    creative = CREATIVES[key][lang].format(site=SITE)
    check_creative(creative)
    return {"campaign_key": key, "daily_budget_eur": campaign["daily_budget_eur"],
            "targeting": campaign["targeting"], "link": SITE,
            "link_description": "jobs.hanibal-ai.com",
            "headline": SEARCH_ASSETS[key][lang]["headline"],
            "creative": creative, "language": lang}


def active_platforms(campaign: dict[str, Any], channels: list[str]) -> list[str]:
    """Segment-Kanäle plus Meta, wenn Meta ausdrücklich gewählt wurde."""
    ordered: list[str] = []
    for platform in list(campaign["platforms"]) + ["meta_ads"]:
        if platform in channels and platform not in ordered:
            ordered.append(platform)
    return ordered


# ── Beobachten ──────────────────────────────────────────────────────────────

def append_dmp(day: date, signals: dict[str, Any], campaigns: list[dict[str, Any]],
               path: Path = DMP_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"date": day.isoformat(), "signal": "active_jobs", "value": suppress(signals["active_jobs"])},
        {"date": day.isoformat(), "signal": "applications", "value": suppress(signals["applications"])},
        {"date": day.isoformat(), "signal": "invited", "value": suppress(signals["invited"])},
        {"date": day.isoformat(), "signal": "hired", "value": suppress(signals["hired"])},
    ]
    rows += [{"date": day.isoformat(), "signal": f"campaign_{c['campaign_key']}",
              "value": c["status"]} for c in campaigns]
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def pay_approved(campaigns: list[dict[str, Any]], x402_cfg: dict[str, str] | None) -> None:
    """x402-Gebot nur für freigegebene Kampagnen; Preisdeckel = geplantes Tagesbudget."""
    for c in campaigns:
        if c["status"] != "paused_ready":
            continue
        if not x402_cfg:
            c["x402"] = {"status": "nicht_konfiguriert"}
            continue
        body = {"campaign": c["campaign_key"], "bid_cpm_eur": c["bid_simulation"]["bid_cpm_eur"],
                "budget_eur": c["daily_budget_eur"], "status": "PAUSED"}
        social.assert_no_pii(json.dumps(body))
        try:
            r = ads_x402.pay_bid(x402_cfg["url"], body, x402_cfg["private_key"],
                                 max_price_usdc=c["daily_budget_eur"])
            c["x402"] = {"status": "paid" if r.status == 200 else f"http_{r.status}",
                         "price_usdc": r.price_usdc, "network": r.network,
                         "payment_response": r.payment_response}
        except ads_x402.X402Error as exc:
            c["x402"] = {"status": "abgelehnt", "error": str(exc)}


def selected_channels() -> list[str]:
    raw = os.environ.get("KMHR_ADS_CHANNELS", "").strip()
    if not raw:
        return list(DEFAULT_CHANNELS)
    chosen = [c.strip() for c in raw.split(",") if c.strip()]
    unknown = [c for c in chosen if c not in CHANNELS]
    if unknown:
        raise AdsError(f"Unbekannte Kanäle: {unknown}")
    return chosen


def live_guard() -> None:
    """Live nur bewusst, nur mit Meta und nur mit bestätigtem Budget."""
    if os.environ.get("KMHR_ADS_LIVE_CONFIRM", "").strip() != "1":
        raise AdsError(
            "Live-Schaltung braucht KMHR_ADS_LIVE_CONFIRM=1 (bewusste Bestätigung). "
            "Ablauf: --check-meta → Freigabedatei → --live → --activate <key> --yes")
    if "meta_ads" not in selected_channels():
        raise AdsError(
            "Live ist nur für Meta implementiert: KMHR_ADS_CHANNELS=meta_ads setzen")
    if float(os.environ.get("KMHR_ADS_DAILY_CAP_EUR", "0") or 0) <= 0:
        raise AdsError("KMHR_ADS_DAILY_CAP_EUR ist 0: kein Budget freigegeben")
    social.load_env_social()


def meta_live_run(campaigns: list[dict[str, Any]], day: date) -> dict[str, Any]:
    """Legt freigegebene Kampagnen PAUSED an. Aktivierung bleibt ein Mensch-Schritt."""
    cfg = meta_ads.MetaConfig.from_env()
    client = meta_ads.MetaAdsClient(cfg)
    report: dict[str, Any] = {"preflight": {}, "created": 0, "failed": 0,
                              "skipped": 0, "errors": []}
    try:
        preflight = client.preflight()
    except meta_ads.MetaAdsError as exc:
        report["preflight"] = {"ok": False, "blockers": [str(exc)]}
        return report
    report["preflight"] = preflight
    if not preflight.get("ok"):
        return report

    for c in campaigns:
        if c["status"] != "paused_ready":
            report["skipped"] += 1
            continue
        try:
            spec = meta_spec(c)
            created = client.launch(spec, day.isoformat(), spec["language"])
        except meta_ads.MetaAdsError as exc:
            c["status"] = "failed"
            c["error"] = str(exc)
            report["failed"] += 1
            report["errors"].append(f"{c['campaign_key']}: {exc}")
            continue
        c["status"] = "paused_created"
        c["meta"] = created
        report["created"] += 1
    return report


def run_once(day: date, db_path: Path, live: bool = False, out_dir: Path = OUT_DIR,
             dmp_path: Path | None = None, x402_cfg: dict[str, str] | None = None) -> dict[str, Any]:
    if live:
        live_guard()
    cap = float(os.environ.get("KMHR_ADS_DAILY_CAP_EUR", "0") or 0)
    approval_path = os.environ.get("KMHR_ADS_APPROVAL_FILE")
    approvals = load_approvals(Path(approval_path) if approval_path else None)

    signals = read_signals(db_path)
    segments = derive_segments(signals)
    creatives = build_creatives()
    campaigns = plan_campaigns(segments, cap, approvals)
    channels = selected_channels()
    builders = {"google_ads": google_ads_payloads, "microsoft_ads": microsoft_ads_payload,
                "meta_ads": meta_payload_dry_run}
    for c in campaigns:
        c["bid_simulation"] = simulate_bid(c)
        c["platforms"] = active_platforms(c, channels)
        c["platform_payloads"] = {p: builders[p](c) for p in c["platforms"]}
    spend = sum(c["daily_budget_eur"] for c in campaigns)
    if spend > cap:
        raise AdsError(f"Cap überschritten: {spend} > {cap}")

    meta_report = None
    blocked_reason = None
    if live:
        meta_report = meta_live_run(campaigns, day)
        preflight = meta_report.get("preflight", {})
        if not preflight.get("ok"):
            blocked_reason = ("Meta-Preflight blockiert: "
                              + "; ".join(preflight.get("blockers", ["unbekannt"])))
        elif meta_report["failed"]:
            blocked_reason = ("Meta-Anlage fehlgeschlagen: "
                              + "; ".join(meta_report["errors"]))
    else:
        if x402_cfg is None:
            x402_cfg = ads_x402.config_from_env()
        pay_approved(campaigns, x402_cfg)

    result = {"date": day.isoformat(), "mode": "live_paused" if live else "dry_run",
              "cap_eur": cap, "planned_budget_eur": spend,
              "signals": {k: v for k, v in signals.items() if k != "jobs_by_land"},
              "channels": channels, "search_assets": build_search_assets(),
              "segments": segments, "creatives": creatives, "campaigns": campaigns}
    if meta_report is not None:
        result["meta_live"] = meta_report
    out = out_dir / day.isoformat()
    out.mkdir(parents=True, exist_ok=True)
    (out / "run.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    append_dmp(day, signals, campaigns, dmp_path or DMP_FILE)
    log(f"Lauf {day}: {len(segments)} Segmente, {len(creatives)} Creatives, "
        f"{len(campaigns)} Kampagnen (blockiert: {sum(c['status'] == 'blocked' for c in campaigns)}), "
        f"geplantes Tagesbudget {spend} EUR"
        + (" (live: PAUSED angelegt)" if live else " (keine Ausgabe)"))
    if blocked_reason:
        raise AdsError(blocked_reason)
    return result


def load_run(day: date, out_dir: Path = OUT_DIR) -> dict[str, Any]:
    path = out_dir / day.isoformat() / "run.json"
    if not path.is_file():
        raise AdsError(f"Kein Lauf für {day} gefunden ({path}). Zuerst --once/--live.")
    return json.loads(path.read_text(encoding="utf-8"))


def find_campaign(run: dict[str, Any], key: str) -> dict[str, Any]:
    for campaign in run.get("campaigns", []):
        if campaign.get("campaign_key") == key:
            return campaign
    raise AdsError(f"Kampagne {key!r} nicht im Lauf gefunden")


def activation_ids(campaign: dict[str, Any]) -> dict[str, str]:
    meta = campaign.get("meta") or {}
    ids = {k: meta.get(k, "") for k in ("campaign_id", "adset_id", "ad_id")}
    if not all(ids.values()):
        raise AdsError(
            f"Kampagne {campaign['campaign_key']} hat keine Meta-IDs; "
            "zuerst --live ausführen (Status paused_created)")
    return ids


def activate_campaign(day: date, key: str, confirm: bool,
                      out_dir: Path = OUT_DIR) -> dict[str, Any]:
    if not confirm:
        raise AdsError("Aktivieren nur mit --yes (der Agent schaltet nichts selbst scharf)")
    if float(os.environ.get("KMHR_ADS_DAILY_CAP_EUR", "0") or 0) <= 0:
        raise AdsError("KMHR_ADS_DAILY_CAP_EUR ist 0: Aktivierung verweigert")
    social.load_env_social()
    run = load_run(day, out_dir)
    campaign = find_campaign(run, key)
    ids = activation_ids(campaign)
    client = meta_ads.MetaAdsClient(meta_ads.MetaConfig.from_env())
    result = client.activate(ids, confirm=True)
    campaign["status"] = "active"
    campaign["activation"] = result
    path = out_dir / day.isoformat() / "run.json"
    path.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / day.isoformat() / f"activation-{key}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"Aktiviert: {key} ({ids['campaign_id']}). Ausgaben laufen ab jetzt.")
    return result


def preflight_report(day: date, out_dir: Path = OUT_DIR) -> dict[str, Any]:
    social.load_env_social()
    client = meta_ads.MetaAdsClient(meta_ads.MetaConfig.from_env())
    try:
        report = client.preflight()
    except meta_ads.MetaAdsError as exc:
        report = {"ok": False, "blockers": [str(exc)], "warnings": []}
    out = out_dir / day.isoformat()
    out.mkdir(parents=True, exist_ok=True)
    (out / "meta-preflight.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log("Meta-Preflight: " + ("OK" if report.get("ok") else "BLOCKIERT"))
    for item in report.get("blockers", []):
        log(f"  Blocker: {item}")
    for item in report.get("warnings", []):
        log(f"  Hinweis: {item}")
    video = report.get("video") or {}
    if video:
        log(f"  Creative: {video.get('creative_type', '?')}"
            + (f" (video_id={video.get('video_id')})" if video.get("video_id") else ""))
    for item in report.get("next_steps", []):
        log(f"  Schritt: {item}")
    return report


def launch_kit(day: date, out_dir: Path = OUT_DIR) -> Path:
    """Manueller Start im Meta Ads Manager – funktioniert ohne API-Freigaben."""
    cap = float(os.environ.get("KMHR_ADS_DAILY_CAP_EUR", "0") or 0)
    approval_path = os.environ.get("KMHR_ADS_APPROVAL_FILE")
    approvals = load_approvals(Path(approval_path) if approval_path else None)
    campaigns = plan_campaigns(derive_segments(read_signals(
        Path(os.environ.get("KMHR_DB_PATH", ROOT / "data" / "feedback.db")))), cap, approvals)
    lines = [f"# Meta Ads Startpaket — {day.isoformat()}", "",
             "Manueller Weg ohne Marketing-API-Freigabe. Alle Werte sind bereits",
             "beschäftigungsrechtskonform (18–65+, alle Geschlechter, keine PLZ,",
             "keine Lookalikes, keine Ausschlüsse).", "",
             f"Ziel-URL: {SITE}", ""]
    for c in campaigns:
        key = c["campaign_key"]
        lang = meta_language(key)
        lines += [f"## {SEGMENTS[key]['label']} (`{key}`)", "",
                  f"- Kampagnenziel: Traffic (`{meta_ads.OBJECTIVE}`)",
                  "- Sonderkategorie: **Beschäftigung (EMPLOYMENT)**",
                  f"- Länder: {', '.join(c['targeting']['countries'])}",
                  f"- Alter: {c['targeting']['age_min']}–{c['targeting']['age_max']}, alle Geschlechter",
                  f"- Tagesbudget: {c['daily_budget_eur']:.2f} EUR "
                  f"(Status: {c['status']})",
                  f"- Sprachen: {', '.join(c['languages'])}",
                  "", "**Video (für ein Video-Ad):**", "",
                  "- MP4/MOV, H.264/AAC, 9:16 (1080×1920) für Reels/Stories;",
                  "  4:5 oder 1:1 für den Feed. Vorschaubild als JPG/PNG bereithalten.",
                  "- Im Ads Manager unter „Anzeige“ das Video hochladen und als",
                  "  Creative auswählen; alternativ `META_VIDEO_PATH`/`META_VIDEO_URL`",
                  "  für den API-Pfad setzen.",
                  "", "**Anzeigentext (Copy & Paste):**", "",
                  "```text", CREATIVES[key][lang].format(site=SITE), "```", "",
                  f"**Titel:** {SEARCH_ASSETS[key][lang]['headline']}", "",
                  "**DSA-Begünstigter/Bezahler:** Hanibal AI (vor dem Speichern prüfen)", ""]
    lines += ["## Schritte im Ads Manager", "",
              "1. adsmanager.facebook.com → Kampagne erstellen → Ziel „Traffic“.",
              "2. Sonderkategorie „Beschäftigung“ wählen (Pflicht in DE/FR).",
              "3. Budget, Länder, Alter 18–65, alle Geschlechter eintragen.",
              "4. Video als Creative hochladen, Anzeigentext einfügen, Seite als Anzeigengeber wählen.",
              "5. DSA-Begünstigten/Bezahler setzen, Anzeige zur Prüfung speichern.",
              "6. Erst nach Meta-Prüfung und Vier-Augen-Kontrolle veröffentlichen.", ""]
    out = out_dir / day.isoformat()
    out.mkdir(parents=True, exist_ok=True)
    path = out / "launch-kit.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    log(f"Startpaket geschrieben: {path}")
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ads-Agent (Dry-Run / Meta live PAUSED)")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--live", action="store_true",
                    help="Meta-Kampagnen PAUSED anlegen (KMHR_ADS_LIVE_CONFIRM=1)")
    ap.add_argument("--check-meta", action="store_true",
                    help="nur Meta-Vorabprüfung (Token, Konto, Zahlungsmittel, Seite)")
    ap.add_argument("--kit", action="store_true",
                    help="manuelles Startpaket für den Meta Ads Manager schreiben")
    ap.add_argument("--activate", metavar="KEY",
                    help="paused_created-Kampagne aktivieren (braucht --yes)")
    ap.add_argument("--yes", action="store_true", help="Aktivierung bestätigen")
    ap.add_argument("--db", type=Path, default=Path(os.environ.get("KMHR_DB_PATH", ROOT / "data" / "feedback.db")))
    args = ap.parse_args(argv)
    today = date.today()
    try:
        if args.check_meta:
            report = preflight_report(today)
            return 0 if report.get("ok") else 2
        if args.kit:
            launch_kit(today)
            return 0
        if args.activate:
            activate_campaign(today, args.activate, args.yes)
            return 0
        if not args.once and not args.live:
            ap.error("--once, --live, --check-meta, --kit oder --activate angeben")
        run_once(today, args.db, live=args.live)
    except AdsError as exc:
        log(f"Abbruch: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
