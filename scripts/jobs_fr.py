#!/usr/bin/env python3
"""Job-Akquise Frankreich über die France-Travail-API (Offres d'emploi v2).

Auth: OAuth2 client_credentials (kostenlos, Konto auf francetravail.io).
Env:  FT_CLIENT_ID, FT_CLIENT_SECRET   (in .env-runner)

Ohne Credentials beendet das Skript mit Exit 3 und einer klaren Meldung –
es wird nichts erfunden und nichts gescraped.

Endpunkte (Stand 31.10.2026, Doku nur nach Login):
- Token:  POST https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire
- Suche:  GET  https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search
- Detail: GET  https://api.francetravail.io/partenaire/offresdemploi/v2/offres/{id}
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jobs_agent as ja  # noqa: E402

TOKEN_URL = ("https://entreprise.francetravail.fr/connexion/oauth2/access_token"
             "?realm=%2Fpartenaire")
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
DETAIL_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/{id}"
SCOPE = "api_offresdemploiv2 o2dsoffre"

SUCHEN: list[tuple[str, str]] = [
    ("Krankenpflege", "infirmier"),
    ("Krankenpflege", "aide-soignant"),
    ("LKW", "chauffeur poids lourd"),
    ("Handwerk", "électricien"),
    ("Handwerk", "menuisier"),
    ("Hotellerie", "cuisinier"),
    ("Hotellerie", "serveur"),
]


def token(client_id: str, client_secret: str, timeout: int = 20) -> str:
    body = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": SCOPE,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())["access_token"]


def _get(url: str, bearer: str, timeout: int = 25) -> dict:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {bearer}")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def suche(bearer: str, mots: str, debut: int = 0, taille: int = 49) -> list[dict]:
    q = urllib.parse.urlencode({"motsCles": mots, "range": f"{debut}-{debut + taille - 1}"})
    data = _get(f"{SEARCH_URL}?{q}", bearer)
    return data.get("resultats") or []


def detail(bearer: str, offer_id: str) -> dict:
    return _get(DETAIL_URL.format(id=offer_id), bearer)


def fr_job(t: dict) -> ja.Job:
    job = ja.Job(
        title=(t.get("intitule") or "").strip(),
        url=((t.get("origineOffre") or {}).get("urlOrigine")
             or f"https://candidat.francetravail.fr/offres/recherche/detail/{t.get('id','')}"),
        country="FR",
        industry="",
    )
    job.employer = ((t.get("entreprise") or {}).get("nom") or "").strip()[:80]
    job.location = ((t.get("lieuTravail") or {}).get("libelle") or "").strip()
    mail = ((t.get("contact") or {}).get("courriel") or "").strip()
    job.contact_email = mail.lower() if "@" in mail else ""
    return job


MOCK_TREFFER = [{
    "id": "MOCK001", "intitule": "Infirmier (H/F) – MOCK",
    "entreprise": {"nom": "MOCK: Clinique Lyon"},
    "lieuTravail": {"libelle": "69 - Lyon"},
    "origineOffre": {"urlOrigine": "https://candidat.francetravail.fr/offres/recherche/detail/MOCK001"},
    "contact": {"courriel": "rh@clinique-mock.fr"},
}]
MOCK_DETAIL = {"description": ("Nous recherchons un infirmier. Visum/Work permit wird unterstuetzt, "
                               "Anerkennung der Abschluesse und Franzoesisch B2. " * 20)}


def run(args: argparse.Namespace) -> int:
    if getattr(args, "mock", False):
        return _run_mock(args)
    cid = os.environ.get("FT_CLIENT_ID", "").strip()
    secret = os.environ.get("FT_CLIENT_SECRET", "").strip()
    if not cid or not secret:
        print("[jobs-fr] FEHLT: FT_CLIENT_ID / FT_CLIENT_SECRET (in .env-runner setzen).")
        print("[jobs-fr] Konto: https://francetravail.io/inscription -> App -> "
              "'Offres d'emploi v2' abonnieren.")
        print("[jobs-fr] Ohne Credentials liefert die API 401; es wird nichts gescraped.")
        return 3

    bearer = token(cid, secret)
    tag = f"{date.today().isoformat()}-fr"
    jobs: list[ja.Job] = []
    gesehen: set[str] = set()

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_context(viewport={"width": 1440, "height": 1000}).new_page()
        for branche, mots in SUCHEN:
            if len(jobs) >= args.max_jobs:
                break
            try:
                treffer = suche(bearer, mots, taille=args.per_query)
            except Exception as e:  # noqa: BLE001
                print(f"[jobs-fr] Suche fehlgeschlagen ({mots}): {type(e).__name__}")
                continue
            print(f"[jobs-fr] {branche} '{mots}': {len(treffer)} Treffer")
            for t in treffer:
                if len(jobs) >= args.max_jobs:
                    break
                oid = str(t.get("id") or "")
                if not oid or oid in gesehen:
                    continue
                gesehen.add(oid)
                job = fr_job(t)
                job.industry = branche
                try:
                    d = detail(bearer, oid)
                    job.text = (d.get("description") or "")[:20000]
                except Exception:  # noqa: BLE001 — Detail optional
                    job.text = ""
                if not job.contact_email:
                    job.contact_email = ja.find_email(job.text)
                job.score, job.reasons = ja.suitability(job.text or t.get("intitule", ""))
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
    print(f"[jobs-fr] Stellen: {len(jobs)} -> {index.relative_to(ja.ROOT)}")
    return 0 if len(jobs) >= args.min_jobs else 2


def _run_mock(args: argparse.Namespace) -> int:
    """Beweist die Pipeline ohne Netz: Fixtures statt API, klar als MOCK markiert."""
    tag = f"{date.today().isoformat()}-fr-mock"
    jobs: list[ja.Job] = []
    for t in MOCK_TREFFER:
        job = fr_job(t)
        job.industry = "Krankenpflege"
        job.text = MOCK_DETAIL["description"]
        job.score, job.reasons = ja.suitability(job.text)
        job.beleg_ok = False
        job.reasons.append("MOCK-Lauf: kein Screenshot")
        ja.persist(job, tag)
        jobs.append(job)
    index = ja.write_index(jobs, tag)
    ja.write_details(jobs, tag)
    print(f"[jobs-fr] MOCK-Stellen: {len(jobs)} -> {index.relative_to(ja.ROOT)}")
    print("[jobs-fr] MOCK: keine echten Daten, kein Netz; belegt nur die Pipeline.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="France-Travail-Adapter (FR)")
    ap.add_argument("--max-jobs", type=int, default=8)
    ap.add_argument("--min-jobs", type=int, default=1)
    ap.add_argument("--per-query", type=int, default=49)
    ap.add_argument("--min-score", type=int, default=40)
    ap.add_argument("--mock", action="store_true", help="Pipeline mit Fixtures testen (kein Netz)")
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
