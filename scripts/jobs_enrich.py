#!/usr/bin/env python3
"""Kontakt-Anreicherung: Impressum/Kontaktseiten der Arbeitgeber auswerten.

Vorgehen (nur öffentliche Seiten, 1 Request/s, keine Captchas/Logins):
1. Kandidaten-Domains aus dem Firmennamen ableiten (ohne Rechtsform).
2. Homepage laden und prüfen, ob der Firmenname dort vorkommt (Verifikation).
3. `/impressum`, `/kontakt`, `/contact`, `/mentions-legales` crawlen.
4. Veröffentlichte E-Mail-Adressen und Kontaktformulare extrahieren.
5. Ergebnisse in `jobs/kontakte_recherche.csv` und die Empfängerliste
   `jobs/empfaenger_final.csv` zurückschreiben.

Es werden keine Adressen erfunden: nur was auf der Firmenseite steht.
"""
from __future__ import annotations

import csv
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "jobs" / "empfaenger_final.csv"
OUT = ROOT / "jobs" / "kontakte_recherche.csv"
UA = "Mozilla/5.0 (compatible; KMHR-JobsAgent/1.0; +https://jobs.hanibal-ai.com)"
PFADE = ("/impressum", "/impressum/", "/kontakt", "/kontakt/", "/contact",
         "/contact/", "/mentions-legales", "/imprint")
SUFFIXE = ("gmbh & co. kg", "gmbh & co kg", "gmbh", "ag", "se", "kg", "ohg", "e.v.",
           "sarl", "sas", "sa", "stiftung", "holding", "gruppe", "group")
MAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]{2,}")
BLOCKLIST = {"hotel.de", "hrs.de", "express.de", "manpower.de", "concordia.de", "stepstone.de"}
FORM_RE = re.compile(r'href="([^"]*(?:kontakt|contact|formular|form|mentions)[^"]*)"', re.I)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def domaenen(name: str, land: str = "DE") -> list[str]:
    n = name.lower()
    # Rechtsform nur am Ende entfernen (nicht mitten in Woertern wie "senioren")
    n = re.sub(r"\b(gmbh\s*&\s*co\.?\s*kg|gmbh|ag|se|kg|ohg|e\.v\.|sarl|sas|sa)\b\.?\s*$", " ", n)
    n = re.sub(r"\(.*?\)|/.*$", " ", n)
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode()
    teile = [t for t in re.split(r"[^a-z0-9]+", n) if len(t) >= 3]
    if not teile:
        return []
    slug = "-".join(teile[:3])
    kurz = teile[0]
    tlds = {"CH": ("ch",), "FR": ("fr",), "DE": ("de", "com")}.get(land, ("de", "com"))
    out = []
    for tld in tlds:
        for d in (f"{slug}.{tld}", f"{kurz}.{tld}"):
            if d not in out:
                out.append(d)
    return out[:3]


def hole(url: str, timeout: int = 12) -> tuple[str, str]:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ctype = r.headers.get("Content-Type", "")
            if "html" not in ctype and "text" not in ctype:
                return "", ""
            return r.read(400_000).decode("utf-8", "replace"), r.geturl()
    except Exception:  # noqa: BLE001 — 404/Timeout/Block sind normal
        return "", ""


def verifiziert(html: str, name: str) -> bool:
    """Streng: alle Namens-Tokens muessen im <title> oder Kopf der Seite stehen."""
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    titel = _norm(m.group(1)) if m else ""
    kopf = _norm(html[:4000])
    token = [t for t in _norm(name).split() if len(t) >= 4][:3]
    if not token:
        return False
    text = titel + " " + kopf
    treffer = sum(1 for t in token if t in text)
    return token[0] in text and treffer >= (1 if len(token) == 1 else 2)


def mails(html: str) -> list[str]:
    out = []
    for m in MAIL_RE.findall(html):
        a = m.rstrip(".,;:)!?").lower()
        if re.search(r"(example|sentry|wixpress|\.png|\.jpg|\.gif|@\d)", a):
            continue
        if a not in out:
            out.append(a)
    # bevorzugt allgemeine Adressen (info/kontakt vor bewerbung)
    def rang(a: str) -> int:
        for i, p in enumerate(("info@", "kontakt@", "contact@", "bewerbung@", "recrutement@")):
            if a.startswith(p):
                return i
        return 9
    out.sort(key=lambda a: (rang(a), a))
    return out


def formular(html: str, basis: str) -> str:
    for m in FORM_RE.findall(html):
        u = m if m.startswith("http") else basis.rstrip("/") + "/" + m.lstrip("/")
        if u != basis:
            return u
    return ""


def recherchiere(zeile: dict) -> dict:
    name = zeile["arbeitgeber"]
    for d in domaenen(name, zeile.get("land", "DE")):
        if d in BLOCKLIST:
            continue
        html, final = hole(f"https://{d}")
        if not html or not verifiziert(html, name):
            time.sleep(0.7)
            continue
        gefunden: list[str] = []
        form = formular(html, final)
        for p in PFADE:
            h, f2 = hole(f"https://{d}{p}")
            if h:
                gefunden += [a for a in mails(h) if a not in gefunden]
                form = form or formular(h, f2)
            time.sleep(0.7)
            if gefunden and form:
                break
        return {"website": f"https://{d}", "email": (gefunden[0] if gefunden else ""),
                "email_quelle": f"https://{d}" if gefunden else "",
                "kontaktformular": form, "status": "email" if gefunden else ("formular" if form else "nicht_gefunden")}
    return {"website": "", "email": "", "email_quelle": "", "kontaktformular": "", "status": "nicht_gefunden"}


def main() -> int:
    zeilen = list(csv.DictReader(CSV.open(encoding="utf-8")))
    ziele = [z for z in zeilen if z.get("prioritaet") == "2" and not z.get("email")]
    print(f"[enrich] Arbeitgeber ohne E-Mail: {len(ziele)}")
    neu = []
    for z in ziele:
        r = recherchiere(z)
        r.update({"arbeitgeber": z["arbeitgeber"], "land": z["land"]})
        neu.append(r)
        print(f"  {z['land']} {z['arbeitgeber'][:40]:40} {r['status']:14} {r['email'] or r['kontaktformular'] or ''}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["arbeitgeber", "land", "website", "email",
                                           "email_quelle", "kontaktformular", "status"])
        w.writeheader()
        w.writerows(neu)

    # Empfängerliste aktualisieren
    index = {n["arbeitgeber"]: n for n in neu}
    for z in zeilen:
        n = index.get(z["arbeitgeber"])
        if not n:
            continue
        if n["email"]:
            z["email"] = n["email"]
            z["prioritaet"] = "1"
            z["kontaktweg"] = "E-Mail"
        elif n["kontaktformular"]:
            z["kontaktweg"] = f"Kontaktformular: {n['kontaktformular']}"
        elif n["website"]:
            z["kontaktweg"] = f"Website: {n['website']}"
    with CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(zeilen[0].keys()))
        w.writeheader()
        w.writerows(zeilen)

    mit_mail = sum(1 for n in neu if n["email"])
    mit_form = sum(1 for n in neu if not n["email"] and n["kontaktformular"])
    print(f"[enrich] neue E-Mails: {mit_mail} | Formulare: {mit_form} | ohne: {len(neu) - mit_mail - mit_form}")
    return 0 if mit_mail + mit_form >= 5 else 2


if __name__ == "__main__":
    sys.exit(main())
