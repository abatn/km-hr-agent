# Sprachtemplates – Deutsch (DE)

> **Geltungsbereich:** Alle Ausgaben des KM-HR-Agenten auf Deutsch  
> **Stand:** September 2026

---

## Match-Bericht

### Kopfzeile
```
MATCH-BERICHT
Datum: {DATUM}
Kandidat: {NAME}
Stelle: {POSITION} bei {UNTERNEHMEN}
```

### Score-Ausgabe
```
Gesamtbewertung: {SCORE}/100 ({KATEGORIE})

Bewertung pro Kategorie:
- Kernkompetenzen: {SCORE_K}/30
- Berufserfahrung: {SCORE_E}/25
- Bildung: {SCORE_B}/15
- Standort: {SCORE_S}/10
- Branchenkenntnis: {SCORE_BR}/10
- Soft Skills: {SCORE_SS}/10
```

### Handlungsempfehlung
| Score | Empfehlung |
|---|---|
| 90–100 | Sofort einladen |
| 75–89 | Einladen |
| 60–74 | Bedingt einladen – Interviewfragen klären |
| 40–59 | Nicht einladen – Begründung dokumentieren |
| 0–39 | Nicht einladen |

---

## Onboarding-Checkliste

### Willkommens-E-Mail
```
Betreff: Willkommen im Team, {NAME}!

Hallo {NAME},

wir freuen uns, dich ab {EINTRITTSDATUM} im Team {ABTEILUNG} begrüßen zu dürfen.

Im Anlaufplan findest du alle wichtigen Informationen für deine ersten Wochen.

Dein Ansprechpartner: {MENTOR}
```

### IT-Ausstattung
```
IT-Ausstattung für {NAME}:
☐ Laptop bestellt
☐ E-Mail-Account erstellt
☐ VPN-Zugang eingerichtet
☐ Software-Lizenzen bestellt
☐ Hardware (Maus, Tastatur) bestellt
```

### Einarbeitungsplan
```
Woche 1: Kennenlernen
- [ ] Tag 1: Begrüßung, IT-Übergabe
- [ ] Tag 2: Tool-Einführung, Team-Vorstellung
- [ ] Tag 3: Prozess-Überblick
- [ ] Tag 4: Erste kleine Aufgabe
- [ ] Tag 5: Rückfragen, erstes Feedback

Woche 2–4: Einarbeitung
- [ ] Eigenständige Aufgaben
- [ ] 1:1s mit Teamleitung
- [ ] Sprint-Teilnahme
- [ ] Zielvereinbarung
```

---

## Feedback-Fragen

```
Wie bewerten Sie den Match für {KANDIDAT} × {STELLE}?

1. War der Match fachlich korrekt? (1–5)
2. Wurden die wichtigsten Skills richtig erkannt? (1–5)
3. War die Standort-Bewertung zutreffend? (1–5)
4. War die Handlungsempfehlung hilfreich? (1–5)
5. Wurde der Kandidat eingeladen? (Ja/Nein/Vorgemerkt)
6. Gab es Compliance-Probleme? (Ja/Nein)
7. Sonstige Anmerkungen (Freitext)
```

---

## Fehlermeldungen

```
⚠️ Fehler: {FEHLERBESCHREIBUNG}

Was ist passiert: {TECHNISCHE_ERKLÄRUNG}
Was du tun kannst: {LÖSUNG}
Alternative: {WORKAROUND}
```

---

## Compliance-Report

```
COMPLIANCE-BERICHT
Geprüfte Länder: {LÄNDER}
Status: {STATUS}

Ergebnisse:
| Prüfpunkt | Land | Status | Details |
|---|---|---|---|
| {PRÜFPUNKT} | {LAND} | {STATUS} | {DETAILS} |

Empfehlung: {EMPFEHLUNG}
```
