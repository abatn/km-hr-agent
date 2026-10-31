#!/usr/bin/env python3
"""Erzeugt deterministische E2E-Fixtures fuer einen frischen Checkout (CI).

Hintergrund (31.10.2026): `testdaten/` und `ergebnisse/` sind gitignored und im
CI-Checkout nicht vorhanden. Acht E2E-Skripte brauchen sie aber:

  * `testdaten/profil-*.md`            -> Profil-Auswahlfelder, keine IndexError
  * `ergebnisse/<tool>-kandidat-*.md`  -> Admin-Download-Karten
  * `ergebnisse/check_compliance-*.md` -> Arbeitgeber-Compliance-Seite
  * `ergebnisse/self-presentation-*.md`-> Prescreen-Einsicht (#8)
  * `ergebnisse/einladung-ics-*.ics`   -> ICS-Knopf in der Einladungskarte

Alle Inhalte sind synthetisch (keine personenbezogenen Daten) und werden nur
angelegt, wenn die Zielordner leer oder nicht vorhanden sind. Damit bleibt ein
bestehender Arbeitsstand (echte `ergebnisse/`, `testdaten/`) unberuehrt;
`--force` ueberschreibt bewusst.

Aufruf:
    python3 scripts/seed_e2e_assets.py            # nur leere/fehlende Ordner
    python3 scripts/seed_e2e_assets.py --force    # auch in belegte Ordner
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Synthetische Stammdaten (bewusst generisch, keine echten Personen).
PROFILE = {
    "profil-anna-schuster.md": """# Profil: Anna Schuster

**Name:** Anna Schuster
**Standort:** Berlin
**Verfuegbarkeit:** ab sofort
**Berufserfahrung:** 6 Jahre

## Schwerpunkte

- Cloud-Infrastruktur (AWS, Terraform)
- CI/CD-Pipelines
- Betrieb containerisierter Anwendungen

## Sprachen

- Deutsch: C1
- Englisch: B2
""",
    "profil-mohammed-soliman.md": """# Profil: Mohammed Soliman

**Name:** Mohammed Soliman
**Standort:** Hamburg
**Verfuegbarkeit:** ab 01.12.2026
**Berufserfahrung:** 4 Jahre

## Schwerpunkte

- Logistik und Lagerleitung
- Staplerschein
- Schichtfuehrung

## Sprachen

- Deutsch: B2
- Arabisch: Muttersprache
""",
}

# Admin-Download-Karten: Dateiname reicht, Inhalt nur lesbar.
TOOL_REPORTS = {
    "extract_profile-kandidat-4-2026-09-12.md": """# Extract Profile – Kandidat #4

**Quelle:** E2E-Fixture (synthetisch)
**Status:** OK

Profil wurde strukturiert extrahiert.
""",
    "match_candidate-kandidat-23-2026-10-13.md": """# Match Candidate – Kandidat #23

**Score:** 72/100

Teilpassung: Fachliche Anforderungen erfuellt, Sprachlevel unter Ziel.
""",
    "check_compliance-kandidat-23-2026-10-13.md": """# Check Compliance – Kandidat #23

Compliance-Status: COMPLIANT

Synthetische E2E-Fixture ohne Personenbezug.
""",
    "notify_user-kandidat-23-2026-10-13.md": """# Notify User – Kandidat #23

Benachrichtigung im E2E-Lauf erzeugt (synthetisch).
""",
    "assess_culture_fit-kandidat-23-2026-10-13.md": """# Assess Culture Fit – Kandidat #23

**Passung:** 68/100

Synthetische E2E-Fixture.
""",
}

# Compliance-Seite (Arbeitgeber): Titel MUSS "Stelle #<id>" enthalten,
# sonst ist der Bericht nicht zuordenbar (Parser `_BERICHT_STELLE`).
COMPLIANCE_REPORTS = {
    # Liefert das Datum 2026-09-29 und den Kandidaten-Bezug.
    "check_compliance-kandidat-1-2026-09-29.md": """# Check Compliance – Kandidat #1 / Stelle #7

Compliance-Status: COMPLIANT

Die Anforderungen sind sachlich gerechtfertigt; die Verarbeitung stuetzt sich
auf Art. 6 Abs. 1 lit. b DSGVO. Synthetische E2E-Fixture.
""",
    # Liefert den Stellen-Titel von Stelle #1 (Senior Cloud/DevOps Engineer).
    "check_compliance-kandidat-13-2026-09-22.md": """# Check Compliance – Kandidat #13 / Stelle #1

Compliance-Status: COMPLIANT

Synthetische E2E-Fixture ohne Personenbezug.
""",
}

ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//KM-HR-Agent//E2E-Fixture//DE
BEGIN:VEVENT
UID:e2e-fixture-bewerbung-25@example.invalid
DTSTAMP:20260921T120000Z
DTSTART:20260921T120000Z
DTEND:20260921T124500Z
SUMMARY:Vorstellungsgespraech (E2E-Fixture)
DESCRIPTION:Synthetischer Termin fuer den E2E-Lauf.
END:VEVENT
END:VCALENDAR
"""


def _write(path: Path, text: str, force: bool) -> str:
    """Schreibt eine Datei; vorhandene Dateien bleiben ohne --force unberuehrt."""
    if path.exists() and not force:
        return "skip"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return "write"


def _dir_state(path: Path) -> str:
    if not path.exists():
        return "fehlt"
    n = sum(1 for _ in path.iterdir())
    return f"{n} Eintraege"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="E2E-Fixtures erzeugen (synthetisch)")
    ap.add_argument("--root", default=str(ROOT), help="Repo-Wurzel (Default: Repo)")
    ap.add_argument("--force", action="store_true",
                    help="auch in bereits belegte Ordner schreiben")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    testdaten = root / "testdaten"
    ergebnisse = root / "ergebnisse"

    # Schutz: bestehende Arbeitsstaende nicht mit Fixtures vermischen.
    belegt = [d for d in (testdaten, ergebnisse)
              if d.exists() and any(d.iterdir())]
    if belegt and not args.force:
        print("[fixtures] Zielordner bereits belegt -> nichts geschrieben:")
        for d in belegt:
            print(f"  - {d.relative_to(root)} ({_dir_state(d)})")
        print("[fixtures] Fuer einen frischen Checkout ist das der Normalfall "
              "im CI; lokal bleiben echte Daten unberuehrt.")
        return 0

    heute = date.today()
    in_30 = heute + timedelta(days=30)

    written = skipped = 0
    for name, text in PROFILE.items():
        r = _write(testdaten / name, text, args.force)
        written += r == "write"
        skipped += r == "skip"

    for name, text in TOOL_REPORTS.items():
        r = _write(ergebnisse / name, text, args.force)
        written += r == "write"
        skipped += r == "skip"

    for name, text in COMPLIANCE_REPORTS.items():
        r = _write(ergebnisse / name, text, args.force)
        written += r == "write"
        skipped += r == "skip"

    # Prescreen-Einsicht (#8): neueste Datei je Kandidat wird angezeigt.
    praesentation = (
        "# Selbstpraesentation – Kandidat #1\n\n"
        "## Video\n\nKein Video hinterlegt (E2E-Fixture).\n\n"
        "## Inhalt\n\n"
        "Synthetische Selbstpraesentation fuer den E2E-Lauf. Der Text ist "
        "absichtlich laenger als der Dateiname, damit die Vorschau im Dialog "
        "gefuellt ist und die Pruefung auf Inhalt greift.\n"
    )
    r = _write(ergebnisse / f"self-presentation-kandidat-1-{heute.isoformat()}.md",
               praesentation, args.force)
    written += r == "write"
    skipped += r == "skip"

    # ICS-Knopf in der Einladungskarte (Bewerbung 25, Seed-Task 117).
    r = _write(ergebnisse / "einladung-ics-bewerbung-25.ics", ICS, args.force)
    written += r == "write"
    skipped += r == "skip"

    print(f"[fixtures] geschrieben: {written}, uebersprungen: {skipped}")
    print(f"[fixtures] testdaten: {_dir_state(testdaten)} | "
          f"ergebnisse: {_dir_state(ergebnisse)}")
    print(f"[fixtures] Datumsbasis: heute={heute.isoformat()} "
          f"(Onboarding-Fixture waere {in_30.isoformat()}, wird NICHT angelegt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
