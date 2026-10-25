# KM-HR-Agent Skills

## Skill-Architektur

Der KM-HR-Agent besteht aus folgenden Skills, die auf MCP-Connectoren basieren:

### Core Skills (immer aktiv)

| Skill | Beschreibung | MCP-Connector | Tool |
|---|---|---|---|
| `extract-profile` | Lebenslauf → Strukturiertes Profil + **DB-Update (NEU 17.09.2026)** | filesystem + pdf-reader | read_text_file + read_pdf_text |
| `match-candidate` | Profil vs. Stelle → Match-Score | filesystem + LLM (Agent) | read_text_file + write_file |
| `explain-match` | Score → Detaillierte Begründung | filesystem | read_text_file |
| `check-compliance` | Länderspezifische Prüfung | filesystem + ansvar-*-law | read_text_file + validate_citation |
| `check-gdpr` | DSGVO-Compliance | filesystem | read_text_file |
| `assess-culture-fit` | Kultur-Fit-Bewertung | filesystem | read_text_file |
| `generate-onboarding` | Onboarding-Checkliste | filesystem | write_file |
| `store-feedback` | Feedback speichern | filesystem | write_file |
| `handle-errors` | Fehler protokollieren + Nutzermeldungen | filesystem | write_file |
| `employer-portal` | Arbeitgeber: Registrierung, Stellen ausschreiben, Kandidaten + Bewerber sehen, Feedback | filesystem + SQLite | read_text_file + write_file |
| `job-application` | Kandidat: Stellenangebote ansehen, bewerben, Bewerbungsstatus verfolgen | filesystem + SQLite | read_text_file + write_file |
| `verify-documents` | Dokumente prüfen: Zeugnisse/Zertifikate (Kandidat) + Visa/Arbeitserlaubnis (HR) – Länder-Routing DE/FR/CH | pdf-reader + ansvar-german/french/swiss-law + filesystem | read_pdf_text + validate_citation + write_file |
| `check-visa` | Visum-, Arbeitserlaubnis- und Anerkennungs-Check für internationale Kandidaten (DE/FR/CH) | filesystem + ansvar-german/french/swiss-law | read_text_file + validate_citation + write_file |
| `language-course` | Sprachkurs-Integration: DE/EN/FR-Kurse finden + Heimatland-Suche (anysearch), Niveaus-Tests, Fortschritt | filesystem + pdf-reader + language-test + anysearch + ansvar-*-law | read_text_file + write_file + read_pdf_text + search + generate_test + score_answer + get_cefr_level |
| `mentoring` | Mentoring/Patenschaft (Phase D P10, User-GO 24.09.2026, implementiert): HR-Klick-Vergabe §2A, separate Tabelle `mentoring` §3C, `{MENTOR}`-Befüllung in Generator + Mail #6 + Report, Lebenszyklus vorgeschlagen→aktiv→beendet | filesystem + email-sender | read_text_file + write_file + send_email |
| `housing-search` | Wohnungssuche-Checkliste + freie Quellen im Onboarding-Report (Phase D P6, **implementiert 24.09.2026**): Info-Orchestrierung, kein Scraping, kein neuer Tab | filesystem + fetch + anysearch | read_text_file + write_file + fetch + search |
| `contract-management` | Contract Preflight (Phase D P8, **implementiert 24.09.2026**): Gehalt ≥ Mindestlohn (Link-Katalog), Formfall-Hinweise (§14/§126a/§623), NachwG-15-Punkte-Checkliste, Vertragsskelett; **Signatur A–F bleibt User-Wahl** | filesystem + ansvar-german-law + fetch | read_text_file + write_file + fetch |
| `contact-candidate` | Kontaktiert Kandidaten per E-Mail (Interview-Einladung) | filesystem + email-sender | read_text_file + send_email |
| `pre-screen` | Pre-Screening: Fragen + VDO.Ninja-Raum + ICS | filesystem + meeting-tools | read_text_file + generate_screening_questions + generate_ics_file |
| `candidate-portal` | Kandidaten-Portal: Registrierung, Profil, Lebenslauf, Dokumente, Passwort ändern, Status | filesystem + SQLite | read_text_file + write_file |
| `export-report` | Match-Ergebnisse als PDF/Excel exportieren | filesystem | write_file |
| `notify-user` | Benachrichtigungen bei Top-Matches (E-Mail) | filesystem + email-sender | read_text_file + send_email |
| `nicegui-migration` | Migration Streamlit→NiceGUI: framework-freie Layer (webui/db.py + logic.py) + webui/-App, Phasen-Doku + Inventar-Pflege | filesystem + SQLite | read_text_file + write_file |

### Entfernte Skills (nie implementiert)

**Kein je implementierter Skill wurde entfernt.** Ein rein konzeptioneller
Ghost-Eintrag (nie angelegt, Verzeichnis + SKILL.md fehlten) wurde am
24.09.2026 aus dieser Liste bereinigt — Herleitung, Beweis und Konsequenz
stehen in `ergebnisse/entscheidungen.md` (Phase-E P0, append-only).

---

## Skill-Nummern (Code-Numerierung)

*Übernommen aus `knowledge.md` (S3-Dedup 10.10.2026) — die Nummern sind Skill-Inventar und gehören zur Skill-Übersicht.*

Zählung: `ls skills/*/SKILL.md | wc -l` = **23** (Stand 24.09.2026, Abgleich Phase-E P0). Nummerierung = Sidebar-/Code-Numerierung der laufenden App (Upload = 0, kein SKILL.md).

**Code-belegte Nummern (Codemarke + Messdatum ⓘ09.10.2026, `app.py` = Archiv):** 0 (Codemarke `Skill 0: Upload`, `app.py` Archiv), 4 (Sidebar `4️⃣ Contact Candidate`, `app.py` Archiv), 6 (Sidebar `6️⃣ Pre-Screen`, `app.py` Archiv), 9 (Codemarke `Skill 9: explain-match`, `app.py` Archiv + Runner-Prompt `explain_match`, `scripts/agent-runner.py`), 12 (Bericht `verify-documents-lab-test-2026-09-12.md`), 13 (Codemarke `Skill 13: check-gdpr`, `app.py` Archiv + Runner-Task `check_gdpr`, `scripts/agent-runner.py`), 16 (Codemarke `Skill 16: export-report`, `app.py` Archiv + `def export_report`, `scripts/agent-runner.py`), 17 (Codemarke `Skill 17: notify-user`, `app.py` Archiv + Runner-Task `notify_user`, `scripts/agent-runner.py`), 18 (`def handle_errors`, `scripts/agent-runner.py`), 23 (`def contract_preflight`, `scripts/agent-runner.py`). Slots 14 und 19–22 sind bisher **nirgends belegt** (in der alten Fassung stand fälschlich ein Pre-Screen-Duplikat auf 14) — die 5 Skills ohne Nummern-Nachweis stehen separat.

| # | Skill | MCP-Connector | Tool |
|---|---|---|---|
| 0 | Upload (UI-Aktion, kein SKILL.md) | filesystem | write_file |
| 1 | extract-profile | filesystem + pdf-reader | read_text_file + read_pdf_text |
| 2 | match-candidate | filesystem + LLM | read_text_file + write_file |
| 3 | check-compliance | filesystem + ansvar-*-law | read_text_file + validate_citation |
| 4 | contact-candidate | filesystem + email-sender | read_text_file + send_email |
| 5 | assess-culture-fit | filesystem | read_text_file |
| 6 | pre-screen | filesystem + meeting-tools | read_text_file + generate_screening_questions + generate_ics_file |
| 7 | generate-onboarding | filesystem | write_file |
| 8 | store-feedback | filesystem | write_file |
| 9 | explain-match | filesystem | read_text_file + write_file |
| 10 | employer-portal | filesystem + SQLite | read_text_file + write_file |
| 11 | job-application | filesystem + SQLite | read_text_file + write_file |
| 12 | verify-documents | pdf-reader + ansvar-german/french/swiss-law + filesystem | read_pdf_text + validate_citation + write_file |
| 13 | check-gdpr | filesystem | read_text_file |
| 15 | candidate-portal | filesystem + SQLite | read_text_file + write_file |
| 16 | export-report | filesystem | write_file |
| 17 | notify-user | filesystem + email-sender | read_text_file + send_email |
| 18 | handle-errors | filesystem | write_file |
| 23 | contract-management | filesystem + ansvar-german-law + fetch | read_text_file + write_file + fetch |

**Ohne Nummern-Nachweis (5 Skills):** `check-visa`, `language-course`, `nicegui-migration`, `mentoring`, `housing-search` — Zählkontrolle: 18 nummerierte Skills (Zeilen 1–13, 15–18, 23; Upload zählt nicht) + 5 ohne Nr. = **23**.

## Workflow

```
Lebenslauf (PDF/TXT)
  ↓
extract-profile (pdf-reader + filesystem)
  ↓
Strukturiertes Profil (profil-[name].md)
  ↓
Stellenprofil (JD)
  ↓
match-candidate (LLM-Matching)
  ↓
Match-Score + Begründung
  ↓
explain-match (detaillierte Analyse)
  ↓
Compliance prüfen (check-compliance + ansvar-*-law)
  ↓
DSGVO prüfen (check-gdpr)
  ↓
Kultur-Fit bewerten (assess-culture-fit)
  ↓
Onboarding-Checkliste (generate-onboarding)
  ↓
Feedback speichern (store-feedback)
```

---

## Skills im Detail

### 1. extract-profile
- **PDF lesen:** `pdf-reader` → `read_pdf_text` (Python MCP)
- **TXT lesen:** `filesystem` → `read_text_file`
- **Ergebnis speichern:** `filesystem` → `write_file`
- **DB-Update (NEU 17.09.2026):** `_update_candidate_from_extract()` schreibt extrahierte Daten automatisch in die `candidates`-Tabelle (hard_skills, soft_skills, berufserfahrung_jahre, abschluss, deutsch, englisch). Vorher: NULL-Werte trotz extrahiertem Lebenslauf.

### 2. match-candidate
- **Profile einlesen:** `filesystem` → `read_text_file`
- **LLM Matching:** Agent-basiert (Skill-Prompt)
- **Ergebnis speichern:** `filesystem` → `write_file`

### 3. check-compliance
- **Regelwerk lesen:** `filesystem` → `read_text_file`
- **Gesetze prüfen:** `ansvar-german-law` / `ansvar-french-law` / `ansvar-swiss-law`
- **Tools:** `search`, `validate_citation`, `get_provision`

### 4. contact-candidate
- **Profil lesen:** `filesystem` → `read_text_file`
- **E-Mail senden:** `email-sender` → `send_email` / `send_interview_invitation`

### 5. pre-screen
- **Profil lesen:** `filesystem` → `read_text_file`
- **Fragen generieren:** `meeting-tools` → `generate_screening_questions`
- **Meeting-Link:** `meeting-tools` → `create_meeting_link` (**LEGACY** — liefert seit 27.09.2026 `https://vdo.ninja/?director=…` statt Jitsi; **0 Aufrufer**, neuere Wege: `scripts/agent-runner.py` Director/Gast-URL; s. `knowledge/system/vdo-ninja-migration.md`)

### 6. handle-errors
- **Fehler loggen:** `filesystem` → `write_file`
- **Fehlerklassen:** TECHNISCH, DATEN, LOGIK, CONNECTOR, DSGVO, COMPLIANCE, USER
- **Fallbacks:** Automatische Fallback-Strategien je nach Fehlertyp

### 7. employer-portal
- **Registrierung:** `employers`-Tabelle in SQLite (argon2id-Hash, transparente SHA256-Migration bei Login — Phase 3.2, wie Candidate Portal)
- **Stellen ausschreiben:** `jobs`-Tabelle (Status: aktiv/pausiert/besetzt/abgelaufen)
- **Kandidaten sehen:** anonymisiert (Pseudonym, keine Kontaktdaten – DSGVO)
- **Bewerber verwalten (NEU Phase 1):** Schritt 7 im SKILL.md – Bewerber zuerst im Kandidaten-Tab, Status angesehen/eingeladen/abgelehnt/eingestellt
- **Feedback geben:** wiederverwendet bestehende `feedback`-Tabelle
- **Matching-Gewichtung (Phase 4):** `feedback.match_id` UNIQUE, idempotentes Speichern; Kandidaten-Picker aus dem Ranking; geschlossener Loop – jedes neue Feedback passt die Gewichtung an (Caps Baseline+15), Scoring liest `get_current_weights()`; Branchen-Score über `employers.branche` (Phase 4.6, Matrix: `knowledge/lifecycle/matching-criteria.md`)
- **Feld-Definitionen:** `knowledge/portal/employer-portal-fields.md`

### 8. job-application (NEU Phase 1)
- **Stellenangebote ansehen:** aktive Stellen (Status `aktiv`) für eingeloggte Kandidaten – ohne Arbeitgeber-Kontaktdaten (DSGVO)
- **Bewerben:** `applications`-Tabelle mit `UNIQUE(candidate_id, job_id)` – Doppelbewerbung ausgeschlossen
- **Status verfolgen:** Lifecycle eingegangen → angesehen → eingeladen → abgelehnt/eingestellt (+ zurückgezogen durch Kandidaten)
- **Zurückziehen:** jederzeit vor `eingestellt` – Eintrag verschwindet aus Arbeitgeber-Sicht
- **Status-Definitionen:** `knowledge/lifecycle/application-status.md` – inkl. DSGVO: Bewerbungen werden 6 Monate nach Prozessende automatisch gelöscht (`dsgvo_cleanup()` beim App-Start, Phase 4.5)

### 9. verify-documents (NEU – Lab-Prinzip)
- **Dokument lesen:** `pdf-reader` → `read_pdf_text` (PDF) bzw. `filesystem` → `read_text_file` (TXT)
- **Typ-Erkennung + Indizienprüfung:** Pflichtfelder, Datumslogik, Profil-Konsistenz – Skala `PLAUSIBEL`/`AUFFAELLIG`/`UNBEKANNT` (kein echtes/falsch-Urteil!)
- **Länder-Rechtsrahmen (Country-Routing):** 🇩🇪 `ansvar-german-law` (AufenthG) · 🇫🇷 `ansvar-french-law` (Code de l'entrée et du séjour) · 🇨🇭 `ansvar-swiss-law` (AuG) – Visa-Dokumente kommen von HR, Zeugnisse/Zertifikate vom Kandidaten
- **Ergebnis speichern:** `filesystem` → `write_file` → `ergebnisse/verify_documents-kandidat-{N}-{datum}.md`
- **Dokumenttypen + Felder:** `knowledge/legal/document-types.md`
- **Rolle (Zwei-Ebenen-Modell):** Agent-Ebene (unsichtbar im Portal), Ergebnis-Sicht nur HR/EMPLOYER

---

## Zugriffskontrolle

Zwei-Ebenen-Modell (v4.5), spezifiziert in `knowledge/system/access-control.md` (v3.1): **Agent-Ebene** (Skills 0–5: Upload-Ingestion, Extract, Match-Tool, Compliance-Tool, Contact, Culture Fit – regulär opencode + MCP, unsichtbar für Portal-Rollen) vs. **Portal-Ebene**. Portal-Menüs (NiceGUI, Stand 20.09.2026 Phase 2 + GAP-Fixes, `webui/pages/`): EMPLOYER 15 Seiten seit 16.10.2026 (PAGE_MAP `webui/pages/employer.py`, Codemarke): Sidebar **7 Punkte** seit 20.10.2026 (Dashboard, Firmenprofil, Stelle ausschreiben, Stellenangebote, Hiring-Board, Einladungen, Mehr; vorher 5 Punkte seit 16.10.2026); „Mehr“ listet die übrigen **8** Seiten (Kandidaten-Suche, Match-Ergebnis, Compliance-Ergebnis, Agent-Details, Dokumente, Pre-Screen Recruiting, Onboarding HR, Feedback). Das Hiring-Board (Spec `knowledge/portal/employer-board.md`) zeigt Bewerbungen nach Status; Einladen/Ablehnen/Einstellen laufen **auf der Match-Seite** (Dialoge `do_invite`/`do_reject`/`do_hire`) und zusätzlich über die Status-Buttons auf 💼 Stellenangebote (`make_transition`, Codemarken gemessen 15.10.2026); **umgesetzt 16.10.2026 (Entscheidung 16.10.2026, Iteration „Einladungen"): dritte Aufrufstelle des gleichen Mechanismus auf der Seite Einladungen (`/employer/einladen`, Codemark `_page_einladen`)**; die Kandidaten-Suche hat keine Schreibaktion und springt zur Match-Seite; die Match-Seite ist **nicht** read-only. Vorher: 12 Seiten seit 13.10.2026; CANDIDATE 7 Tabs (📊 Dashboard [NEU 01.10.2026, 1. Tab], 👤 Mein Profil [inkl. Lebenslauf-Upload + Dokumente, seit 02.10.2026 — frühere Sidebar-Tabs „Upload"/„Dokumente" entfallen], Stellen, Bewerbungen, Sprachtest, Pre-Screen, Onboarding — _TAB_MAP `webui/pages/candidate.py`, Stand 02.10.2026); GAST nur Login; **ADMIN** (v3.1): geschützter Login, 12 Seiten inkl. ausführbarer Agent-Tools 0–5, kein Candidate Portal. Streamlit-Ära (12.09.2026): EMPLOYER 7 Seiten, CANDIDATE 5, ADMIN 11. Hintergrund: „Ein Arbeitgeber lädt keine Lebensläufe hoch und führt keine Agent-Skills aus – er sieht Ergebnisse; der Admin betreibt die Agent-Ebene." Umsetzung (Streamlit-Ära 12.09.2026 in `app.py`, abgelöst durch NiceGUI `webui/` — `PAGE_MAP`/`_TAB_MAP`): ✅ **implementiert 12.09.2026** (18/18 AppTest-Checks; Admin-Login via `admins`-Tabelle, Seed: admin@km-hr-agent.local).

---

## Dokumentation

| Dokument | Pfad | Zweck |
|---|---|---|
| matching-criteria.md | knowledge/ | Matching-Kriterien und Gewichtung |
| compliance-rules.md | knowledge/ | Länderspezifische Compliance-Regeln |
| mcp-connector-config.md | knowledge/ | MCP-Connector-Konfiguration |
| candidate-portal-fields.md | knowledge/ | Kandidaten-Felder + SQLite-Schema |
| employer-portal-fields.md | knowledge/ | Arbeitgeber-Felder + SQLite-Schema (jobs, employers, applications) |
| application-status.md | knowledge/ | Bewerbungs-Status-Lebenszyklus + DSGVO-Regeln |
| lifecycle/mentoring.md | knowledge/ | Mentoring/Patenschaft-Spec (Phase D P10) – §2 Vergabe-Optionen, §3 Speicher-Optionen, §4 Lebenszyklus, §5 {MENTOR}-Befüllung, §7 Rollen |
| portal/housing-search.md | knowledge/ | Wohnungssuche-Spec (Phase D P6) – Checkliste + freie Quellen, ToS-Status der Portale, MD-only Datenfelder, Anbindung an Onboarding-Report |
| legal/contract-management.md | knowledge/ | Contract-Management-Spec (Phase D P8) – Bipperz-Lücken, Recherche-Status, Signatur-Optionen A–F |
| legal/contract-sources.md | knowledge/ | **Link-Katalog** (Single Source of Truth für externe URLs; Code parst MD, 0 hartkodierte Links) |
| templates/contract-templates/arbeitsvertrag-de-skeleton.md | knowledge/ | Vertragsskelett DE: §2-NachwG 15 Pflichtangaben + Formfall-Tabelle |

---

**Stand:** 21.10.2026 (Inventar ⓘ21.10.2026: **23 Skills** · **76 Knowledge-MD** (`find knowledge -name '*.md' -not -name '*.bak*' | wc -l`, gemessen 21.10.2026) · **615 Tests** (`.venv-streamlit/bin/python3 -m pytest --collect-only -q` → „615 tests collected"; Volllauf 610 passed / 5 skipped, gemessen 22.10.2026; Vorwerte 544/539 (21.10.2026), 522/0sk (19.10.2026)) · 17 DB-Tabellen (gemessen 21.10.2026) · 14 MCP-Server; v4.5: Zwei-Ebenen-Zugriffskontrolle + ADMIN ✅ implementiert; Matching/Feedback Phase 2–4.6 ✅: Synonyme, Gehaltscheck, geschlossener Feedback-Loop, DSGVO-Löschung, Branchen-Score; **23 Skills seit 24.09.2026** incl. `mentoring` + `housing-search` (beide implementiert) + `contract-management` (Preflight implementiert, Signatur offen))
