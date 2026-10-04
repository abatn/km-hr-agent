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
from datetime import datetime, timedelta

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
def generate_screening_questions(candidate_name: str, position: str, match_score: int, cultural_fit_score: int, strengths: str, gaps: str) -> str:
    """
    Generiert personalisierte Screening-Fragen basierend auf Kandidatenprofil.
    
    Args:
        candidate_name: Name des Kandidaten
        position: Stellenbezeichnung
        match_score: Match-Score (0-100)
        cultural_fit_score: Kultur-Fit-Score (0-100)
        strengths: Stärken des Kandidaten (kommasepariert)
        gaps: Lücken/Offene Fragen (kommasepariert)
    
    Returns:
        Strukturierte Fragenliste
    """
    # Kategorie basierend auf Score
    if match_score >= 90:
        kategorie = "Hervorragend – Fokus auf Leadership & Vision"
    elif match_score >= 75:
        kategorie = "Gut – Fokus auf Skills & Kultur"
    elif match_score >= 60:
        kategorie = "Bedingt – Fokus auf Lücken klären"
    else:
        kategorie = "Schwach – Grundlegende Eignung prüfen"
    
    # Stärken als Liste
    staerken_liste = [s.strip() for s in strengths.split(",")]
    luecken_liste = [g.strip() for g in gaps.split(",")]
    
    # Fragen generieren
    fragen_a = []
    for i, s in enumerate(staerken_liste[:5], 1):
        fragen_a.append(f"{i}. **{s}:** Beschreiben Sie ein konkretes Projekt, in dem Sie {s} eingesetzt haben. Welche Ergebnisse wurden erzielt?")
    
    fragen_b = []
    for i, g in enumerate(luecken_liste[:3], 1):
        fragen_b.append(f"{i}. **{g}:** Inwieweit haben Sie Erfahrung mit {g}? Wie würden Sie sich hier einarbeiten?")
    
    fragen_c = [
        f"1. Warum interessiert Sie die Position als {position}?",
        "2. Was sind Ihre beruflichen Ziele für die nächsten 3 Jahre?",
        "3. Wie beschreiben Sie Ihren idealen Arbeitsstil?",
        "4. Welche Erwartungen haben Sie an das Gehalt?"
    ]
    
    fragen_d = [
        "1. Wann könnten Sie starten?",
        "2. Sind Sie bereit, nach München zu ziehen / remote zu arbeiten?",
        "3. Haben Sie Fragen an uns?"
    ]
    
    result = f"""OK
=== SCREENING-FRAGEN: {candidate_name} ===

**Stelle:** {position}
**Match-Score:** {match_score}/100
**Kultur-Fit:** {cultural_fit_score}/100
**Kategorie:** {kategorie}

---

## A. Technische Kompetenz (15 Min.)

{chr(10).join(fragen_a)}

## B. Lücken klären (10 Min.)

{chr(10).join(fragen_b)}

## C. Motivation & Kultur (10 Min.)

{chr(10).join(fragen_c)}

## D. Praktische Details (5 Min.)

{chr(10).join(fragen_d)}

---

## Interviewer-Checkliste

- [ ] Profil-Check vor dem Gespräch
- [ ] Technische Fragen vorbereitet
- [ ] Kultur-Fit-Fragen notiert
- [ ] Nächste Schritte besprochen
- [ ] Feedback-Formular ausgefüllt

## Bewertungsbogen

| Bereich | Score (1–5) | Notizen |
|---|---|---|
| Technische Kompetenz | | |
| Erfahrungs-Relevanz | | |
| Motivation & Kultur | | |
| Kommunikation | | |
| **Gesamt** | /20 | |

**Empfehlung:** ✅ Weiter / ⚠️ Klärungsbedarf / ❌ Absage"""
    
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
