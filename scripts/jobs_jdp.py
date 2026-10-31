#!/usr/bin/env python3
"""Job-Akquise Hotellerie/Gastronomie über den Journal-des-Palais-RSS.

Quelle (getestet 31.10.2026): https://www.journaldespalaces.com/carriere/feed/rss.xml
Kein Key, keine Registrierung, ~2.075 Items, ~1.899 mit country-name=France.
Felder: title, contract-type, society, locality, country-name, link, pubDate.

Grenze: kein Volltext im Feed (Eignung nur aus Titel/Vertrag ableitbar);
Luxus-/Gastro-Segment. Bei Weitergabe gilt die Quelle (Link zum Original).
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jobs_agent as ja  # noqa: E402

FEED = "https://www.journaldespalaces.com/carriere/feed/rss.xml"
UA = "Mozilla/5.0 (compatible; KMHR-JobsAgent/1.0)"


def feed(timeout: int = 45) -> list[dict]:
    req = urllib.request.Request(FEED)
    req.add_header("User-Agent", UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        roh = r.read()
    root = ET.fromstring(roh)
    out = []
    for item in root.iter("item"):
        def t(tag: str) -> str:
            el = item.find(tag)
            return (el.text or "").strip() if el is not None else ""
        out.append({
            "title": t("title"), "contract": t("contract-type"),
            "society": t("society"), "locality": t("locality"),
            "country": t("country-name"), "link": t("link"), "date": t("pubDate"),
        })
    return out


def jdp_job(e: dict) -> ja.Job:
    job = ja.Job(title=e["title"][:160], url=e["link"], country="FR", industry="Hotellerie")
    job.employer = e["society"][:80]
    job.location = e["locality"]
    job.text = f"{e['title']} {e['contract']} {e['society']} {e['locality']}"
    return job


def run(args: argparse.Namespace) -> int:
    tag = f"{date.today().isoformat()}-jdp"
    try:
        eintraege = feed()
    except Exception as ex:  # noqa: BLE001
        print(f"[jobs-jdp] Feed fehlgeschlagen: {type(ex).__name__}")
        return 2
    nur_fr = [e for e in eintraege if e["country"] == "France"]
    print(f"[jobs-jdp] Feed: {len(eintraege)} Items, davon FR: {len(nur_fr)}")

    from playwright.sync_api import sync_playwright

    jobs: list[ja.Job] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        for e in nur_fr:
            if len(jobs) >= args.max_jobs:
                break
            job = jdp_job(e)
            job.score, job.reasons = ja.suitability(job.text)
            if job.score < args.min_score:
                continue
            try:
                page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(1000)
                job.shot = page.screenshot(full_page=True)
                job.html_text = page.content()
                job.beleg_ok = True
            except Exception as ex:  # noqa: BLE001
                job.reasons.append(f"Beleg fehlgeschlagen: {type(ex).__name__}")
            ja.persist(job, tag)
            jobs.append(job)
        browser.close()

    index = ja.write_index(jobs, tag)
    ja.write_details(jobs, tag)
    print(f"[jobs-jdp] Stellen: {len(jobs)} -> {index.relative_to(ja.ROOT)}")
    return 0 if len(jobs) >= args.min_jobs else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Journal-des-Palais-RSS-Adapter (FR Hotellerie)")
    ap.add_argument("--max-jobs", type=int, default=6)
    ap.add_argument("--min-jobs", type=int, default=1)
    ap.add_argument("--min-score", type=int, default=30)
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
