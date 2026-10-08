#!/usr/bin/env python3
"""
Meeting-MCP-Server für KM-HR-Agent
Generiert Meeting-Links (VDO.Ninja), Meeting-Metadaten und Screening-Fragen.
Kein API-Key nötig – alles lokal.

Quellen:
- VDO.Ninja-Link-Format: https://vdo.ninja/?director=…
  (Projektstandard seit 27.09.2026, Spec knowledge/system/vdo-ninja-migration.md;
   Vorher Jitsi https://meet.jit.si/xxxxxxx – Umbau Punkt e, 27.09.2026)
- IETF UUID v4 für zufällige Codes
"""

from fastmcp import FastMCP
import uuid
import json
import random
import string
import sys
from pathlib import Path
from datetime import datetime, timedelta

# i18n (Variante B, P2b 07.10.2026): framework-freie Kernschicht (gettext,
# kein NiceGUI). Spec: knowledge/system/i18n-runner-chain.md §7.1.
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
from webui.i18n_core import tr

mcp = FastMCP("meeting-tools")


@mcp.tool()
def create_meeting_link(topic: str, date: str, time: str, duration_minutes: int = 45) -> str:
    """
    Erstellt einen VDO.Ninja-Link und Meeting-Metadaten
    (LEGACY-Tool – im Projekt aktuell 0 Aufrufer; Umbau Jitsi → VDO.Ninja 27.09.2026).
    
    Args:
        topic: Meeting-Thema (z.B. "Pre-Screening Anna Schuster")
        date: Datum im Format YYYY-MM-DD
        time: Uhrzeit im Format HH:MM
        duration_minutes: Dauer in Minuten (Standard: 45)
    
    Returns:
        Meeting-Link + Metadaten als strukturierter Text
    """
    # VDO.Ninja-Raum-URL (Projektstandard agent-runner.py:518; Umbau Punkt e 27.09.2026;
    # Raumname alphanumerisch seit 04.10.2026, Spec vdo-ninja-migration.md §2.5)
    code = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    meet_url = f"https://vdo.ninja/?director=prescreening{code}"
    
    # Zeitberechnung
    try:
        start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end = start + timedelta(minutes=duration_minutes)
        time_range = f"{start.strftime('%H:%M')} – {end.strftime('%H:%M')} Uhr"
        day_name_de = ["Montag","Dienstag","Mittwoch","Donnerstag","Freitag","Samstag","Sonntag"]
        day_name = day_name_de[start.weekday()]
        date_formatted = f"{day_name}, {start.strftime('%d.%m.%Y')}"
    except:
        time_range = f"{time} Uhr ({duration_minutes} Min.)"
        date_formatted = date
    
    result = f"""OK
=== MEETING ERSTELLT ===

Thema: {topic}
Datum: {date_formatted}
Uhrzeit: {time_range}
Dauer: {duration_minutes} Minuten
Format: Online (VDO.Ninja)

Link: {meet_url}

=== TEILNEHMER ===
- Interviewer: [Name eintragen]
- Kandidat: [Name eintragen]

=== CALENDAR-EVENT (zum Kopieren) ===
Titel: {topic}
Start: {date}T{time}:00
Ende: {date}T{end.strftime('%H:%M')}:00
Ort: {meet_url}
Beschreibung: Pre-Screening im Rahmen des Bewerbungsverfahrens.

===ICS-DATEI (optional) ===
BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
DTSTART:{date.replace('-','')}T{time.replace(':','')}00
DTEND:{date.replace('-','')}T{end.strftime('%H%M')}00
SUMMARY:{topic}
LOCATION:{meet_url}
DESCRIPTION:Pre-Screening im Rahmen des Bewerbungsverfahrens.
END:VEVENT
END:VCALENDAR"""
    
    return result


@mcp.tool()
def generate_screening_questions(candidate_name: str, position: str, match_score: int, cultural_fit_score: int, strengths: str, gaps: str, language: str = "de") -> str:
    """
    Generiert personalisierte Screening-Fragen basierend auf Kandidatenprofil.

    Args:
        candidate_name: Name des Kandidaten
        position: Stellenbezeichnung
        match_score: Match-Score (0-100)
        cultural_fit_score: Kultur-Fit-Score (0-100)
        strengths: Stärken des Kandidaten (kommasepariert)
        gaps: Lücken/Offene Fragen (kommasepariert)
        language: Zielsprache (de/en/fr/ar; Default de – Altverhalten)

    Returns:
        Strukturierte Fragenliste
    """
    # Kategorie basierend auf Score
    if match_score >= 90:
        kategorie = tr("Hervorragend – Fokus auf Leadership & Vision", language)
    elif match_score >= 75:
        kategorie = tr("Gut – Fokus auf Skills & Kultur", language)
    elif match_score >= 60:
        kategorie = tr("Bedingt – Fokus auf Lücken klären", language)
    else:
        kategorie = tr("Schwach – Grundlegende Eignung prüfen", language)

    # Stärken als Liste
    staerken_liste = [s.strip() for s in strengths.split(",")]
    luecken_liste = [g.strip() for g in gaps.split(",")]

    # Fragen generieren
    fragen_a = []
    for i, s in enumerate(staerken_liste[:5], 1):
        fragen_a.append(tr("{i}. **{s}:** Beschreiben Sie ein konkretes Projekt, "
                           "in dem Sie {s} eingesetzt haben. Welche Ergebnisse "
                           "wurden erzielt?", language, i=i, s=s))

    fragen_b = []
    for i, g in enumerate(luecken_liste[:3], 1):
        fragen_b.append(tr("{i}. **{g}:** Inwieweit haben Sie Erfahrung mit {g}? "
                           "Wie würden Sie sich hier einarbeiten?", language, i=i, g=g))

    fragen_c = [
        tr("1. Warum interessiert Sie die Position als {position}?", language, position=position),
        tr("2. Was sind Ihre beruflichen Ziele für die nächsten 3 Jahre?", language),
        tr("3. Wie beschreiben Sie Ihren idealen Arbeitsstil?", language),
        tr("4. Welche Erwartungen haben Sie an das Gehalt?", language),
    ]

    fragen_d = [
        tr("1. Wann könnten Sie starten?", language),
        tr("2. Sind Sie bereit, nach München zu ziehen / remote zu arbeiten?", language),
        tr("3. Haben Sie Fragen an uns?", language),
    ]

    result = "\n".join([
        "OK",
        tr("=== SCREENING-FRAGEN: {candidate_name} ===", language, candidate_name=candidate_name),
        "",
        tr("**Stelle:** {0}", language).format(position),
        tr("**Match-Score:** {0}/100", language).format(match_score),
        tr("**Kultur-Fit:** {cultural_fit_score}/100", language, cultural_fit_score=cultural_fit_score),
        tr("**Kategorie:** {kategorie}", language, kategorie=kategorie),
        "",
        "---",
        "",
        tr("## A. Technische Kompetenz (15 Min.)", language),
        "",
        "\n".join(fragen_a),
        "",
        tr("## B. Lücken klären (10 Min.)", language),
        "",
        "\n".join(fragen_b),
        "",
        tr("## C. Motivation & Kultur (10 Min.)", language),
        "",
        "\n".join(fragen_c),
        "",
        tr("## D. Praktische Details (5 Min.)", language),
        "",
        "\n".join(fragen_d),
        "",
        "---",
        "",
        tr("## Interviewer-Checkliste", language),
        "",
        tr("- [ ] Profil-Check vor dem Gespräch", language),
        tr("- [ ] Technische Fragen vorbereitet", language),
        tr("- [ ] Kultur-Fit-Fragen notiert", language),
        tr("- [ ] Nächste Schritte besprochen", language),
        tr("- [ ] Feedback-Formular ausgefüllt", language),
        "",
        tr("## Bewertungsbogen", language),
        "",
        tr("| Bereich | Score (1–5) | Notizen |", language),
        "|---|---|---|",
        tr("| Technische Kompetenz | | |", language),
        tr("| Erfahrungs-Relevanz | | |", language),
        tr("| Motivation & Kultur | | |", language),
        tr("| Kommunikation | | |", language),
        tr("| **Gesamt** | /20 | |", language),
        "",
        tr("**Empfehlung:** ✅ Weiter / ⚠️ Klärungsbedarf / ❌ Absage", language),
    ])

    return result


@mcp.tool()
def generate_ics_file(topic: str, date: str, time: str, duration_minutes: int, meet_url: str, description: str = "") -> str:
    """
    Generiert eine ICS-Datei für Calendar-Import.
    
    Args:
        topic: Meeting-Thema
        date: Datum YYYY-MM-DD
        time: Uhrzeit HH:MM
        duration_minutes: Dauer in Minuten
        meet_url: VDO.Ninja-Link
        description: Beschreibung (optional)
    
    Returns:
        ICS-Inhalt
    """
    try:
        start = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        end = start + timedelta(minutes=duration_minutes)
    except:
        return "FEHLER: Ungültiges Datum/Uhrzeit-Format"
    
    dt_start = start.strftime("%Y%m%dT%H%M%S")
    dt_end = end.strftime("%Y%m%dT%H%M%S")
    dt_stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    uid = str(uuid.uuid4())
    
    desc = description or f"Pre-Screening im Rahmen des Bewerbungsverfahrens. Meet-Link: {meet_url}"
    
    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//KM-HR-Agent//Meeting Tools//DE
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dt_stamp}
DTSTART:{dt_start}
DTEND:{dt_end}
SUMMARY:{topic}
LOCATION:{meet_url}
DESCRIPTION:{desc}
STATUS:CONFIRMED
SEQUENCE:0
END:VEVENT
END:VCALENDAR"""
    
    return f"OK\n{ics}"


if __name__ == "__main__":
    mcp.run()
