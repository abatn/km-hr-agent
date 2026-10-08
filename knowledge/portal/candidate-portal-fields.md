# Candidate Portal – Felder und Struktur

> **Stand:** September 2026 (NiceGUI-Referenz ergänzt 20.09.2026)  
> **Ziel:** Kandidaten können sich registrieren, Profil anlegen und Status verfolgen
> **Prinzip:** Wie ein echtes Jobportal – unregistrierte User können NICHTS machen
> **Gegenstück:** `knowledge/portal/employer-portal-fields.md` (Arbeitgeber-Seite), `knowledge/lifecycle/application-status.md` (Bewerbungs-Status)

> **NiceGUI-Umsetzung (Phase 2 am 20.09.2026, Tab-Zahl aktualisiert 02.10.2026)** = `_TAB_MAP` (`webui/pages/candidate.py`, Codemarke, Stand 02.10.2026) (7 Tabs, gerendert via `shell()` aus components.py): 📊 **Dashboard (NEU 01.10.2026, 1. Tab — Nutzerentscheidung: Landing nach Login)** · 👤 Mein Profil (**inkl. Lebenslauf-Upload + 🗂️ Dokumente als aufklappbare Kästen — seit 02.10.2026, frühere Sidebar-Tabs „Upload"/„Dokumente" entfallen**; Status-Historie) · 💼 Stellen · 📨 Bewerbungen (bewerben/zurückziehen) · 🗣️ Sprachtest (**P1.1**: voller Flow generate_test → Scoring → CEFR via MCP → DB) · 📹 Pre-Screen (**P2.2**: eigener VDO.Ninja-Raum seit 27.09.2026 ⓘ08.10.2026 — vorher Jitsi-Raum, Screening-Fragen, MD-Download) · 📋 Onboarding. Streamlit-Ära (app.py): Candidate Portal mit 6 Portal-Tabs + 5 Menü-Seiten.

> **Korrektur 08.10.2026 (VERIFY, Messung ⓘ08.10.2026):** `candidates` hat **22 Spalten** (PRAGMA `table_info`). 7 Felder dieser Datei sind **Phantom-Felder** (keine Spalte, werden nicht gespeichert): `geburtsdatum`, `aktuelles_unternehmen`, `referenzen`, `fachrichtung`, `zertifikate`, `andere_sprachen`, `gehalt_verhandelbar` — in den Tabellen unten durchgestrichen. Umgekehrt fehlte die Code-Spalte `franzoesisch` (optional, jetzt in der Sprachen-Tabelle).

**AKTUELLER STATUS (10.09.2026):**
- ✅ Skills 2-8 sind geschützt (brauchen Lebenslauf-Status)
- ✅ Skills 0-1 sind geschützt (brauchen Login)
- ✅ Login-Schutz implementiert (Session State)
- ✅ Session-Timeout (30 Min, 19.09.2026) + argon2id-Passwort-Hashing (seit 19.09.2026, Migration bei Login) — der frühere „NÄCHSTER SCHRITT" ist umgesetzt

---

## Registrierung (Pflichtfelder)

| Feld | Typ | Beschreibung | Validierung |
|---|---|---|---|
| `email` | Text | E-Mail-Adresse | Muss eindeutig sein |
| `password` | Passwort | Mindestens 8 Zeichen | argon2id-Hash (seit 19.09.2026, Migration bei Login; nicht im Klartext) |
| `name` | Text | Vollständiger Name | Mindestens 2 Zeichen |

---

## Profil (optional, aber empfohlen)

### Persönliche Daten

| Feld | Typ | Beschreibung |
|---|---|---|
| `telefon` | Text | Telefonnummer |
| `standort` | Text | Stadt, Land |
| ~~`geburtsdatum`~~ | Datum | **PHANTOM** — keine Spalte in `candidates` (PRAGMA ⓘ08.10.2026), wird nicht gespeichert |
| `nationalitaet` | Text | Staatsangehörigkeit |
| `visum_status` | Auswahl | EU-Bürger / Arbeitsvisum / Kein Visum / Sonstiges |
| `verfuegbarkeit` | Auswahl | Sofort / 1 Monat / 3 Monate / Kündigungslaufzeit |

### Berufserfahrung

| Feld | Typ | Beschreibung |
|---|---|---|
| `berufserfahrung_jahre` | Zahl | Gesamte Berufserfahrung in Jahren |
| `aktuelle_position` | Text | Aktuelle Stellenbezeichnung |
| ~~`aktuelles_unternehmen`~~ | Text | **PHANTOM** — keine Spalte in `candidates` (PRAGMA ⓘ08.10.2026), wird nicht gespeichert |
| ~~`referenzen`~~ | Text | **PHANTOM** — keine Spalte in `candidates` (PRAGMA ⓘ08.10.2026), wird nicht gespeichert |

### Skills & Bildung

| Feld | Typ | Beschreibung |
|---|---|---|
| `hard_skills` | Liste | Technische Fähigkeiten (kommasepariert) |
| `soft_skills` | Liste | Persönliche Fähigkeiten |
| `abschluss` | Auswahl | Bachelor / Master / Diplom / PhD / Sonstiges |
| ~~`fachrichtung`~~ | Text | **PHANTOM** — keine Spalte in `candidates` (PRAGMA ⓘ08.10.2026), wird nicht gespeichert |
| ~~`zertifikate`~~ | Liste | **PHANTOM** — keine Spalte in `candidates` (PRAGMA ⓘ08.10.2026), wird nicht gespeichert |

### Sprachen

| Feld | Typ | Beschreibung |
|---|---|---|
| `deutsch` | Auswahl | A1 / A2 / B1 / B2 / C1 / C2 / Muttersprache |
| `englisch` | Auswahl | A1 / A2 / B1 / B2 / C1 / C2 / Muttersprache |
| `franzoesisch` | Auswahl | A1–C2/Muttersprache — **optional** (Code-Whitelist `_PROFIL_SPALTEN`, nur editierbar falls Spalte existiert; Live-DB ohne Spalte, PRAGMA ⓘ08.10.2026) |
| ~~`andere_sprachen`~~ | Text | **PHANTOM** — keine Spalte in `candidates` (PRAGMA ⓘ08.10.2026), wird nicht gespeichert |

### Gehaltsvorstellung

| Feld | Typ | Beschreibung |
|---|---|---|
| `gehaltsvorstellung` | Zahl | Brutto-Jahresgehalt in EUR |
| ~~`gehalt_verhandelbar`~~ | Checkbox | **PHANTOM** — keine Spalte in `candidates` (PRAGMA ⓘ08.10.2026), wird nicht gespeichert |

### Lebenslauf

| Feld | Typ | Beschreibung |
|---|---|---|
| `lebenslauf_datei` | Datei | PDF, DOCX oder TXT |
| `lebenslauf_text` | Text | Automatisch extrahierter Text |

---

## Profil-Vollständigkeit (Pflichtfelder für Matching)

| Kategorie | Pflichtfelder | Mindestens |
|---|---|---|
| **Persönliches** | name, email, standort | 3 von 3 |
| **Erfahrung** | berufserfahrung_jahre, hard_skills | 2 von 2 |
| **Sprachen** | deutsch, englisch | 2 von 2 |
| **Gehalt** | gehaltsvorstellung | 1 von 1 |
| **Lebenslauf** | lebenslauf_datei | 1 von 1 |

**Gesamt:** 9 Pflichtfelder müssen ausgefüllt sein.

**Status-Logik:**
- `registriert` → Nur Email + Name
- `profil_vollstaendig` → Alle 9 Pflichtfelder ausgefüllt
- `lebenslauf_hochgeladen` → + Lebenslauf-Datei
- `match_berechnet` → Erst wenn `lebenslauf_hochgeladen`

**Regel:** Matching (Skill 2) nur wenn Status ≥ `lebenslauf_hochgeladen`

**Ergänzung 29.09.2026 (P0-1, Design-Entscheidung, `cv-pflicht.md` (g)): `profil_vollstaendig` gilt nur **ohne** Lebenslauf; ein Profil-Save mit vorhandenem CV setzt/hebt auf `lebenslauf_hochgeladen` und darf bestehende Status nie absenken (damit „Bewerben" nach dem Speichern nie dauerhaft gesperrt ist).

---

## Status-Tracking

| Status | Beschreibung | Sichtbar für Kandidaten |
|---|---|---|
| `registriert` | Konto angelegt | ✅ |
| `profil_vollstaendig` | Alle Pflichtfelder ausgefüllt | ✅ |
| `lebenslauf_hochgeladen` | Datei vorhanden | ✅ |
| `profil_geprueft` | HR hat Profil angeschaut | ✅ |
| `match_berechnet` | Score vorhanden | ✅ |
| `eingeladen` | Interview-Einladung verschickt | ✅ |
| `abgelehnt` | Nicht passend | ✅ |
| `eingestellt` | Vertrag unterschrieben | ✅ |

---

## SQLite-Schema

```sql
CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name TEXT NOT NULL,
    telefon TEXT,
    standort TEXT,
    geburtsdatum TEXT,
    nationalitaet TEXT,
    visum_status TEXT DEFAULT 'EU-Bürger',
    verfuegbarkeit TEXT DEFAULT 'Sofort',
    berufserfahrung_jahre INTEGER,
    aktuelle_position TEXT,
    aktuelles_unternehmen TEXT,
    hard_skills TEXT,
    soft_skills TEXT,
    abschluss TEXT,
    fachrichtung TEXT,
    zertifikate TEXT,
    deutsch TEXT DEFAULT 'B1',
    englisch TEXT DEFAULT 'B1',
    andere_sprachen TEXT,
    gehaltsvorstellung INTEGER,
    gehalt_verhandelbar INTEGER DEFAULT 1,
    lebenslauf_datei TEXT,
    lebenslauf_text TEXT,
    status TEXT DEFAULT 'registriert',
    registriert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    aktualisiert_am TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS candidate_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    changed_by TEXT,
    notizen TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id)
);
```

---

## Read-View Anzeige (NiceGUI) — 12 Speicher-Felder

> **Stand:** 22.09.2026 (P1, Profil-Parität)
> **Quelle Speicher-Liste:** `app.py:2798-2806` (UPDATE candidates SET …, 12 Parameter + cand_id)
> **Quelle Edit-Formular:** `app.py:2779-2795`
> **Umsetzung:** `webui/pages/candidate.py` `_tab_profil()` Read-View (expansionsloser Karten-Block vor „Profil bearbeiten")
> **Regel:** Jedes der 12 Felder, die `save_profile()` in die DB schreibt, MUSS vor dem Edit-Expander lesbar angezeigt werden (Parität zur Streamlit-Read-View).

| # | Feld (DB) | Anzeige-Karte | NiceGUI-Helfer | Quelle Edit (Streamlit) |
|---|---|---|---|---|
| 1 | `standort` | Persönliche Daten | `info_row` | `app.py:2779` |
| 2 | `nationalitaet` | Persönliche Daten | `info_row` | `app.py:2780` |
| 3 | `visum_status` | Persönliche Daten | `info_row` | `app.py:2781` |
| 4 | `verfuegbarkeit` | Persönliche Daten | `info_row` | `app.py:2782` |
| 5 | `aktuelle_position` | Persönliche Daten | `info_row` | `app.py:2784` |
| 6 | `berufserfahrung_jahre` | Berufserfahrung | `stat_card` | `app.py:2785` |
| 7 | `hard_skills` | Fachkompetenzen | `skill_chip` | `app.py:2786` |
| 8 | `soft_skills` | Fachkompetenzen | `info_row` | `app.py:2787` |
| 9 | `abschluss` | Berufserfahrung | `info_row` | `app.py:2791` |
| 10 | `deutsch` | Sprachen | `info_row` | `app.py:2792` |
| 11 | `englisch` | Sprachen | `info_row` | `app.py:2793` |
| 12 | `gehaltsvorstellung` | Gehaltsvorstellung (eigene Karte) | `stat_card` | `app.py:2795` |

**Bereits vor P1 vorhanden (unverändert):** `name`, `email`, `status` (Persönliche Daten), Status-Historie-Karte, Passwort-Expander.

**Nicht in der 12er-Liste (kein Speichern, nur Anzeige optional):** `telefon`, `geburtsdatum` (Feature-Freeze, Spec-feld nur) — werden NICHT zur Read-View hinzugefügt.

---

## API-Endpunkte (Streamlit)

| Aktion | Skill | Connector |
|---|---|---|
| Registrieren | `candidate-portal` | SQLite |
| Profil anlegen | `candidate-portal` | SQLite |
| Lebenslauf hochladen | `candidate-portal` | filesystem |
| Status abrufen | `candidate-portal` | SQLite |
| Profil bearbeiten | `candidate-portal` | SQLite |
| Passwort ändern | `candidate-portal` | SQLite |

---

## Passwort ändern (N5, 20.09.2026)

> **Design-Entscheidung** (Lab-Prinzip 1: keine externe Quelle für Passwort-Policy in diesem Projekt):
> - **Regel:** Mindestens 8 Zeichen.
> - **Warum:** Minimale Sicherheitsanforderung, konsistent mit Registrierung (candidate-portal-fields.md Z.23).
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

### Rollen

| Rolle | Implementierung | Stelle |
|---|---|---|
| CANDIDATE | Expander "🔒 Passwort ändern" | Tab "👤 Mein Profil" |
| EMPLOYER | Expander "🔒 Passwort ändern" | Seite "🏢 Portal" |
| ADMIN | Expander "🔒 Passwort ändern" | Admin-Seite |

---

*Erstellt am 10.09.2026 für den KM-HR-Agenten. Aktualisiert am 02.10.2026 (7 Tabs: Upload/Dokumente in 👤 Mein Profil integriert, keine eigenen Sidebar-Tabs mehr; 📊 Dashboard als 1. Tab, Nutzerentscheidung 01.10.2026); zuvor 20.09.2026 (NiceGUI-_TAB_MAP-Referenz, argon2id).*
