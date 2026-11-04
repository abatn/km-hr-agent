#!/usr/bin/env python3
"""Empfängerliste und personalisierte Entwürfe aus allen Beleg-Läufen.

Quelle: `jobs/belege/*/index.md` (DE, CH, FR). Pro Stelle werden Arbeitgeber,
Stelle, Ort, Land, Branche, Quelle und – falls veröffentlicht – die
Kontaktadresse übernommen. Keine Adresse wird erfunden.

Priorität:
  1 = direkte E-Mail-Adresse vorhanden
  2 = kein E-Mail-Feld (Kontaktformular/Website nötig)

Ausgabe:
  jobs/empfaenger_final.csv
  jobs/outbox/final/*.eml   (nur Priorität 1, personalisiert DE/EN/FR)

Aufruf:
    python3 scripts/jobs_recipients.py
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jobs_agent as ja  # noqa: E402

ROOT = ja.ROOT
BELEGE = ROOT / "jobs" / "belege"
CSV = ROOT / "jobs" / "empfaenger_final.csv"
OUTBOX = ROOT / "jobs" / "outbox" / "final"


def _quelle(pfad: Path) -> str:
    n = pfad.parent.name
    if "eures" in n:
        return "EURES"
    if "lhr" in n:
        return "LHR"
    if "jdp" in n:
        return "Journal des Palaces"
    if n.endswith("-ch"):
        return "Job-Room"
    return "Bundesagentur"


def sammle() -> list[dict]:
    zeilen: list[dict] = []
    for idx in sorted(BELEGE.glob("*/index.md")):
        if "mock" in idx.parent.name.lower():
            continue
        quelle = _quelle(idx)
        for z in idx.read_text(encoding="utf-8").splitlines():
            if not z.startswith("| ") or "---" in z or "Arbeitgeber" in z:
                continue
            f = [x.strip() for x in z.split("|")]
            if len(f) < 9:
                continue
            land, branche, kontakt = f[4], f[5], f[7]
            if land not in ("DE", "CH", "FR") or branche == "":
                continue
            if f[1].upper().startswith("MOCK"):
                continue
            mail = ""
            m = re.search(r"[\w.+-]+@[\w-]+\.[\w.-]{2,}", kontakt)
            if m:
                mail = m.group(0).rstrip(".,;:").lower()
            zeilen.append({
                "prioritaet": 1 if mail else 2,
                "arbeitgeber": f[1], "stelle": f[2], "ort": f[3],
                "land": land, "branche": branche, "email": mail,
                "quelle": quelle, "url": f[8][:300],
                "kontaktweg": "E-Mail" if mail else "Kontaktformular/Website",
            })
    # Dedupe: pro (Arbeitgeber, E-Mail) eine Zeile, Priorität 1 gewinnt
    best: dict[tuple[str, str], dict] = {}
    for r in zeilen:
        key = (r["arbeitgeber"].lower(), r["email"])
        if key not in best or r["prioritaet"] < best[key]["prioritaet"]:
            best[key] = r
    return sorted(best.values(), key=lambda r: (r["prioritaet"], r["land"], r["arbeitgeber"]))


def schreibe_csv(rows: list[dict]) -> None:
    CSV.parent.mkdir(parents=True, exist_ok=True)
    with CSV.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["prioritaet", "arbeitgeber", "stelle", "ort",
                                           "land", "branche", "email", "quelle", "kontaktweg", "url"])
        w.writeheader()
        w.writerows(rows)


def schreibe_entwuerfe(rows: list[dict]) -> int:
    OUTBOX.mkdir(parents=True, exist_ok=True)
    n = 0
    for r in rows:
        if not r["email"]:
            continue
        lang = "fr" if r["land"] == "FR" else "de"
        job = ja.Job(title=r["stelle"], url=r["url"], country=r["land"],
                     industry=r["branche"], employer=r["arbeitgeber"],
                     location=r["ort"], source=r["quelle"])
        betreff, body = ja.render_mail(lang, job, {"arbeitgeber": r["arbeitgeber"]})
        name = re.sub(r"[^a-z0-9]+", "-", r["arbeitgeber"].lower()).strip("-")[:50]
        p = OUTBOX / f"{r['land'].lower()}-{name}.eml"
        p.write_text(f"To: {r['email']}\nSubject: {betreff}\n\n{body}", encoding="utf-8")
        n += 1
    return n


def formular_nachrichten(rows: list[dict]) -> int:
    ziel = OUTBOX.parent / "formular"
    ziel.mkdir(parents=True, exist_ok=True)
    n = 0
    for r in rows:
        if r.get("email") or "Kontaktformular:" not in (r.get("kontaktweg") or ""):
            continue
        url = r["kontaktweg"].split("Kontaktformular:", 1)[1].strip()
        lang = "fr" if r["land"] == "FR" else "de"
        job = ja.Job(title=r["stelle"], url=r["url"], country=r["land"],
                     industry=r["branche"], employer=r["arbeitgeber"],
                     location=r["ort"], source=r["quelle"])
        betreff, body = ja.render_mail(lang, job, {"arbeitgeber": r["arbeitgeber"]})
        name = re.sub(r"[^a-z0-9]+", "-", r["arbeitgeber"].lower()).strip("-")[:50]
        (ziel / f"{r['land'].lower()}-{name}.txt").write_text(
            f"URL: {url}\nBetreff: {betreff}\n\n{body}", encoding="utf-8")
        n += 1
    return n


def _csv_lesen() -> list[dict]:
    with CSV.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    import sys as _sys
    prepare = "--prepare-only" in _sys.argv
    if prepare:
        rows = _csv_lesen()
    else:
        rows = sammle()
        schreibe_csv(rows)
    n = schreibe_entwuerfe(rows)
    f = formular_nachrichten(rows)
    mit_mail = sum(1 for r in rows if r["email"])
    print(f"[recipients] Stellen: {len(rows)} | mit E-Mail: {mit_mail} | ohne: {len(rows) - mit_mail}")
    print(f"[recipients] CSV: {CSV.relative_to(ROOT)} | Entwuerfe: {n} -> {OUTBOX.relative_to(ROOT)}")
    print(f"[recipients] Formularnachrichten: {f} -> jobs/outbox/formular")
    for r in rows[:8]:
        print(f"  P{r['prioritaet']} {r['land']} {r['arbeitgeber'][:38]:38} {r['email'] or '—'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
