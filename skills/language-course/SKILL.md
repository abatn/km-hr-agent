---
description: Sprachkurs-Integration – Deutsch/Französisch/Englisch finden, Niveaus testen, Fortschritt verfolgen
---

## Funktionierende MCP-Connectors

| Connector | Tool | Zweck |
|---|---|---|
| `filesystem` | `read_text_file` | Knowledge-Dateien (language-courses.md, Kandidatenprofil) + Fortschritts-Dateien lesen |
| `filesystem` | `write_file` | Fortschritts-Dateien, Kurs-Empfehlungen, Berichte speichern |
| `filesystem` | `list_directory` | Verzeichnisse durchsuchen (testdaten/, ergebnisse/) |
| `filesystem` | `glob` | Fortschritts-Dateien finden (`fortschritt-*.md`) |
| `pdf-reader` | `read_pdf_text` | Sprachzertifikate (Goethe, TELC, IELTS) extrahieren und prüfen |
| `ansvar-german-law` | `search` | 🇩🇪 Integrationskurs-Pflicht (IntV), BAMF-Förderung,AufenthG-Sprachanforderungen |
| `ansvar-french-law` | `search` | 🇫🇷 CIR/CFI Kurse, obligation d'intégration |
| `ansvar-swiss-law` | `search` | 🇨🇭 Integrationskurse (IDS), cantonale Vorschriften |

**Hinweis:** Lab-Prinzip – kein eigener Code. Der Skill definiert NUR Workflow und Regeln.
Web-Suche für aktuelle Kursangebote über `anysearch` (anonymous Access, `search` Tool).

---

## Zugriff (v4.5, Zwei-Ebenen-Modell)

| Rolle | Zugriff |
|---|---|
| **CANDIDATE** | ✅ Eigene Kurs-Empfehlung sehen, Fortschritt eintragen, Niveaus-Test starten |
| **EMPLOYER** | ✅ Sprachanforderungen für Stelle definieren, Kandidaten-Fortschritt einsehen |
| **ADMIN** | ✅ Alle Funktionen, Kurs-Daten verwalten |
| **Agent-Ebene** | ✅ Automatische Kurs-Empfehlung bei Bewerbung (wenn Sprachscore < Anforderung) |

## Trigger

- **Manuell:** Kein automatischer Trigger in app.py
- **Auslösung:** HR oder Kandidat startet Niveaus-Test über MCP-Server `language-test-server.py`
- **Grund:** Sprachtests sind Optional, kein Bestandteil des automatischen Bewerbungsflows

---

## Schritte

### 1. Sprachbedarf ermitteln

**Eingabe:** Kandidatenprofil + Stellenanforderung

**Quellen:**
- Kandidat: `testdaten/profil-{kandidat}.md` (Felder: `deutsch`, `englisch`, `französisch`)
- Stelle: `testdaten/stellenprofil-{id}.txt` oder DB `jobs` (Felder: `deutsch_level`, `englisch_level`)

**Logik:**
```
Wenn Kandidat-Deutsch < Stelle-Deutsch:
    → Deutschkurs empfehlen
   Wenn Kandidat-Englisch < Stelle-Englisch:
    → Englischkurs empfehlen
Wenn FR/CH-Stelle UND kein Französisch:
    → Französischkurs empfehlen
```

**Ergebnis:** Liste der benötigten Kurse mit aktuellem und Ziel-Level

### 2. Kursangebote finden

**Zwei Wege:**

#### A) DE/FR/CH-Kurse (Ziel-Land)

**Quelle:** `knowledge/language-courses.md`

**Agent nutzt:**
- `filesystem.read_text_file` → Knowledge-Datei für statische Kurs-Daten
- `anysearch.search` → Aktuelle Kursangebote (Goethe, TELC, lokale Anbieter)

**Suchparameter:**
- Sprache (Deutsch/Englisch/Französisch)
- Niveau (A1→A2, B1→B2, etc.)
- Format (Online/Präsenz/Intensiv)
- Land/Region (DE/FR/CH)
- Kosten (gefördert/privat)

#### B) HEIMATLAND-Suche (NEU — für Kandidaten vor Auswanderung)

**Quelle:** Kandidatenprofil (`nationalitaet`-Feld aus DB)

**Connector:** `anysearch` (anonymous Access, `search`-Tool)

**Ablauf:**
1. Agent liest `nationalitaet` aus Kandidatenprofil (z.B. "Tunesisch")
2. Agent leitet Heimatland + Sprachbedarf ab
3. Agent sucht via `anysearch.search`:

| Sprache | Query-Beispiel | Erwartung |
|---|---|---|
| Deutsch | `"Deutschkurs Tunis"` | Lokale Sprachschulen |
| Deutsch | `"Goethe-Institut Tunesien"` | Filialen (falls vorhanden) |
| Deutsch | `"private Deutschlehrer Tunesien"` | Einzelunterricht |
| Deutsch | `"online Deutsch lernen Tunesien"` | Online-Plattformen |
| Französisch | `"cours allemand Tunisie"` | FR-sprachige Suche |

**Beispiel-Ablauf (Kandidat aus Tunesien):**
```
Kandidat: nationalitaet = "Tunesisch", will Deutsch B2
Agent: anysearch.search("Deutschkurs Tunis")
Ergebnis: Goethe-Institut Tunis + lokale Schulen + italki.com
Empfehlung: "Goethe Tunis ( Präsenz, 800 TND) oder italki (Online, 15 EUR/h)"
```

**Ergebnis:** Max. 5 Kurs-Empfehlungen (lokal + online) mit Name, Anbieter, Kosten, Dauer, Format

### 3. Niveaus-Test (optional)

**Connector:** `language-test` (MCP-Server, scripts/language-test-server.py)

**Ablauf:**
1. Agent ruft `language-test.generate_test(sprache, niv, 10)` auf → 10 Fragen
2. Kandidat beantwortet (Text-Input im Portal)
3. Pro Antwort: Agent ruft `language-test.score_answer(frage_id, antwort, sprache)` auf → LLM bewertet (NVIDIA API)
4. Agent ruft `language-test.get_cefr_level(durchschnitt, sprache)` auf → CEFR-Level
5. Ergebnis: `testdaten/fortschritt-{kandidat}-test-{sprache}-{datum}.md`

**Verfügbare Tests:** DE A1 (10 Seed), EN A2 (10 Seed), FR B2 (10 Seed) + LLM-generiert (unbegrenzt)
**Quellen:** Sprachschule Aktiv München (DE), OpenExamPrep (EN), communfrancais.com DELF B2 (FR)
**Modell:** Hybrid — Seed-Fragen (offiziell) als Basis, LLM generiert zusätzliche Fragen bei Bedarf

### 4. Fortschritt verfolgen

**Datei-Schema:** `testdaten/fortschritt-{kandidat}-{sprache}.md`

```markdown
# Sprachfortschritt – Kandidat #N

| Datum | Aktion | Niveau | Bestanden | Notizen |
|---|---|---|---|---|
| 2026-09-16 | Test: Deutsch | A2→B1 | ✅ (8/10) | Grammatik stark, Wortschatz ok |
| 2026-09-20 | Kurs gestartet | B1 | – | Goethe B1 Intensiv, 4 Wochen |
| 2026-10-18 | Kurs abgeschlossen | B1 | ✅ | Zeugnis erwartet |
```

**Connector:** `filesystem.write_file` (speichern), `filesystem.read_file` (lesen)

### 5. Empfehlung generieren

**Für Kandidaten:**
- Welche Kurse passen zum aktuellen Level
- Welche Kurse das Ziel-Level erreichen
- Kostenübersicht (gefördert vs. privat)

**Für HR:**
- Sprach-Status des Kandidaten
- Offene Lücken zu Stellenanforderung
- Geschätzte Dauer bis Ziel-Level

**Format:** Markdown-Tabelle in `ergebnisse/language-course-kandidat-{N}-{datum}.md`

---

## Connector: contract-check-filesystem

**Zweck:** Fortschritts-Dateien lesen/schreiben (属于 `testdaten/`)

**Nutzung:**
- `read_text_file` → Fortschritt lesen
- `write_file` → Fortschritt aktualisieren
- `glob` → Alle Fortschritts-Dateien finden

**Kein extra Connector nötig** – der bestehende `filesystem`-Connector (in `opencode.json`) deckt das ab.

---

## Regeln

1. **Keine Auto-Empfehlung ohne Kandidaten-Zustimmung** – Kursvorschläge sind Optionen, keine Pflicht
2. **DSGVO:** Sprachtests werden in `testdaten/` gespeichert, gelöscht mit 6-Monats-Frist (wie alle Bewerbungsdaten)
3. **Quellen-Transparenz:** Jede Kurs-Empfehlung mit Anbieter-URL und Kosten (keine erfundenen Werte)
4. **Länder-Routing:** DE → Goethe/TELC/VHS · FR → Alliance Française/CFI · CH → ESL/FSE
5. **Niveau-Tests:** Basierend auf GER (Common European Framework of Reference) – A1 bis C2

---

## Integration mit anderen Skills

| Skill | Verbindung |
|---|---|
| `check-compliance` | Sprachanforderungen aus Stellenprofil → Kurs-Bedarf ableiten |
| `verify-documents` | Sprachzertifikate (Goethe, TELC, IELTS) verifizieren |
| `check-visa` | Sprachniveau für Visa/Blue Card prüfen (§18a/b AufenthG: B1 obligatorisch) |
| `match-candidate` | Sprache als Gewichtungskategorie (aktuell 0%, aktiviert via Feedback-Loop) |
| `assess-culture-fit` | Sprachkompetenz als Kultur-Fit-Indikator |
