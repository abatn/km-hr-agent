---
description: Kandidaten-Portal – Registrierung, Profil anlegen, Status verfolgen
---

## Funktionierende MCP-Connector

| Connector | Tool | Zweck |
|---|---|---|
| `filesystem` | `read_text_file` | Knowledge-Dateien + Profile lesen |
| `filesystem` | `write_file` | Kandidaten-Daten speichern |
| `pdf-reader` | `read_pdf_text` | Lebenslauf-Text extrahieren |

**Hinweis:** Alles lokal, kein Code nötig. SQLite für Datenbank.

**Zugriff (v4.2, `knowledge/system/access-control.md`):** Das Candidate Portal ist NUR in CANDIDATE-Sessions sichtbar (HR-Sessions: kein Zugriff). Alle Tabs (Profil/Lebenslauf/Status) sind SESSION-GEBUNDEN: Sie wirken ausschließlich auf `app.storage.user['user_cand_id']` (NiceGUI-Session, Helfer `_session()` in `webui/pages/candidate.py`) – kein Kandidat-Dropdown, keine fremden Profile editierbar (DSGVO-Datenselbstverwaltung).

---

## Schritte

### 1. Registrierung

**Eingabe:** email, password, name

**Validierung:**
- Email: Eindeutig, kein Doppel
- Password: Mindestens 8 Zeichen
- Name: Mindestens 2 Zeichen

**Aktion:**
- SQLite: `INSERT INTO candidates (email, password_hash, name, status) VALUES (?, ?, ?, 'registriert')`
- Passwort: **argon2id**-Hash (nicht im Klartext; SHA256 nur als Migrationspfad – transparente Re-Hashung bei Login, Phase 3.2, `webui/logic.py`)

**Rückgabe:** "Registrierung erfolgreich. Bitte Profil vervollständigen."

---

### 2. Profil anlegen/bearbeiten

**Eingabe:** candidate_id (= `app.storage.user['user_cand_id']`, NICHT frei wählbar), feld-wert-paare

**Erlaubte Felder:**
- Persönliche Daten: telefon, standort, geburtsdatum, nationalitaet, visum_status, verfuegbarkeit
- Erfahrung: berufserfahrung_jahre, aktuelle_position, aktuelles_unternehmen
- Skills: hard_skills, soft_skills, abschluss, fachrichtung, zertifikate
- Sprachen: deutsch, englisch, andere_sprachen
- Gehalt: gehaltsvorstellung, gehalt_verhandelbar

**Aktion:**
- SQLite: `UPDATE candidates SET [feld] = ?, aktualisiert_am = CURRENT_TIMESTAMP WHERE id = ?`
- Status-Prüfung: Wenn alle Pflichtfelder ausgefüllt → Status = `profil_vollstaendig` — **nur solange kein Lebenslauf vorliegt**; mit CV darf der Save den Status nie absenken (bzw. `registriert`/`profil_vollstaendig` → `lebenslauf_hochgeladen`). Quelle: `knowledge/portal/cv-pflicht.md` (g), Design-Entscheidung 29.09.2026

**Rückgabe:** "Profil aktualisiert. Status: [status]"

---

### 3. Lebenslauf hochladen

**Eingabe:** candidate_id, datei (PDF/DOCX/TXT)

**Schritte:**
1. Datei in `testdaten/` speichern
2. Text extrahieren (PDF → pdf-reader, TXT → filesystem)
3. SQLite: `UPDATE candidates SET lebenslauf_datei = ?, lebenslauf_text = ?, status = 'lebenslauf_hochgeladen' WHERE id = ?`

**Rückgabe:** "Lebenslauf hochgeladen. Text extrahiert: [Zeichen] Zeichen."

---

### 3b. Dokumente hochladen (Tab 🗂️ Dokumente — Spec v6.1)

**Eingabe:** candidate_id, datei (PDF/TXT), dokumententyp (Auswahl: `Zeugnis` · `Zertifikat` · `Sprachzeugnis` · `Pass` · `Visum/Aufenthaltstitel` · `Sonstiges`)

**Regeln:**
- Mehrere Dateien pro Typ erlaubt (jede Datei = eigener Eintrag)
- **KEIN** Überschreiben von `candidates.lebenslauf_*` und **KEIN** Statuswechsel — nur der Lebenslauf (Schritt 3) ändert das Profil
- Session-gebunden: Upload wirkt ausschließlich auf `app.storage.user['user_cand_id']` (DSGVO-Datenselbstverwaltung)
- Kandidat kann eigene Einträge im selben Tab löschen (Art. 17 Selbstservice)

**Schritte:**
1. Datei speichern: `testdaten/kandidat-{id}-{typ}-{originalname}`
2. SQLite: `INSERT INTO candidate_documents (candidate_id, datei_pfad, dokumententyp) VALUES (?, ?, ?)`
3. Liste der eigenen Dokumente (mit Typ + Datum) im Tab anzeigen; Löschen-Button je Eintrag (Datei + Zeile)

**Rückgabe:** "Dokument gespeichert: [Typ] ([Dateiname])."

**Verbraucher:** Runner-Task `verify_documents` (Spec v6) liest `candidate_documents` als TYPED-Quelle — der LLM-Prompt erhält „[Typ]: [Datei]" statt eines blinden Glob.

**DSGVO:** `dsgvo_cleanup()` löscht candidate_documents-Zeilen + Dateien 6 Monate nach Prozessende (gleiches Fenster wie Bewerbungsdaten, gdpr-policy.md).

---

### 4. Status abrufen

**Eingabe:** candidate_id oder email

**Aktion:**
- SQLite: `SELECT status, registriert_am, aktualisiert_am FROM candidates WHERE id = ?`

**Rückgabe:**
```
Status: profil_vollstaendig
Registriert: 10.09.2026 20:30
Zuletzt aktualisiert: 10.09.2026 20:45
```

---

### 5. Status-Verlauf anzeigen

**Eingabe:** candidate_id

**Aktion:**
- SQLite: `SELECT status, changed_at, notizen FROM candidate_status_history WHERE candidate_id = ? ORDER BY changed_at DESC`

**Rückgabe:**
```
10.09.2026 20:45 – profil_vollstaendig
10.09.2026 20:35 – lebenslauf_hochgeladen
10.09.2026 20:30 – registriert
```

---

## Connectors für Streamlit-UI

| Skill | Tool | Connector |
|---|---|---|
| `candidate-register` | INSERT INTO candidates | SQLite |
| `candidate-profile` | UPDATE candidates | SQLite |
| `candidate-upload` | read_pdf_text + UPDATE | pdf-reader + SQLite |
| `candidate-status` | SELECT FROM candidates | SQLite |
| `candidate-history` | SELECT FROM candidate_status_history | SQLite |

---

## Beispiel-Aufrufe

### Registrieren
```json
{
  "action": "register",
  "email": "max.mustermann@example.de",
  "password": "sicher123",
  "name": "Max Mustermann"
}
```

### Profil anlegen
```json
{
  "action": "update_profile",
  "candidate_id": 1,
  "fields": {
    "standort": "München",
    "hard_skills": "Python, AWS, Kubernetes",
    "deutsch": "Muttersprache",
    "englisch": "C1"
  }
}
```

### Status abrufen
```json
{
  "action": "get_status",
  "candidate_id": 1
}
```

---

*Erstellt am 10.09.2026 für den KM-HR-Agenten.*
