#!/usr/bin/env python3
"""Job-Akquise Hotellerie/Gastronomie Frankreich über lhotellerie-restauration.fr.

Quelle (getestet 31.10.2026):
- Liste:  https://www.lhotellerie-restauration.fr/emploi-<metier>/france
- Detail: https://www.lhotellerie-restauration.fr<card-href>  (JSON-LD JobPosting)

Kein Key, kein Login. robots.txt erlaubt die Stellenpfade (`/emploi/`,
`/emploi-*`); gesperrt ist nur `/api/`. Footer: „REPRODUCTION INTERDITE" —
deshalb nur interner Index, immer auf das Original verlinken.

Felder: Titel, Ort (Département + Stadt), Arbeitgeber
(`hiringOrganization.name`), Beschreibung, Datum (`datePosted`).

Aufruf:
    python3 scripts/jobs_lhr.py --max-jobs 8
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jobs_agent as ja  # noqa: E402

BASE = "https://www.lhotellerie-restauration.fr"
METIERS = [
    ("Hotellerie", "cuisinier"),
    ("Hotellerie", "serveur"),
    ("Hotellerie", "chef-de-partie"),
    ("Hotellerie", "gouvernante"),
    ("Hotellerie", "receptionniste"),
    ("Hotellerie", "commis-de-cuisine"),
]
UA = "Mozilla/5.0 (compatible; KMHR-JobsAgent/1.0)"


def _get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def liste(metier: str) -> list[dict]:
    h = _get(f"{BASE}/emploi-{metier}/france")
    treffer = []
    for m in re.finditer(r'href="(/emploi/[^"]+)"[^>]*class="[^"]*job-item[^"]*"[^>]*id="(\d+)"', h):
        start = m.end()
        block = h[start:start + 2500]
        t = re.search(r"<h3[^>]*>(.*?)</h3>", block, re.S)
        ort = re.search(r'<p class="location">.*?</i>\s*(.*?)</p>', block, re.S)
        dat = re.search(r'<small class="date">(.*?)</small>', block, re.S)
        treffer.append({
            "href": html.unescape(m.group(1)),
            "id": m.group(2),
            "title": html.unescape(re.sub(r"<[^>]+>", "", t.group(1))).strip() if t else "",
            "location": html.unescape(re.sub(r"<[^>]+>", "", ort.group(1))).strip() if ort else "",
            "date": html.unescape(re.sub(r"<[^>]+>", "", dat.group(1))).strip() if dat else "",
        })
    return treffer


def detail(href: str) -> dict:
    h = _get(BASE + href)
    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', h, re.S):
        try:
            d = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict) and d.get("@type") == "JobPosting":
            return d
    return {}


def lhr_job(karte: dict) -> ja.Job:
    job = ja.Job(
        title=karte["title"][:160],
        url=BASE + karte["href"],
        country="FR",
        industry="Hotellerie",
    )
    job.location = karte["location"]
    d = detail(karte["href"])
    org = (d.get("hiringOrganization") or {}).get("name") or ""
    job.employer = org.strip()[:80]
    job.text = re.sub(r"<[^>]+>", " ", d.get("description") or "")[:20000]
    job.contact_email = ja.find_email(job.text)
    return job


def run(args: argparse.Namespace) -> int:
    tag = f"{date.today().isoformat()}-lhr"
    jobs: list[ja.Job] = []
    gesehen: set[str] = set()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        for branche, metier in METIERS:
            if len(jobs) >= args.max_jobs:
                break
            try:
                karten = liste(metier)
            except Exception as e:  # noqa: BLE001
                print(f"[jobs-lhr] Liste fehlgeschlagen ({metier}): {type(e).__name__}")
                continue
            print(f"[jobs-lhr] {branche}/{metier}: {len(karten)} Karten")
            for k in karten:
                if len(jobs) >= args.max_jobs:
                    break
                if k["id"] in gesehen or not k["title"]:
                    continue
                gesehen.add(k["id"])
                try:
                    job = lhr_job(k)
                except Exception as e:  # noqa: BLE001
                    print(f"[jobs-lhr] Detail fehlgeschlagen ({k['id']}): {type(e).__name__}")
                    continue
                job.score, job.reasons = ja.suitability(job.text)
                if job.score < args.min_score:
                    continue
                try:
                    page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(1200)
                    job.shot = page.screenshot(full_page=True)
                    job.html_text = page.content()
                    job.beleg_ok = True
                except Exception as e:  # noqa: BLE001
                    job.reasons.append(f"Beleg fehlgeschlagen: {type(e).__name__}")
                ja.persist(job, tag)
                jobs.append(job)
        browser.close()

    index = ja.write_index(jobs, tag)
    ja.write_details(jobs, tag)
    print(f"[jobs-lhr] Stellen: {len(jobs)} -> {index.relative_to(ja.ROOT)}")
    return 0 if len(jobs) >= args.min_jobs else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="LHR-Adapter (FR Hotellerie/Gastronomie)")
    ap.add_argument("--max-jobs", type=int, default=8)
    ap.add_argument("--min-jobs", type=int, default=1)
    ap.add_argument("--min-score", type=int, default=35)
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
