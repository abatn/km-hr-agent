# Project knowledge

This file gives Freebuff context about your project: goals, commands, conventions, and gotchas.

---

# LAB-PRINZIPIEN (Gesetz)

> **Gilt ab: 15.09.2026** | **Für jede Aufgabe bindend – keine Ausnahme.**

## Schritt 1: Quelle finden
Bevor du eine Zahl, eine Regel oder einen Wert verwendest, MUSST du eine externe Quelle finden:
- Gesetz (z.B. ansvar-german-law)
- Studie (z.B. SHRM, LinkedIn)
- Offizielle Dokumentation (z.B. Bipperz)
Wenn keine Quelle gefunden wird: SAGE ES KLAR – und kennzeichne den Wert als "Design-Entscheidung".

## Schritt 2: MD-first
Schreibe die Logik in SKILL.md und knowledge/ – nicht in Python.
Nur wenn MD nicht ausreicht (UI, DB, API), darf Python genutzt werden.

## Schritt 3: Konsistenz prüfen
Vergleiche SKILL.md und Code. Wenn sie nicht übereinstimmen:
Korrigiere das MD – nicht den Code.

## Schritt 4: Transparenz
Dokumentiere jede Entscheidung in ergebnisse/entscheidungen.md:
- Was wurde geändert?
- Warum?
- Welche Quelle?

## Schritt 5: Iteration
Arbeite einen Skill nach dem anderen ab. Nicht alles auf einmal.

## Regeln (verbindlich)
- Keine Erfindungen – jede Zahl hat eine Quelle oder wird als "Design-Entscheidung" gekennzeichnet.
- Kein Code, wo MD reicht.
- Keine Inkonsistenz zwischen MD und Code.
- Keine Behauptung ohne Beweis.

---

## Quickstart
- Setup: `source .venv-streamlit/bin/activate`
- Dev (NiceGUI, einzige UI): `./start-webui.sh` (öffnet http://localhost:8080). **R6-2.2 (30.09.2026):** der Starter liest `./.env` (Vorlage `.env.example`, in `.gitignore`) und verweigert den Start ohne `KMHR_STORAGE_SECRET` + `KMHR_ADMIN_SEED_PASSWORD` (rc=1) — `KMHR_DEV` ist **kein** Starter-Default mehr. Entwicklung ohne Secrets bewusst: `KMHR_DEV=1 ./start-webui.sh`. Direkter `python3 -m webui.main` braucht dieselben Secrets, sonst Abbruch (R3-4). Spec: `knowledge/system/configuration-secrets.md`.
- ~~Dev (Streamlit)~~ **ABGESCHALTET 23.09.2026** (Streamlit-Retirement): `app.py` bleibt als Paritäts-Referenz, wird nicht mehr gestartet (`start.sh` verweigert den Start)
- Test: `pytest -q` (**354 passed**, Stand 04.10.2026 nach VDO-Raumname-Fix, Laufzeit ~50 s (die früher 5 übersprungenen `test_language_scoring`-Tests laufen mit Netz mit)) + E2E-Skripte `tests/e2e_*.py` (Playwright). **R6-0 (30.09.2026):** `tests/e2e_harness.py` bricht ohne `KMHR_E2E_BASE` ab — E2E nur isoliert via `tests/e2e_isolation.py` starten, nie gegen die Live-App :8080

## Architecture
- Key directories: **webui/ (NiceGUI, main UI: main.py, db.py, logic.py, theme.py, components.py, pages/)**, app.py (archiviert 23.09.2026 — Streamlit-Altstand, nur Paritäts-Referenz), testdaten/ (input data), ergebnisse/ (output results), knowledge/ (knowledge base), skills/ (skill definitions), data/feedback.db (SQLite)
- Data flow (candidates): Resume PDF/TXT → Extract Profile → Match Candidate → Compliance Check → Email/Pre-Screen/Onboarding → Store Feedback
- Data flow (employers): Register → Firmenprofil → Stelle ausschreiben → Anonymisierte Kandidaten-Ranking → Bewerber verwalten → Feedback
- Data flow (applications, Phase 1): Candidate browses active jobs (💼 Job Application) → Bewerben → Employer sees applicant first in Kandidaten-Tab → Status lifecycle (eingegangen/angesehen/eingeladen/abgelehnt/eingestellt/zurückgezogen, spec: knowledge/lifecycle/application-status.md)
- 23 skills total (inventarisiert/verifiziert 24.09.2026, `ls skills/*/SKILL.md | wc -l` = 23); full docs in instructions.md (v4.5), knowledge.md and skills/README.md. Knowledge-Inventar: **47 MD-Dateien** (`find knowledge -name '*.md' -not -name '*.bak*' | wc -l`, **Messung 01.10.2026**; Verlauf: 46 am 27.09.2026 — +1 danach, u. a. geschrieben: `knowledge/ui-design-system.md` (UI-Design-System, 28.09.), `knowledge/portal/candidate-portal-fields.md` (29.09.), `knowledge/system/configuration-secrets.md` (30.09.)) — +4 Phase-D-Specs: `housing-search.md`, `relocation.md`, `contract-management.md`, `mentoring.md` + `system/mvp.md` (Phase-E Runde 2) + **5 Phase-E-B1-Specs 25.09.2026**: `legal/dsgvo-gate.md`, `portal/matching-filter.md`, `portal/cv-pflicht.md`, `portal/applicants-first.md`, `lifecycle/status-automation.md` + `system/vdo-ninja-migration.md` (27.09.2026, VDO.Ninja-Migration) + **`legal/recording-consent.md` (27.09.2026, Aufnahme-Einwilligung: 12-Punkte-Gate; Gate 12/12 offen ⇒ weiterhin KEIN Aufnahme-Parameter in der URL — und laut Anbieter-Doku kann der Director auch ohne Parameter ferngesteuert aufnehmen, daher Härtung `&record=off` + HR-Prozessregel Pflicht (✅ umgesetzt 28.09.2026, Gates 8/9/10 — Nachweis entscheidungen.md)) `; `matching-criteria.md` erweitert um Candidate-Score-Sektion, .bak-20260924-1130). NEU: `nicegui-migration` (skills/nicegui-migration/SKILL.md) – Migration Streamlit→NiceGUI (webui/), Phasen-Doku in ergebnisse/nicegui-phase-*.md + ergebnisse/KM-HR-Streamlit-vs-NiceGUI.md. `verify-documents` (agent-plane only, no UI, spec: skills/verify-documents/SKILL.md): document type detection + authenticity indication check per `knowledge/legal/document-types.md` (certificates/diplomas from CANDIDATE, visa/work-permit docs from HR); connectors pdf-reader + ansvar-german/french/swiss-law (country routing like Skill 3). `language-course` (skills/language-course/SKILL.md): Deutsch/Englisch/Französisch-Kurse finden (+ Heimatland-Suche via anysearch für Kandidaten vor Auswanderung, z.B. Tunesien), Niveaus-Tests, Fortschritt verfolgen; Knowledge: knowledge/language-courses.md + knowledge/language-tests.md
- Scoring (Phase 2): matching weights per knowledge/lifecycle/matching-criteria.md (Kern 30/Erf 25/Bild 15/Stand 10/Branche 10/Soft 10/Sprache 0) via `berechne_match_score()` (`webui/logic.py:607` ⓘ01.10.2026; Archiv-Parität `app.py:656`); skill synonyms (`skills_match`, k8s↔Kubernetes); salary check via `gehalt_check()` (max=0 = open, unknown = ❓)
- Feedback (Phase 3): Tab 4 candidate picker built from the actual ranking (applicants first, then passive matches — same rules as Tab 3); `feedback.match_id` UNIQUE (idx_feedback_match_id); save is idempotent: same day = UPDATE, next day = new row (no INSERT OR REPLACE)
- Feedback-Loop (Phase 4, CLOSED): every NEW feedback (INSERT, both triggers: Employer Tab 4 + Skill 8) calls `adjust_weights_from_feedback()` — success (eingeladen=Ja, score≥80) → Berufserfahrung +5, failure (Nein, <70) → Sprache +10; caps Baseline+15; scoring reads ONLY `get_current_weights()` (gewichtung_historie → raw weights → normalized to 100); baseline 30/25/15/10/10/10/0 (spec: knowledge/lifecycle/matching-criteria.md)
- DSGVO (Phase 4.5): `dsgvo_cleanup()` runs at app start — deletes `applications` + `application_status_history` 183 days after process end (final status `abgelehnt/eingestellt/zurückgezogen`, date = last `aktualisiert_am`); active applications never deleted; failure-safe (try/except) (spec: knowledge/lifecycle/application-status.md, gdpr-policy.md)
- Branch score (Phase 4.6): `score_branche(branche, cv_text)` compares `employers.branche` (IT/IT-nah/fremd) with candidate CV keywords — matrix in knowledge/lifecycle/matching-criteria.md; job context carries `branche` (joined in Tab 3 + feedback picker); no branch or old callers → previous heuristic fallback

## Arbeitgeber-Portal (🏢 Employer Portal)
- Employer-Portal implemented in NiceGUI `webui/pages/employer.py` (Skill #10, spec: skills/employer-portal/SKILL.md; historical Streamlit version in app.py, archiviert 23.09.2026, fields/schema: knowledge/portal/employer-portal-fields.md)
- Login gate: `if not check_login() and not check_employer_login():` – TWO session types (candidate: `user_logged_in`, employer: `employer_logged_in`). Login screen has 5 tabs incl. "🏢 Arbeitgeber-Login" / "🏢 Arbeitgeber-Registrieren" (argon2id, transparente SHA256-Migration bei Login – Phase 3.2; Beweis: `app.py:848` (Archiv), Migration-Block `webui/logic.py:847-873` + Login-Aufruf `webui/pages/login.py:146`, beide ⓘ01.10.2026)
- 11 pages (NiceGUI, PAGE_MAP `employer.py:2757-2768` ⓘ01.10.2026): 📊 Dashboard, 🏢 Portal (Firmenprofil + Stellen ausschreiben), 💼 Stellenangebote (HR-write: Bewerber + Archiv), 🔍 Kandidaten-Suche, 📄 Match-Ergebnis, ✅ Compliance, 🔎 Agent-Details, 🗂️ Dokumente, 📞 Pre-Screen, 📋 Onboarding, 💬 Feedback (reuses `feedback` table, match_id `employer-job-{id}-cand-{id}-{date}`)
- Matching rule: status ≥ `lebenslauf_hochgeladen` AND ≥ 1 must-have skill match AND experience ≥ 50% of requirement
- Applicants (Phase 1): new skill `job-application` (skills/job-application/SKILL.md); new tables `applications` (UNIQUE(candidate_id, job_id), no double-apply) + `application_status_history`; applicants listed BEFORE passive matches in Kandidaten-Tab; contact data released only after status `eingeladen`
- **NEU 17.09.2026: 🔍 Agent-Details Seite** – 8. Seite im Employer-Portal (Sidebar: 8 Seiten statt 7; **seit 20.09.2026: 11 Seiten** mit 🗂️ Dokumente + 🏢 Portal + 💼 Stellenangebote (HR-write)). Zeigt ALLE Agent-Ergebnisse (9 Tasks) als Badge-Zeile + aufklappbare Expander. Badge-Farben: 🟢 positiv, 🔴 negativ, 🟡 unsicher, ⚪ fehlend. Doku: `ergebnisse/agent-details-doku.md`
- **NEU 17.09.2026: extract_profile → DB-Update** – Nach LLM-Extraktion werden hard_skills, soft_skills, berufserfahrung_jahre, abschluss, deutsch, englisch automatisch in die candidates-Tabelle geschrieben (`_update_candidate_from_extract()` in agent-runner.py). Vorher: NULL-Werte trotz extrahiertem Lebenslauf.
- SQLite tables in data/feedback.db (16 total, verifiziert 24.09.2026 via `SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'`): `admins`, `agent_tasks`, `application_status_history`, `applications`, `candidate_documents`, `candidate_status_history`, `candidates`, `compliance_protokoll`, `employers`, `feedback`, `gewichtung_historie`, `job_status_history`, `jobs`, `language_tests`, **`mentoring` (NEU Phase D P10, 24.09.2026)**, `notifications` (Benachrichtigungen für notify-user/Portal, Layer: webui/db.py)
- MCP-Server (**14** in `opencode.json`, **27.09.2026: `jitsi-meeting` entfernt** (11 Tools, 0 Code-Aufrufe, VDO.Ninja-Migration; Key `mcp`, 13 local + 1 remote): playwright, filesystem, fetch, pdf-reader, meeting-tools, email-sender, ansvar-german-law, ansvar-french-law, ansvar-swiss-law, anysearch (remote), hr-benchmark, salary-data, prescreen-config, language-test — **entfernt 24.09.2026 (0 Code-Aufrufe): `memory`, `mobileid`, `payment`** (Verzeichnis `mcp-connectors/` existiert **nicht mehr auf Disk** — `ls -d mcp-connectors` → No such file or directory, Stand 25.09.2026; wirksam nach OpenCode-Neustart) — Zählwerk §G 26.09.2026 bestätigt: 15 Server, **27.09.2026 → 14**; **49 dokumentiert (instructions.md, nach §G) / 181 live (Handshake 26.09.2026)** (Ist-vs-dokumentiert-Tabelle: knowledge/system/mcp-connector-config.md §Ist vs. dokumentiert)
- E2E verified: login → job → ranking → feedback (test employer: hr@techvision.de / sicher123, job #1)
- E2E verified 17.09.2026: Candidate #13 (taoufik) → extract_profile DB-Update → Agent-Kette (12 Tasks done) → verify_documents AUFFÄLLIG → Employer-Portal Agent-Details sichtbar

## Access Control (v4.5 – two-plane model: Agent-Ebene vs. Portal-Ebene + ADMIN)
- Spec (source of truth): `knowledge/system/access-control.md` (v3.1) – Skills 0–5 run on the agent plane (opencode + MCP), invisible to CANDIDATE/EMPLOYER/GAST; EMPLOYER menu has **11 portal pages** (`employer.py:2757-2768` PAGE_MAP): 📊 Dashboard, 🏢 Portal (Firmenprofil + Stellen ausschreiben — **P1.2 portiert 20.09.2026**), 💼 **Stellenangebote (HR-write, 20.09.2026: Bewerber-Status-Verwaltung + Archiv)**, 🔍 Kandidaten-Suche (Bewerber-Verwaltung + einladen/ablehnen/**eingestellt** mit onboarding_release-Trigger — **P1.3 portiert 20.09.2026**), 📄 Match-Ergebnis (read-only + Visum-Klick), ✅ Compliance-Ergebnis (read-only), 🔍 Agent-Details (NEU 17.09.2026), 🗂️ Dokumente (NEU 18.09.2026), 📞 Pre-Screen (Recruiting), 📋 Onboarding (HR), 💬 Feedback (voll: Formular + Phase-4-Loop — **GAP-2 20.09.2026**); CANDIDATE: **7 Tabs** (`_TAB_MAP` (`webui/pages/candidate.py`, Stand 02.10.2026), gerendert via shell()): 📊 Dashboard (**NEU 01.10.2026, erster Tab — Nutzerentscheidung: Kandidat landet nach Login im Dashboard**), 👤 Mein Profil (**enthält seit 02.10.2026 Lebenslauf-Upload + Dokumente als aufklappbare Kästen — die früheren Sidebar-Tabs „Upload" und „Dokumente" entfallen**), 💼 Stellen, 📨 Bewerbungen, 🗣️ Sprachtest (**voller Flow, P1.1 portiert 20.09.2026**), 📹 Pre-Screen (**P2.2 portiert 20.09.2026**), 📋 Onboarding; GAST: login only; **ADMIN** (v3.1): protected login, 12 pages incl. executable agent tools 0–5, no Candidate Portal
- Status: ✅ **implemented 12.09.2026 (7 Seiten), erweitert 17.09.2026 (+Agent-Details = 8), Stand 24.09.2026: 11 Seiten** (`employer.py:2757-2768`) – read-only Match/Compliance result views, ADMIN login via `admins` table (seed: admin@km-hr-agent.local, 12 pages incl. agent tools), server HTTP 200

## Agent Automation (Phase 5 – Spec v3 IMPLEMENTED 12.09.2026, 8/8 E2E checks passed; **Spec v6 IMPLEMENTED 12.09.2026**: visa workflow — verify_documents task after application (visa info only in JA-mail), HR 'Visum-Antrag bestätigen' click (💼 + 🏢) → visa-steps mail (WAS/WIE/WO), visa section in onboarding release, **Onboarding-Mail #6 (`send_onboarding_mail`) implemented 23.09.2026** (Variante-A-Guard, same `onboarding_release` handler; NB6 closed, entscheidungen.md 23.09.2026); E2E T1–T8 passed (AppTest + runner simulation). **v6.1**: 🗂️ Dokumente tab in Candidate Portal (candidate_documents table, typed uploads, no CV overwrite, Art. 17 delete, DSGVO file cleanup) feeds verify_documents typed — implemented, E2E T1–T5 passed)
- Spec (source of truth): `knowledge/system/agent-automation.md` – portal writes Tasks into `agent_tasks` queue (SQLite); hybrid background runner (`scripts/agent-runner.py`): deterministic tasks (mails, ICS, questions, Jitsi room) executed **directly via the project MCP connectors** (no LLM), LLM tasks (Extract/Match/Compliance/Culture-Fit + verify_documents + check_visa) via **direct NVIDIA API** (`requests.post`, since 13.09.2026 — `opencode run` dropped: streamed only `step_start`, no text; NVIDIA NIM)
- JA/NEIN gatekeeper rule (user-approved 12.09.2026): match score ≥ 60 AND compliance = COMPLIANT → JA → HR email, then wait; otherwise NEIN → no email, results stay visible in HR views (search/talent pool). **R6-1 (30.09.2026):** Sweep merkt sich je `(application_id, gen, Signatur)` einen `gatekeeper_eval`-Marker (status `done`) — vorher bewertete er jede fertige Bewerbung bei jedem Loop neu (336–419 Log-Zeilen/Stunde, 34.186 hr-benchmark-Subprozesse); `gatekeeper_decision` nutzt jetzt `logic.get_score_category_lokal` statt Subprozess; Nachweis `tests/test_gatekeeper_memo.py` (0 neue Zeilen in 60 s gemessen)
- Human-in-the-loop Variant A (user-approved 12.09.2026): the agent NEVER invites or rejects on its own – invitation only after HR clicks `→ eingeladen`, rejection mail (sent by the agent via email-sender) only after HR clicks `→ abgelehnt`
- Triggers (user-approved 12.09.2026): CV-Upload → extract_profile (+ **DB-Update NEU 17.09.2026**: extrahierte Daten werden in candidates-Tabelle geschrieben: hard_skills, soft_skills, berufserfahrung_jahre, abschluss, deutsch, englisch); application → match/compliance/culture-fit + confirmation mail + explain_match + check_gdpr + notify_user + verify_documents + check_visa; agent-JA → notify_hr mail only; `→ eingeladen` (HR) → invitation (Jitsi + questions + ICS + mail); `→ abgelehnt` (HR) → neutral rejection mail; `→ eingestellt` → onboarding release; store_feedback → export_report (NEU 16.09.2026); language-course: manuell (kein Trigger)
- Emails (6 implemented): application confirmation (candidate), results-ready (HR), invitation (candidate), rejection (candidate), visa-steps mail (v6, only after HR visa click, candidate), onboarding welcome mail #6 (candidate, after status `eingestellt`, Variante-A-Guard `send_onboarding_mail` in same handler — implemented 23.09.2026, NB6 closed) – all sent via email-sender MCP, never SMTP in app.py. NB6 backlog (Onboarding-Mail „nie implementiert“) is closed: DRY_RUN verified 23.09.2026 (Task #149, `[DRY-RUN] mcp-email-server.py::send_email … Willkommen im Team`), see entscheidungen.md 23.09.2026
- Meetings (user decision 12.09.2026, **ersetzt 27.09.2026**): **VDO.Ninja only, NO Google Meet, NO Jitsi** – room URL `https://vdo.ninja/?director=prescreening{code}` (gleiches Muster wie zuvor app.py:2279-2280). Grund: Jitsi-Aufzeichnung braucht Jibri auf eigenem Server. Spec: `knowledge/system/vdo-ninja-migration.md`. **Kein aufnahme-aktivierender Parameter** (`&record`/`&autorecord` zum Einschalten) in der URL – Aufzeichnung nur manuell nach bestätigter Einwilligung (§ 26 Abs. 2 BDSG); **Härtung seit 28.09.2026: Kandidaten-Gast-Link `vdo_ninja_gast_url` = `?room=…&record=off`, HR-Director-Link parameterfrei, HR-Prozessregel als UI-Hinweis, `recording: false` im Ergebnis-JSON (Gates 8/9/10 ✅)**; `meeting-tools` (Fragen + ICS unverändert; **Punkt e) 27.09.2026:** LEGACY-Tool `create_meeting_link` von meet.jit.si auf `https://vdo.ninja/?director=…` **umgebaut statt entfernt**, 0 Aufrufer); `jitsi-meeting` ist am 27.09.2026 aus `opencode.json` **entfernt** (11 Tools, 0 Aufrufe), Zählwerk 15 → **14**. Aufnahme-Param-Einwilligung: Spec `knowledge/legal/recording-consent.md`. **VDO-Fix 03.10.2026 (Nutzerauftrag):** Kandidaten-**Selbstpräsentation** ist ein **Solo-Sender** → `webui/pages/candidate.py` erzeugt jetzt **`?push=<id>`** statt `?director=` (Regieraum sendet kein eigenes Bild; offizielle Doku: Solo = `&push`, nicht `&director`); **kein** `&record` (rechtlich erst nach Einwilligung bei der Registrierung — `recording-consent.md` (i) Punkt 8); Alt-Links ohne Migration; Arbeitgeber-Seite = separate Aufgabe; Test `tests/e2e_video_prescreen.py` angepasst; Spec `knowledge/system/vdo-ninja-migration.md` §2.3. **VDO-Raumname-Fix 04.10.2026:** Raumname alphanumerisch `prescreening{code}` statt `pre-screening-{code}` (VDO-Doku: `&room` nur aLphaNumEric; VDO ersetzte `-` sonst durch `_`) — `scripts/agent-runner.py` (Director+Gast) + `webui/components.py` + Legacy `mcp-meeting-server.py`; Test `tests/test_vdo_raumname.py` (3); Spec §2.5
- Connector status: `email-sender` added to `opencode.json` (12.09.2026, handshake-getestet); `jitsi-meeting` **entfernt 27.09.2026** (VDO.Ninja-Migration, 0 Aufrufe); LLM via **direkte NVIDIA-API** (`requests.post`, Key in `.env-runner`, ersetzt 13.09.2026 `opencode run` das nur `step_start` ohne Text lieferte); Modell-ID: `nvidia/nemotron-3-super-120b-a12b` (env-overridebar via `KMHR_LLM_MODEL`); optional: `moonshotai/kimi-k3` über dieselbe API
- NVIDIA 503-Status (16.09.2026): **20% Fehlerrate** bei 20 parallelen Requests (nemotron-120b), **0% bei lightning-30b**; **Exponential Backoff 5s→10s→20s, 3 Versuche pro Modell** (`agent-runner.py:1103`), Fallback-Modellkette `nemotron-120b → lightning-30b → kimi-k3` in `agent-runner.py:1086-1089` konfiguriert; 503-Cluster nachts 00:00–00:03 Uhr; Erholung 8–118s; kimi-k3: Timeout (>30s, nicht nutzbar)
- Runner autostarts with the app (PID file `data/agent-runner.pid`; opt-out env `KMHR_RUNNER_AUTOSTART=0`); dry-run mode: `python3 scripts/agent-runner.py --once --dry-run`
- Former live gap evidence (now closed): `ergebnisse/e2e-test-einladungsuebergang.md`

## HR-Connectoren (15.09.2026)

3 verifizierte Connectoren in `connectors/` + `opencode.json`:

| Connector | Quelle | Formel | Status |
|---|---|---|---|
| `hr-benchmark` | ZYTHR | `(score/max) × weight` | ✅ Verifiziert |
| `salary-data` | BambooHR | `Min/Mid/Max = 25th/50th/75th` | ✅ Verifiziert |
| `prescreen-config` | CareerPlug | `15-30 Minuten` | ✅ Verifiziert |

**Entfernt (15.09.2026):** `fallback-config` (falsche Quelle: SSRN-ID 4893265 existiert nicht), `gewicht-cap` (falsche Quelle: Nature-Artikel = AlphaFold 3)

**NEU (16.09.2026, hybrid 19.09.2026):** `language-test` (MCP-Server: `scripts/language-test-server.py`) — CEFR-Niveautests: 732 Fragen (DE 120, EN 522, FR 90, offiziell, `knowledge/language-tests.md`) + LLM-generierte Zusatzfragen (NVIDIA API). Hybrid-Modell: Seed als Basis, LLM für zusätzliche Fragen.

**NEU (18.09.2026):** Sprachtest-Integration (Phase 2):
- Candidate Portal: Tab "🗣️ Sprachtest" mit interaktivem Test (DE/EN/FR, A1-C1)
- DB-Tabelle: `language_tests` (candidate_id, sprache, niveau, punkte, cefr_level)
- HR-Portal: Sprachtest-Ergebnisse im Kandidaten-Expander — **✅ portiert 30.09.2026 (R3-6/P2d):** Expander „Sprachtests" je Bewerber in `webui/pages/employer.py::_page_match` (Caller `db.get_language_tests`, nur Kandidaten mit Bewerbung beim eigenen Arbeitgeber); Test `tests/test_p2_block.py`
- Video-Vorstellung: Meeting-Link generieren (VDO.Ninja)
- Auto-Refresh: Nach extract_profile → match_candidate für aktive Bewerbungen

**NEU (18.09.2026):** HR Dokumenten-Ansicht (Phase 3):
- HR Portal: Tab "🗂️ Dokumente" — **Status-Gate: umgesetzt B2-1 am 25.09.2026, umgestellt auf Bewerbungs-Status am 30.09.2026 (P0-2, Runde 1):** `webui/pages/employer.py::_page_dokumente`/`_page_dokumente`-Helfer `_visible_documents` filtert über `EXISTS (SELECT 1 FROM applications a JOIN jobs j ON j.id=a.job_id WHERE a.candidate_id=cd.candidate_id AND j.employer_id=? AND a.status IN ('eingeladen','eingestellt'))` — Grund: `applications` hat keine `employer_id`-Spalte, und `candidates.status` wird nie auf `eingeladen` gesetzt (Gate war sonst dauerhaft gesperrt); 🔒-Hinweis + Spalte Status; Nachweis `tests/e2e_dsgvo_gate.py` **PASS**, Spec `knowledge/legal/dsgvo-gate.md`
- Zeigt (NiceGUI-Ist, gemessen 30.09.2026): Dokumenten-Tabelle (Kandidat/Datei/Typ/Hochgeladen/Status) + Öffnen-Download + 🔒-Hinweis; Typ-Filter case-insensitiv — **nicht** vorhanden: PDF-Vorschau, Agent-Ergebnisse (= eigene Seite 🔎 Agent-Details); **Sprachtest-Ergebnisse seit 30.09.2026 in 📄 Match-Ergebnis** (nicht hier) — **Video-Link/Selbstpräsentation liegt NICHT hier**, sondern in 📞 Pre-Screen (Recruiting-Modus, **ohne Status-Gate zur Bewertung vor der Übernahme**, Nutzer-Entscheidung 28.09.2026)
- DSGVO: Art. 6(1)(b) – Kontaktdaten erst nach Einladung freigegeben

**Status (16.09.2026):** Alle 3 HR-Connectoren sind JETZT AKTIV im Code aufgerufen:
- `hr-benchmark`: 4× `_mcp_connector_call()` in app.py (Scoring, Feedback, Employer-Tab)
- `salary-data`: 1× `_mcp_connector_call()` in app.py (gehalt_check)
- `prescreen-config`: 1× `mcp_connector_call()` in agent-runner.py (create_invitation)
- Fallback: Bei Connector-Fehler → hardcoded Design-Entscheidung (Werte bleiben erhalten)

## Externe Recherche (16.09.2026)

| Fund | Status | Quelle | Relevanz für Projekt |
|---|---|---|---|
| SphinxATS Paper | ✅ existiert, IEEE-Paywall | CrossRef `10.1109/ICSSAS68835.2026.11559449` | Resume-Screening mit Multi-Attribute-Entscheidungsunterstützung — exakt unsere Domäne |
| SphinxATS Code | ✅ GitHub | `github.com/MANISH-K-07/SphinxATS` | Flask + NLP Implementation des Papers |
| SphinxATS LinkedIn | ✅ Autor-Post | `linkedin.com/posts/manish-k-kandrakota` | Explainability Layer: transparente Attribut-level-Begründungen |
| questio (PDF-Forensik) | ✅ GitHub, MIT | `github.com/abcreativ/questio` | Font-Session-Tracking, Trust Score 0-100 → könnte verify_documents ergänzen |
| PDFRecon (PDF-Forensik) | ✅ GitHub, 45 Stars | `github.com/Rasmus-Riis/PDFRecon` | 40+ Forensik-Indikatoren, GUI, meistgenutztes Tool |
| pdforensic (PDF-Forensik) | ✅ GitHub | `github.com/genie360s/pdforensic` | Metadaten, Previous Versions, Python/CLI |
| pdf-forense (PDF-Forensik) | ✅ GitHub, MIT | `github.com/AnkbNikas/pdf-forense` | Incremental-Update-Erkennung, Redaktionsprüfung |
| pdf-verify-mcp (MCP) | ✅ npm, getestet | `@shuji-bonji/pdf-verify-mcp` v0.26.0 | 7 Tools: evaluate_policy (Trust-Verdict), verify_integrity (Tamper), verify_signatur, PAdES, PDF/A; **Test auf CV-sirine-ilahi.pdf: `use_with_caution` (kein Signatur, 2 Revisions)** |
| NVIDIA 503 | ⚠️ 20% bei Load | Eigener Test 16.09.2026 | Exponential Backoff 5/10/20s im Code (agent-runner.py:1103), lightning-30b als Fallback verfügbar; Free-Tier: 40 RPM (NVIDIA Forum, 25.06.2026) |
| anysearch | ✅ **Kein Schlüssel nötig (anonym), 01.10.2026:** `Authorization`-Zeile in `opencode.json` endgültig entfernt, nur `X-Anysearch-Client` bleibt (Nutzer-Entscheidung 01.10.2026). | `python3 -c "import json;print(json.load(open('opencode.json'))['mcp']['anysearch']['headers'])"` → `{'X-Anysearch-Client': 'mcp/1.0.0'}`; README anysearch: Key optional, anonym funktional | MCP-Server für Websuche (Apache-2.0); **wirksam erst nach OpenCode-Neustart** |

**10-Zeilen-Projekthilfe:**
1. **SphinxATS** bestätigt: Resume-Screening kann als Multi-Attribute-Optimierung modelliert werden (unser Projekt macht das schon) → `knowledge/lifecycle/referenz-sphinxats.md`
2. **SphinxATS** nutzt NLP + semantische Ähnlichkeit —-validiert unseren Ansatz (Extract → Match → Score)
3. **questio** könnte verify_documents um Font-Analyse erweitern (statt nur "manuell")
4. **pdf-forense** könnte Redaktionsprüfung automatisieren (Text unter schwarzen Rectangles)
5. **Lightning-30b** ist bereits als Fallback konfiguriert (`agent-runner.py:1086-1089`) — 0% 503-Rate vs. 20% bei nemotron-120b
6. **NVIDIA 503** löst sich mit Exponential Backoff 5s→10s→20s (`agent-runner.py:1103`, 3 Versuche pro Modell) statt Sofort-Retries
7. **anysearch** war ab 24.09.2026 defekt (`invalid_auth_header` bei `search`). Ursache: leere/fehlende Auth. **01.10.2026 (Nutzer-Entscheidung): anysearch braucht keinen Schlüssel** → `Authorization`-Zeile in `opencode.json` entfernt, `X-Anysearch-Client` bleibt (anonym, offiziell unterstützt); wirksam erst nach OpenCode-Neustart; Arbeits-Ersatz bis dahin `fetch`. Die Zeile war am 26.09. (H1/M1-Versuch) wieder eingetragen worden — damit ist der `H9`-Restpunkt geschlossen.
8. **error-statistics.md** ist gefüllt (49 Z., 503-Statistik + API-Tests vom 16.09.2026) — `knowledge/error-statistics.md`
9. **verify_documents** hat jetzt Fälschungserkennung — pdf-verify-mcp (`_pdf_forensic_pre_scan()` in `agent-runner.py:49-101` ⓘ01.10.2026) integriert (evaluate_policy + verify_integrity via npx, Trust-Verdict wird dem LLM-Prompt vorgelegt)
10. **SphinxATS** hat 0 Zitationen — Early-Stage-Paper, nicht als Autorität zitieren
11. **Explainability Layer** in `berechne_match_score()` — 7 Kategorien mit menschenlesbaren Begründungen (SphinxATS-Pattern, Quelle: `matching-criteria.md:130`); Code: `webui/logic.py:651-665` (`erklaerung`-Dict, laufende App, beide ⓘ01.10.2026), Archiv-Parität `app.py:713/727`

## Implementierte Änderungen (16.09.2026)

| Änderung | Datei | Status |
|---|---|---|
| Explainability Layer (erklaerung-Dict, 7 Kategorien) | webui/logic.py:651-665 (laufend, ⓘ01.10.2026) · app.py:713/727 (Archiv) | ✅ Implementiert |
| pdf-verify-mcp Pre-Scan (_pdf_forensic_pre_scan) | agent-runner.py:49-101 (ⓘ01.10.2026) | ✅ Implementiert |
| Forensik-Ergebnis in verify_documents-Prompt | agent-runner.py:858-860 (Berechnung) + :939 (Prompt), ⓘ01.10.2026 | ✅ Implementiert |
| Exponential Backoff + Fallback-Modellkette | agent-runner.py:1086-1089 (Kette) + :1103 (wait=[5,10,20]), ⓘ01.10.2026 | ✅ Implementiert |

## Nachtrag 02.10.2026: Landingpage `/`

| Änderung | Datei/Beleg | Status |
|---|---|---|
| Landingpage `/` (Gäste): Three.js **lokal** (`webui/static/three/`, kein CDN), **exakt 30 s** (`TOTAL = 30.0`), Loop + „Nochmal ansehen", Countdown 30→0; **Reihenfolge (Bipperz-Angleich 02.10.2026): Hero → ▶ 30-Sekunden-Tour-Animation → Zielgruppen-Karten (Für Arbeitgeber/Für Kandidaten, je eigener CTA) → „Warum KM-HR-Agent?" (6 Vorteil-Karten, `_VORTEILE`, alle Zahlen code-belegt) → `ui.expansion("So funktioniert's")` (7 Schritte) → Häufige Fragen (FAQ) → Abschluss-CTA → Footer (Impressum/Datenschutz/AGB/Kontakt)**; Hero entdoppelt (Sub 1,06 rem / h1 max 2,8 rem); frühere „Aufgabe"/„Nutzen"-Karten **entfernt** (02.10.2026) | `webui/pages/landing.py`, `tests/test_landing_page.py` (10 Tests), `ergebnisse/entscheidungen.md` 02.10.2026 | ✅ Umgesetzt |
| **Rechts-Seiten (Entwurf 02.10.2026):** `/impressum` + `/datenschutz` + `/agb` + `/kontakt` (neu `webui/pages/legal.py`, rendert MD aus `knowledge/legal/`); Inhalte `impressum.md` (§ 5 DDG), `datenschutz.md` (Art. 13 DSGVO, inkl. Drittland Tunesien, 183-Tage-Löschung, TDDDG § 25), `agb.md` (Plattform-AGB, Struktur angelehnt an Bipperz — eigener Text), `kontakt.md`; Rechtsträger **Agic Tunisie GmbH** (Tochtergesellschaft, Sitz Ben Arous/Tunesien, MwSt-ID 1096754W), Kontakt **contact@zedintek.com** (als Text, **kein** `mailto`); Footer verlinkt alle vier — **anwaltlich zu prüfen** (keine Rechtsberatung) | `webui/pages/legal.py`, `webui/main.py`, `knowledge/legal/{impressum,datenschutz,agb,kontakt}.md`, `ergebnisse/entscheidungen.md` 02.10.2026 | ✅ Entwurf |
| **i18n Phase 1+2+2b+3+4+5+6+6b (02.–03.10.2026):** gettext + Babel, Sprachumschalter **DE/EN/FR/AR**, Sprache je Session (`app.storage.user['language']`), RTL bei `ar`; neu `webui/i18n.py` (`_()`/`get_language`/`set_language`/`is_rtl`/`apply_direction`/`language_switcher`), `webui/locales/{de,en,fr,ar}/LC_MESSAGES/messages.{po,mo}` (**544 Keys**), `knowledge/system/i18n.md` (Spec), `tests/test_i18n.py` (**18 Tests**); Umschalter in Landing-Header + `shell()`-Header + Login + **Rechts-Seiten**; **Phase 2: Landingpage-Strings in `_()` gewickelt + übersetzt**; **Phase 2b: Animations-Captions (JS `CH`), 3D-Labels (`makeLabel`) + Replay-Button übersetzt** (Injektion `window.__KMHR_CH__` / `window.__KMHR_LABELS__`); **Phase 3: `webui/pages/login.py` komplett in `_()` (69 Stellen, 5 Tab-/Panel-Namen konsistent), f-Strings → `.format()` (Ruff INT001), `apply_direction()`+`language_switcher()`**; **Phase 4 (03.10.2026): Rechts-Seiten `<name>.<lang>.md`** — `legal.py::_resolve()` lädt `knowledge/legal/<name>.<lang>.md` mit Fallback `<name>.md`, **12 neue MD-Dateien** (impressum/datenschutz/agb/kontakt × en/fr/ar, jede mit „deutsche Fassage gilt"-Hinweis), Rechtstexte bewusst NICHT über gettext (MD-first); **Phase 5 (03.10.2026): `webui/pages/candidate.py` — 180 msgids in `_()` (f-Strings → `.format()`), Sidebar-Labels von Importzeit-Konstante `_MENU_ITEMS` auf Renderzeit-`_menu_items()` umgestellt; NICHT übersetzt (Design-Entscheidung): `PROFIL_*_OPTIONEN`/`_PROFIL_SPALTEN` (DB-Werte), `VIDEO_HEADING` + MD-Persistenz-Helfer (Speicher-Marker), SQL/Pfade/Logs/Status-Rohwerte (→ Phase 8); Phase 5b: `section_header`/`empty_state`/`ui.number(label=)`/IfExp-Buttons nachgezogen (+27 Keys)**; **Phase 6 (03.10.2026): `webui/pages/employer.py` — 239 msgids (214 neu), Sidebar `_MENU_ITEMS_EMP` → `_menu_items_emp()` (Renderzeit), `ui.table`-Spaltenlabels + `ui.echart`-Titel + Timeline-Titel + `date_input`/`time_input`-Label mitgewrappt; NICHT übersetzt: `ui.select`-Optionen die Werte sind (Branche/Größe/Ja-Nein/Status-Filter), Status-Slugs, SQL/Pfade/Regex/Icons/Task-Status; Kataloge 293→507; Phase 6b (03.10.2026): geteilte `components.py` — 45 msgids (37 neu), Default-Parameter auf `Optional[str]=None`+Fallback (kein `_()` als Default = Importzeit-Falle), `STATUS_LABELS` bleibt für Phase 8, Markenname `KM-HR-Agent` unübersetzt; Kataloge 507→544**; **RTL-Bugfix (03.10.2026): `webui/i18n.py::apply_direction()` aktiviert zusätzlich Quasars RTL (`Quasar.lang.set(…rtl)`), weil Quasar sein RTL NICHT aus `document.dir` ableitet → vorher reservierte `q-page-container` das Drawer-Padding auf der logischen Seite, in AR lief der Content beim Schließen des Benachrichtigungs-Panels unter die Nav-Sidebar (Karten/Kreisdiagramm abgeschnitten); Nachweis `tests/e2e_rtl_drawer.py` (isoliert, PASS) — **Hinweis:** vor `e2e_isolation.py --port N` prüfen, dass N frei ist, sonst läuft der Test gegen einen Alt-Server**; Babel 2.18.0 in venv installiert | `webui/i18n.py`, `webui/locales/`, `knowledge/system/i18n.md`, `tests/test_i18n.py`, `webui/pages/landing.py`, `webui/pages/login.py`, `webui/pages/legal.py`, `webui/pages/candidate.py`, `webui/pages/employer.py`, `webui/components.py`, `knowledge/legal/*.{en,fr,ar}.md`, `webui/components.py`, `ergebnisse/entscheidungen.md` 03.10.2026 | ✅ Phase 1+2+2b+3+4+5+6+6b |

## Nachträge 01.10.2026

| Änderung | Datei/Beleg | Status |
|---|---|---|
| anysearch ohne Schlüssel (`Authorization` entfernt, nur `X-Anysearch-Client`) + Jitsi-Doku-Reste bereinigt | `opencode.json` (14 Server), `ergebnisse/entscheidungen.md` 01.10.2026 | ✅ Erledigt (wirksam nach OpenCode-Neustart) |
| `.bak`-Retention-Bugfix: `_bak_timestamp()` liest nur den Stempel nach `bak` — vorher matchte das Original-Datum im Namen und löschte **frische** Backups (real eingetreten 01.10. 20:02, 2 Dateien, Rollback `/tmp/opencode/bakcheck/deleted_2_20261001-2002.tar.gz`) | `webui/logic.py:741` (`_bak_timestamp`) / `:757` (`bak_retention_scan`) / `:778` (`run_bak_retention_once`), alle ⓘ01.10.2026; Nachweis `tests/test_bak_retention.py` (5 Tests) | ✅ Behoben |
| Zeilenangaben-Drift-Register: alle 78 Code-Refs in `ergebnisse/reports/` gedriftet → **Zitierregel** in Conventions (Codemarke + Messdatum) | `ergebnisse/zeilenangaben-drift-2026-10-01.md` §3/§4 | ✅ Regel bindend ab 01.10.2026 |
| UI-MVP-Plan **v2** ersetzt v1 (v1 nur noch als Vorgänger) | `ergebnisse/ui-mvp-plan-v2.md`, `ergebnisse/ui-analyse-2026-09-29.md` | ✅ Aktuell |

## Hardcoded-Werte (15.09.2026)

| Wert | Quelle | Status |
|---|---|---|
| DSGVO 183 Tage | Art. 17 DSGVO | ✅ Offiziell |
| MiLoG 13,90 EUR/h (Stand 2026) | MiLoV5 § 1, **BGBl. 2025 I Nr. 268 v. 07.11.2025**, in Kraft 01.01.2026 (MiLoG § 1 Abs. 2 = Ermächtigung) | ✅ Primär (BGBl./BMAS, Abruf 25.09.2026; vorher ⚠️ Sekundär Wikipedia bis 25.09.) – vorher 12,41 (Stand 2025, veraltet) |
| Blue Card 50.700/45.934 EUR | BAMF/ZAV (2026) | ✅ Offiziell |
| Matching 30/25/15/10/10/10/0 | Keine | ❌ Design-Entscheidung |
| Score-Schwellen (≥60/70/80/90) | Keine | ❌ Design-Entscheidung |
| Gehalts-Toleranz 0.8/1.1 | Keine | ❌ Design-Entscheidung |
| Default-Werte (soft=0, bildung=0, branche=0) | Keine | ❌ Design-Entscheidung (15.09.2026 gefixt: 7→0, 4→0, 6→0) |

**Recherche (15.09.2026):** 6 Quellen geprüft (ZYTHR, BambooHR, CareerPlug, Zainali8315/GitHub, SHRM, HuggingFace). Keine liefert validierte Matching-Gewichte. Die Gewichte werden durch den Feedback-Loop (Phase 4) iterativ optimiert.

## CI/CD (neu 06.10.2026): Sync lokal → GitHub → Contabo VPS

- **Ablauf:** lokal `git push` (RefSpec `remote.origin.push = master:main`, einmalig gesetzt) → GitHub-`CI` grün → **`deploy-contabo.yml`** (Workflow `workflow_run`) → SSH auf `root@169.58.83.32` → `git reset --hard $TARGET_SHA` + `git clean -fd` → `systemctl restart km-hr-agent` → Health-Check `curl 127.0.0.1:8080` → SHA-Abgleich.
- **Auth:** Key-Paar `kmhr-deploy` (ed25519) — Pub-Key = read-only Deploy-Key im Repo (id 165560904), Privat-Key = Secret `CONTABO_SSH_KEY`; Server-Remote `git@github.com:…` mit `core.sshCommand`. Spec + Design-Entscheidungen: `knowledge/system/deploy-pipeline.md`; Beweislog: `ergebnisse/entscheidungen.md` 06.10.2026.
- **Gilt nie als synchron** (gitignored, unberührt): `.env*`, `data/`, `testdaten/`, `ergebnisse/`, `.venv-*/`. Rollback = SSH `git reset --hard <SHA>` (gleiche Befehle).

## Conventions
- Formatting/linting: None configured
- Patterns to follow: NiceGUI-App (webui/, frameworkfreie Layer db.py/logic.py), German UI, MCP-Connectors for external services (filesystem, pdf-reader, meeting-tools, email-sender, ansvar-*-law, hr-benchmark, salary-data, prescreen-config), Lab-Prinzip (skills + knowledge + connector, no separate codebase); Tool-Namen-Pflicht: nur MCP-Server-Namen aus opencode.json (kein websearch/webfetch) — siehe `knowledge/system/mcp-connector-config.md` §Tool-Namen-Pflicht
- Things to avoid: Tests existieren als `pytest -q` (**354 passed**, Stand 04.10.2026) + E2E-Skripte `tests/e2e_*.py` (Playwright, **isoliert via `tests/e2e_isolation.py`** — der Harness bricht ohne `KMHR_E2E_BASE` ab, R6-0); session state auth not secure for production, must activate venv before running, never modify contract-check-filesystem (belongs to another project)
- **Zeilenangaben-Drift (Regel ab 01.10.2026, bindend):** `Datei:Zeile` ist **kein** stabiler Verweis — Zeilen wandern mit dem Wachstum des Codes (Befund: alle 78 Code-Refs in `ergebnisse/reports/*.md` gedriftet, 53/53 getroffen anders als beschrieben; `ergebnisse/zeilenangaben-drift-2026-10-01.md`). Zitate daher immer mit **Codemarke** (`PAGE_MAP`, `_TAB_MAP`, `def berechne_match_score`) und/oder Messdatum (`employer.py:2757-2768` ⓘ01.10.2026) angeben; vor dem Zitat `grep -n "<marke>" <datei>` prüfen. Alt-Reports unangetastet lassen (datierte Messung bleibt gültig, Nachtrag am Kopf).
- **`.bak`-Retention (Regel ab 27.09.2026, bindend):** Von Sicherheitskopien (`*.bak*`) bleiben nur noch die der **letzten 2 Kalendertage** (Datum im Namen, z. B. 26.+27.09.) — **alles ältere und alle ohne Datum wird gelöscht**. **Design-Entscheidung** auf ausdrücklichen Nutzerbefehl (keine externe Quelle). Ausführung + Beweise: `ergebnisse/entscheidungen.md` (Abschnitt .bak-Inventur); Rollback-Archive unter `/tmp/opencode/bakcheck/deleted_*.tar.gz`. Beim Löschen: erst frisch scannen, Rollback-Archiv anlegen, danach `pytest` (26) + Live-DB-Snapshot prüfen. **Automatisiert seit 28.09.2026 (Nutzer-GO „führe das"):** `webui/logic.py::run_bak_retention_once()` (Scan → Rollback-Archiv → Löschung, fehlerresistent) läuft bei jedem App-Start über `app_bootstrap()`; manuell z. B. `python3 -c "from webui.logic import run_bak_retention_once as f; print(f())"`. **Bugfix 01.10.2026:** der Scan suchte das erste 8-stellige Datum im Dateinamen — bei Originalen mit eigenem Datum (z. B. `x-20260929.md.bak-20261001-1955`) matchte das **Original**-Datum → frische Backups galten als Verstoß und wurden gelöscht (wirklich eingetreten, Rollback-Archiv `deleted_2_20261001-2002.tar.gz`); Fix `_bak_timestamp()` liest nur den Stempel nach `bak` (`webui/logic.py:741` ⓘ01.10.2026), Nachweis `tests/test_bak_retention.py` (5 Tests).
