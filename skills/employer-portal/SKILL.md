---
description: Arbeitgeber-Portal – Registrierung, Stellen ausschreiben, Kandidaten sehen, Feedback geben
---

## Funktionierende MCP-Connectors

| Connector | Tool | Zweck |
|---|---|---|
| `filesystem` | `read_text_file` | Feld-Definitionen + Knowledge-Dateien lesen |
| `filesystem` | `write_file` | Stellenprofile + Berichte speichern |
| `meeting-tools` | `generate_ics_file` | Interview-Termine (optional) |
| `email-sender` | `send_email` | Interview-Einladungen an Kandidaten |

**Connector für die UI:** SQLite (lokal, kostenlos) – Tabellen `employers`, `jobs`, `job_status_history` in `data/feedback.db`. Siehe `knowledge/portal/employer-portal-fields.md` für das vollständige Schema.

**Ist-Umsetzung (NiceGUI, verifiziert 09.10.2026):** Der Skill ist als Skill #10 im **NiceGUI**-Employer-Portal umgesetzt (`webui/pages/employer.py`), nicht mehr in Streamlit. **12 Seiten** seit 13.10.2026 (`PAGE_MAP`, Codemarke; `grep -n "^PAGE_MAP = {" webui/pages/employer.py`): 📊 Dashboard, 📝 Firmenprofil (eigene Seite `firmenprofil`), 🏢 Portal (Stelle ausschreiben), 💼 Stellenangebote, 🔍 Kandidaten-Suche, 📄 Match-Ergebnis, ✅ Compliance, 🔎 Agent-Details, 🗂️ Dokumente, 📞 Pre-Screen, 📋 Onboarding, 💬 Feedback.

**Hinweis:** Lab-Prinzip – kein eigener Code. Der Skill definiert NUR Workflow, Regeln und Felder. Die Umsetzung erfolgt als NiceGUI-Seitenerweiterung analog zum Candidate Portal (Login-Schutz, Tabs, SQLite).

**Zugriff (v4.2, `knowledge/system/access-control.md`):** Das Arbeitgeber-Portal ist NUR in EMPLOYER/HR-Sessions sichtbar. Dasselbe gilt für die Recruiting-Skills 0–8 (Upload, Extract Profile, Match Candidate, …, Store Feedback) mit dem Kandidat-Selector: Diese Seiten gehören zur HR-Sicht und sind für CANDIDATE-Sessions nicht sichtbar/nutzbar (Rollen-Sichtbarkeit + Session-Bindung).

---

## Schritte

### 1. Registrierung (Arbeitgeber)

**Eingabe:** email, password, firma, kontaktperson

**Validierung:**
- Email: Eindeutig, kein Doppel
- Password: Mindestens 8 Zeichen
- Firma: Mindestens 2 Zeichen
- Kontaktperson: Mindestens 2 Zeichen

**Aktion:**
- SQLite: `INSERT INTO employers (email, password_hash, firma, kontaktperson) VALUES (?, ?, ?, ?)`
- Passwort: **argon2id**-Hash (nicht im Klartext) – `webui/logic.py` (Codemarke `def hash_password_argon2id`, gemessen 10.10.2026); SHA256 existiert nur noch als **Migrationspfad** für Alt-Hashes (`verify_password_sha256`/`is_sha256_hash`, transparente Umstellung bei Login, Phase 3.2)

**Rückgabe:** "Registrierung erfolgreich. Bitte Firmenprofil vervollständigen."

---

### 2. Firmenprofil anlegen/bearbeiten

**Eingabe:** employer_id, feld-wert-paare

**Erlaubte Felder:** branche, groesse, standort, website, beschreibung, telefon, kontakt_email

**Aktion:**
- SQLite: `UPDATE employers SET [feld] = ?, aktualisiert_am = CURRENT_TIMESTAMP WHERE id = ?`

**Rückgabe:** "Firmenprofil aktualisiert."

---

### 3. Stelle ausschreiben

**Eingabe:** employer_id, titel, beschreibung, standort, stellentyp, hard_skills, soft_skills, berufserfahrung_jahre, deutsch_level, englisch_level, abschluss (+ optionale Konditionen)

**Pflichtfelder:** titel, beschreibung (≥ 50 Zeichen), standort, stellentyp, hard_skills

**Aktion:**
- SQLite: `INSERT INTO jobs (employer_id, titel, beschreibung, standort, stellentyp, hard_skills, soft_skills, berufserfahrung_jahre, deutsch_level, englisch_level, abschluss, gehaltsrahmen_min, gehaltsrahmen_max, nice_to_have) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
- Status automatisch: `aktiv`

**Rückgabe:** "Stelle ausgeschrieben: [titel]. Kandidaten-Matching ist jetzt möglich."

---

### 4. Kandidaten sehen (anonymisiert)

**Eingabe:** job_id

**Voraussetzungen:**
- Stelle hat Status `aktiv`
- Arbeitgeber ist eingeloggt und Besitzer der Stelle

**Matching-Regel (siehe knowledge/portal/employer-portal-fields.md):**
1. Kandidat-Status ≥ `lebenslauf_hochgeladen`
2. Mindestens 1 Must-Have-Skill-Übereinstimmung
3. Berufserfahrung ≥ 50% der Anforderung

**Scoring:** Wie Skill 2 (match-candidate) – Score 0–100 mit Kategorien.

**Aktion:**
- SQLite: `SELECT id, hard_skills, soft_skills, berufserfahrung_jahre, deutsch, englisch, standort, status FROM candidates WHERE status IN ('lebenslauf_hochgeladen', 'profil_geprueft', 'match_berechnet', 'eingeladen')`
- Score je Kandidat berechnen (LLM oder Keyword-Matching wie Skill 2)

**DSGVO-Anonymisierung:**
- ❌ KEINE Kontaktdaten (email, telefon, lebenslauf_datei)
- ⚠️ Name nur als Pseudonym: `Kandidat #[id]`
- ⚠️ Gehalt nur als Kompatibilitätshinweis (passt / passt nicht zum Gehaltsrahmen)

**Rückgabe (Ranking-Liste):**
```
1. Kandidat #12 – 92/100 (Hervorragend) – 5/5 Must-Have-Skills – München
2. Kandidat #7  – 81/100 (Gut) – 4/5 Must-Have-Skills – Remote
3. Kandidat #3  – 67/100 (Bedingt) – 3/5 Must-Have-Skills – München
```

---

### 5. Feedback geben

**Eingabe:** job_id, kandidat_id (pseudonym), score, kategorie, bewertungen (1–5), eingeladen, anmerkungen

**Aktion:**
- SQLite: `INSERT INTO feedback (match_id, kandidat_name, stellenprofil, score, kategorie, fachlich_korrekt, skills_richtig, standort_zutreffend, empfehlung_hilfreich, eingeladen, anmerkungen) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
- Wiederverwendet die bestehende `feedback`-Tabelle (siehe knowledge/lifecycle/feedback-schema.md)
- `match_id`-Format: `employer-job-[job_id]-cand-[candidate_id]-[datum]`
- Optional: Gewichtung anpassen wie Skill 8 (store-feedback)

**Rückgabe:** "Feedback gespeichert. Matching-Gewichtung wird angepasst."

---

### 6. Stelle verwalten (Status ändern)

**Eingabe:** job_id, neuer_status (aktiv / pausiert / besetzt / abgelaufen)

**Aktion:**
- SQLite: `UPDATE jobs SET status = ? WHERE id = ?`
- SQLite: `INSERT INTO job_status_history (job_id, status, changed_by) VALUES (?, ?, ?)`

**Rückgabe:** "Stellen-Status geändert: [status]"

---

### 7. Bewerber verwalten (NEU Phase 1 – Job-Seeker-Flow)

**Eingabe:** job_id (oder employer_id für alle Stellen)

**Voraussetzungen:**
- Arbeitgeber ist eingeloggt und Besitzer der Stelle

**Aktion (Bewerber-Liste):**
- SQLite: `SELECT a.id, a.candidate_id, a.status, a.bewerbungstext, a.erstellungsdatum, j.titel FROM applications a JOIN jobs j ON a.job_id = j.id WHERE j.employer_id = ? AND a.status IN ('eingegangen', 'angesehen', 'eingeladen') ORDER BY a.erstellungsdatum ASC`
- Bewerber werden im Kandidaten-Tab ZUERST gelistet (mit Match-Score gegen die jeweilige Stelle, wie Schritt 4), danach die passiven Matches.

**Sichtbarkeit (siehe knowledge/portal/employer-portal-fields.md, Bewerber-Sichtbarkeit):**
- Pseudonym "Kandidat #N", vollständiges anonyisiertes Profil + Bewerbungstext
- ❌ KEINE Kontaktdaten – erst nach Status `eingeladen` (Kontaktfreigabe beidseitig)
- Zieht der Kandidat zurück (`zurückgezogen`), verschwindet der Eintrag aus der Liste

**Aktionen (Status ändern, siehe knowledge/lifecycle/application-status.md):**
- `angesehen`: automatisch beim Öffnen der Bewerbung, oder manuell
  - SQLite: `UPDATE applications SET status = 'angesehen', aktualisiert_am = CURRENT_TIMESTAMP WHERE id = ?`
  - SQLite: `INSERT INTO application_status_history (application_id, status, changed_by) VALUES (?, 'angesehen', 'arbeitgeber')`
- `eingeladen`: entrevista-Einladung via Skill 4 (contact-candidate) – danach sind Kontaktdaten freigegeben
- `abgelehnt`: mit optionaler, sachlicher Begründung (max. 500 Zeichen, AGG-konform)
- `eingestellt`: zusätzlich Stellen-Status auf `besetzt` setzen (Schritt 6)
- Bei JEDEM Statuswechsel: Eintrag in `application_status_history` (changed_by = 'arbeitgeber')

**Rückgabe:** Bewerber-Liste mit Status-Badges + Aktions-Buttons (Ansehen / Einladen / Ablehnen / Einstellen).

---

## UI-Umsetzung (Umsetzungshinweis)

**Integration in `webui/pages/employer.py` (NiceGUI). Historischer Nachtrag – Streamlit-Ära (`app.py`, abgeschaltet 23.09.2026):** Die unten stehenden Punkte 1–5 beschreiben die ursprüngliche Streamlit-Integration und sind **nicht mehr gültig**; die aktuelle NiceGUI-Umsetzung ist oben (Ist-Umsetzung) und in `knowledge/system/access-control.md` dokumentiert.

1. **Login:** Eigene Tabs "🔑 Arbeitgeber-Login" / "📝 Arbeitgeber-Registrieren" auf dem bestehenden Login-Bildschirm (Trennung von Kandidaten-Accounts durch `employers`-Tabelle)
2. **Session State:** `employer_logged_in`, `employer_email`, `employer_firma`, `employer_id` *(NiceGUI: `app.storage.user`)*
3. **Sidebar-Eintrag:** Neuer Punkt "🏢 Arbeitgeber-Portal" in der Skills-Navigation
4. **Tabs im Portal:** `📝 Firmenprofil` | `📢 Stellen` | `👥 Kandidaten` | `💬 Feedback` *(NiceGUI-Ist: 12 Seiten, siehe oben)*
5. **Zugriffsregel:** Kandidaten-Liste nur wenn mindestens 1 Stelle mit Status `aktiv`

**Test-Szenario (E2E):**
1. Arbeitgeber registriert sich → `employers`-Eintrag exists
2. Stelle ausgeschrieben → `jobs`-Eintrag mit Status `aktiv`
3. Passende Kandidaten sichtbar → Ranking-Liste anonymisiert, Scores vorhanden
4. Feedback gegeben → `feedback`-Eintrag mit match_id
5. (NEU Phase 1) Kandidat bewirbt sich (Skill `job-application`) → Bewerber erscheint ZUERST im Kandidaten-Tab
6. (NEU Phase 1) Statuswechsel angesehen → eingeladen → Kandidat sieht Status in "Meine Bewerbungen"

---

## Beispiel-Aufrufe

### Registrieren
```json
{
  "action": "register_employer",
  "email": "hr@techvision.de",
  "password": "sicher123",
  "firma": "TechVision GmbH",
  "kontaktperson": "Max Mustermann"
}
```

### Stelle ausschreiben
```json
{
  "action": "create_job",
  "employer_id": 1,
  "titel": "Senior Cloud/DevOps Engineer",
  "beschreibung": "Aufbau und Betrieb unserer AWS-Infrastruktur mit Kubernetes...",
  "standort": "München",
  "stellentyp": "Vollzeit",
  "hard_skills": "AWS, Kubernetes, Terraform, CI/CD",
  "soft_skills": "Teamführung, Kommunikation",
  "berufserfahrung_jahre": 5,
  "deutsch_level": "B2",
  "englisch_level": "C1",
  "abschluss": "Master",
  "gehaltsrahmen_min": 75000,
  "gehaltsrahmen_max": 95000
}
```

### Kandidaten abrufen
```json
{
  "action": "list_candidates",
  "job_id": 1
}
```

### Feedback geben
```json
{
  "action": "give_feedback",
  "job_id": 1,
  "candidate_id": 12,
  "score": 92,
  "kategorie": "Hervorragend",
  "bewertungen": {
    "fachlich_korrekt": 5,
    "skills_richtig": 5,
    "standort_zutreffend": 4,
    "empfehlung_hilfreich": 5
  },
  "eingeladen": "Ja",
  "anmerkungen": "Sehr gutes K8s-Profil, Terraform-Lücke vorhanden"
}
```

---

## Klappen/Ausklappen (23.09.2026, Playwright 18/18)

- **Match-Ergebnis:** pro Kandidat×Job `ui.expansion` (default zu); Header (`add_slot("header")`) = Titel + score_bar + `total/100 (kategorie)`; Gehalt, 7 Erklaerungs-Balken, „Erklaerung", Visa/Ics nur bei geöffneter Klappe; **Einladen/Ablehnen/Einstellen bleiben immer sichtbar** (Human-in-the-loop Variante A). Parität: `app.py` (gemessen 10.10.2026) `st.expander`. Achtung: `ui.timer(15s)`-Refresh setzt Klappen auf zu.
- **Agent-Details → Detaillierte Berichte:** 9× `ui.expansion(f"{icon} {label} ({datei})")` (`webui/pages/employer.py` (gemessen 10.10.2026)) = `app.py` (gemessen 10.10.2026) – Toggle geprüft.
- **Agent-Details → Task-Queue (Datenbank):** `ui.expansion("Task-Queue (Datenbank)", icon="database", value=False)` (employer.py:~984) – Design-Entscheidung (Queue = NiceGUI-Eigenbau C5, kein Streamlit-Pendant); Statusfilter + Refresh bleiben innen funktionsfähig.
- Doku-Quelle: nicegui.io/documentation/expansion (`value` default False, `add_slot("header")`, `.open()/.close()`, aria `Expand/Collapse`).
- Rollback: `/tmp/opencode/rollback/employer.py.bak` → zurück, `py_compile`, Server-Neustart (Kill/Spawn getrennt).

---

*Erstellt am 11.09.2026 für den KM-HR-Agenten.*
