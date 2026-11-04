#!/usr/bin/env python3
"""Kontaktsperre aus alten Versand-Logs befüllen (einmalige Migration).

Warum: `jobs/ansprache.jsonl` entsteht erst mit dem neuen Versand-Code. Für
bereits angeschriebene Arbeitgeber ist die Sperre leer — der nächste Lauf würde
sie erneut anschreiben. Dieses Script rekonstruiert die Sperre aus den
Versand-Logs (`versand-*.md`), der Empfängerliste und den archivierten `.eml`.

Quellen:
  - `jobs/outbox/**/versand-*.md` — erfolgreiche Zeilen `- OK: <mail> — <betreff> — …`
  - `jobs/empfaenger_final.csv`    — Arbeitgeber/Stelle/URL (für id-Schlüssel)
  - `jobs/outbox/final/*.eml`, `jobs/outbox/backup-*/*.eml`
                                   — Firma aus „Guten Tag …", Titel aus dem Betreff

Ausgabe: `jobs/ansprache.jsonl` (eine Zeile pro E-Mail), Default ist **Dry-Run**.

Aufruf:
    python3 scripts/jobs_seed_sperre.py                 # Dry-Run
    python3 scripts/jobs_seed_sperre.py --write         # schreiben (mit Backup)
    python3 scripts/jobs_seed_sperre.py --write --force # ohne Rückfrage/Backup-Grenze
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jobs_agent as ja  # noqa: E402
import jobs_keys as jk  # noqa: E402

ROOT = ja.ROOT
OUTBOX = ROOT / "jobs" / "outbox"
CSV = ROOT / "jobs" / "empfaenger_final.csv"
ZIEL = ROOT / "jobs" / "ansprache.jsonl"

OK_RE = re.compile(r"^- OK: (\S+@\S+) — (.*?) — ")
DATUM_RE = re.compile(r"^# Versand (\d{4}-\d{2}-\d{2})")
FIRMA_RE = re.compile(r"Guten Tag (.+?),")
BETREFF_MUSTER = (
    re.compile(r"Ihre Stellenanzeige „(.+?)“[ ]*–"),
    re.compile(r"Kostenlose Listung: (.+?) auf "),
    re.compile(r"Votre offre « (.+?) »"),
    re.compile(r"Publication gratuite : (.+?) sur "),
    re.compile(r"Your job posting “(.+?)”"),
    re.compile(r"Free listing: (.+?) on "),
)


def titel_aus_betreff(betreff: str) -> str:
    """Stellentitel aus den bekannten Betreff-Formaten (DE/FR/EN, alt/neu)."""
    for muster in BETREFF_MUSTER:
        m = muster.search(betreff or "")
        if m:
            return m.group(1).strip()
    return ""


def parse_logs(basis: Path) -> dict[str, dict]:
    """Liefert {email: {datum, betreff}} aus allen `versand-*.md` unter `basis`."""
    treffer: dict[str, dict] = {}
    for pfad in sorted(basis.rglob("versand-*.md")):
        datum = ""
        for zeile in pfad.read_text(encoding="utf-8", errors="replace").splitlines():
            m = DATUM_RE.match(zeile)
            if m:
                datum = m.group(1)
                continue
            m = OK_RE.match(zeile)
            if not m:
                continue
            email, betreff = m.group(1).lower(), m.group(2).strip()
            alt = treffer.get(email)
            if alt is None or datum >= alt["datum"]:
                treffer[email] = {"datum": datum, "betreff": betreff}
    return treffer


def parse_csv(pfad: Path) -> dict[str, dict]:
    """{email: {arbeitgeber, stelle, url}} aus der Empfängerliste."""
    if not pfad.exists():
        return {}
    rows = csv.DictReader(pfad.open(encoding="utf-8"))
    return {
        (r.get("email") or "").lower(): {
            "arbeitgeber": r.get("arbeitgeber") or "",
            "stelle": r.get("stelle") or "",
            "url": r.get("url") or "",
        }
        for r in rows if r.get("email")
    }


def parse_eml(basis: Path) -> dict[str, dict]:
    """{email: {firma, betreff}} aus `final/` und `backup-*/`."""
    treffer: dict[str, dict] = {}
    if not basis.exists():
        return treffer
    for pfad in sorted(list(basis.glob("*.eml")) + list(basis.glob("backup-*/*.eml"))):
        text = pfad.read_text(encoding="utf-8", errors="replace")
        kopf, _, body = text.partition("\n\n")
        to = re.search(r"(?im)^to:\s*(.+)$", kopf)
        subj = re.search(r"(?im)^subject:\s*(.+)$", kopf)
        firma = FIRMA_RE.search(body)
        if not (to and firma):
            continue
        treffer.setdefault(to.group(1).strip().lower(), {
            "firma": firma.group(1).strip(),
            "betreff": (subj.group(1) if subj else "").strip(),
        })
    return treffer


def baue_datensaetze(logs: dict[str, dict], csv_map: dict[str, dict],
                     eml_map: dict[str, dict]) -> tuple[list[dict], list[str]]:
    """Baut die Sperr-Datensätze; liefert (saetze, unaufgeloeste_emails)."""
    saetze: list[dict] = []
    offen: list[str] = []
    for email in sorted(logs):
        info = logs[email]
        quelle = csv_map.get(email)
        if quelle and quelle.get("arbeitgeber"):
            firma, titel, url = quelle["arbeitgeber"], quelle["stelle"], quelle["url"]
            herkunft = "csv"
        else:
            eml = eml_map.get(email)
            if not eml:
                offen.append(email)
                continue
            firma, titel, url = eml["firma"], titel_aus_betreff(eml["betreff"]), ""
            herkunft = "eml"
        if not firma:
            offen.append(email)
            continue
        keys = jk.anzeige_keys(url, firma, titel)
        saetze.append({
            "datum": info["datum"],
            "firma": firma,
            "firma_key": jk.firma_key(firma),
            "keys": keys,
            "email": email,
            "betreff": info["betreff"],
            "herkunft": herkunft,
        })
    return saetze, offen


def schreibe(saetze: list[dict], ziel: Path, force: bool, jetzt: datetime | None = None) -> Path | None:
    """Schreibt/merged die Sperre; Backup der bestehenden Datei."""
    vorhanden: dict[str, dict] = {}
    if ziel.exists():
        for zeile in ziel.read_text(encoding="utf-8").splitlines():
            if not zeile.strip():
                continue
            try:
                satz = json.loads(zeile)
            except json.JSONDecodeError:
                continue
            vorhanden[(satz.get("email") or "").lower()] = satz
    backup = None
    if ziel.exists():
        backup = ziel.with_suffix(ziel.suffix + f".bak-{(jetzt or datetime.now()):%Y%m%d-%H%M%S}")
        shutil.copy2(ziel, backup)
    for satz in saetze:
        vorhanden.setdefault(satz["email"], satz)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    zeilen = [json.dumps(vorhanden[k], ensure_ascii=False, sort_keys=True) for k in sorted(vorhanden)]
    ziel.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return backup


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kontaktsperre aus Versand-Logs rekonstruieren")
    ap.add_argument("--logs", default=str(OUTBOX), help="Wurzel für versand-*.md")
    ap.add_argument("--csv", default=str(CSV), help="Empfängerliste")
    ap.add_argument("--eml", default=str(OUTBOX / "final"), help="Ordner mit .eml/backup-*")
    ap.add_argument("--ziel", default=str(ZIEL), help="Sperrdatei (JSONL)")
    ap.add_argument("--write", action="store_true", help="schreiben (Default: Dry-Run)")
    ap.add_argument("--force", action="store_true", help="auch bei unaufgeloesten Empfaengern schreiben")
    args = ap.parse_args(argv)

    logs = parse_logs(Path(args.logs))
    csv_map = parse_csv(Path(args.csv))
    eml_map = parse_eml(Path(args.eml))
    saetze, offen = baue_datensaetze(logs, csv_map, eml_map)

    mit_id = sum(1 for s in saetze if any(k.startswith("id:") for k in s["keys"]))
    nur_hash = len(saetze) - mit_id
    print(f"Logs: {len(logs)} Empfänger | aufgelöst: {len(saetze)} "
          f"(id+hash: {mit_id}, nur hash: {nur_hash}) | offen: {len(offen)}")
    for s in saetze:
        print(f"  {s['datum']}  {s['herkunft']:3s}  {s['firma'][:34]:34s}  {s['email'][:34]:34s}  "
              f"{' '.join(s['keys'])}")
    for e in offen:
        print(f"  OFFEN  {e}")

    if not args.write:
        print("\nDry-Run: nichts geschrieben. Mit --write ausführen.")
        return 0 if not offen else 2
    if offen and not args.force:
        print("ABBRUCH: unaufgelöste Empfänger — erst klären oder --force.")
        return 2
    backup = schreibe(saetze, Path(args.ziel), args.force)
    print(f"\nGeschrieben: {args.ziel} ({len(saetze)} Datensätze)"
          + (f" | Backup: {backup}" if backup else " | kein Backup (Datei war neu)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
