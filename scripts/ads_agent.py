"""Ads-Agent (Werbe-Komponente, DSP/DMP-ähnlich). Standard: Dry-Run, Budget 0.

Wahrnehmen -> Planen -> Handeln (simuliert) -> Beobachten.
Entscheidung und Grenzen: marketing/ADS_ENTSCHEIDUNG.md.

- Nur Aggregate (social_agent.read_aggregates); keine Personen-, Kandidaten- oder Payload-Daten.
- DMP = Aggregat-Tabelle `ergebnisse/ads/dmp_signals.jsonl` (Kleinzellen < 5 werden unterdrückt).
- Budget: Cap standardmäßig 0; Freigabedatei nötig; Kampagnen immer PAUSED.
- Gebot: simuliert mit Design-Annahmen, nach oben begrenzt, nie selbst erhöht.
- `--live` ist bewusst nicht implementiert und bricht ab.
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

FORBIDDEN_CLAIMS = ("garantiert", "dsgvo-konform", "100 %", "100%", "kostenlos",
                    "visum garantiert", "sofort eingestellt", "guaranteed", "garanti",
                    "gratuit", "مضمون")
DE_COUNTRIES = {"DE", "FR", "CH", "Deutschland", "Frankreich", "Schweiz"}

SEGMENTS: dict[str, dict[str, Any]] = {
    "employers_eu": {
        "label": "Arbeitgeber DE/FR/CH",
        "platforms": ["linkedin", "facebook"],
        "max_cpm_eur": 15.0,
        # Design-Annahme, nicht gemessen (siehe ADS_ENTSCHEIDUNG.md Punkt 6)
        "assumed_cpm_eur": 12.0,
    },
    "candidates_north_africa": {
        "label": "Kandidaten Nordafrika",
        "platforms": ["facebook", "instagram"],
        "max_cpm_eur": 4.0,
        "assumed_cpm_eur": 2.5,
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


def check_creative(text: str) -> None:
    social.assert_no_pii(text)
    low = text.lower()
    for claim in FORBIDDEN_CLAIMS:
        if claim in low:
            raise AdsError(f"Werbeaussage verboten: {claim!r}")
    has_ai_note = any(marker in text for marker in ("KI-", "AI note", "Note IA", "الذكاء"))
    if SITE not in text or not has_ai_note:
        raise AdsError("Pflichtbestandteile fehlen (Link oder KI-Hinweis)")


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


def meta_payload_dry_run(campaign: dict[str, Any]) -> dict[str, Any]:
    t = campaign["targeting"]
    return {"url": "https://graph.facebook.com/v26.0/act_<AD_ACCOUNT_ID>/campaigns",
            "data": {"name": f"KMHR-{campaign['campaign_key']}", "status": "PAUSED",
                     "special_ad_categories": ["EMPLOYMENT"],
                     "countries": t["countries"], "age_min": t["age_min"],
                     "age_max": t["age_max"], "genders": t["genders"]},
            "access_token": "<ADS_ACCESS_TOKEN>", "note": "Dry-Run: kein Netzwerkaufruf"}


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


def run_once(day: date, db_path: Path, live: bool = False, out_dir: Path = OUT_DIR,
             dmp_path: Path | None = None) -> dict[str, Any]:
    if live:
        raise AdsError("Live-Schaltung ist nicht implementiert (siehe marketing/ADS_ENTSCHEIDUNG.md)")
    cap = float(os.environ.get("KMHR_ADS_DAILY_CAP_EUR", "0") or 0)
    approval_path = os.environ.get("KMHR_ADS_APPROVAL_FILE")
    approvals = load_approvals(Path(approval_path) if approval_path else None)

    signals = read_signals(db_path)
    segments = derive_segments(signals)
    creatives = build_creatives()
    campaigns = plan_campaigns(segments, cap, approvals)
    for c in campaigns:
        c["bid_simulation"] = simulate_bid(c)
        c["platform_payloads"] = {p: meta_payload_dry_run(c) for p in c["platforms"] if p == "facebook"}
    spend = sum(c["daily_budget_eur"] for c in campaigns)
    if spend > cap:
        raise AdsError(f"Cap überschritten: {spend} > {cap}")

    result = {"date": day.isoformat(), "mode": "dry_run", "cap_eur": cap,
              "planned_budget_eur": spend, "signals": {k: v for k, v in signals.items() if k != "jobs_by_land"},
              "segments": segments, "creatives": creatives, "campaigns": campaigns}
    out = out_dir / day.isoformat()
    out.mkdir(parents=True, exist_ok=True)
    (out / "run.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    append_dmp(day, signals, campaigns, dmp_path or DMP_FILE)
    log(f"Lauf {day}: {len(segments)} Segmente, {len(creatives)} Creatives, "
        f"{len(campaigns)} Kampagnen (blockiert: {sum(c['status'] == 'blocked' for c in campaigns)}), "
        f"geplantes Tagesbudget {spend} EUR (keine Ausgabe)")
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ads-Agent (Dry-Run)")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--live", action="store_true", help="nicht implementiert, bricht ab")
    ap.add_argument("--db", type=Path, default=Path(os.environ.get("KMHR_DB_PATH", ROOT / "data" / "feedback.db")))
    args = ap.parse_args(argv)
    if not args.once:
        ap.error("--once angeben")
    try:
        run_once(date.today(), args.db, live=args.live)
    except AdsError as exc:
        log(f"Abbruch: {exc}")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
