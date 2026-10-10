# KM-HR-Agent – Wissensübersicht (NiceGUI-Prototyp, `webui/`)

## Project Overview
A minimal web prototype for testing 23 HR recruiting skills using AI. NiceGUI (`webui/`, main app since 23.09.2026; Streamlit `app.py` archived) provides:
- Candidate profile extraction from PDF/TXT resumes
- Job-candidate matching (score 0–100)
- Compliance checks (DE/FR/CH + GDPR)
- Email generation, culture fit assessment, pre-screening
- Onboarding checklist generation
- Feedback storage in SQLite
- Employer portal: job postings + anonymized candidate ranking (DSGVO)

## Arbeitgeber-Portal UI (NiceGUI, webui/pages/employer.py — app.py archiviert 23.09.2026)

**Login:** dedicated tabs "🏢 Arbeitgeber-Login" / "🏢 Arbeitgeber-Registrieren" on the start screen (argon2id password hash, transparente SHA256-Migration bei Login — Phase 3.2; `employers` table).

**Sidebar entry:** "🏢 Arbeitgeber-Portal" – requires employer session (`employer_logged_in`).

**4 Tabs (Streamlit-Ära) — heute 11 Seiten (NiceGUI `PAGE_MAP` `webui/pages/employer.py`, 2791–2803, Messung ⓘ09.10.2026):**

| Tab | Funktion |
|---|---|
| 📝 Firmenprofil | Branche, Größe, Standort, Website, Kurzprofil, Telefon |
| 📢 Stellen | Job posting (title, description ≥ 50 chars, location, type, must-have skills required) + status management (aktiv / pausiert / besetzt / abgelaufen) with `job_status_history` log |
| 👥 Kandidaten | Anonymized ranking (score 0–100) – DSGVO: pseudonym only ("Kandidat #12"), no contact data, no resume files; salary shown as compatibility only |
| 💬 Feedback | 1–5 sliders (fachlich, skills, standort, empfehlung), stored in existing `feedback` table with match_id-Schema `employer-job-<job_id>-cand-<cand_id>-<datum>` |

**Matching rule (Tab 👥):** candidate status ≥ `lebenslauf_hochgeladen` AND ≥ 1 must-have skill match AND experience ≥ 50 % of requirement. Score: Baseline-Gewichte `BASELINE_GEWINCHTE` (kern 30, erfahrung 25, bildung 15, standort 10, branche 10, soft 10, sprache 0), normalisiert auf Summe 100 (Messung ⓘ08.10.2026; frühere Fassung „skills 60 + experience 20 + language 10 + location 10" war falsch).

**E2E verified:** login → job posting → anonymized ranking → feedback saved (test employer: hr@techvision.de / sicher123, job #1 "Senior Cloud/DevOps Engineer")

## Quick Commands

### Start Development Server (NiceGUI — einzige UI seit 23.09.2026)
```bash
cd ~/mimo-agents/km-hr-agent
source .venv-streamlit/bin/activate
./start-webui.sh          # oder: python3 -m webui.main
# → http://localhost:8080
```

### ~~Streamlit (app.py)~~ ABGESCHALTET 23.09.2026 (Streamlit-Retirement)
```bash
./start.sh   # → exit 1, "DEAKTIVIERT"
# streamlit run app.py wird nicht mehr gestartet; app.py = Paritäts-Referenz
```

## Dependencies
Quelle: `requirements.txt` (Stand 04.10.2026, aus den tatsächlichen Importen) — die frühere Liste war veraltet (Streamlit an erster Stelle, `nicegui`/`babel`/`argon2-cffi` fehlten). Ist-Abgleich ⓘ09.10.2026:
```
nicegui==3.17.1           # UI (einzige App, webui/)
babel>=2.11               # i18n-Katalog-Kompilierung
argon2-cffi>=23.1         # argon2id-Passwort-Hashing
requests>=2.31            # direkte NVIDIA-API im Runner
PyMuPDF>=1.23.0           # PDF-Textextraktion
reportlab>=4.0            # PDF-Export
Pillow>=10.0
fastmcp==4.0.11           # mcp-*-server.py + connectors/
mcp==2.3.0                # MCP-Client/Server-Kern (bisher nur transitiv über fastmcp)
python-dateutil>=2.8.0
streamlit>=1.30.0         # Archiviert (Altstand app.py, nur Paritäts-Referenz)
```

## Project Structure

| Directory | Purpose |
|---|---|
| `app.py` | **ARCHIVIERT 23.09.2026** — Streamlit-Altstand (`wc -l app.py` = 4041 Z., Messung ⓘ09.10.2026; vormals 4040 Z. Stand 23.09.2026, damals 20 Skills), nur Paritäts-Referenz; Main-App = `webui/` (NiceGUI, 23 Skills) |
| `testdaten/` | Test data: profiles (profil-*.md), resumes (*.txt/*.pdf), job descriptions (stellenprofil-*.txt) |
| `ergebnisse/` | Generated results (match reports, compliance checks, emails, etc.) |
| `knowledge/` | Knowledge base (**72 MD**, Stand 08.10.2026 — Messung `find knowledge -name '*.md' -not -name '*.bak*' | wc -l` = 72 ⓘ08.10.2026; war 66 am 08.10.2026 früh, 46 am 27.09.2026): matching criteria, compliance rules, email templates, portal/lifecycle/legal/system-Specs + 4 Phase-D-Neuspecs (housing, relocation, contract, mentoring) + `system/mvp.md` (Phase-E Runde 2 P2) + 5 Phase-E-B1-Specs (25.09.2026: `legal/dsgvo-gate.md`, `portal/matching-filter.md`, `portal/cv-pflicht.md`, `portal/applicants-first.md`, `lifecycle/status-automation.md`) + `system/vdo-ninja-migration.md` + **`legal/recording-consent.md` (NEU 27.09.2026, Aufnahme-Einwilligung mit 12-Punkte-Gate)** |
| `skills/` | Skill definitions in SKILL.md files |
| `data/feedback.db` | SQLite database for candidates, employers, jobs, applications, feedback + weighting history |
| `connectors/` | MCP connector documentation |
| `.venv-streamlit/` | Python virtual environment |

## Key Architecture Notes

- **Single-file app**: `app.py` (archiviert 23.09.2026, damals 20 Skills) — laufende App ist `webui/` NiceGUI (23 Skills, Stand 24.09.2026)
- **MCP-Connectors**: Used for PDF reading (PyMuPDF), meetings (VDO.Ninja-Raum-URL + meeting-tools für Fragen/ICS), email (Gmail SMTP, seit 24.09.2026)
- **Access control**: "Jobportal-Prinzip" – **Login-Gate der laufenden NiceGUI-App:** `role = logic.current_role(s)` → `if role not in ("employer", "admin"):` (Codemarken `current_role` in `webui/logic.py`, Gate in `webui/pages/employer.py`, Messung ⓘ09.10.2026; two session types: candidate `user_logged_in`, employer `employer_logged_in`). **Archiv-Zitat (Streamlit, abgeschaltet 23.09.2026):** `if not check_login() and not check_employer_login():` (`app.py`). Candidates need resume upload (status ≥ `lebenslauf_hochgeladen`) for Skills 2–8. Employers register via the "🏢 Arbeitgeber-Registrieren" tab, manage jobs and see anonymized candidates in the Employer Portal
- **Role-based access (v4.5 spec, two-plane model + ADMIN)**: source of truth is `knowledge/system/access-control.md` (v3.1) – **Agent-Ebene vs. Portal-Ebene**: Skills 0️⃣–5️⃣ (Upload-Ingestion, Extract, Match-Tool, Compliance-Tool, Contact, Culture Fit) run on the agent plane (opencode + MCP), invisible to CANDIDATE/EMPLOYER/GAST; current page counts (NiceGUI): **EMPLOYER 11 Seiten** (`PAGE_MAP` `webui/pages/employer.py`, 2791–2803 ⓘ09.10.2026), **CANDIDATE 7 Tabs** (`_TAB_MAP`, `webui/pages/candidate.py`, Stand 02.10.2026 — Upload/Dokumente in 👤 Mein Profil), **ADMIN 12 Seiten** incl. executable agent tools, no Candidate Portal; ADMIN login via `admins` table (seed: admin@km-hr-agent.local). Status: ✅ implemented 12.09.2026 (v4.5/v3.1), seit 20.09.2026 auf NiceGUI portiert; Details + Evolution (Phase 1/2) in `knowledge/system/access-control.md`
- **SQLite storage**: Candidates, employers, jobs, applications, feedback and weighting history in `data/feedback.db` (16 tables, Stand 24.09.2026: `admins`, `agent_tasks`, `application_status_history`, `applications`, `candidate_documents`, `candidate_status_history`, `candidates`, `compliance_protokoll`, `employers`, `feedback`, `gewichtung_historie`, `job_status_history`, `jobs`, `language_tests`, `mentoring`, `notifications`)
- **Closed feedback loop (Phase 4)**: every NEW feedback (INSERT, from Employer Portal Tab 4 AND Skill 8) calls `adjust_weights_from_feedback()` – success (eingeladen=Ja, score ≥ Erfolgsschwelle) → Berufserfahrung +5, failure (Nein, score < Misserfolgsschwelle) → Sprache +10 — Schwellen **kategorieabhängig**: 80/70 Fallback/„Strong", **60/60 bei Kategorie „Consider"** (hr-benchmark `get_score_category`, Messung ⓘ08.10.2026); caps Baseline+15; scoring reads ONLY `get_current_weights()` (gewichtung_historie → raw weights → normalized to 100); baseline 30/25/15/10/10/10/0 (spec: `knowledge/lifecycle/matching-criteria.md`)
- **Feedback integrity (Phase 3)**: `feedback.match_id` UNIQUE (`idx_feedback_match_id`); save is idempotent (same day = UPDATE, next day = new row); Tab 4 candidate picker built from the actual ranking (applicants first, then passive matches)
- **DSGVO auto-deletion (Phase 4.5)**: `dsgvo_cleanup()` runs at app start (once/day, failure-safe) – deletes `applications` + `application_status_history` 183 days after process end (final status `abgelehnt/eingestellt/zurückgezogen`); active applications never deleted (spec: `knowledge/lifecycle/application-status.md`, `knowledge/legal/gdpr-policy.md`)
- **Branch score (Phase 4.6)**: `score_branche(branche, cv_text)` compares `employers.branche` (IT/IT-nah/fremd matrix) with candidate CV keywords; job context carries `branche` (joined in Tab 3 + feedback picker); NULL/old callers → previous heuristic fallback
- **MVP definition (Phase-E Runde 2, Schritt P2)**: source of truth is `knowledge/system/mvp.md` (angelegt 25.09.2026, MD-only) – **In-Scope** = Phasen 1–4.6 + Phase 5 + Zwei-Ebenen-Zugriff + 15 MCP-Server + 23 Skills/16 Tabellen, jede Zeile mit Quelle (§1.1); **Out-of-Scope** = Partnernetzwerk-Betrieb, Bezahlung, mobile App, Signatur/E-Signatur, Vertrags-Status-Tracking-DB – je mit Datei:Zeile-Beweis (§1.2); **Live-Basislinie** „live verifiziert 24.09.2026" (+ Wiederholung 25.09.2026) mit Befehl pro Zeile (§2: pytest **26**, HTTP **200**, **1** Runner, failed-IDs `[20,21,23,39,105]`, feedback **8**, **16** Tabellen, **23** Skills, Knowledge-MD **37→38** (+ diese Datei), **15** MCP, `gewichtung_historie` **4**); **Erfolgskriterien E1–E8** – alle Schwellen als Design-Entscheidung gekennzeichnet (§3); **Bezug** = schließt den offenen Punkt „MVP undefiniert / Konzept existiert nirgends" aus `ergebnisse/entscheidungen.md:1382` für die Scope-Definition (§4, Zitat dort). Pilot dazu (P3): `ergebnisse/pilot-plan.md` · Zählwerk §G 26.09.2026: 15 MCP-Server bestätigt, 49 dokumentiert (instructions.md, nach §G) / 181 live (Handshake 26.09.2026)
- **German language**: UI and documentation primarily in German

## Skills (23 total)

Zählung: `ls skills/*/SKILL.md | wc -l` = **23** (Stand 24.09.2026, Abgleich Phase-E P0). Nummerierung = Sidebar-/Code-Numerierung der laufenden App (Upload = 0, kein SKILL.md).
**Code-belegte Nummern (Codemarke + Messdatum ⓘ09.10.2026, app.py = Archiv):** 0 (Codemarke `Skill 0: Upload`, `app.py` Archiv), 4 (Sidebar `4️⃣ Contact Candidate`, `app.py` Archiv), 6 (Sidebar `6️⃣ Pre-Screen`, `app.py` Archiv), 9 (Codemarke `Skill 9: explain-match`, `app.py` Archiv + Runner-Prompt `explain_match`, `scripts/agent-runner.py`), 12 (Bericht `verify-documents-lab-test-2026-09-12.md`), 13 (Codemarke `Skill 13: check-gdpr`, `app.py` Archiv + Runner-Task `check_gdpr`, `scripts/agent-runner.py`), 16 (Codemarke `Skill 16: export-report`, `app.py` Archiv + `def export_report`, `scripts/agent-runner.py`), 17 (Codemarke `Skill 17: notify-user`, `app.py` Archiv + Runner-Task `notify_user`, `scripts/agent-runner.py`), 18 (`def handle_errors`, `scripts/agent-runner.py`), 23 (`def contract_preflight`, `scripts/agent-runner.py`). Slots 14 und 19–22 sind bisher **nirgends belegt** (in der alten Fassung stand fälschlich ein Pre-Screen-Duplikat auf 14) — die 5 Skills ohne Nummern-Nachweis stehen unten separat.

| # | Skill | Description | MCP-Connector | Tool |
|---|---|---|---|---|
| 0 | Upload | PDF/TXT file upload (UI-Aktion, kein SKILL.md) | filesystem | write_file |
| 1 | Extract Profile | Resume → structured profile | filesystem + pdf-reader | read_text_file + read_pdf_text |
| 2 | Match Candidate | Candidate × Job → score (0–100) | filesystem + LLM | read_text_file + write_file |
| 3 | Check Compliance | DE/FR/CH + GDPR compliance check | filesystem + ansvar-*-law | read_text_file + validate_citation |
| 4 | Contact Candidate | Personalized email generation (interview invitation) | filesystem + email-sender | read_text_file + send_email |
| 5 | Assess Culture Fit | Culture fit evaluation | filesystem | read_text_file |
| 6 | Pre-Screen | Screening questions + VDO.Ninja meeting link + ICS | filesystem + meeting-tools | read_text_file + generate_screening_questions + generate_ics_file |
| 7 | Generate Onboarding | Onboarding checklist creation | filesystem | write_file |
| 8 | Store Feedback | SQLite feedback storage | filesystem | write_file |
| 9 | Explain Match | Detailed score justification (7 categories) | filesystem | read_text_file + write_file |
| 10 | Employer Portal | Employer registration, job postings, anonymized candidates + applicant management, feedback | filesystem + SQLite | read_text_file + write_file |
| 11 | Job Application | Candidate: browse active jobs, apply, track application status | filesystem + SQLite | read_text_file + write_file |
| 12 | Verify Documents | Certificates/diplomas (from candidate) + visa/work-permit (from HR) → authenticity indication check, country routing DE/FR/CH | pdf-reader + ansvar-german/french/swiss-law + filesystem | read_pdf_text + validate_citation + write_file |
| 13 | Check GDPR | DSGVO compliance check (Art. 5/6/15–20) | filesystem | read_text_file |
| 15 | Candidate Portal | Registration, profile, CV upload, documents, password change, status | filesystem + SQLite | read_text_file + write_file |
| 16 | Export Report | Match results as PDF/Excel | filesystem | write_file |
| 17 | Notify User | Notifications for top matches (email) | filesystem + email-sender | read_text_file + send_email |
| 18 | Handle Errors | Error logging + user messages | filesystem | write_file |
| 23 | Contract Management | Contract Preflight (Phase D P8): minimum-wage link catalogue, form-error hints (§14/§126a/§623), NachwG 15-point checklist, contract skeleton | filesystem + ansvar-german-law + fetch | read_text_file + write_file + fetch |

**Ohne Nummern-Nachweis (5 Skills):** `check-visa`, `language-course`, `nicegui-migration`, `mentoring`, `housing-search` — Zählkontrolle: 18 nummerierte Skills (Zeilen 1–13, 15–18, 23; Upload zählt nicht) + 5 ohne Nr. = **23**.

## Matching Criteria (Score 0–100)

**Phase 4 baseline (raw weights, normalized to 100):** Kern 30 / Erf 25 / Bildung 15 / Standort 10 / Branche 10 / Soft 10 / Sprache 0 – weights are feedback-driven via `get_current_weights()` (caps: Baseline+15), category points = `score/max × share`. Details + branch matrix: `knowledge/lifecycle/matching-criteria.md`.

| Category | Baseline (Raw) | Min/Max Cap | Description |
|---|---|---|---|
| Kernkompetenzen | 30 | 15/45 | Hard skills match (synonyms: k8s↔Kubernetes) |
| Berufserfahrung | 25 | 10/40 | Relevance and duration (+5 per positive feedback) |
| Bildung | 15 | 0/30 | Degree level and relevance |
| Standort | 10 | 0/25 | Physical proximity or remote (remote = 10) |
| Branchenkenntnis | 10 | 0/25 | `employers.branche` vs. candidate CV (Phase 4.6) |
| Soft Skills | 10 | 0/25 | Communication, teamwork, leadership |
| Sprache | 0 | 0/15 | German/English (activates via negative feedback) |

### Score Interpretation
- **90–100**: Hervorragend → Sofort einladen
- **75–89**: Gut → Einladen
- **60–74**: Bedingt → Prüfung empfohlen
- **40–59**: Schwach → Bedenken
- **0–39**: Nicht passend → Ablehnen

## Compliance Rules

### 🇩🇪 Deutschland (ansvar-german-law)
- **AGG §1**: Diskriminierungsverbot (Alter, Geschlecht, Herkunft)
- **EU AI Act Art. 50**: Transparenz bei KI-entscheidung
- **BDSG §26**: Datenverarbeitung für Einstellung
- **MiLoG**: Gehalt ≥ Mindestlohn (13,90 EUR/h Stand 2026; Quellenstatus: sekundär, siehe `knowledge/legal/contract-sources.md` Key `mindestlohn_2026`)

### 🇫🇷 Frankreich (ansvar-french-law)
- **Code du travail L.1132-1**: Diskriminierungsverbot
- **Loi sur le travail L.3121-27**: 35h-Woche
- **RGPD**: Datenschutz
- **SMIC**: Mindestlohn

### 🇨🇭 Schweiz (ansvar-swiss-law)
- **OR Art. 319**: Arbeitsvertrag
- **ArG Art. 9**: Arbeitszeit (45h/50h)
- **DSG Art. 6**: Datenschutz
- **Mindestlohn**: Je nach Kanton

## MCP-Connectors (14 in `opencode.json` konfiguriert — Messung `len(mcp)` = 14 ⓘ08.10.2026; frühere Fassung „7 active" war falsch)

| Connector | Type | Auth | Purpose | Tools |
|---|---|---|---|---|
| filesystem | local (uvx) | None | File system access for km-hr-agent | read_text_file, write_file, list_directory, search_files (26.09.2026 korrigiert: `glob` existiert nicht in `tools/list` — Phantom, Ist `search_files`) |
| ansvar-german-law | mcp-remote | OAuth | DE laws (6,870 laws) | search, validate_citation, get_provision |
| ansvar-french-law | mcp-remote | OAuth | FR laws (3,958 laws) | search, validate_citation, get_provision |
| ansvar-swiss-law | mcp-remote | OAuth | CH laws (4,873 laws) | search, validate_citation, get_provision |
| pdf-reader | local (Python) | None | PDF text extraction (PyMuPDF) | read_pdf_text, get_pdf_info |
| meeting-tools | local (Python) | None | Screening questions + ICS | generate_screening_questions, generate_ics_file |
| jitsi-meeting | ~~local (Node.js)~~ | — | **ENTFERNT 27.09.2026** (0 Aufrufe) | — |
| email-sender | local (Python) | Gmail SMTP (seit 24.09.2026) | Send emails | send_email, send_interview_invitation |

> **Ergänzung 08.10.2026 (Messung ⓘ08.10.2026):** `opencode.json` führt **14** MCP-Server. In der Tabelle oben fehlen: `anysearch`, `fetch`, `hr-benchmark`, `language-test`, `playwright`, `prescreen-config`, `salary-data`.

## Conventions

- **Formatting**: No formal linting configured
- **Language**: German for UI, comments can be mixed
- **File naming**: Results saved as `ergebnisse/{type}-{name}-{date}.md`
- **Database**: SQLite via standard library (no ORM)
- **PDF handling**: PyMuPDF (fitz module) for text extraction

## Gotchas

- Session state used for login/auth (not secure for production) — NiceGUI `app.storage.user` (laufende App); die Streamlit-Ära nutzte `st.session_state` (archiviert 23.09.2026)
- MCP servers configured in `opencode.json` but not all are active
- Test data must be manually created or uploaded via UI
- **Tests: `pytest` (434 Tests — Messung `.venv-streamlit/bin/python3 -m pytest -q` = „434 passed" ⓘ09.10.2026; vorher 409 am 08.10.2026, war 26 Unit-Tests am 25.09.2026)** + E2E-Skripte `tests/e2e_*.py` (Playwright, `ls tests/e2e_*.py | wc -l` = 50 ⓘ09.10.2026) — Stand 25.09.2026, Phase-E Runde 2
- Python venv must be activated before running (`source .venv-streamlit/bin/activate`)
- Ansvar OAuth tokens expire after 15 min (auto-refresh available)
- **Sprachtest-Ergebnisse im HR-Portal:** ✅ **Caller vorhanden** — Expander „Sprachtests" je Bewerber in `webui/pages/employer.py::_page_match` (Codemarke `db.get_language_tests`, Aufruf `employer.py:1609` ⓘ09.10.2026), portiert 30.09.2026 (R3-6/P2d); Test `tests/test_p2_block.py`. (Frühere Fassung „0 Caller" war falsch.)
- **Verbindliche Doku:** `AGENTS.md` (Lab-Prinzipien), `instructions.md` (v4.5), `ergebnisse/entscheidungen.md` (Entscheidungs-Log) — bei MD-vs-Code-Konflikt: MD korrigieren, nicht den Code (Lab-Schritt 3)

## Agent-Automatisierung (Phase 5 – Spec v3 ✅ implementiert + **Spec v6 ✅ IMPLEMENTIERT 12.09.2026**: Visum-Workflow `verify_documents` (Bewerbung → Dokument-Check, Visum-INFO erst beim JA-Pfad) · `visa_confirmation` (HR-Klick „📩 Visum-Antrag bestätigen" an 💼 + 🏢 → Visum-Schritte-Mail WAS/WIE/WO an Kandidat) · Visa-Abschnitt in Onboarding-Freigabe-Report `ergebnisse/onboarding-freigabe-bewerbung-{app_id}.md` · **Onboarding-Mail #6 `send_onboarding_mail` ✅ implementiert 23.09.2026** (Guard `trigger` + Status `eingestellt`, selben Handler; NB6 geschlossen, DRY_RUN Task #149 verifiziert); E2E T1–T8 bestanden (AppTest + Runner-Simulation, keine echten Mails). **v6.1:** Dokumenten-Tab im Candidate Portal (`candidate_documents`, Typ-Auswahl, kein CV-Overwrite, Art.-17-Löschung, DSGVO-Frist-Löschung der Dateien) als typed Quelle für verify_documents — ✅ implementiert (E2E T1–T5))

> **Spec:** `knowledge/system/agent-automation.md` – Queue + Hybrid-Runner; das Portal sieht nur Ergebnisse (Zwei-Ebenen-Modell bleibt intakt). **v3 = Pförtner-Regel + Variante A · 8/8 E2E-Checks bestanden**

| Baustein | Plan |
|---|---|
| Queue | `agent_tasks`-Tabelle (data/feedback.db): task_type, status, payload (JSON), result_path, attempts |
| Runner | `scripts/agent-runner.py`: 60-s-Loop, max. 5 Tasks/Run, PID-File · **Hybrid v2:** deterministische Tasks (Mails, ICS, Fragen, VDO.Ninja-Link-Raum) **direkt über die Projekt-MCP-Connectors** (kein LLM, handshake-getestet); LLM-Tasks (Extract/Match/Compliance/Culture-Fit + verify_documents + check_visa) via **direkte NVIDIA-API** (`requests.post`, Stand 13.09.2026 – `opencode run` verworfen: nur `step_start` ohne Text) |
| Trigger | CV-Upload → Extract · Bewerbung → Match+Compliance+Culture-Fit (+Eingangs-Mail) · **Agent-JA (Score ≥ 60 UND COMPLIANT) → HR-Mail, dann warten** · Agent-NEIN → keine Mail, Ergebnisse bleiben für HR sichtbar (Suche/Talentpool) · HR-Klick eingeladen → Einladung (VDO.Ninja/ICS/Mail, seit 27.09.2026 ⓘ08.10.2026) · HR-Klick abgelehnt → Absage-Mail (vom Agenten gesendet) · eingestellt → Onboarding-Freigabe |
| E-Mails | 6 implementiert: Eingangsbestätigung (Kandidat), Ergebnis-bereit (HR), Einladung (Kandidat), Absage (Kandidat), Visum-Schritte (v6, Kandidat), Onboarding-Begrüßung #6 (Kandidat, Status `eingestellt`, `send_onboarding_mail` Variante-A-Guard, 23.09.2026) – alle via email-sender MCP, nie SMTP in app.py |
| Kandidaten-Sicht | 💼 Tab 2: VDO.Ninja-Link + ICS-Download bei `eingeladen`; Agent-Status anonymisiert |
| HR-Sicht | Badge „🤖 Agent-Ergebnisse" an Bewerbern; 2️⃣/3️⃣-Sichten lesen die Agent-Berichte |
| Mensch-in-der-Schleife (Variante A) | Agent lädt/lehnt NIE selbst ab: Einladung/Absage nur nach HR-Klick; die Mail sendet dann der Agent (email-sender) – nie SMTP in app.py |
| Meetings | **VDO.Ninja (User-Entscheidung 27.09.2026, ersetzt Jitsi vom 12.09.2026; KEIN Google Meet, KEIN Jitsi):** Raum-URL `https://vdo.ninja/?director=prescreening{code}`; Spec `knowledge/system/vdo-ninja-migration.md`; `jitsi-meeting` **entfernt 27.09.2026** (0 Aufrufe); `create_meeting_link` (LEGACY, erzeugt seit 27.09.2026 VDO.Ninja-Link statt Jitsi/Google Meet) wird nicht verwendet |
| Blocker | ✅ keine – `email-sender` in `opencode.json` (handshake-getestet; `jitsi-meeting` 27.09.2026 entfernt); LLM ✅ live getestet: nemotron-120b via **direkte NVIDIA-API** (13.09.2026, Task #50 check_visa done — Visum ERFORDERLICH für tunesischen IT-Admin), kimi-k3 optional (HTTP 200) |

## Test-Report Index (ergebnisse/ – Milestone-Berichte)

| Bericht | Inhalt |
|---|---|
| `e2e-test-login-schutz.md` | Login-Gate, unregistrierte User, Rollen-Zugriffe |
| `schritt-1` … `schritt-8`-Tests (8 Dateien) | Schritt-Tests der 8 Skills (Extract, Match, Compliance, Contact, Culture-Fit, Pre-Screen, Onboarding, Feedback) vom 10.09. |
| `connector-test-2026-09-10.md` | Erster MCP-Connector-Testlauf (alle Connectoren, 10.09.) |
| `km-hr-agent-connector-fix.md` | Connector-Fix v4.0: `filesystem` statt contract-check-Connector (Access-denied-Problem) |
| `pdf-connector-recherche.md` · `matching-connector-recherche.md` | Recherchen: PDF-Verarbeitung (→ pymupdf/fastmcp) + semantisches Matching |
| `hr-api-connectors.md` · `hr-integration-recherche.md` | Job-API-Quellen (arbeitnow keyless, arbeitsamt OAuth) – Grundlage für Stellenangebote-Sicht |
| `recherche-2026-09-10.md` | Digitale Dienste Tunesien (khadamet.gov.tn, Playwright MCP) |
| `bipperz-konkurrenz-analyse.md` | Abgrenzung KM-HR-Agent vs. Bipperz |
| `erweiterung-2026-09-10.md` · `erweiterung-2026-09-10-v3.md` | Lab-Erweiterungen v2.0/v3.0 (10.09.) |
| `vergleichsmatrix.md` + `match-*.md` (9) | Match-Matrix + Match-Berichte der Testkandidaten (10.09.) |
| `e2e-test-unregistrierter-user.md` | GAST-Sicht: keine Daten, nur Login-Bildschirm |
| `e2e-test-bewerbungsflow.md` | Kompletter Bewerbungsflow (Registrierung → Bewerben → Status → Withdraw) + Access-Control 9/9 + Phase-2-Scoring |
| `e2e-test-einladungsuebergang.md` | `→ eingeladen` via echte UI-Buttons live verifiziert; **Lücken-Nachweis**: danach entsteht kein Jitsi/ICS/E-Mail (Fundament Automatisierung Phase A) |
| `phase-3-feedback-integritaet.md` | Feedback-UNIQUE, idempotentes Speichern, Ranking-Picker |
| `phase-4-feedback-loop.md` | Geschlossener Feedback-Loop (`get_current_weights`, Caps, beide Trigger) |
| `e2e-test-v4.5-2026-09-13.md` | Vollständiger E2E-Test v4.5: 19/19 bestanden (Candidate + Employer + Agent + Access-Control + Static Checks) |
| `phase-4-5-dsgvo-loeschung.md` | DSGVO-6-Monats-Löschung (`dsgvo_cleanup`) |
| `phase-4-6-branchen-score.md` | Branchen-Score über `employers.branche` |
| `access-control-v3-1-zwei-ebenen-admin.md` | Zwei-Ebenen-Modell + ADMIN-Rolle (18/18 AppTest) |
| `verify-documents-lab-test-2026-09-12.md` | Lab-Test Skill 12 (`verify-documents`): pdf-reader live (538 Zeichen extrahiert), Datums-Indiz greift → AUFFAELLIG, kein Code |
| `agent-automatisierung-live-run.md` | **Phase 5 Live-Run**: Kette Ende-zu-Ende mit **3 echten Mails** + NVIDIA-LLM; 8 Live-Bugs gefunden/behoben; Pförtner-Regel (NEIN-Pfad) + Variante A + **JA-Pfad (Jitsi/ICS/Einladungsmail)** live bewiesen |
| `v6-live-run-visum-workflow.md` | **Spec v6 Live-Run**: erste echte `verify_documents`-Dokumentenprüfung (NVIDIA + pdf-reader), Visum WAS/WIE/WO live, Guard-Test (#39 abgefangen), JA-Mail + Visum-Schritte-Mail real; Doppel-Mail-Bug gefunden + gefixt (Guard zählt pending/running/done) |
| `v6-1-implementierung-dokumente-tab.md` | **v6.1 Implementierung**: 🗂️ Dokumente-Tab im Candidate Portal (`candidate_documents`, Typ-Auswahl, kein CV-Overwrite, Art.-17-Löschung, DSGVO-Datei-Bereinigung) — E2E T1–T5 bestanden, typed Quelle für verify_documents |
| `guard-fix-visa-button-verifikation.md` | **Guard-Fix-Verifikation**: Visa-Button verschwindet sofort nach Klick (Runner pausiert = Bug-Fenster simuliert); 3/3 Checks via AppTest; Cleanup + Runner SIGCONT bestätigt |
| `check_visa-kandidat-7-2026-09-13.md` | **check_visa erster LIVE-LLM-Lauf (13.09.2026)**: tunesischer Kandidat #7 × Stelle #1 → Visum ERFORDERLICH, Blue Card möglich (IT = Mangelberuf), Anerkennung freiwillig; Modell nemotron-120b via **direkte NVIDIA-API** (opencode run verworfen — nur `step_start` ohne Text) |

**Index-Abdeckung:** Alle 366 Einträge in `ergebnisse/` (Messung `ls ergebnisse | wc -l` = 366, davon 344 `.md`, ⓘ08.10.2026; war 85) sind entweder im Index genannt (Milestone-/Recherche-/Match-Berichte), gehören zu den generierten Agent-Artefakten (E-Mail-/Match-/Compliance-/Onboarding-/Einladungs-Berichte nach `ergebnisse/{type}-{name}-{date}.md`, indexed via naming convention), oder sind Unterverzeichnisse (`contact-candidate/` Mail-Entwürfe, `testdaten/`, `.ics`-Kalendereintrag). |
