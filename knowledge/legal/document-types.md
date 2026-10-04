# Dokumenttypen – Verifizierung (Skill: verify-documents)

> **Stand:** September 2026 (v2 – Herkunfts-Modell: Kandidat vs. HR + Länder-Routing DE/FR/CH) · Quelle für `skills/verify-documents/SKILL.md`
> **Prinzip:** Der Agent erkennt Typen an Signatur-Merkmalen, prüft Pflichtfelder + Plausibilität
> (Indizienprüfung) und markiert alles Sicherheitsrelevante als manuelle Prüfung. **Kein behördlicher
> Echtheitsnachweis.**

---

## 1. Dokumenttypen im Überblick

**Ingestion-Pfad (seit v6.1):** Kandidaten-Dokumente werden im 👤 Candidate Portal → **Tab „🗂️ Dokumente"** hochgeladen (Typ-Auswahl pro Datei, session-gebunden, kein Profil-Overwrite). Ablage: `testdaten/kandidat-{id}-{typ}-{name}`, Registrierung in Tabelle `candidate_documents`. Quelle für Runner-Task `verify_documents` (typed). Visa-/Aufenthaltsdokumente werden von HR beschafft (Arbeitgeberpflicht) — scanned und dem Agenten zur Prüfung vorgelegt.

| Typ | Herkunft | Häufige Formate | Pflichtfelder (Signatur) | Typische Prüfpunkte | Rechtsrahmen |
|---|---|---|---|---|---|
| **Arbeitszeugnis** (Zwischen-/Endzeugnis) | 🧑 **KANDIDAT** | PDF | Aussteller (Firma), Position, Beschäftigungszeitraum, Ausstellungsdatum, Unterschriftszeile | Datumslogik, Konsistenz zum CV, Zeugnissprache-Plausibilität (Geheimcode-Indizien), vollständiger Schlusspartikel | 🇩🇪 BGB § 630, AGG · 🇫🇷 Code du travail · 🇨🇭 OR Art. 319 |
| **Schul-/Studienabschluss** (Bachelor/Master/Abitur) | 🧑 **KANDIDAT** | PDF | Institution, Abschlussgrad, Datum, Notenskala, Matrikel-/Prüfungsnummer (nur Vorhandensein) | Notenskala plausibel (DE 1–5 / ECTS A–F), Datum vs. Studiendauer, Institution existent | Anerkennung: ZAB/anabin (DE, manuell), ENIC-NARIC (FR/CH, manuell) |
| **Berufszertifikat** (AWS, Kubernetes, ITIL, Scrum …) | 🧑 **KANDIDAT** | PDF | Aussteller, Zertifikats-ID, erworben-am-Datum, ggf. Gültigkeit | Gültigkeit noch offen (z. B. AWS 3 Jahre), ID-Format, Aussteller-Schreibweise | – |
| **Sprachzertifikat** (Goethe, telc, TOEFL, IELTS) | 🧑 **KANDIDAT** | PDF | Prüfungsanbieter, GER-Niveau (A1–C2) bzw. TOEFL/IELTS-Score, Prüfungsdatum | Niveau-Konsistenz zum Profil („Deutsch B2"), Datum ≤ 2 Jahre (übliche HR-Praxis) | – |
| **Pass / Personalausweis** *(nur relevante Angaben!)* | 🧑 **KANDIDAT** | PDF (Scan) | Staatsangehörigkeit, Gültig bis, ausstellende Behörde | Gültigkeit noch offen; **KEINE** Volltext-/Nummern-Speicherung | 🇩🇪 PassG · 🇫🇷/🇨🇭 analog · DSGVO/RGPD/DSG Art. 5 (Datenminimierung) |
| **Visum / Aufenthaltstitel / Arbeitserlaubnis** | 🏢 **HR** (Arbeitgeberpflicht: Beschäftigungserlaubnis prüfen und vorlegen) | PDF (Scan) | Typ (z. B. § 18a/b AufenthG, Titre de séjour, AuG-Bewilligung), Gültigkeit, Arbeitserlaubnis-Flag | Gültigkeit, Arbeitgeber-/Beschäftigungsbezug, Ergänzungspass vorhanden? | 🇩🇪 **AufenthG** (§ 4, § 18a/b, § 19c), BeschV · 🇫🇷 Code de l'entrée et du séjour · 🇨🇭 **AuG** (Bewilligung, Kontingente) |
| **Führerschein** (falls stellentyprelevant) | 🧑 **KANDIDAT** | PDF (Scan) | Klassen, Gültigkeit | Klassen decken Stellentyp ab (z. B. B für Außendienst) | 🇩🇪 FeV · 🇫🇷/🇨🇭 analog |

Unbekannter Typ → Status `UNBEKANNT` (Skill-Schritt 2) – HR klassifiziert manuell.

---

## 2. Ergebnis-Skala (Indizienprüfung, kein Urteil)

| Status | Bedeutung | Konsequenz |
|---|---|---|
| `PLAUSIBEL` | Alle Pflichtfelder da, Datumslogik + Profil-Konsistenz ok | Weiter im Prozess (HR entscheidet endgültig) |
| `AUFFAELLIG` | Mindestens 1 Indiz verletzt (fehlendes Feld, Datums-Widerspruch, Profil-Abweichung) | HR prüft das Dokument manuell nach – **keine Auto-Ablehnung** |
| `UNBEKANNT` / `UNLESBAR` | Typ nicht erkennbar / PDF leer-verschlüsselt | handle-errors-Meldung, HR-Entscheidung |
| `MANUELLE_PRUEFUNG_ERFORDERLICH` | Sicherheitsmerkmale, Registerabgleich (anabin, ZAB, Aussteller-Hotline) | Immer zusätzlich zum Status, nie vom Agenten ersetzbar |

---

## 3. Indizien-Checks im Detail (Agent-Ausführung)

1. **Pflichtfelder** gemäß Tabelle §1 – fehlend → `AUFFAELLIG` (Begründung im Bericht)
2. **Datumslogik:** Ausstellung ≤ heute · Gültigkeit > heute (bei befristeten) · Zeiträume widerspruchsfrei
3. **Profil-Konsistenz:** Name/Position/Daten gegen `testdaten/profil-{kandidat}.md` (aus 1️⃣ Extract)
4. **Sprach/Format-Signatur:** erwartete Abschnitte vorhanden (z. B. „Unterschrift", „Ort, Datum")
5. **Länder-Rechtsrahmen (Country-Routing DE/FR/CH)** – IMMER bei Visa-/Aufenthalts-/Arbeitserlaubnis-Dokumenten (Herkunft HR), sonst nur bei FR/CH-Sachverhalten:
   🇩🇪 `ansvar-german-law` (AufenthG, BeschV) · 🇫🇷 `ansvar-french-law` (Code de l'entrée et du séjour) · 🇨🇭 `ansvar-swiss-law` (AuG, ArG); DSGVO/RGPD/DSG Art. 6 Abs. 1 b (Verarbeitungszweck Bewerbungsverfahren)
6. **Nicht agent-prüfbar (immer manuell):** Wasserzeichen/Hologramme/QR-Sicherheit, Registerabgleich, Beglaubigungen

---

## 4. DSGVO-Verarbeitungsregeln für Ausweisdokumente

| Regel | Umsetzung |
|---|---|
| Datenminimierung (Art. 5 Abs. 1 c) | Nur Typ + extrahierte Pflichtfelder + Gültigkeitsjahr in Berichte; **keine** Dokumentennummern, keine Volltext-Kopien |
| Zweckbindung (Art. 5 Abs. 1 b) | Verarbeitung nur im laufenden Bewerbungsverfahren (Art. 6 Abs. 1 b) |
| Löschfristen | Mit dem DSGVO-6-Monate-Job des Portals (`dsgvo_cleanup`); Dokumente in `testdaten/` entsprechend |
| Sichtbarkeit | Bericht nur HR/EMPLOYER (Pseudonym „Kandidat #N"), Agent-Ebene unsichtbar (access-control v4.5) |

---

## 5. Felder für den Verifizierungs-Bericht (Vorlage)

```markdown
# Dokumenten-Verifizierung – Kandidat #N (Datum)

| Dokument | Typ | Pflichtfelder | Indizien | Status |
|---|---|---|---|---|
| zeugnis-mustermann.pdf | Arbeitszeugnis | ✅ vollständig | Datumslogik ✅ · Profil ✅ · Sprache ✅ | PLAUSIBEL |
| zertifikat-aws.pdf | Berufszertifikat | ✅ | Gültigkeit abgelaufen ⚠️ | AUFFAELLIG |
| visum-scan.pdf | Visum (§ 18b AufenthG) | ✅ | Gültigkeit ✅ · Rechtsrahmen ✅ | PLAUSIBEL |
| — | Sicherheitsmerkmale / Register | – | – | MANUELLE_PRUEFUNG_ERFORDERLICH |

**Gesamtstatus:** AUFFAELLIG (1 Indiz)
**Manuelle Prüfpunkte:** anabin-Abgleich Bachelor-Zeugnis · Aussteller-Zertifikat verifizieren
*AI-Hinweis (EU AI Act Art. 50): Automatisierte Indizienprüfung, kein Echtheitsnachweis.*
```
