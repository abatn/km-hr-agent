#!/usr/bin/env python3
"""Job-Akquise über die öffentliche EURES-Suche (EU/EWR, ohne Credentials).

Quelle (getestet 31.10.2026):
    POST https://europa.eu/eures/api/jv-searchengine/public/jv-search/search
    Body: {"resultsPerPage":N,"page":1,"sortSearch":"MOST_RECENT",
           "keywords":[{"keyword":"...","specificSearchCode":"TITLE"}],
           "locationCodes":["de"],"sessionId":"<40 Zeichen>"}
    Antwort: {"numberRecords":…, "jvs":[{title,description,id,employer,locationMap,…}]}
    Detailseite: https://europa.eu/eures/portal/jv-se/jv-details/{id}?lang=de

Deckt DE, FR, CH und weitere EU-Länder ab – inklusive Arbeitgebername und
Volltext. Kein Key, kein Login.

Aufruf:
    python3 scripts/jobs_eures.py --max-jobs 12
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jobs_agent as ja  # noqa: E402

URL = "https://europa.eu/eures/api/jv-searchengine/public/jv-search/search"
DETAIL = "https://europa.eu/eures/portal/jv-se/jv-details/{id}?lang=de"
SESSION = "0" * 40

# (Land, Branche, Keyword)
SUCHEN: list[tuple[str, str, str]] = [
    ("de", "Krankenpflege", "Pflegefachkraft"),
    ("de", "LKW", "LKW Fahrer"),
    ("de", "Handwerk", "Elektroniker"),
    ("de", "Hotellerie", "Koch"),
    ("fr", "Krankenpflege", "infirmier"),
    ("fr", "LKW", "chauffeur poids lourd"),
    ("fr", "Handwerk", "électricien"),
    ("fr", "Hotellerie", "cuisinier"),
    ("ch", "Krankenpflege", "Pflegefachfrau"),
    ("ch", "LKW", "Chauffeur"),
    ("ch", "Handwerk", "Schreiner"),
    ("ch", "Hotellerie", "Koch"),
]
LAND_NAME = {"de": "DE", "fr": "FR", "ch": "CH", "at": "AT"}


def suche(keyword: str, land: str, size: int = 20) -> list[dict]:
    body = json.dumps({
        "resultsPerPage": size, "page": 1, "sortSearch": "MOST_RECENT",
        "keywords": [{"keyword": keyword, "specificSearchCode": "TITLE"}],
        "locationCodes": [land], "sessionId": SESSION,
    }).encode()
    req = urllib.request.Request(URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "KMHR-JobsAgent/1.0")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace")).get("jvs") or []


def eures_job(t: dict, land: str) -> ja.Job:
    jid = str(t.get("id") or "")
    job = ja.Job(
        title=(t.get("title") or "").strip()[:160],
        url=DETAIL.format(id=jid),
        country=LAND_NAME.get(land, land.upper()),
        industry="",
    )
    job.employer = ((t.get("employer") or {}).get("name") or "").strip()[:80]
    orte = t.get("locationMap") or {}
    liste = [x for x in (orte.get(LAND_NAME.get(land, "DE"), []) or []) if x]
    job.location = ", ".join(liste[:1]) or LAND_NAME.get(land, "")
    job.text = (t.get("description") or "")[:20000]
    job.contact_email = ja.find_email(job.text)
    return job


def run(args: argparse.Namespace) -> int:
    tag = f"{date.today().isoformat()}-eures" + (f"-{args.country}" if args.country else "")
    jobs: list[ja.Job] = []
    gesehen: set[str] = set()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()
        quote: dict[tuple[str, str], int] = {}
        for land, branche, keyword in SUCHEN:
            if args.country and land != args.country:
                continue
            if len(jobs) >= args.max_jobs:
                break
            if quote.get((land, branche), 0) >= args.per_quota:
                continue
            try:
                treffer = suche(keyword, land, size=args.per_query)
            except Exception as e:  # noqa: BLE001
                print(f"[jobs-eures] Suche fehlgeschlagen ({land}/{branche}): {type(e).__name__}")
                continue
            print(f"[jobs-eures] {land.upper()}/{branche} '{keyword}': {len(treffer)} Treffer")
            for t in treffer:
                if len(jobs) >= args.max_jobs:
                    break
                if quote.get((land, branche), 0) >= args.per_quota:
                    break
                jid = str(t.get("id") or "")
                if not jid or jid in gesehen or not t.get("title"):
                    continue
                gesehen.add(jid)
                job = eures_job(t, land)
                job.industry = branche
                job.score, job.reasons = ja.suitability(job.text)
                if job.score < args.min_score:
                    continue
                try:
                    page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(1500)
                    job.shot = page.screenshot(full_page=True)
                    job.html_text = page.content()
                    job.beleg_ok = True
                except Exception as e:  # noqa: BLE001
                    job.reasons.append(f"Beleg fehlgeschlagen: {type(e).__name__}")
                ja.persist(job, tag)
                quote[(land, branche)] = quote.get((land, branche), 0) + 1
                jobs.append(job)
        ctx.close()
        browser.close()

    jobs.sort(key=lambda j: (j.country, -j.score))
    index = ja.write_index(jobs, tag)
    ja.write_details(jobs, tag)
    empfaenger = ja.empfänger_aus_jobs(jobs)
    ja.csv_schreiben(empfaenger)
    briefe = ja.outbox_schreiben(jobs, empfaenger, tag)

    print(f"[jobs-eures] Stellen: {len(jobs)} -> {index.relative_to(ja.ROOT)}")
    mit_mail = sum(1 for e in empfaenger if e.get("email"))
    print(f"[jobs-eures] Empfaenger: {len(empfaenger)} ({mit_mail} mit Adresse)")
    print(f"[jobs-eures] Outbox: {len(briefe)} Entwuerfe")
    return 0 if len(jobs) >= args.min_jobs else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="EURES-Adapter (EU/EWR)")
    ap.add_argument("--max-jobs", type=int, default=12)
    ap.add_argument("--min-jobs", type=int, default=10)
    ap.add_argument("--per-query", type=int, default=20)
    ap.add_argument("--per-quota", type=int, default=2)
    ap.add_argument("--min-score", type=int, default=45)
    ap.add_argument("--country", default="", help="nur ein Land: de/fr/ch")
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
