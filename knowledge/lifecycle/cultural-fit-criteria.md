# Kultur-Fit-Kriterien – KM-HR-Agent

> **Stand:** September 2026  
> **Geltungsbereich:** Automatische Bewertung bei jedem Match  
> **Voraussetzung:** Login + Lebenslauf-Upload (Jobportal-Prinzip)  
> **Kontext:** Deutsch-Tunesisches Recruiting (DE/TN)

---

## Score-Verteilung (Gesamt: 100 Punkte)

| Kategorie | Max. Punkte | Gewichtung | Beschreibung |
|---|---|---|---|
| Sprache | 25 | 25% | Deutsch-Level, Englisch, weitere Sprachen |
| Motivation | 20 | 20% | Karriereziele, Unternehmensinteresse, Erwartungen |
| Arbeitsstil | 25 | 25% | Strukturiert/flexibel, Remote/Onsite, Teamarbeit |
| Kulturelle Passung | 30 | 30% | Kommunikation, Werte, Arbeitsweise im DE/TN-Kontext |

---

## Sprache (0–25 Punkte)

### Bewertungsschema

| Level | Punkte | Beschreibung |
|---|---|---|
| Deutsch C1/C2 | 25 | Fließend, professionell |
| Deutsch B2 | 20 | Gut, kleinere Einschränkungen |
| Deutsch B1 | 15 | Grundkenntnisse, alltagstauglich |
| Deutsch A2 | 10 | Einfache Kommunikation |
| Deutsch A1 | 5 | Sehr grundlegend |
| Kein Deutsch | 0 | Nur Englisch/Fremdsprachen |

### Bonuspunkte

- +3 Pkt: Englisch C1+ (berufliche Kommunikation)
- +2 Pkt: Französisch/Arabisch als Zusatzsprache
- +1 Pkt: Mehr als 3 Sprachen

---

## Motivation (0–20 Punkte)

### Bewertungsschema

| Faktor | Punkte | Beschreibung |
|---|---|---|
| Karriereziele klar | 0–5 | Ziele passen zur Stelle |
| Unternehmensinteresse | 0–5 | Recherche über Unternehmen betrieben |
| Erwartungen realistisch | 0–5 | Gehalt, Rolle, Entwicklung |
| Lernbereitschaft | 0–5 | Weiterbildung, neue Technologien |

---

## Arbeitsstil (0–25 Punkte)

### Bewertungsschema

| Faktor | Punkte | Beschreibung |
|---|---|---|
| Strukturiertheit | 0–5 | Organisiert, planvoll |
| Flexibilität | 0–5 | Anpassungsfähig, agil |
| Remote-Tauglichkeit | 0–5 | Erfahrung mit Remote/Hybrid |
| Teamarbeit | 0–5 | Zusammenarbeit, Kommunikation |
| Feedbackkultur | 0–5 | Konstruktives Geben/Empfangen |

---

## Kulturelle Passung (0–30 Punkte)

### DE-Kontext

| Faktor | Punkte | Beschreibung |
|---|---|---|
| Direkte Kommunikation | 0–6 | Sachlich, direkt, ohne Umwege |
| Pünktlichkeit | 0–6 | Zuverlässigkeit bei Terminen |
| Hierarchie | 0–6 | Flache Strukturen, Eigenverantwortung |
| Ergebnisorientierung | 0–6 | Fokus auf Ergebnisse, nicht Prozesse |
| Arbeitszeit | 0–6 | Flexibilität bei Arbeitszeiten |

### TN-Kontext (bei tunesischen Kandidaten)

| Faktor | Punkte | Beschreibung |
|---|---|---|
| Beziehungsaufbau | 0–6 | Persönliche Beziehung vor Geschäft |
| Hierarchie | 0–6 | Respekt vor Autorität, aber agil |
| Kommunikation | 0–6 | Höflicher, indirekter Stil |
| Teamorientierung | 0–6 | Kollektiv > Individuum |
| Anpassungsfähigkeit | 0–6 | Kulturelle Brücke bauen |

### DE/TN-Brücke

| Faktor | Punkte | Beschreibung |
|---|---|---|
| Kulturelle Offenheit | 0–6 | Interesse an anderer Kultur |
| Sprachliche Anpassung | 0–6 | Kommunikationsstil anpassen |
| Integration | 0–6 | Bereitschaft zur Integration |

---

## DE-TN-Spezialisierung (Phase-E Runde 2, 24.09.2026)

> **Quellenlage (Recherche 24.09.2026, MCP-Connector `fetch`):**
> Externe TN-Quellen im Projekt: **0** (`grep -ri tunesien knowledge/ | wc -l` → 4 Treffer, alle interne
> Projekt-Dateien: `knowledge/language-courses.md`, `knowledge/legal/visa-rules.md` – keine externe Quelle).
> Recherche-Schläge: `https://www.bamf.de/` (HTTP 200, nur Themen-Übersicht, keine TN-/Arbeitsstil-Angaben),
> `https://www.daad.de/deutschland/studienangebote/studiengaenge/` (HTTP 404),
> `https://www.bamf.de/DE/Themen/MigrationAufenthalt/ZuzugBeruf/ZuzugBeruf-node.html` (HTTP 404),
> `https://www.bamf.de/DE/Themen/MigrationAufenthalt/migrationaufenthalt-node.html` (HTTP 200, nur BAMF-Veranstaltungsmeldung).
> **Konsequenz nach Lab-Prinzip:** Aussagen ohne externen Fund sind ausdrücklich als
> **Design-Entscheidung** gekennzeichnet. Rechtsrahmen-Zeilen sind mit interner Quelle hinterlegt.

> **P5-Disclaimer (DE-TN, §H-18, 26.09.2026):** Die DE-TN-Aussagen dieses Abschnitts sind
> **Design-Entscheidung** — es gibt **keine** externe DE-TN-Quelle (Beleg: recherche-plan-restpunkte-2026-09-25.md:182-197,
> Abruf 25.09.2026): GLOBE „Middle East"-Cluster ohne Tunesien (Kabasakal et al. 2012, 62 Gesellschaften),
> Hofstede-TN-Werte = Nachrechnung (Eljammi et al.), Omrane & Khan 2024 deskriptiv. Kein Wert hier ist als
> empirisch belegter DE-TN-Wert zu zitieren; bei NEIN dieser GO-Frage: Abschnitt streichen bis Quelle vorliegt.

### Arbeitsstil – Design-Entscheidung

| Aspekt | DE-Erwartung | TN-Kandidat-Erwartung | Bewertung |
|---|---|---|---|
| Struktur vs. Beziehung | Abläufe/Prozesse zuerst | Beziehungsaufbau vor Geschäft | Punkte aus „Strukturiertheit" (Zeile 61), Erwartungslogik Design-Entscheidung |
| Hierarchie | Flache Strukturen, Eigenverantwortung | Respekt vor Autorität, dennoch agil | übernommen aus Zeile 77 / Zeile 86 |
| Feedbackkultur | Direktes, häufiges Feedback | Höflicher, indirekter Feedbackstil | Punkte aus „Feedbackkultur" (Zeile 65), Erwartung Design-Entscheidung |
| Remote/Onsite | Hybrid möglich | Onsite-Teambezug bevorzugt | Punkte aus „Remote-Tauglichkeit" (Zeile 63), Präferenz Design-Entscheidung |

### Kommunikation – Design-Entscheidung

| Aspekt | Beobachtung/Erwartung | Kennzeichnung |
|---|---|---|
| DE-Seite | Sachlich, direkt, ohne Umwege | etabliert Zeile 75 (Ursprung Design-Entscheidung, 10.09.2026) |
| TN-Seite | Höflicher, indirekter Stil; Small Talk vor Fachthema | etabliert Zeile 87 (Ursprung Design-Entscheidung, 10.09.2026) |
| Übersetzungsbrücke | HR übersetzt Direktheit als Wertschätzung; indirekte Ablehnung wird explizit benannt | **Design-Entscheidung** (24.09.2026) |
| Sprachen im Gespräch | Deutsch = Arbeitssprache, Französisch/Arabisch als Bonus | Bonusregeln Zeile 36–37 (Design-Entscheidung) |

### Rechtsrahmen – interne Quelle (kein externer Neubefund, 24.09.2026)

| Regel | Wert | Quelle |
|---|---|---|
| Aufenthaltszweck TN-Kandidat | § 18a (Fachkraft) oder § 18b (Blue Card) | `knowledge/legal/visa-rules.md` |
| ZAV-Zustimmung | BaA muss zustimmen (§ 39 AufenthG), 4–8 Wochen | `knowledge/legal/visa-rules.md` |
| Blue Card Mindestgehalt 2026 | 50.700 € / Mangelberufe 45.934 € | `knowledge/legal/visa-rules.md`; Herkunft laut `AGENTS.md` Hardcoded-Tabelle = BAMF/ZAV (offiziell); externe Neuprüfung 24.09.2026 nicht möglich (bamf.de-Abrufe 404 bzw. ohne Inhalt) |
| Anerkennung IT-Berufe | freiwillig (reglementierte Berufe: Pflicht) | `knowledge/legal/visa-rules.md` |
| Visum Botschaft Tunis | Bearbeitungszeit 4–8 Wochen | `knowledge/legal/visa-rules.md` |
| Gesamtprozess ZAV + Visum + Einreise | 3–6 Monate (Kandidat nicht sofort startfähig) | `knowledge/legal/visa-rules.md` |
| Kultur-Fit ist kein Rechts-Check | Visumsfragen bleiben beim Skill `check-visa`, nicht in der Kultur-Bewertung | **Design-Entscheidung** |

### Erwartungshaltung – Design-Entscheidung

| Seite | Erwartung | Kennzeichnung |
|---|---|---|
| HR an TN-Kandidat | Deutsch B2 empfohlen (keine Pflicht für Blue Card) | `knowledge/legal/visa-rules.md` (intern) |
| HR an TN-Kandidat | Start erst nach 3–6 Monaten einplanen | `knowledge/legal/visa-rules.md` (intern) |
| HR an TN-Kandidat | Kultur-Fit-Score ist Indiz, kein Ausschlusskriterium – finale Entscheidung immer Mensch (Variant A, 12.09.2026) | `AGENTS.md`, Abschnitt „Human-in-the-loop Variant A" |
| TN-Kandidat an HR | Transparenz über Visumsweg, Anerkennung, Gehaltsband | **Design-Entscheidung** |
| Score-Wirkung | Spezialisierung ändert **keine** Punktegewichte (25/20/25/30, Zeile 14–17) und **keine** Kategorisierungsschwellen (Zeile 159–163) – sie spezifiziert nur die Bewertungs-/Begründungstexte | **Design-Entscheidung** |

---

## Kategorisierung

| Score | Kategorie | Empfehlung |
|---|---|---|
| 90–100 | Hervorragend | Perfekter Kultur-Fit |
| 75–89 | Gut | Kultur-Fit gegeben |
| 60–74 | Bedingt | Kultur-Fit mit Einschränkungen |
| 40–59 | Schwach | Kulturelle Herausforderungen |
| 0–39 | Nicht passend | Kultur-Fit nicht gegeben |

---

*Erstellt am 10.09.2026 für den KM-HR-Agenten.*
