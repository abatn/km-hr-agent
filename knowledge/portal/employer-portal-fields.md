# Employer Portal – Felder und Struktur

> **Stand:** September 2026 (erweitert um Bewerbungs-Flow, Phase 1)  
> **Ziel:** Arbeitgeber können sich registrieren, Stellen ausschreiben, passende Kandidaten sehen UND Bewerbungen verwalten  
> **Prinzip:** Lab-Muster – kein eigener Code, nur Skills + Knowledge + Connector (SQLite + Streamlit-UI)  
> **Gegenstück:** `knowledge/portal/candidate-portal-fields.md` (Kandidaten-Seite), `knowledge/lifecycle/application-status.md` (Bewerbungs-Status)

---

## Registrierung (Pflichtfelder)

| Feld | Typ | Beschreibung | Validierung |
|---|---|---|---|
| `email` | Text | Firmen-E-Mail | Muss eindeutig sein |
| `password` | Passwort | Mindestens 8 Zeichen | argon2id-Hash (seit 19.09.2026, Migration bei Login; nicht im Klartext) |
| `firma` | Text | Firmenname | Mindestens 2 Zeichen |
| `kontaktperson` | Text | Ansprechpartner | Mindestens 2 Zeichen |

---

## Firmenprofil (optional, aber empfohlen)

### Unternehmensdaten

| Feld | Typ | Beschreibung |
|---|---|---|
| `branche` | Auswahl | IT / Consulting / Industrie / Handel / Gesundheit / Finanzen / Sonstiges |
| `groesse` | Auswahl | 1–10 / 11–50 / 51–200 / 201–1000 / 1000+ Mitarbeiter |
| `standort` | Text | Stadt, Land (Hauptstandort) |
| `website` | Text | Firmen-Website (optional) |
| `beschreibung` | Text | Kurzprofil des Unternehmens (max. 500 Zeichen) |

### Kontakt

| Feld | Typ | Beschreibung |
|---|---|---|
| `telefon` | Text | Telefonnummer (optional) |
| `kontakt_email` | Text | Abweichende Kontakt-E-Mail (optional, default: Registrierungs-E-Mail) |

---

## Stellenprofil (für jede ausgeschriebene Stelle)

### Stammdaten (Pflichtfelder)

| Feld | Typ | Beschreibung | Validierung |
|---|---|---|---|
| `titel` | Text | Stellenbezeichnung (z.B. "Senior Cloud/DevOps Engineer") | Mindestens 3 Zeichen |
| `beschreibung` | Text | Aufgabenbeschreibung | Mindestens 50 Zeichen |
| `standort` | Text | Arbeitsort | Pflicht |
| `land` | Text | Zielland (DE/FR/CH) | Pflicht, Default: DE |
| `stellentyp` | Auswahl | Vollzeit / Teilzeit / Freelance / Hybrid / Remote | Pflicht |

### Anforderungen (Pflichtfelder für Matching)

| Feld | Typ | Beschreibung | Beispiel |
|---|---|---|---|
| `hard_skills` | Liste | Must-Have-Skills (kommasepariert) | AWS, Kubernetes, Terraform |
| `soft_skills` | Liste | Soft-Skills (kommasepariert) | Teamführung, Kommunikation |
| `berufserfahrung_jahre` | Zahl | Mindestens erforderliche Jahre | 5 |
| `deutsch_level` | Auswahl | A1 / A2 / B1 / B2 / C1 / C2 / Muttersprache / Keine Anforderung | B2 |
| `englisch_level` | Auswahl | A1–C2 / Muttersprache / Keine Anforderung | C1 |
| `abschluss` | Auswahl | Bachelor / Master / PhD / Egal | Master |

### Konditionen (optional)

| Feld | Typ | Beschreibung |
|---|---|---|
| `gehaltsrahmen_min` | Zahl | Brutto-Jahresgehalt von (EUR) |
| `gehaltsrahmen_max` | Zahl | Brutto-Jahresgehalt bis (EUR) |
| `nice_to_have` | Liste | Nice-to-Have-Skills (kommasepariert) |

---

## Doppelklick-Schutz beim Veröffentlichen (Doppel-Submit-Schutz)

**Regel:** Eine Stellenanzeige wird **nur einmal** gespeichert.

- Der Absende-Button ist während des Speicherns gesperrt (Codemarke `create_job`) und wird danach wieder freigegeben.
- Das Formular wird nach Erfolg zurückgesetzt (Textfelder), damit ein zweiter Klick keine identische Stelle anlegt (Codemarke `create_job`).
- `insert_job` unterdrückt identische Wiederholungen (gleicher `employer_id`+`titel`+`standort`) innerhalb eines kurzen Zeitfensters (≤ 60 s): es legt **keine** zweite Zeile an, sondern gibt idempotent die bestehende `job_id` zurück (Codemarke `insert_job`).

**Kennzeichnung:** **Design-Entscheidung** (Lab-Prinzip 1 — keine externe Quelle). Anlass: Live-Vorfall 11.10.2026, Doppelklick speicherte dieselbe Stelle zweimal (`jobs` #10/#11, employer_id 3, 16 s Abstand, UTC).

---

## Status-Lebenszyklus einer Stelle

| Status | Beschreibung | Sichtbar für Arbeitgeber |
|---|---|---|
| `aktiv` | Stelle ausgeschrieben, Matching möglich | ✅ |
| `pausiert` | Temporär deaktiviert, keine neuen Matches | ✅ |
| `besetzt` | Kandidat eingestellt | ✅ |
| `abgelaufen` | Nach 90 Tagen automatisch | ✅ |

---

## Kandidaten-Sichtbarkeit (Datenschutz / DSGVO)

**Regel:** Arbeitgeber sehen KEINE Kontaktdaten oder den vollständigen Lebenslauf.

| Daten | Sichtbar für Arbeitgeber? |
|---|---|
| Anonymisiertes Profil (Skills, Erfahrung, Sprachen, Standort-Region) | ✅ Ja |
| Match-Score + Kategorie | ✅ Ja |
| Kandidaten-Name | ⚠️ Nur Pseudonym (z.B. "Kandidat #12") |
| E-Mail, Telefon, Lebenslauf-Datei | ❌ Nein – erst nach Kandidaten-Zustimmung (Einladung) |
| Gehaltsvorstellung | ⚠️ Nur als Spanne-Kompatibilität (✅ passt / ❌ zu weit auseinander) |

**Grund:** DSGVO Art. 6(1)(b) – Datenminimierung. Kontakt nur über Einladungs-Workflow (Skill 4: Contact Candidate).

---

## Bewerber-Sichtbarkeit (Datenschutz / DSGVO – NEU Phase 1)

**Regel:** Ein Kandidat, der sich aktiv auf eine Stelle bewirbt, hat mit der Bewerbung sein Einverständnis gegeben (Art. 6(1)(b) – vorvertragliche Maßnahmen), dass sein Profil für DIESE Stelle geprüft wird.

| Daten | Passiver Match (nur Ranking) | Aktiver Bewerber |
|---|---|---|
| Anonymisiertes Profil (Skills, Erfahrung, Sprachen, Standort) | ✅ Ja | ✅ Ja (vollständig, inkl. Bewerbungstext) |
| Match-Score + Kategorie | ✅ Ja | ✅ Ja (Bewerber zuerst gelistet) |
| Pseudonym | ✅ "Kandidat #N" | ⚠️ "Kandidat #N" – echten Namen erst nach `eingeladen` |
| Bewerbungstext | ❌ | ✅ Ja |
| E-Mail, Telefon, Lebenslauf-Datei | ❌ Nein | ❌ Nein – erst nach Status `eingeladen` (Kontaktfreigabe beidseitig) |

**Rangfolge im Arbeitgeber-Tab "Kandidaten":** Aktive Bewerber (Status `eingegangen`/`angesehen`) werden ZUERST gelistet, danach die passiven Matches.

**Rückzug:** Zieht der Kandidat die Bewerbung zurück (Status `zurückgezogen`, siehe `application-status.md`), verschwindet sein Eintrag aus der Bewerber-Liste des Arbeitgebers.

---

## SQLite-Schema (neue Tabellen)

```sql
-- Tabelle: employers
CREATE TABLE IF NOT EXISTS employers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    firma TEXT NOT NULL,
    kontaktperson TEXT NOT NULL,
    branche TEXT,
    groesse TEXT,
    standort TEXT,
    website TEXT,
    beschreibung TEXT,
    telefon TEXT,
    kontakt_email TEXT,
    registriert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    aktualisiert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabelle: jobs
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employer_id INTEGER NOT NULL,
    titel TEXT NOT NULL,
    beschreibung TEXT NOT NULL,
    standort TEXT NOT NULL,
    land TEXT DEFAULT 'DE',
    stellentyp TEXT NOT NULL,
    hard_skills TEXT NOT NULL,
    soft_skills TEXT,
    berufserfahrung_jahre INTEGER,
    deutsch_level TEXT DEFAULT 'Keine Anforderung',
    englisch_level TEXT DEFAULT 'Keine Anforderung',
    abschluss TEXT DEFAULT 'Egal',
    gehaltsrahmen_min INTEGER,
    gehaltsrahmen_max INTEGER,
    nice_to_have TEXT,
    status TEXT DEFAULT 'aktiv',
    erstellt_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    aktualisiert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employer_id) REFERENCES employers(id)
);

-- Tabelle: job_status_history
CREATE TABLE IF NOT EXISTS job_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    changed_by TEXT,
    notizen TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

-- Tabelle: applications (NEU Phase 1 – Kandidat bewirbt sich auf Stelle)
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL,
    status TEXT DEFAULT 'eingegangen',
    bewerbungstext TEXT,
    erstellungsdatum TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    aktualisiert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (candidate_id, job_id),
    FOREIGN KEY (candidate_id) REFERENCES candidates(id),
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

-- Tabelle: application_status_history (NEU Phase 1)
CREATE TABLE IF NOT EXISTS application_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    changed_by TEXT,
    notizen TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (application_id) REFERENCES applications(id)
);
```

**Bestehende Tabellen werden wiederverwendet:** `candidates` (siehe candidate-portal-fields.md), `feedback` (siehe feedback-schema.md).

**Status-Lebenszyklus für `applications`:** siehe `knowledge/lifecycle/application-status.md` (eingegangen → angesehen → eingeladen → abgelehnt/eingestellt, plus zurückgezogen durch Kandidaten).

---

## Kandidaten-Matching (Regelwerk)

Ein Kandidat erscheint in der Kandidaten-Liste einer Stelle, wenn:

1. Kandidat-Status ≥ `lebenslauf_hochgeladen` (Jobportal-Prinzip)
2. Stelle hat Status `aktiv`
3. Mindestens 1 Must-Have-Skill-Übereinstimmung
4. Berufserfahrung ≥ 50% der Anforderung (Rundung nach unten)

**Ranking:** Wie Skill 2 (match-candidate) – Score 0–100, Kategorien Hervorragend/Gut/Bedingt/Schwach/Nicht passend.

---

## Zugriffskontrolle (Jobportal-Prinzip)

| Aktion | Kein Konto | Registriert (Arbeitgeber) | Mit Stelle (aktiv) |
|---|---|---|---|
| Registrieren | ✅ | – | – |
| Stellen ausschreiben | ❌ | ✅ | ✅ |
| Kandidaten sehen | ❌ | ❌ (erst mit aktiver Stelle) | ✅ (anonymisiert) |
| Bewerber sehen | ❌ | ❌ | ✅ (Bewerber zuerst, dann passive Matches) |
| Bewerbungs-Status ändern | ❌ | ❌ | ✅ (angesehen / eingeladen / abgelehnt / eingestellt) |
| Feedback geben | ❌ | ❌ | ✅ |

**Kandidaten-Seite (Gegenstück, NEU Phase 1):** eingeloggte Kandidaten können aktive Stellen sehen und sich bewerben – siehe Skill `job-application`.

---

## Employer-Portal Sidebar (Streamlit-Ära: 8 Seiten, 17.09.2026; NiceGUI: 10 Seiten, 20.09.2026 Phase 1)

> **NiceGUI-Umsetzung** = `webui/pages/employer.py` (Codemarke `PAGE_MAP`, gemessen 10.10.2026) (PAGE_MAP, 11 Einträge; Zeilenstand 28.09.2026 — war 1492-1503): 📊 Dashboard · 🏢 Portal (Firmenprofil + Stellen, **P1.2 portiert 20.09.2026**) · 💼 **Stellenangebote (HR-write, 20.09.2026: Bewerber-Status-Verwaltung + Archiv)** · 🔍 Kandidaten-Suche (Bewerber-Verwaltung: einladen/ablehnen/**eingestellt** mit onboarding_release-Trigger, **P1.3 portiert 20.09.2026**) · 📄 Match (read-only + Visum-Klick, GAP-3) · ✅ Compliance · 🔎 Agent-Details · 🗂️ Dokumente · 📞 Pre-Screen · 📋 Onboarding · 💬 Feedback (voll, GAP-2). Die folgende Tabelle dokumentiert die Streamlit-Sidebar (inkl. 4-Tab-Portal) als historische Referenz.

| Seite | Beschreibung | Nur lesen? |
|---|---|---|
| 📝 Firmenprofil | Firmen-Daten bearbeiten | ❌ Schreibend |
| 📢 Stellen | Stellen ausschreiben/pausieren | ❌ Schreibend |
| 👥 Kandidaten | Bewerber + Passive Matches + Agent-Badges | ⚠️ Lesen + Status ändern |
| 💬 Feedback | Bewertung abgeben | ❌ Schreibend |
| 2️⃣ Match-Ergebnis | Match-Bericht aus ergebnisse/ | ✅ Read-only |
| 3️⃣ Compliance-Ergebnis | Compliance-Bericht aus ergebnisse/ | ✅ Read-only |
| **🔍 Agent-Details** | **ALLE 9 Agent-Ergebnisse** (NEU 17.09.2026) | ✅ Read-only |
| 6️⃣ Pre-Screen | VDO.Ninja-Link + ICS-Download | ✅ Read-only |
| 7️⃣ Generate Onboarding | Onboarding-Checkliste | ❌ Schreibend |
| 8️⃣ Store Feedback | Bewertungsformular | ❌ Schreibend |
| 💼 Stellenangebote | Job-Liste | ⚠️ Abhängig |
| 🏢 Arbeitgeber-Portal | 4-Tab-Portal (Firmenprofil, Stellen, Kandidaten, Feedback) | ⚠️ Gemischt |

Formularfeld `Eingeladen?`: Optionen/Semantik → knowledge/lifecycle/feedback-schema.md („UI-Optionsliste", O3 23.09.2026).

### 🔍 Agent-Details Seite (NEU 17.09.2026)

**Zweck:** Zeigt ALLE Agent-generierten Ergebnisse für einen gewählten Kandidaten an einer Stelle.

**Badge-Zeile (Status-Übersicht):**
- 🟢 Grün = POSITIV (PLAUSIBEL, COMPLIANT, KONFORM, NICHT ERFORDERLICH)
- 🔴 Rot = NEGATIV (AUFFÄLLIG, ERFORDERLICH, NICHT_COMPLIANT, NICHT_KONFORM)
- 🟡 Gelb = UNSICHER (UNBEKANNT, andere Status)
- ⚪ Grau = NICHT VORHANDEN (kein Bericht)

**9 Agent-Tasks (Expander):**
1. 📋 Extract Profile – strukturiertes Profil aus Lebenslauf
2. 🎯 Match Candidate – Score 0-100 mit Kategorien
3. ⚖️ Check Compliance – AGG/DSGVO/EU AI Act
4. 🏢 Assess Culture-Fit – Kultur-Fit-Bewertung
5. 📄 Verify Documents – Dokumenten-Prüfung (AUFFÄLLIG/PLAUSIBEL)
6. 🛂 Check Visa – Visum-Bedarf (ERFORDERLICH/NICHT ERFORDERLICH)
7. 🔒 Check GDPR – DSGVO-Compliance (KONFORM/NICHT KONFORM)
8. 💡 Explain Match – Detaillierte Score-Erklärung
9. 📧 Notify User – Benachrichtigung

**Datenquelle:** `ergebnisse/*.md` (Agent-Berichte)

### 👥 Kandidaten-Tab: Agent-Badges (NEU 17.09.2026)

Im Kandidaten-Expander werden zusätzlich zu Match-Score und Status-Aktionen auch Agent-Badges angezeigt:
- 🔴/🟢 verify_documents Badge
- 🔴/🟢 check_visa Badge
- 🔴/🟢 check_gdpr Badge (wenn vorhanden)
- 💡 explain_match Expander (wenn vorhanden)

### ✅ Compliance-Seite — Datenquellen (R3-3, 30.09.2026, GO „A")

**Block 1 = Primärquelle: `ergebnisse/check_compliance-kandidat-*.md`**
(17 Dateien, read-only Vorab-Befund 30.09.2026; `compliance_protokoll` hat KEINEN Writer).

Berichts-Schema (an allen 17 Dateien verifiziert):

| Baustein | Muster / Wert |
|---|---|
| Dateiname | `check_compliance-kandidat-<kandidat_id>-<YYYY-MM-DD>.md` |
| Titelzeile | `# Check Compliance – Kandidat #<id> / Stelle #<job_id>` → **job_id** |
| Status | `Compliance-Status: COMPLIANT` bzw. `NICHT_COMPLIANT` (+ ggf. Text hinten) |
| Begründung | eigene Zeile mit uneinheitlichem Label (`Begründung:` / `Justification:` / `Grund:` / `Justierung:`) **oder ohne Label** als Fließtext |
| Werteverteilung | 15× `COMPLIANT` (3× mit angehängtem Text), 2× `NICHT_COMPLIANT` |

Parser (Modulfunktionen in `webui/pages/employer.py`):
- `_compliance_berichte(employer_id, ordner=None) -> list[dict]` — glob + Parsing + Zurechnung, jüngste zuerst; `ordner` = Verzeichnis-Override für Tests (Design-Entscheidung).
- `_compliance_status(text) -> (status, begruendung)` — `NICHT_COMPLIANT` wird zuerst geprüft (Substring-Falle `COMPLIANT`), Label wird abgetrennt.

**Zurechnung:** Titelzeile → `job_id` → `jobs.employer_id` (`applications` hat KEINE employer_id — Schema-Fakt; unter pytest greift der Spiegel aus `tests/conftest.py`).
Nicht existierende Stellen bzw. fremde Arbeitgeber werden **gezählt, nicht verschwiegen**: UI-Hinweis „ℹ️ N Berichte sind keiner eigenen Stelle zuzuordnen …".

**Block 2 = Archiv (bleibt, GO):** `compliance_protokoll` über `_compliance_rows` (P1-9-Guard: match_id-Schema `employer-job-<job>-cand-<cand>-<datum>`), sichtbar unter dem Label „🗄️ Archiv: compliance_protokoll (Legacy)".

**UI:** Kartenliste (Status-Badge roh `COMPLIANT`/`NICHT_COMPLIANT`, Datum, Kandidaten-Klarname mit Fallback `Kandidat #id`, Stellen-Titel, Zurechnung `(Stelle #x · Kandidat #y)`) + `ui.expansion("Begründung")` — Layout = Design-Entscheidung.

**Tests:** `tests/test_r33_compliance_reports.py` (Schema/Attribution/Nicht-zuordenbar), `tests/e2e_compliance_reports.py` (Login → ✅ Compliance → echter Bericht + Archiv-Block sichtbar).

### 🔔 Benachrichtigungen bei Statuswechsel (R3-5, 30.09.2026, GO „A: Anbinden")

| Baustein | Wert |
|---|---|
| Auslöser | die 3 HR-Klick-Ziel-Status **`eingeladen` / `abgelehnt` / `eingestellt`** |
| Handler | `do_invite` / `do_reject` / `do_hire` (📄 Match) **und** `make_transition` (💼 Stellenangebote) — jeweils **NACH** erfolgreichem `UPDATE` + `commit` |
| Helper | `webui/pages/employer.py` (Codemarke `def _notify_statuswechsel`, gemessen 10.10.2026) |
| Query | `applications` → `JOIN jobs` → `JOIN employers` (candidate_id + Firma + Stellen-Titel) |
| Schreibung | EINE Zeile `notifications(user_id = candidate_id, role = 'candidate', titel = 'Bewerbungsstatus', nachricht = …, gelesen = 0)` |
| Nachricht | `Deine Bewerbung bei <Firma> für <Titel>: <Status>` |
| Anzeige | Kandidaten-Portal-Drawer (`components.py::notifications_drawer`, role `candidate`, N-D2) |

**Design-Entscheidung (Text/Quelle):** kein externes Vorbild nötig — der Text ist Verhalten, nicht ein Wert. Er nennt Firma und Stelle, aber **keinen Grund/Ablehnungsdetail** (AGG-neutral, Parität zur neutralen Ablehnungs-Mail des Runners) und läuft in der **Erzeugungs-/Session-Sprache** des auslösenden HR-Nutzers (E2, `knowledge/system/i18n.md`; Code nutzt `_()`, Codemark `def _notify_statuswechsel`). Der Status-Slug `{2}` selbst bleibt als DB-Rohwert deutsch (Negativregel).

**Defensiv:** andere Status (`angsehen` usw.), unbekannte `application_id`, leere/fremde Rows → **keine** Zeile; jeder Fehler im Helper wird abgefangen (`try/except` + `print`, db-Konvention) und blockiert den Handler nie.

**Tests:** `tests/test_r35_status_notify.py` (3 Status → je 1 Zeile, unbeteiligt → 0, Fehlerfall, AST-Bindung der 4 Call-Sites), `tests/e2e_transition_guard.py` Sektion D (echter Klick „→ eingeladen" → Zeile in der Spiegel-DB, danach Restore).

---

## Passwort ändern (N5, 20.09.2026)

> **Design-Entscheidung** (Lab-Prinzip 1: keine externe Quelle für Passwort-Policy in diesem Projekt):
> - **Regel:** Mindestens 8 Zeichen.
> - **Warum:** Minimale Sicherheitsanforderung, konsistent mit Registrierung (employer-portal-fields.md Z.15).
> - **Alternative:** Komplexitäts-Regeln (Groß-/Kleinbuchstaben, Zahlen, Sonderzeichen) — verworfen (OWASP 2024: Länge > Komplexität).
> - **Validierung:** `len(neues_pw) >= 8`. Kein Maximal-Limit (argon2id hat interne Grenzen).

### Felder

| Feld | Typ | Pflicht | Beschreibung |
|---|---|---|---|
| `altes_pw` | Passwort | ✅ | Aktuelles Passwort (argon2id oder SHA256-Migrations-Pfad) |
| `neues_pw` | Passwort | ✅ | Neues Passwort (min. 8 Zeichen) |
| `neues_pw_wdh` | Passwort | ✅ | Wiederholung (muss übereinstimmen) |

### Verhalten

| Fall | Ausgabe |
|---|---|
| Altes PW falsch | Fehler: "Altes Passwort ist nicht korrekt." |
| Neues PW zu kurz (< 8) | Fehler: "Neues Passwort muss mindestens 8 Zeichen lang sein." |
| Wiederholung stimmt nicht | Fehler: "Passwörter stimmen nicht überein." |
| Erfolg | Erfolg: "Passwort geändert." + DB-Update (argon2id-Hash) |

---

*Erstellt am 11.09.2026 für den KM-HR-Agenten. Erweitert am 17.09.2026 um Agent-Details Seite. Aktualisiert am 20.09.2026 (NiceGUI-PAGE_MAP-Referenz, argon2id, P1.2/P1.3-Vermerke, N5 Passwort ändern).*

---

## Match-Dialog-Semantik (NB1+NB4, 23.09.2026)

- **Ablehnen (Match-Dialog):** schließt ALLE aktiven Bewerbungen des Kandidaten bei diesem Employer (Aktiv-IN-Liste `eingegangen`/`angesehen`/`eingeladen`) — UPDATE + History je Bewerbung, GENAU EIN `send_rejection`-Task mit `{application_id: neueste aktive, candidate_id, trigger: hr_klick_portal}`.
- **Einladen / Einstellen:** handeln ausschließlich die neueste aktive Bewerbung (`LIMIT 1`, dieselbe Aktiv-IN-Liste); beide Payloads (`create_invitation`, `onboarding_release`) tragen zusätzlich `candidate_id`.
- **Kein aktiver Treffer** (z. B. nur Terminal-Status): Fehler-`ui.notify` „Keine aktive Bewerbung", kein DB-Write, kein Task.
- **Terminal-Status unantastbar:** `eingestellt`, `abgelehnt`, `zurückgezogen` werden von keinem der 3 Dialoge geändert (erl-Matrix `webui/pages/employer.py` (gemessen 10.10.2026)).
- **Identity-Regel:** Dialog-States speichern die Candidate-ID (`_reject_cid`/`_invite_cid`/`_hire_cid`); die echte `application_id` wird am Queue-Punkt per SELECT (employer-JOIN, id DESC) aufgelöst — Spec: `knowledge/system/agent-automation.md` §4, Identity-Regel.
- **NB5 (behoben, 23.09.2026):** alle `'zurueckgezogen'`-Filter (ASCII) auf `'zurückgezogen'` (UTF-8-ü, DB-Sollwert) umgestellt: `webui/pages/employer.py` (gemessen 10.10.2026) + Label, `webui/pages/candidate.py` (gemessen 10.10.2026), `webui/pages/admin.py` (gemessen 10.10.2026), `scripts/agent-runner.py` (gemessen 10.10.2026), `app.py` (gemessen 10.10.2026) (Parität). Sweep 0, App 22-Verifikation bestanden.

---

## Feedback-Picker-Bindung (N-F1, 29.09.2026)

**Regel:** Die Seite 💬 Feedback hat genau **ein** Kandidaten-Picker-Widget. `refresh_cands()` zerstört den alten Select (`cand_container.clear()`) und baut einen neuen auf — deshalb **muss der Stellen-Handler den Rückgabewert neu binden** (`nonlocal cand_select`), statt ihn zu verwerfen:

- `save_feedback` liest danach **immer den aktuell sichtbaren Picker** (keine tote Referenz auf den Kandidaten der VORHERIGEN Stelle).
- Rückgabewert `None` (Stelle ohne Kandidaten) wird vom bestehenden Guard abgefangen (`if not cand_select …`) statt stillschweigend mit dem alten Kandidaten zu speichern.
- Ein Widget, keine Duplikate: `cand_container.clear()` bleibt (kein zweites Select im DOM).

**Roter Beweis vor Fix (29.09.2026):** `python3 tests/e2e_feedback_jobswitch.py` → Picker zeigt `taoufik` (#13), gespeichert wird `match_id='employer-job-6-cand-1-…'` (Kandidat X der alten Stelle) → FAIL. **Nach Fix:** PASS (dieser Test ist der Dauer-Nachweis).
**Quelle:** Design-Entscheidung (ui-analyse N-F1 → P0-Hochstufung = Datenintegrität, `feedback.match_id` UNIQUE + Feedback-Loop; Entschiedung siehe `ergebnisse/entscheidungen.md` #92).
