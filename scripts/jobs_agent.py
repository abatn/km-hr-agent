#!/usr/bin/env python3
"""Autonomer Job-Akquise-Agent für Jobs.hanibal-ai.com.

Ablauf (Wahrnehmen → Filtern → Belegen → Anschreiben):

1. Suche über den MCP-Server `anysearch` (remote, JSON-RPC) nach Stellen in
   DE/FR/CH in vier Branchen (Krankenpflege, LKW, Handwerk, Hotellerie).
2. Filtere auf Eignung für ausländische Kandidaten (Visum, Anerkennung,
   Sprachlevel, Relocation) — nachvollziehbar über `suitability()`.
3. Belege jede Stelle: Screenshot + HTML-Snapshot (Playwright) unter
   `jobs/belege/<datum>/`, Quell-URL, Abrufdatum, Archivversuch.
4. Erzeuge die Tabelle `jobs/belege/<datum>/index.md` und die Empfängerliste
   `jobs/empfaenger.csv`.
5. Rendere Anschreiben (DE/EN/FR) in die Outbox `jobs/outbox/<datum>/`.
   Versand nur mit `--send` und ausschließlich an veröffentlichte Adressen.

Grundsätze:
- Keine erfundenen Stellen, keine erfundenen E-Mail-Adressen. Adressen kommen
  ausschließlich aus dem Seitentext (mailto/Impressum) oder aus der
  bereitgestellten Empfängerliste.
- Default ist Dry-Run: kein Netzversand, nur Outbox-Dateien.
- Keine personenbezogenen Daten in Logs; Empfängeradressen sind geschäftliche
  Kontakte und werden nur in der CSV/Outbox geführt.

Spec: knowledge/system/jobs-agent.md
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JOBS_DIR = ROOT / "jobs"
VORLAGEN = JOBS_DIR / "vorlagen"
BELEGE = JOBS_DIR / "belege"
OUTBOX = JOBS_DIR / "outbox"
EMPFAENGER = JOBS_DIR / "empfaenger.csv"

ANYSEARCH_URL = "https://api.anysearch.com/mcp"
ANYSEARCH_HEADER = {"X-Anysearch-Client": "mcp/1.0.0"}

# Branche × Land. Bewusst allgemein formuliert; die Eignungsprüfung läuft
# danach über den Seitentext (Visum/Anerkennung/Sprache/Relocation).
QUERIES: list[tuple[str, str, str]] = [
    ("DE", "Krankenpflege", "Ausbildung Pflegefachkraft Stellenangebot Deutschland 2026"),
    ("DE", "LKW", "LKW Fahrer Stellenangebot Deutschland 2026 Fernverkehr"),
    ("DE", "Handwerk", "Handwerk Ausbildungsplatz Stellenangebot Deutschland 2026"),
    ("DE", "Hotellerie", "Hotel Restaurant Fachkraft Stellenangebot Deutschland 2026"),
    ("FR", "Krankenpflege", "offre emploi infirmier France 2026 recrutement"),
    ("FR", "LKW", "offre emploi chauffeur poids lourd France 2026"),
    ("FR", "Handwerk", "offre emploi artisanat France 2026 recrutement"),
    ("FR", "Hotellerie", "offre emploi hôtellerie restauration France 2026"),
    ("CH", "Krankenpflege", "Stelle Pflegefachkraft Schweiz 2026"),
    ("CH", "LKW", "Stelle LKW Fahrer Schweiz 2026"),
    ("CH", "Handwerk", "Stelle Handwerk Schweiz 2026"),
    ("CH", "Hotellerie", "Stelle Gastronomie Hotellerie Schweiz 2026"),
    # Visum-/Anerkennungs-Fokus: erhoeht die Trefferquote geeigneter Stellen.
    ("DE", "Krankenpflege", "Pflegefachkraft Anerkennung Visum Stellenangebot Deutschland"),
    ("DE", "LKW", "LKW Fahrer Visum Arbeitserlaubnis Stellenangebot Deutschland"),
    ("DE", "Handwerk", "Handwerk Fachkraft Anerkennung Visum Stelle Deutschland"),
    ("DE", "Hotellerie", "Gastronomie Fachkraft Visum Stellenangebot Deutschland"),
    ("FR", "Krankenpflege", "infirmier recrutement titre de séjour France"),
    ("CH", "Krankenpflege", "Pflegefachkraft Ausländer Aufenthaltsbewilligung Schweiz Stelle"),
]

SUITABILITY_POS = {
    "visum": r"\b(visum|visa|arbeitserlaubnis|aufenthalts(?:titel|bewilligung)|blue ?card|blaue karte|fachkr(?:ä|ae)fteeinwanderung|titre de s(?:é|e)jour|permis de travail|work permit)\b",
    "anerkennung": r"\b(anerkennung|recognition|equivalence|gleichwertigkeit|nostrifikation|diploma recognition)\b",
    "relocation": r"\b(relocation|umzugshilfe|housing|wohnung|unterkunft|logement|aide au logement)\b",
    "sprache": r"\b(a1|a2|b1|b2|c1|deutschkenntnisse|sprachkurs|language course|fran(?:ç|c)ais|allemand)\b",
    "international": r"\b(international|ausl(?:ä|ae)ndische|migration|willkommen|vielfalt|diversity)\b",
}
SUITABILITY_NEG = {
    "zulassung": r"\b(nur mit (?:deutscher|schweizer|franz(?:ö|o)sischer) (?:staatsangeh(?:ö|o)rigkeit|berufszulassung)|only eu citizens|nur eu-b(?:ü|ue)rger)\b",
}


@dataclass
class Job:
    title: str
    url: str
    country: str
    industry: str
    employer: str = ""
    location: str = ""
    contact_email: str = ""
    snippet: str = ""
    text: str = ""
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    screenshot: str = ""
    html: str = ""
    archive: str = ""
    captured_at: str = ""
    shot: bytes = b""
    html_text: str = ""
    site_name: str = ""
    h1: str = ""
    page_title: str = ""
    beleg_ok: bool = False

    @property
    def key(self) -> str:
        return hashlib.sha1(self.url.encode("utf-8")).hexdigest()[:12]

    @property
    def slug(self) -> str:
        roh = f"{self.employer or 'arbeitgeber'}-{self.title}".lower()
        roh = re.sub(r"[^a-z0-9]+", "-", roh).strip("-")[:60]
        return f"{self.key}-{roh or 'stelle'}"


# ── MCP ────────────────────────────────────────────────────────────────

def anysearch(name: str, args: dict, timeout: int = 60) -> dict:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": name, "arguments": args}}).encode()
    req = urllib.request.Request(ANYSEARCH_URL, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    for k, v in ANYSEARCH_HEADER.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _text_of(resp: dict) -> str:
    content = (resp.get("result") or {}).get("content") or []
    return "\n".join(c.get("text", "") for c in content if c.get("type") == "text")


def feedback(request_id: str, score: int = 4) -> None:
    """Anysearch verlangt Rueckmeldung zu jeder Suche (best effort)."""
    try:
        anysearch("score", {"feedbacks": [{"request_id": request_id, "score": score}]}, timeout=20)
    except Exception:  # noqa: BLE001 — Feedback darf den Lauf nicht stoppen
        pass


def search(query: str, max_results: int = 10) -> tuple[list[dict], str]:
    resp = anysearch("search", {"query": query, "max_results": max_results})
    rid = ((resp.get("result") or {}).get("_meta") or {}).get("request_id", "")
    text = _text_of(resp)
    treffer: list[dict] = []
    aktuell: dict | None = None
    for line in text.splitlines():
        m = re.match(r"^###\s+\d+\.\s+(.*)$", line.strip())
        if m:
            if aktuell:
                treffer.append(aktuell)
            aktuell = {"title": m.group(1).strip(), "url": ""}
            continue
        m = re.match(r"^-\s+\*\*URL\*\*:\s+(\S+)", line.strip())
        if m and aktuell is not None:
            aktuell["url"] = m.group(1).strip()
    if aktuell:
        treffer.append(aktuell)
    return [t for t in treffer if t.get("url")], rid


# ── Eignung ────────────────────────────────────────────────────────────

def suitability(text: str) -> tuple[int, list[str]]:
    """Heuristik 0–100 mit Begruendung. Kein LLM, deterministisch."""
    t = (text or "").lower()
    score = 35
    gruende: list[str] = []
    for name, muster in SUITABILITY_POS.items():
        if re.search(muster, t):
            punkte = 18
            score += punkte
            gruende.append(f"+{punkte} {name}")
    for name, muster in SUITABILITY_NEG.items():
        if re.search(muster, t):
            score -= 40
            gruende.append(f"-40 {name}")
    if len(t) < 200:
        score -= 20
        gruende.append("-20 Seite ohne verwertbaren Text")
    return max(0, min(100, score)), gruende


# ── Belege ─────────────────────────────────────────────────────────────

def capture(page, job: Job, tag: str) -> None:
    """Screenshot + HTML-Snapshot in den Speicher (Dateien erst nach dem Filter)."""
    try:
        page.goto(job.url, wait_until="domcontentloaded", timeout=45000)
        page.wait_for_timeout(1200)
        job.text = page.inner_text("body")[:20000]
        job.shot = page.screenshot(full_page=True)
        job.html_text = page.content()
        job.page_title = page.title() or ""
        try:
            job.h1 = page.locator("h1").first.inner_text(timeout=3000).strip()[:160]
        except Exception:  # noqa: BLE001 — kein H1 vorhanden
            job.h1 = ""
        try:
            job.site_name = page.evaluate(
                "() => (document.querySelector('meta[property=\'og:site_name\']')||{}).content || ''"
            ) or ""
        except Exception:  # noqa: BLE001 — optional
            job.site_name = ""
        job.beleg_ok = True
    except Exception as e:  # noqa: BLE001 — Beleg fehlt, wird dokumentiert
        job.reasons.append(f"Beleg fehlgeschlagen: {type(e).__name__}")
    job.captured_at = date.today().isoformat()
    if not job.contact_email:
        job.contact_email = find_email(job.text)


def find_email(text: str) -> str:
    """Nur veroeffentlichte Adressen aus dem Seitentext (keine Erfindung)."""
    if not text:
        return ""
    treffer = re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]{2,}", text)
    for adresse in treffer:
        adresse = adresse.rstrip(".,;:)!?")
        if not re.search(r"(example|sentry|wixpress|@\d|\.png|\.jpg)", adresse, re.I):
            return adresse.lower()
    return ""


def archive_attempt(url: str) -> str:
    """Wayback-Save versuchen; Ergebnis ehrlich zurueckgeben."""
    try:
        req = urllib.request.Request(f"https://web.archive.org/save/{url}", method="GET")
        req.add_header("User-Agent", "Mozilla/5.0 (compatible; KMHR-JobsAgent/1.0)")
        with urllib.request.urlopen(req, timeout=45) as r:
            if r.status in (200, 302) and r.geturl().startswith("https://web.archive.org/web/"):
                return r.geturl()
            return f"nicht verfuegbar (HTTP {r.status})"
    except urllib.error.HTTPError as e:
        return f"nicht verfuegbar (HTTP {e.code})"
    except Exception as e:  # noqa: BLE001
        return f"nicht verfuegbar ({type(e).__name__})"


# ── Ausgabe ────────────────────────────────────────────────────────────

def employer_from(title: str, text: str, url: str = "", site_name: str = "") -> str:
    """Arbeitgebername: og:site_name, sonst Domain, sonst Textfeld, sonst Titel."""
    from urllib.parse import urlparse

    if site_name and not re.search(r"cookie|facebook|willkommen|job|stellen", site_name, re.I):
        return site_name.strip()[:80]
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host and not re.search(r"(facebook|instagram|indeed|stepstone|linkedin)", host):
        teile = host.split(".")
        name = teile[-2] if len(teile) >= 2 else host
        return name.replace("-", " ").replace("_", " ").title()[:80]
    m = re.search(r"(?:Unternehmen|Arbeitgeber|Employer|Entreprise|Firma)\s*[:\-]\s*(.+)", text or "")
    if m:
        return m.group(1).strip()[:80]
    for trenner in (" - ", " | ", " – "):
        if trenner in title:
            return title.split(trenner)[0].strip()[:80]
    return title[:80]


def location_from(text: str, country: str) -> str:
    m = re.search(r"(?:Standort|Ort|Location|Lieu)\s*[:\-]\s*(.+)", text or "")
    if m:
        return m.group(1).strip().splitlines()[0][:80]
    return {"DE": "Deutschland", "FR": "France", "CH": "Schweiz"}.get(country, country)


def write_index(jobs: list[Job], tag: str) -> Path:
    ziel = BELEGE / tag
    ziel.mkdir(parents=True, exist_ok=True)
    pfad = ziel / "index.md"
    zeilen = [
        f"# Gefundene Stellen – {tag}",
        "",
        "| Arbeitgeber | Stelle | Ort | Land | Branche | Eignung | Kontakt | Quelle |",
        "|---|---|---|---|---|---|---|---|",
    ]
    def sauber(v: str) -> str:
        return " ".join((v or "").split()).replace("|", "/")

    for j in jobs:
        j.title, j.employer, j.location = sauber(j.title), sauber(j.employer), sauber(j.location)
        eignung = f"{j.score}/100" + (f" ({', '.join(j.reasons[:3])})" if j.reasons else "")
        quelle = f"[Link]({j.url})" + (f" · [Archiv]({j.archive})" if j.archive.startswith("http") else "")
        if j.screenshot:
            quelle += f" · [Screenshot](../{j.screenshot.split('belege/', 1)[-1]})" if "belege/" in j.screenshot else ""
        zeilen.append(
            f"| {j.employer or '—'} | {j.title} | {j.location or '—'} | {j.country} | {j.industry} "
            f"| {eignung} | {j.contact_email or '—'} | {quelle} |"
        )
    zeilen += ["", f"_Erzeugt am {tag} durch scripts/jobs_agent.py._"]
    pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return pfad


def persist(job: Job, tag: str) -> None:
    """Schreibt PNG/HTML fuer eine behaltene Stelle (stabiler Slug)."""
    ziel = BELEGE / tag
    ziel.mkdir(parents=True, exist_ok=True)
    if job.shot:
        png = ziel / f"{job.slug}.png"
        png.write_bytes(job.shot)
        job.screenshot = str(png.relative_to(ROOT))
    if job.html_text:
        html = ziel / f"{job.slug}.html"
        html.write_text(job.html_text, encoding="utf-8")
        job.html = str(html.relative_to(ROOT))


def is_aggregator(title: str, url: str, text: str) -> bool:
    """Job-Boersen, Social-Media-Posts und Listen-Seiten aussortieren."""
    from urllib.parse import urlparse

    host = urlparse(url).netloc.lower()
    if re.search(r"(facebook|instagram|linkedin|xing|youtube|tiktok|twitter|pinterest)\.", host):
        return True
    if re.search(r"(indeed|stepstone|jooble|talent\.com|jobware|monster|jobs\.ch|jobup\.ch|jobscout24|kimeta|meinestadt"
                 r"|azubiyo|aubi-plus|heyjobs|rekruter|ausbildung\.de|jobninja|yourfirm|stellenanzeigen"
                 r"|karriere-[a-z]+\.de|stellenmarkt\.|jobboerse|job-?portal|bewerberportal)\.", host):
        return True
    if re.search(r"karriere-[a-z]+\.de|stellenmarkt\.", host):
        return True
    pfad = urlparse(url).path.rstrip("/").lower()
    if pfad in ("", "/jobs", "/stellenangebote", "/karriere", "/careers", "/emplois", "/offres-emploi"):
        return True
    t = (title or "").lower()
    if re.search(r"\b\d{2,}\s*(open positions|hoteljobs|stellen|jobs)\b", t):
        return True
    if re.search(r"\bjobangebote in\b|\bkategorie:|\balle berufe\b|\bjobs in\b|\bjobsuche\b", t):
        return True
    if re.search(r"gibt es nicht|seite nicht gefunden|page not found|\b404\b|nicht mehr aktuell", t):
        return True
    if len(text or "") < 300:
        return True
    if len(re.findall(r"\b(stellenangebot|offre d'emploi|job)\b", (text or "").lower())) > 60:
        return True
    return False


def write_details(jobs: list[Job], tag: str) -> None:
    ziel = BELEGE / tag
    for j in jobs:
        md = ziel / f"{j.slug}.md"
        md.write_text(
            f"""# {j.title}

- **Arbeitgeber:** {j.employer or "—"}
- **Ort:** {j.location or "—"}
- **Land:** {j.country}
- **Branche:** {j.industry}
- **Quelle:** {j.url}
- **Abgerufen:** {j.captured_at}
- **Archiv:** {j.archive or "—"}
- **Screenshot:** {j.screenshot or "—"}
- **HTML-Snapshot:** {j.html or "—"}
- **E-Mail (veröffentlicht):** {j.contact_email or "—"}
- **Eignung:** {j.score}/100 ({", ".join(j.reasons) or "keine Treffer"})

## Auszug

{(j.text or j.snippet or "")[:1200]}
""",
            encoding="utf-8",
        )


def csv_lesen() -> list[dict]:
    if not EMPFAENGER.exists():
        return []
    with EMPFAENGER.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def csv_schreiben(zeilen: list[dict]) -> None:
    EMPFAENGER.parent.mkdir(parents=True, exist_ok=True)
    with EMPFAENGER.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["arbeitgeber", "email", "sprache", "notiz"])
        w.writeheader()
        for z in zeilen:
            w.writerow({k: z.get(k, "") for k in w.fieldnames})


def empfänger_aus_jobs(jobs: list[Job]) -> list[dict]:
    zeilen = csv_lesen()
    bekannt = {(z.get("arbeitgeber") or "").strip().lower() for z in zeilen}
    for j in jobs:
        if not j.contact_email:
            continue
        name = (j.employer or "").strip()
        if not name or name.lower() in bekannt:
            continue
        zeilen.append({"arbeitgeber": name, "email": j.contact_email,
                       "sprache": "de" if j.country in ("DE", "CH") else "fr",
                       "notiz": f"Quelle: {j.url}"})
        bekannt.add(name.lower())
    return zeilen


def render_mail(lang: str, job: Job | None, emp: dict) -> tuple[str, str]:
    lang = (lang or "de").lower()
    vorlage = VORLAGEN / f"mail_{lang}.md"
    text = vorlage.read_text(encoding="utf-8")
    arbeitgeber = (job.employer if job else emp.get("arbeitgeber")) or "Damen und Herren"
    stelle = job.title if job else "Ihre offene Stelle"
    ort = job.location if job else ""
    werte = {
        "{{ARBEITGEBER}}": arbeitgeber,
        "{{STELLE}}": stelle,
        "{{ORT}}": ort,
        "{{LAND}}": job.country if job else "",
        "{{PLATTFORM}}": "https://jobs.hanibal-ai.com",
        "{{ABSENDER}}": "Team Jobs.hanibal-ai.com",
    }
    for k, v in werte.items():
        text = text.replace(k, v)
    # Vorlagen beginnen mit einer Betreff-Zeile; im .eml steht der Subject-Header.
    zeilen = text.splitlines()
    if zeilen and zeilen[0].lower().startswith(("betreff:", "subject:", "objet :")):
        text = "\n".join(zeilen[1:]).lstrip()
    betreff = {
        "de": f"Kostenlose Listung: {stelle} auf Jobs.hanibal-ai.com",
        "en": f"Free listing: {stelle} on Jobs.hanibal-ai.com",
        "fr": f"Publication gratuite : {stelle} sur Jobs.hanibal-ai.com",
    }[lang]
    return betreff, text


def outbox_schreiben(jobs: list[Job], empfaenger: list[dict], tag: str) -> list[Path]:
    ziel = OUTBOX / tag
    ziel.mkdir(parents=True, exist_ok=True)
    geschrieben: list[Path] = []
    # 1) Stellenbezogene Anschreiben (nur mit veroeffentlichter Adresse)
    for j in jobs:
        if not j.contact_email:
            continue
        lang = "de" if j.country in ("DE", "CH") else "fr"
        betreff, body = render_mail(lang, j, {"arbeitgeber": j.employer})
        p = ziel / f"{j.slug}.eml"
        p.write_text(f"To: {j.contact_email}\nSubject: {betreff}\n\n{body}", encoding="utf-8")
        geschrieben.append(p)
    # 2) Bereitgestellte Testkontakte (nur mit Adresse)
    bereits = {(j.contact_email or "").lower() for j in jobs if j.contact_email}
    for e in empfaenger:
        mail = (e.get("email") or "").strip()
        if not mail or mail.lower() in bereits:
            continue
        lang = (e.get("sprache") or "de").lower()
        betreff, body = render_mail(lang, None, e)
        name = re.sub(r"[^a-z0-9]+", "-", (e.get("arbeitgeber") or "kontakt").lower()).strip("-")
        p = ziel / f"kontakt-{name}.eml"
        p.write_text(f"To: {mail}\nSubject: {betreff}\n\n{body}", encoding="utf-8")
        geschrieben.append(p)
    return geschrieben


# ── Lauf ───────────────────────────────────────────────────────────────

def interleaved(queries: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    """Länder abwechseln, damit kein Land durch das Stellenlimit verdraengt wird."""
    je_land: dict[str, list[tuple[str, str, str]]] = {}
    for q in queries:
        je_land.setdefault(q[0], []).append(q)
    reihenfolge: list[tuple[str, str, str]] = []
    for i in range(max(len(v) for v in je_land.values())):
        for land in ("DE", "FR", "CH"):
            if i < len(je_land.get(land, [])):
                reihenfolge.append(je_land[land][i])
    return reihenfolge


def run(args: argparse.Namespace) -> int:
    tag = date.today().isoformat()
    BELEGE.mkdir(parents=True, exist_ok=True)
    gesehen: set[str] = set()
    jobs: list[Job] = []

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 1000},
                                  user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                                             "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
        page = ctx.new_page()
        captures = 0
        quote = {"DE": 5, "FR": 5, "CH": 4}
        je_host: dict[str, int] = {}
        pro_land = {"DE": 0, "FR": 0, "CH": 0}
        for land, branche, query in interleaved(QUERIES):
            if len(jobs) >= args.max_jobs or captures >= args.max_captures:
                break
            if pro_land.get(land, 0) >= quote.get(land, 4):
                continue
            try:
                treffer, rid = search(query, args.per_query)
                if rid:
                    feedback(rid)
            except Exception as e:  # noqa: BLE001 — eine Suche darf den Lauf nicht stoppen
                print(f"[jobs-agent] Suche fehlgeschlagen ({land}/{branche}): {type(e).__name__}")
                continue
            print(f"[jobs-agent] {land}/{branche}: {len(treffer)} Treffer")
            for t in treffer:
                if len(jobs) >= args.max_jobs:
                    break
                url = t["url"].split("?")[0].rstrip("/")
                if url in gesehen:
                    continue
                gesehen.add(url)
                job = Job(title=t["title"], url=url, country=land, industry=branche)
                job.snippet = t.get("title", "")
                if not args.no_screenshots:
                    if captures >= args.max_captures:
                        break
                    captures += 1
                    capture(page, job, tag)
                if not args.no_screenshots and is_aggregator(job.title, job.url, job.text):
                    continue
                job.score, job.reasons = suitability(job.text or job.snippet)
                if job.score < args.min_score:
                    continue
                if job.h1 and 8 <= len(job.h1) <= 120 and not re.fullmatch(
                        r"(achtung!?|stellenangebot|jobs?|karriere|bewerbung|home)", job.h1.strip(), re.I):
                    job.title = job.h1
                from urllib.parse import urlparse as _up
                _host = _up(job.url).netloc.lower()
                if je_host.get(_host, 0) >= 2:
                    continue
                job.employer = employer_from(job.title, job.text, job.url, job.site_name).strip()[:80]
                job.location = location_from(job.text, job.country)
                job.archive = archive_attempt(job.url) if not args.no_archive else "uebersprungen"
                persist(job, tag)
                jobs.append(job)
                je_host[_host] = je_host.get(_host, 0) + 1
                pro_land[land] = pro_land.get(land, 0) + 1
        ctx.close()
        browser.close()

    jobs.sort(key=lambda j: (-j.score, j.country, j.industry))
    index = write_index(jobs, tag)
    write_details(jobs, tag)
    empfaenger = empfänger_aus_jobs(jobs)
    csv_schreiben(empfaenger)
    briefe = outbox_schreiben(jobs, empfaenger, tag)

    print(f"[jobs-agent] Stellen: {len(jobs)} -> {index.relative_to(ROOT)}")
    print(f"[jobs-agent] Empfaenger: {len(empfaenger)} ({sum(1 for e in empfaenger if e.get('email'))} mit Adresse)")
    print(f"[jobs-agent] Outbox: {len(briefe)} Entwurf/Entwuerfe -> {OUTBOX / tag}")
    if args.send:
        print("[jobs-agent] --send ist gesetzt, aber der Versand ist bewusst nicht implementiert:")
        print("             Kontakte pruefen, dann ueber mcp-email-server.py senden (siehe README).")
    return 0 if len(jobs) >= 10 else 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Job-Akquise-Agent (Dry-Run Default)")
    ap.add_argument("--max-jobs", type=int, default=12)
    ap.add_argument("--per-query", type=int, default=8)
    ap.add_argument("--min-score", type=int, default=40)
    ap.add_argument("--max-captures", type=int, default=50)
    ap.add_argument("--no-screenshots", action="store_true")
    ap.add_argument("--no-archive", action="store_true")
    ap.add_argument("--send", action="store_true", help="Versand beabsichtigt (nur mit echten Adressen)")
    return run(ap.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
