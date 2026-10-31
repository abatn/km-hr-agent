#!/usr/bin/env python3
"""Job-Akquise über die Bundesagentur-für-Arbeit-Jobsuche (DE).

Warum: Die allgemeine Websuche lieferte überwiegend Job-Börsen. Die
BA-Jobsuche liefert strukturierte Arbeitgeberdaten (Firma, Titel, Ort,
Referenznummer, Volltext) und ist ohne Registrierung nutzbar.

Quelle/Stand 31.10.2026:
- Suche:  GET https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs
          Header: X-API-Key: jobboerse-jobsuche
- Detail: GET .../pc/v4/jobdetails/{base64(referenznummer)}
- Seite:  https://www.arbeitsagentur.de/jobsuche/jobdetail/{referenznummer}

Grenzen (belegt):
- Frankreich (France Travail): OAuth2, Zugang derzeit nur auf Antrag.
- Schweiz: jobs.ch/jobup nur mit JobCloud-Freigabe; Job-Room ist keine Suche.
  Siehe `knowledge/system/jobs-agent.md` §Datenquellen.

Aufruf:
    python3 scripts/jobs_api.py --max-jobs 12
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jobs_agent as ja  # noqa: E402

BA_BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
BA_KEY = "jobboerse-jobsuche"

# Branche -> (Suchbegriff, angebotsart)  angebotsart: 1=Arbeit, 4=Ausbildung
SUCHEN: list[tuple[str, str, str, str]] = [
    ("Krankenpflege", "Pflegefachkraft", "Berlin", "1"),
    ("Krankenpflege", "Pflegefachkraft", "München", "1"),
    ("Krankenpflege", "Altenpfleger", "Hamburg", "1"),
    ("Krankenpflege", "Ausbildung Pflegefachkraft", "Köln", "4"),
    ("LKW", "LKW Fahrer", "Berlin", "1"),
    ("LKW", "Berufskraftfahrer", "Hamburg", "1"),
    ("LKW", "LKW Fahrer", "Köln", "1"),
    ("Handwerk", "Elektroniker", "München", "1"),
    ("Handwerk", "Mechatroniker", "Stuttgart", "1"),
    ("Handwerk", "Ausbildung Elektroniker", "Berlin", "4"),
    ("Hotellerie", "Hotelfachmann", "Berlin", "1"),
    ("Hotellerie", "Restaurantfachmann", "Hamburg", "1"),
    ("Hotellerie", "Koch", "München", "1"),
    ("Hotellerie", "Ausbildung Hotelfachmann", "Köln", "4"),
]


def _get(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url)
    req.add_header("X-API-Key", BA_KEY)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "KMHR-JobsAgent/1.0")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def suche(was: str, wo: str, angebotsart: str, size: int = 25) -> list[dict]:
    q = urllib.parse.urlencode({"was": was, "wo": wo, "umkreis": 30,
                                "angebotsart": angebotsart, "size": size, "page": 1})
    data = _get(f"{BA_BASE}/pc/v6/jobs?{q}")
    return data.get("ergebnisliste") or []


def detail_url(refnr: str) -> str:
    """Detail-Endpunkt mit base64-kodierter Referenznummer (Padding URL-kodiert)."""
    b64 = base64.b64encode(refnr.encode()).decode()
    return f"{BA_BASE}/pc/v4/jobdetails/{urllib.parse.quote(b64, safe='')}"


def detail(refnr: str) -> dict:
    return _get(detail_url(refnr))


def ort(treffer: dict) -> str:
    lok = treffer.get("stellenlokationen") or []
    if lok:
        adresse = lok[0].get("adresse") or {}
        return adresse.get("ort") or adresse.get("region") or ""
    return ""


def ba_job(treffer: dict) -> ja.Job:
    ref = treffer.get("referenznummer") or ""
    job = ja.Job(
        title=(treffer.get("stellenangebotsTitel") or "").strip(),
        url=f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref}",
        country="DE",
        industry="",
    )
    job.employer = (treffer.get("firma") or "").strip()[:80]
    job.location = ort(treffer)
    job.snippet = treffer.get("beruf") or ""
    return job


def anreichern(job: ja.Job, refnr: str) -> None:
    """Detailbeschreibung + veroeffentlichte Kontaktadresse ergaenzen."""
    try:
        d = detail(refnr)
    except Exception as e:  # noqa: BLE001 — Detail optional
        job.reasons.append(f"Detail fehlgeschlagen: {type(e).__name__}")
        return
    job.text = (d.get("stellenangebotsBeschreibung") or "")[:20000]
    if not job.text:
        return
    if not job.contact_email:
        job.contact_email = ja.find_email(job.text)
    externe = (d.get("externeURL") or "").strip()
    if externe and not job.contact_email:
        try:
            req = urllib.request.Request(externe)
            req.add_header("User-Agent", "Mozilla/5.0 (compatible; KMHR-JobsAgent/1.0)")
            with urllib.request.urlopen(req, timeout=20) as r:
                html = r.read().decode("utf-8", "replace")
            job.contact_email = ja.find_email(html)
        except Exception:  # noqa: BLE001 — externe Seite optional
            pass


def interleaved(suchen: list[tuple[str, str, str, str]]) -> list[tuple[str, str, str, str]]:
    """Branchen abwechseln, damit keine Branche das Limit fuellt."""
    je_branche: dict[str, list[tuple[str, str, str, str]]] = {}
    for s in suchen:
        je_branche.setdefault(s[0], []).append(s)
    reihenfolge: list[tuple[str, str, str, str]] = []
    for i in range(max(len(v) for v in je_branche.values())):
        for b in ("Krankenpflege", "LKW", "Handwerk", "Hotellerie"):
            if i < len(je_branche.get(b, [])):
                reihenfolge.append(je_branche[b][i])
    return reihenfolge


def run(args: argparse.Namespace) -> int:
    tag = date.today().isoformat()
    gesehen: set[str] = set()
    jobs: list[ja.Job] = []
    captures = 0
    je_host: dict[str, int] = {}

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()
        quote = {'Krankenpflege': 3, 'LKW': 3, 'Handwerk': 3, 'Hotellerie': 3}
        pro_branche: dict[str, int] = {}
        for branche, was, wo, art in interleaved(SUCHEN):
            if pro_branche.get(branche, 0) >= quote.get(branche, 3):
                continue
            if len(jobs) >= args.max_jobs or captures >= args.max_captures:
                break
            try:
                treffer = suche(was, wo, art, size=args.per_query)
            except Exception as e:  # noqa: BLE001 — eine Suche darf den Lauf nicht stoppen
                print(f"[jobs-api] Suche fehlgeschlagen ({was}/{wo}): {type(e).__name__}")
                continue
            print(f"[jobs-api] {branche} {was} {wo} (art={art}): {len(treffer)} Treffer")
            for t in treffer:
                if len(jobs) >= args.max_jobs or captures >= args.max_captures:
                    break
                if pro_branche.get(branche, 0) >= quote.get(branche, 3):
                    break
                ref = (t.get("referenznummer") or "").strip()
                if not ref or ref in gesehen:
                    continue
                gesehen.add(ref)
                host = "arbeitsagentur.de"
                if je_host.get(host, 0) >= args.max_jobs:
                    break
                job = ba_job(t)
                job.industry = branche
                anreichern(job, ref)
                job.score, job.reasons = ja.suitability(job.text or job.snippet)
                if job.score < args.min_score:
                    continue
                if not job.contact_email:
                    job.contact_email = ""
                # Screenshot der BA-Detailseite (Beleg)
                if captures < args.max_captures:
                    captures += 1
                    try:
                        page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
                        page.wait_for_timeout(1500)
                        job.shot = page.screenshot(full_page=True)
                        job.html_text = page.content()
                        job.beleg_ok = True
                    except Exception as e:  # noqa: BLE001
                        job.reasons.append(f"Beleg fehlgeschlagen: {type(e).__name__}")
                ja.persist(job, tag)
                je_host[host] = je_host.get(host, 0) + 1
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

    print(f"[jobs-api] Stellen: {len(jobs)} -> {index.relative_to(ja.ROOT)}")
    print(f"[jobs-api] Empfaenger: {len(empfaenger)} "
          f"({sum(1 for e in empfaenger if e.get('email'))} mit Adresse)")
    print(f"[jobs-api] Outbox: {len(briefe)} Entwurf/Entwuerfe")
    return 0 if len(jobs) >= args.min_jobs else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="BA-Jobsuche-Adapter (DE)")
    ap.add_argument("--max-jobs", type=int, default=12)
    ap.add_argument("--min-jobs", type=int, default=10)
    ap.add_argument("--per-query", type=int, default=25)
    ap.add_argument("--max-captures", type=int, default=40)
    ap.add_argument("--min-score", type=int, default=45)
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
