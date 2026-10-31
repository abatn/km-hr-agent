#!/usr/bin/env python3
"""Job-Akquise Schweiz über die öffentliche Job-Room-Suche (SECO/arbeit.swiss).

Quelle (getestet 31.10.2026):
    POST https://www.job-room.ch/jobadservice/api/jobAdvertisements/_search
         ?page=0&size=50&sort=date_desc
    Body: {"onlineSince":30,"displayRestricted":false,"cantonCodes":[],"keywords":["..."]}
    Kein Key, kein Login, kostenlos.

Geliefert werden: Titel + Beschreibung (DE/FR/IT), Arbeitgeber (Name, Ort,
E-Mail), Kanton, `applyChannel`, `externalUrl`.

Grenzen (dokumentiert):
- Undokumentierter Endpunkt → defensiv parsen, menschliches Volumen.
- `displayRestricted:false` blendet RAV-only-Inserate aus (legal).
- Viele Inserate sind Reposts von JobCloud (jobs.ch/jobup.ch) → über
  `externalUrl`/Fingerprint deduplizieren.
- Frankreich (France Travail) braucht OAuth-Credentials; siehe jobs_api.py.

Aufruf:
    python3 scripts/jobs_ch.py --max-jobs 8
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jobs_agent as ja  # noqa: E402

ROOM_URL = ("https://www.job-room.ch/jobadservice/api/jobAdvertisements/_search"
            "?page=0&size=50&sort=date_desc")

# Branche -> Keywords (DE/FR gemischt, Job-Room sucht in allen Sprachen)
SUCHEN: list[tuple[str, list[str]]] = [
    ("Krankenpflege", ["Pflegefachfrau", "Pflegefachmann", "Infirmier"]),
    ("LKW", ["Chauffeur", "Lastwagenführer", "Berufschauffeur"]),
    ("Handwerk", ["Schreiner", "Elektriker", "Sanitär"]),
    ("Hotellerie", ["Koch", "Serviceangestellte", "Gastronomie"]),
]


def suche(keywords: list[str], size: int = 50) -> list[dict]:
    body = json.dumps({"onlineSince": 30, "displayRestricted": False,
                       "cantonCodes": [], "keywords": keywords}).encode()
    req = urllib.request.Request(ROOM_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (compatible; KMHR-JobsAgent/1.0)")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _text(desc: list[dict]) -> str:
    """Beschreibung in DE bevorzugen, sonst FR/IT."""
    for sprache in ("de", "fr", "it", "en"):
        for d in desc:
            if d.get("languageIsoCode") == sprache:
                return (d.get("description") or "")
    return desc[0].get("description", "") if desc else ""


def _clean(text: str) -> str:
    """HTML-Tags aus Job-Room-Titeln/Beschreibungen entfernen."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _titel(desc: list[dict]) -> str:
    for sprache in ("de", "fr", "it", "en"):
        for d in desc:
            if d.get("languageIsoCode") == sprache and d.get("title"):
                return _clean(d["title"])
    return _clean(desc[0].get("title", "")) if desc else ""


def ch_job(eintrag: dict) -> ja.Job:
    adv = eintrag.get("jobAdvertisement") or eintrag
    content = adv.get("jobContent") or {}
    desc = content.get("jobDescriptions") or []
    company = content.get("company") or {}
    ort = content.get("location") or {}
    job = ja.Job(
        title=_titel(desc).strip(),
        url=(content.get("externalUrl") or "").strip(),
        country="CH",
        industry="",
    )
    job.employer = (company.get("name") or "").strip()[:80]
    job.location = (ort.get("city") or company.get("city") or "").strip()
    job.text = _clean(_text(desc))[:20000]
    mail = (company.get("email") or "").strip()
    if not mail:
        mail = ((content.get("applyChannel") or {}).get("emailAddress") or "").strip()
    job.contact_email = mail.lower() if "@" in mail else ja.find_email(job.text)
    return job


def run(args: argparse.Namespace) -> int:
    tag = f"{date.today().isoformat()}-ch"
    gesehen: set[str] = set()
    jobs: list[ja.Job] = []
    captures = 0

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()
        quote = {"Krankenpflege": 2, "LKW": 2, "Handwerk": 2, "Hotellerie": 2}
        pro_branche: dict[str, int] = {}
        for branche, keywords in SUCHEN:
            if len(jobs) >= args.max_jobs:
                break
            if pro_branche.get(branche, 0) >= quote.get(branche, 2):
                continue
            try:
                treffer = suche(keywords, size=args.per_query)
            except Exception as e:  # noqa: BLE001 — eine Suche darf den Lauf nicht stoppen
                print(f"[jobs-ch] Suche fehlgeschlagen ({branche}): {type(e).__name__}")
                continue
            print(f"[jobs-ch] {branche}: {len(treffer)} Treffer")
            for eintrag in treffer:
                if len(jobs) >= args.max_jobs:
                    break
                if pro_branche.get(branche, 0) >= quote.get(branche, 2):
                    break
                adv = eintrag.get("jobAdvertisement") or eintrag
                jid = adv.get("id") or ""
                if not jid or jid in gesehen:
                    continue
                gesehen.add(jid)
                job = ch_job(eintrag)
                job.industry = branche
                if not job.title or not job.url:
                    continue
                job.score, job.reasons = ja.suitability(job.text)
                if job.score < args.min_score:
                    continue
                if captures < args.max_captures:
                    captures += 1
                    try:
                        page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
                        page.wait_for_timeout(1200)
                        job.shot = page.screenshot(full_page=True)
                        job.html_text = page.content()
                        job.beleg_ok = True
                    except Exception as e:  # noqa: BLE001
                        job.reasons.append(f"Beleg fehlgeschlagen: {type(e).__name__}")
                ja.persist(job, tag)
                pro_branche[branche] = pro_branche.get(branche, 0) + 1
                jobs.append(job)
        ctx.close()
        browser.close()

    jobs.sort(key=lambda j: (-j.score, j.industry))
    index = ja.write_index(jobs, tag)
    ja.write_details(jobs, tag)
    empfaenger = ja.empfänger_aus_jobs(jobs)
    ja.csv_schreiben(empfaenger)
    briefe = ja.outbox_schreiben(jobs, empfaenger, tag)

    print(f"[jobs-ch] Stellen: {len(jobs)} -> {index.relative_to(ja.ROOT)}")
    print(f"[jobs-ch] Empfaenger: {len(empfaenger)} "
          f"({sum(1 for e in empfaenger if e.get(chr(39)+"email"+chr(39)))}) mit Adresse")
    print(f"[jobs-ch] Outbox: {len(briefe)} Entwurf/Entwuerfe")
    return 0 if len(jobs) >= args.min_jobs else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Job-Room-Adapter (CH)")
    ap.add_argument("--max-jobs", type=int, default=8)
    ap.add_argument("--min-jobs", type=int, default=1)
    ap.add_argument("--per-query", type=int, default=50)
    ap.add_argument("--max-captures", type=int, default=20)
    ap.add_argument("--min-score", type=int, default=40)
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
