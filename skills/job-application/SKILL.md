---
description: Job-Application – Aktive Stellen ansehen, sich bewerben, Bewerbungsstatus verfolgen (Kandidaten-Seite)
---

## Funktionierende MCP-Connectors

| Connector | Tool | Zweck |
|---|---|---|
| `filesystem` | `read_text_file` | Feld-Definitionen + Knowledge-Dateien lesen |
| `filesystem` | `write_file` | Bewerbungs-Bestätigungen / Berichte speichern |
| `email-sender` | `send_email` | Bewerbungs-Bestätigung an Kandidaten (optional) |

**Connector für NiceGUI-UI (`webui/pages/candidate.py`):** SQLite (lokal, kostenlos) – neue Tabellen `applications`, `application_status_history` in `data/feedback.db`. Siehe `knowledge/portal/employer-portal-fields.md` (Schema) und `knowledge/lifecycle/application-status.md` (Status-Lebenszyklus).

**Hinweis:** Lab-Prinzip – kein eigener Code. Der Skill definiert NUR Workflow, Regeln und Felder. Die Umsetzung erfolgt in der NiceGUI-UI (`webui/pages/candidate.py`) analog zum Candidate Portal und Employer Portal (Login-Schutz, Tabs, SQLite).

---

## Voraussetzungen (Jobportal-Prinzip)

- Kandidat ist **eingeloggt** (Session `user_logged_in = True`) – unregistrierte User sehen keine Stellen.
- Kandidat-Status ≥ `lebenslauf_hochgeladen` (**Lebenslauf ist PFLICHT** vor Bewerbung – entscheidet der Nutzer, bestätigt 11.09.2026). Ohne CV: Stellen ansehen ja, Bewerben nein (Fehlermeldung mit Hinweis auf Upload).
- Stelle hat Status `aktiv` (gepausierte/besetzte/abgelaufene Stellen sind nicht bewerbbar).

---

## Schritte

### 1. Stellenangebote ansehen (Job-Browse)

**Eingabe:** keine (Liste wird automatisch gefiltert)

**Aktion:**
- SQLite: `SELECT j.id, j.titel, j.beschreibung, j.standort, j.stellentyp, j.hard_skills, j.soft_skills, j.berufserfahrung_jahre, j.deutsch_level, j.englisch_level, j.abschluss, j.gehaltsrahmen_min, j.gehaltsrahmen_max, e.firma, e.branche, e.groesse FROM jobs j JOIN employers e ON j.employer_id = e.id WHERE j.status = 'aktiv' ORDER BY j.erstellt_am DESC`

**Sichtbar pro Stelle (Kandidaten-Sicht):**

| Feld | Sichtbar |
|---|---|
| Titel, Beschreibung, Standort, Stellentyp | ✅ |
| Must-Have-Skills, Soft-Skills, geforderte Jahre, Sprach-Level, Abschluss | ✅ |
| Gehaltsrahmen (min–max) | ✅ (falls gesetzt) |
| Firmenname, Branche, Größe | ✅ |
| Arbeitgeber-Kontaktperson, Telefon, E-Mail | ❌ NEIN (DSGVO – erst nach Einladung) |
| Bewerber-Liste der Stelle | ❌ NEIN |

**Filter (optional):** Standort enthält Text, Stellentyp, Mindestens-1-Skill-Übereinstimmung mit eigenem Profil.

**Rückgabe:** Stellenliste mit Bewerbungs-Button pro Stelle.

---

### 2. Bewerben (Application erstellen)

**Eingabe:** job_id, bewerbungstext (optional, max. 2000 Zeichen)

**Validierung:**
- Stelle existiert und hat Status `aktiv`
- Kandidat ist eingeloggt
- Kandidat-Status ≥ `lebenslauf_hochgeladen` (CV-PFLICHT – sonst Fehlermeldung "Bitte zuerst Lebenslauf hochladen")
- Noch KEINE bestehende Bewerbung dieses Kandidaten auf diese Stelle (`UNIQUE(candidate_id, job_id)`)

**Aktion:**
- SQLite: `INSERT INTO applications (candidate_id, job_id, status, bewerbungstext) VALUES (?, ?, 'eingegangen', ?)`
- SQLite: `INSERT INTO application_status_history (application_id, status, changed_by) VALUES (?, 'eingegangen', 'kandidat')`
- Optional: Bestätigungs-E-Mail an Kandidaten (email-sender)

**Rückgabe:** "Bewerbung eingegangen. Der Arbeitgeber sieht Ihre Bewerbung anonymisiert als 'Kandidat #[id]'."

---

### 3. Bewerbungsstatus verfolgen (Meine Bewerbungen)

**Eingabe:** candidate_id (aus Session)

**Aktion:**
- SQLite: `SELECT a.id, a.job_id, j.titel, e.firma, a.status, a.erstellungsdatum, a.aktualisiert_am FROM applications a JOIN jobs j ON a.job_id = j.id JOIN employers e ON j.employer_id = e.id WHERE a.candidate_id = ? ORDER BY a.erstellungsdatum DESC`

**Status-Anzeige:** Wie `knowledge/lifecycle/application-status.md` – Kandidat sieht jeden Statuswechsel inkl. Datum. Bei `abgelehnt`: optionale, sachliche Begründung des Arbeitgebers.

**Kandidaten-Aktionen:**
- `zurückziehen` (nur solange Status NOT IN (`eingestellt`, `zurückgezogen`)):
  - SQLite: `UPDATE applications SET status = 'zurückgezogen', aktualisiert_am = CURRENT_TIMESTAMP WHERE id = ? AND candidate_id = ?`
  - SQLite: `INSERT INTO application_status_history (application_id, status, changed_by) VALUES (?, 'zurückgezogen', 'kandidat')`

**Rückgabe:** Bewerbungsliste mit Status-Badges + Zurückziehen-Button.

---

## DSGVO-Regeln (siehe knowledge/lifecycle/application-status.md)

- Rechtsgrundlage: Art. 6(1)(b) – Kandidat bewirbt sich aktiv.
- Arbeitgeber sieht Bewerbung anonymisiert (Pseudonym "Kandidat #N") – Kontaktdaten erst nach Status `eingeladen`.
- Löschung: 6 Monate nach Prozessende (wie `gdpr-policy.md`).
- Doppelbewerbung: durch `UNIQUE(candidate_id, job_id)` ausgeschlossen; erneute Bewerbung nach Zurückzug/Ablehnung auf dieselbe Stelle nicht möglich.

---

## NiceGUI-UI-Erweiterung (Umsetzungshinweis)

1. **Sidebar-Eintrag:** Neuer Punkt "💼 Stellenangebote" (nur für eingeloggte Kandidaten sichtbar)
2. **Tabs:** `🔎 Stellenangebote` | `📨 Meine Bewerbungen`
3. **Zugriffsregel:** Arbeitgeber-Session sieht diese Seite NICHT (Trennung der Sessions wie bei Candidate/Employer Portal)
4. **Bewerben-Button:** Pro Stelle, mit optionalen Motivationstext-Textfeld (Expander)

## Test-Szenario (E2E):
1. Kandidat registriert sich und loggt ein → sieht "💼 Stellenangebote"; Bewerben-Button gesperrt mit Hinweis (CV-Pflicht)
2. Kandidat lädt Lebenslauf hoch → Stellen aktiv sichtbar, Bewerbung möglich
3. Aktive Stelle sichtbar (Titel, Firma, Skills, Gehalt) – KEINE Arbeitgeber-Kontaktdaten
4. Kandidat bewirbt sich → `applications`-Eintrag mit Status `eingegangen`
5. Doppelbewerbung abgefangen → Hinweis mit bestehendem Status
6. Arbeitgeber (employer-portal Schritt 7) sieht Bewerber zuerst in seiner Kandidaten-Liste
7. Arbeitgeber lädt ein → Status `eingeladen`, Kandidat sieht Statuswechsel in "Meine Bewerbungen"
8. Kandidat zieht zurück → Status `zurückgezogen`, Eintrag verschwindet aus Arbeitgeber-Sicht

---

## Beispiel-Aufrufe

### Stellen ansehen
```json
{
  "action": "list_jobs",
  "filter": { "standort": "München", "stellentyp": "Vollzeit" }
}
```

### Bewerben
```json
{
  "action": "apply",
  "candidate_id": 2,
  "job_id": 1,
  "bewerbungstext": "Ich bringe 5 Jahre AWS/Kubernetes-Erfahrung mit und möchte mich auf diese Position bewerben."
}
```

### Bewerbungen verfolgen
```json
{
  "action": "list_my_applications",
  "candidate_id": 2
}
```

### Zurückziehen
```json
{
  "action": "withdraw",
  "application_id": 1,
  "candidate_id": 2
}
```

---

*Erstellt am 11.09.2026 für den KM-HR-Agenten (Phase 1: Job-Seeker-Flow).*
