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

## Quickstart & Verification (Stand 10.10.2026)

- **Setup:** `source .venv-streamlit/bin/activate`
- **Dev (NiceGUI, einzige UI):** `./start-webui.sh` → http://localhost:8080. **R6-2.2 (30.09.2026):** der Starter liest `./.env` (Vorlage `.env.example`, in `.gitignore`) und **verweigert den Start ohne `KMHR_STORAGE_SECRET` + `KMHR_ADMIN_SEED_PASSWORD`** (rc=1); `KMHR_DEV` ist kein Starter-Default mehr. Bewusst ohne Secrets: `KMHR_DEV=1 ./start-webui.sh`. Direktstart `python3 -m webui.main` braucht dieselben Secrets (R3-4). Spec: `knowledge/system/configuration-secrets.md`.
- **Streamlit = abgeschaltet (23.09.2026):** `app.py` bleibt als Paritäts-Referenz, `start.sh` verweigert den Start.
- **Unit-Tests:** `.venv-streamlit/bin/python3 -m pytest -q` → **434 passed, 0 failed, 148–165 s** (Messung 10.10.2026, conftest spiegelt `tests/fixtures/seed.db` → deterministisch); `--collect-only` = **434 collected**. **Ohne Netz:** 398 passed + 5 skipped (die 5 netzabhängigen `test_language_scoring`). **CI-Parität (gleicher Stand):** mit `--ignore=tests/test_r33_compliance_reports.py` + `--deselect tests/test_ui_fixes_p0.py::test_profile_display_name_kein_dateiname` = **425 passed, 1 deselected, 148,73 s** — Differenz 9 = die im CI aus DSGVO-Gründen nicht lauffähigen Tests. Spec: `knowledge/system/e2e-ci-seed.md`.
- **E2E (Playwright):** immer **isoliert** via `tests/e2e_isolation.py <port>` — `tests/e2e_harness.py` bricht ohne `KMHR_E2E_BASE` ab (R6-0), **nie** gegen die Live-App :8080. **Konten-Geltungsbereich (F2, 09.10.2026):** *lokal* läuft der Harness gegen einen **Spiegel der Live-DB** → die Skripte melden sich mit den Originale-Mails an (`hr@techvision.de`, `test@example.de` u. a.); *in CI* setzt `e2e.yml` `KMHR_E2E_SEED=1` und `seed_email()` übersetzt dieselben Konstanten auf die anonymisierten Seed-Konten **`hr1@example.invalid` / `kandidatN@example.invalid` / `admin@example.invalid`** (Quelle `tests/fixtures/seed.db`, erzeugt von `scripts/seed_ci_db.py`, Passwort-Hashes unverändert). `pytest` ist davon getrennt: `tests/conftest.py` spiegelt die Seed-Fixture als **Quelle**, damit dieselben datenabhängigen Tests wie im CI laufen. Vollständiges Live↔Seed-Mapping: `knowledge/system/e2e-ci-seed.md`. Ist 10.10.2026: **50 Dateien `tests/e2e_*.py`, davon 48 lauffähig** (SKIP = `e2e_harness.py` + `e2e_isolation.py` als Nicht-Tests; Zählung `ls tests/e2e_*.py | wc -l`). **Letzter dokumentierter Volllauf 07.10.2026: 47/47 `rc=0`** (Port 8081, 991,7 s, Live-DB sha256 unverändert); Teil-Läufe P9.5 4/4 (185,2 s) und P9.5b 3/3 (130,7 s); `tests/e2e_i18n_full_chain.py` = 4-Sprachen-Kette Kandidat→Arbeitgeber `rc=0` (184,3 s). **Ein neuer Volllauf ist am 10.10.2026 nicht gefahren** — Zahlen oben sind datierte Messungen.
- **Doc-Gates (NEU 10.10.2026):** `./.venv-streamlit/bin/staledocs check` (PyPI **2.1.0** — **nicht** `npx staledocs`, das ist ein anderes npm-Paket ohne `ack`) + `npx -y docrot-cli` (A+). Config `.staledocs.yaml` (55 Paare, 49 standalone, `global: README.md`, `gate: strict`), Workflow `.github/workflows/docrot.yml`.
- **i18n-Kataloge bauen:** `.venv-streamlit/bin/pybabel compile -d webui/locales` (kein `babel.cfg`, keine `.pot`) — **2 bekannte Altdefekte** in en/ar (`.po` Zeile 1112, unescaped `%`), `.mo` werden trotzdem vollständig geschrieben. Spec: `knowledge/system/i18n.md`.
- **Beweislog (Pflicht, Lab-Schritt 4):** `ergebnisse/entscheidungen.md`; Änderungsverlauf zusätzlich `git log --oneline -10`.

## Architecture
- **Key directories:** **webui/** (NiceGUI: `main.py`, `db.py`, `logic.py`, `theme.py`, `components.py`, `pages/`), `app.py` (archiviert 23.09.2026, nur Paritäts-Referenz), `testdaten/` (input), `ergebnisse/` (output), `knowledge/` (**72** MD), `skills/` (**23** `SKILL.md`), `data/feedback.db` (SQLite, **16** Tabellen).
- **Data flow (candidates):** Resume PDF/TXT → Extract Profile → Match Candidate → Compliance Check → Email/Pre-Screen/Onboarding → Store Feedback.
- **Data flow (employers):** Register → Firmenprofil → Stelle ausschreiben → anonymisiertes Kandidaten-Ranking → Bewerber verwalten → Feedback.
- **Data flow (applications, Phase 1):** Kandidat bewirbt sich auf aktive Stellen → Employer sieht Bewerber zuerst im Kandidaten-Tab → Status-Zyklus `eingegangen/angesehen/eingeladen/abgelehnt/eingestellt/zurückgezogen` (Spec `knowledge/lifecycle/application-status.md`).
- **Inventar-Stand 10.10.2026 (Messung):** 23 Skills, 72 knowledge-MD, 993 msgid je Sprache, 14 MCP-Server (`opencode.json`), 16 DB-Tabellen, 50 E2E-Dateien.

## Scoring, Feedback, DSGVO
- **Scoring:** Gewichte aus `knowledge/lifecycle/matching-criteria.md` (Kern 30 / Erf 25 / Bild 15 / Stand 10 / Branche 10 / Soft 10 / Sprache 0) über `berechne_match_score` (`webui/logic.py`, Codemarke gemessen 10.10.2026); Gewichts-Quelle = **nur** `get_current_weights` (`gewichtung_historie` → Rohgewichte → Normalisierung auf 100). Skill-Synonyme: `skills_match` (z. B. k8s ↔ Kubernetes); Gehaltscheck `gehalt_check` (`max=0` = offen, unbekannt = ❓). **Explainability-Layer:** 7 Kategorien mit menschenlesbaren Begründungen (`erklaerung`-Dict, Codemarken `berechne_match_score`/`erklaerung` in `webui/logic.py`; Archiv-Parität `app.py`).
- **Feedback (Phase 3):** Tab 4 baut den Kandidaten-Picker aus dem echten Ranking (Bewerber zuerst, dann passive Matches); `feedback.match_id` UNIQUE (Index `idx_feedback_match_id`); Speichern ist idempotent (gleicher Tag = UPDATE, nächster Tag = neue Zeile — kein `INSERT OR REPLACE`).
- **Feedback-Loop (Phase 4, closed):** jedes **neue** Feedback (INSERT, beide Trigger: Employer-Tab 4 + Skill 8) ruft `adjust_weights_from_feedback` (Codemarke in `webui/logic.py`, gemessen 10.10.2026) — Erfolg (eingeladen=Ja, Score ≥ Schwelle) → Berufserfahrung +5; Misserfolg (Nein, Score < Sprachschwelle) → Sprache +10. **Schwellen dynamisch** aus `hr-benchmark` `get_score_category` (Strong → 80/70, Consider → 60/60); lokal `get_score_category_lokal` = ≥80 Strong / ≥60 Consider; **Fallback bei Connector-Fehler 80/70** (Design-Entscheidung); Caps = Baseline+15.
- **DSGVO (Phase 4.5):** `dsgvo_cleanup` (Codemarke in `webui/logic.py`) löscht beim App-Start `applications` + `application_status_history` 183 Tage nach Prozessende (Datum = letztes `aktualisiert_am`); aktive Bewerbungen nie; fehlertolerant (try/except).
- **Branch-Score (Phase 4.6):** `score_branche` vergleicht `employers.branche` (IT / IT-nah / fremd) mit CV-Keywords; Matrix in `knowledge/lifecycle/matching-criteria.md`; ohne Branche oder bei Alt-Callern → vorherige Heuristik.

## Access Control (two-plane: Agent-Ebene vs. Portal-Ebene + ADMIN)
- **Spec (source of truth):** `knowledge/system/access-control.md` (v3.1). Skills 0–5 laufen auf der **Agent-Ebene** (opencode + MCP), für CANDIDATE/EMPLOYER/GAST unsichtbar.
- **EMPLOYER — 11 Seiten** (`PAGE_MAP` in `webui/pages/employer.py`, gemessen 10.10.2026): 📊 Dashboard, 🏢 Portal (Firmenprofil + Stellen ausschreiben), 💼 Stellenangebote (HR-write: Bewerber + Archiv), 🔍 Kandidaten-Suche (einladen/ablehnen/eingestellt mit `onboarding_release`-Trigger), 📄 Match-Ergebnis (read-only + Visum-Klick), ✅ Compliance (read-only), 🔎 Agent-Details, 🗂️ Dokumente, 📞 Pre-Screen, 📋 Onboarding, 💬 Feedback (voll: Formular + Phase-4-Loop).
- **CANDIDATE — 7 Tabs** (`_TAB_MAP` in `webui/pages/candidate.py`, gerendert via `shell()`): 📊 Dashboard (erster Tab, Nutzerentscheidung 01.10.2026), 👤 Mein Profil (seit 02.10.2026 mit Lebenslauf-Upload + Dokumenten als aufklappbare Kästen; die früheren Sidebar-Tabs „Upload"/„Dokumente" entfallen), 💼 Stellen, 📨 Bewerbungen, 🗣️ Sprachtest, 📹 Pre-Screen, 📋 Onboarding.
- **GAST:** nur Login. **ADMIN:** geschützter Login, **12** Seiten inkl. ausführbarer Agent-Tools 0–5, kein Employer-Portal.
- **ADMIN → Candidate Portal: erlaubt (Ist-Code, Design-Entscheidung ⓘ09.10.2026):** Gate in `webui/pages/candidate.py` (`role != "candidate" and role != "admin"`) + Freigabe in `webui/main.py` (`role == page_role or (role == "admin" and page_role in ("candidate", "employer"))`). Die frühere Regel „ADMIN hat kein Candidate Portal" ist vom Ist-Code überholt (Spec `access-control.md` hält es als Design-Entscheidung fest).
- **Login-Gate (laufende NiceGUI-App):** `logic.current_role` (Codemarke in `webui/logic.py`) → `if role not in ("employer", "admin")` im Employer-Portal. Zwei Session-Typen (candidate: `user_logged_in`, employer: `employer_logged_in`). ~~`if not check_login() and not check_employer_login():`~~ = **Streamlit/Archiv-Zitat** (`app.py`, abgeschaltet 23.09.2026).

## Arbeitgeber-Portal (Details)
- Umgesetzt in `webui/pages/employer.py` (Skill #10, Spec `skills/employer-portal/SKILL.md`; Felder/Schema `knowledge/portal/employer-portal-fields.md`). Login-Screen hat 5 Tabs inkl. „🏢 Arbeitgeber-Login"/„🏢 Arbeitgeber-Registrieren" (argon2id, transparente SHA256-Migration bei Login).
- **Matching-Regel:** Status ≥ `lebenslauf_hochgeladen` **und** ≥ 1 Must-Have-Skill **und** Erfahrung ≥ 50 % der Anforderung.
- **Bewerber (Phase 1):** neuer Skill `job-application`; Tabellen `applications` (UNIQUE(candidate_id, job_id), kein Doppel-Bewerben) + `application_status_history`; Bewerber stehen vor passiven Matches; Kontaktdaten erst ab Status `eingeladen`.
- **🔍 Agent-Details (17.09.2026, 8. bzw. seit 20.09.2026 11. Seite):** zeigt alle 9 Agent-Tasks als Badge-Zeile + aufklappbare Expander (🟢 positiv / 🔴 negativ / 🟡 unsicher / ⚪ fehlend). Doku: `ergebnisse/agent-details-doku.md`.
- **extract_profile → DB-Update (17.09.2026):** nach LLM-Extraktion werden hard_skills, soft_skills, berufserfahrung_jahre, abschluss, deutsch, englisch in `candidates` geschrieben (`_update_candidate_from_extract`, Codemarke in `scripts/agent-runner.py`) — vorher NULL trotz CV.
- **DSGVO-Dokumenten-Gate (B2-1, 25.09.2026; auf Bewerbungs-Status umgestellt P0-2, 30.09.2026):** Helfer `_visible_documents` in `webui/pages/employer.py` filtert über `EXISTS (… JOIN jobs j … WHERE … j.employer_id=? AND a.status IN ('eingeladen','eingestellt'))` — Grund: `applications` hat keine `employer_id`-Spalte und `candidates.status` wird nie auf `eingeladen` gesetzt (Gate war sonst dauerhaft gesperrt). 🔒-Hinweis + Status-Spalte; Nachweis `tests/e2e_dsgvo_gate.py` PASS; Spec `knowledge/legal/dsgvo-gate.md`.
- **🗂️ Dokumente zeigt:** Dokumenten-Tabelle (Kandidat/Datei/Typ/Hochgeladen/Status), Download, 🔒-Hinweis; Typ-Filter case-insensitiv. **Nicht** hier: PDF-Vorschau, Agent-Ergebnisse (eigene Seite 🔎), Sprachtest-Ergebnisse (in 📄 Match-Ergebnis), Video-Link/Selbstpräsentation (in 📞 Pre-Screen, Recruiting-Modus, ohne Status-Gate zur Bewertung — Nutzerentscheidung 28.09.2026). DSGVO-Grundlage Art. 6(1)(b).
- **E2E:** Login → Stelle → Ranking → Feedback verifiziert (Test-Arbeitgeber `hr@techvision.de` / `sicher123`, Stelle #1, plus Seed-Konten, Mapping in `knowledge/system/e2e-ci-seed.md`); Candidate #13 (taoufik) → extract_profile → Agent-Kette (12 Tasks) → verify_documents AUFFÄLLIG → Agent-Details im Employer-Portal sichtbar.

## Agent Automation (Phase 5)
- **Spec:** `knowledge/system/agent-automation.md` — Portal schreibt Tasks in `agent_tasks` (SQLite); hybrider Hintergrund-Runner `scripts/agent-runner.py`: deterministische Tasks (Mails, ICS, Fragen, Meeting-Raum) direkt über die MCP-Connectoren (kein LLM), LLM-Tasks (Extract/Match/Compliance/Culture-Fit + `verify_documents` + `check_visa`) über **direkte NVIDIA-API** (`requests.post`, Key in `.env-runner`; `opencode run` seit 13.09.2026 entfallen — lieferte nur `step_start` ohne Text). Modell-ID `nvidia/nemotron-3-super-120b-a12b` (env-override `KMHR_LLM_MODEL`), optional `moonshotai/kimi-k3`.
- **JA/NEIN-Gatekeeper (user-approved 12.09.2026):** Score ≥ 60 **und** Compliance = COMPLIANT → JA → HR-Mail, dann warten; sonst NEIN → keine Mail, Ergebnisse bleiben in HR-Sicht. **R6-1 (30.09.2026):** der Sweep merkt sich je `(application_id, gen, Signatur)` einen `gatekeeper_eval`-Marker (status `done`) — vorher bewertete er jede fertige Bewerbung bei jedem Loop neu; `gatekeeper_decision` (Codemarke in `scripts/agent-runner.py`) nutzt `logic.get_score_category_lokal` statt Subprozess. Nachweis `tests/test_gatekeeper_memo.py`.
- **Human-in-the-loop Variante A:** der Agent lädt **nie** selbst ein und lehnt **nie** selbst ab — Einladung erst nach HR-Klick `→ eingeladen`, Ablehnungs-Mail erst nach `→ abgelehnt`. Live-Gap-Nachweis (closed): `ergebnisse/e2e-test-einladungsuebergang.md`.
- **Triggers (12.09.2026):** CV-Upload → `extract_profile` (+DB-Update); Bewerbung → match/compliance/culture-fit + Bestätigungsmail + `explain_match` + `check_gdpr` + `notify_user` + `verify_documents` + `check_visa`; Agent-JA → nur HR-Mail; `→ eingeladen` → Einladung (Raum + Fragen + ICS + Mail); `→ abgelehnt` → neutrale Ablehnung; `→ eingestellt` → Onboarding-Freigabe; `store_feedback` → `export_report`; language-course manuell (kein Trigger).
- **6 implementierte Mails:** Bewerbungsbestätigung (Kandidat), Ergebnisse bereit (HR), Einladung (Kandidat), Ablehnung (Kandidat), Visum-Schritte (v6, erst nach HR-Visum-Klick), Onboarding-Willkommen #6 (Kandidat, nach `eingestellt`, Variante-A-Guard `send_onboarding_mail` im selben Handler, implementiert 23.09.2026) — alle via email-sender-MCP, nie SMTP in `app.py`. NB6-Backlog ist geschlossen (DRY_RUN 23.09.2026, Task #149).
- **LLM-503 (16.09.2026):** 20 % Fehlerrate bei 20 parallelen Requests (nemotron-120b), 0 % bei lightning-30b; **Exponential Backoff 5s→10s→20s, 3 Versuche pro Modell** (`wait = [5, 10, 20]`, Codemarke in `scripts/agent-runner.py`, gemessen 10.10.2026) + **Fallback-Kette** `model_chain` (`nemotron-120b → lightning-30b → kimi-k3`; kimi-k3 Timeout >30 s = nicht nutzbar). 503-Cluster nachts 00:00–00:03; Free-Tier 40 RPM (NVIDIA Forum, 25.06.2026); gefüllte Statistik `knowledge/error-statistics.md`.
- **Runner:** startet mit der App (PID-Datei `data/agent-runner.pid`); Opt-out `KMHR_RUNNER_AUTOSTART=0`; Dry-Run `python3 scripts/agent-runner.py --once --dry-run`.
- **Connectoren:** `email-sender` 12.09.2026 handshake-getestet; `jitsi-meeting` 27.09.2026 entfernt (11 Tools, 0 Aufrufe, VDO.Ninja-Migration); entfernt 24.09.2026 `memory`, `mobileid`, `payment` (0 Code-Aufrufe). Zählwerk: **14** Server in `opencode.json` (13 local + anysearch remote).

## Meetings (VDO.Ninja)
- **Nur VDO.Ninja** (user decision 12.09.2026, ersetzt Jitsi 27.09.2026): HR-Raum `https://vdo.ninja/?director=prescreening{code}`; Spec `knowledge/system/vdo-ninja-migration.md`. Grund: Jitsi-Aufzeichnung braucht Jibri auf eigenem Server.
- **HR-Raumfall (recording-consent-Gate 8/9/10 ✅):** Kandidaten-Gast-Link `vdo_ninja_gast_url` = `?room=…&record=off` (Härtung), HR-Director-Link `vdo_ninja_url` parameterfrei, HR-Prozessregel als UI-Hinweis, `recording: false` im Ergebnis-JSON. **Kein aufnahme-aktivierender Parameter im HR-Raumfall** — Spezifikation `knowledge/legal/recording-consent.md` (Gate (d) 12/12 offen).
- **Kandidaten-Selbstpräsentation (Solo-Sender):** `?push=<id>&record=6000` (Aufnahme-Knopf, 6 Mbps) — Codemarken `meet_url` und `video_url` in `webui/pages/candidate.py`, gemessen 10.10.2026. **VDO-Fix 03.10.2026:** Solo = `&push`, **nicht** `&director` (Regieraum sendet kein eigenes Bild); Alt-Links ohne Migration; Test `tests/e2e_video_prescreen.py`. Spec §2.3/§2.4.
- **Raumname-Fix 04.10.2026:** alphanumerisch `prescreening{code}` statt `pre-screening-{code}` (VDO-Doku: `&room` nur aLphaNumEric, sonst ersetzt VDO `-` durch `_`) — `scripts/agent-runner.py` (Director + Gast), `webui/components.py`, Legacy `mcp-meeting-server.py`; Test `tests/test_vdo_raumname.py`; Spec §2.5.
- `meeting-tools` behält Fragen + ICS; LEGACY-Tool `create_meeting_link` ist auf VDO umgebaut (0 Aufrufer).

## HR-Connectoren (15.09.2026)
| Connector | Quelle | Formel | Status |
|---|---|---|---|
| `hr-benchmark` | ZYTHR | `(score/max) × weight` | ✅ verifiziert |
| `salary-data` | BambooHR | `Min/Mid/Max = 25th/50th/75th` | ✅ verifiziert |
| `prescreen-config` | CareerPlug | `15–30 Minuten` | ✅ verifiziert |

- **Entfernt 15.09.2026 (falsche Quellen):** `fallback-config` (SSRN-ID 4893265 existiert nicht), `gewicht-cap` (Nature-Artikel = AlphaFold 3).
- **NEU `language-test` (16.09./19.09.2026, hybrid):** MCP-Server `scripts/language-test-server.py` — 732 offizielle Seed-Fragen (DE 120, EN 522, FR 90) + LLM-Zusatzfragen (NVIDIA API); Spec `knowledge/language-tests.md` + `knowledge/language-courses.md`.
- **Sprachtest-Integration (18.09.2026):** Candidate-Tab mit vollem Flow (DE/EN/FR, A1–C1), Tabelle `language_tests`, HR-Ansicht im Kandidaten-Expander (**portiert 30.09.2026, R3-6/P2d**: „Sprachtests" je Bewerber in `_page_match`, Test `tests/test_p2_block.py`), Video-Vorstellung via VDO.Ninja, Auto-Refresh nach extract_profile.
- **Alle 3 HR-Connectoren sind im Code aufgerufen** (Stand 16.09.2026): `hr-benchmark` 4×, `salary-data` 1× (`gehalt_check`), `prescreen-config` 1× (`create_invitation`); bei Connector-Fehler → hardcoded Design-Entscheidung (Werte bleiben).

## i18n (Phase 1–6b, 02.–03.10.2026)
- **gettext + Babel**, Sprachumschalter **DE/EN/FR/AR**, Sprache je Session (`app.storage.user['language']`), RTL bei `ar`. Kern: `webui/i18n.py` (`_()`/`get_language`/`set_language`/`is_rtl`/`apply_direction`/`language_switcher`) + `webui/i18n_core.py` (framework-frei für den Runner).
- **Kataloge: 993 msgid je Sprache** (Messung 10.10.2026, `grep -c '^msgid ' webui/locales/de/LC_MESSAGES/messages.po`; de/en/fr/ar gleich). Verlauf: 803 → 927 (P2/P3) → 969 → 990/991 (P9.5/P9.5b) → **993**.
- **Phasen:** Landingpage (Phase 2 + 2b Animations-Captions), Login (Phase 3, 69 Stellen), Rechts-Seiten (Phase 4, MD-Varianten `<name>.<lang>.md` statt gettext), Candidate-Portal (Phase 5, 180 msgids), Employer-Portal (Phase 6, 239 msgids), geteilte Komponenten (Phase 6b, 45 msgids). NICHT übersetzt (Design-Entscheidung): DB-Werte als Select-Optionen, SQL/Pfade/Status-Slugs, Markenname.
- **RTL-Bugfix (03.10.2026):** `apply_direction()` aktiviert zusätzlich Quasars RTL (`Quasar.lang.set(…rtl)`), weil Quasar sein RTL **nicht** aus `document.dir` ableitet — sonst lief Content in AR unter die Nav-Sidebar. Nachweis `tests/e2e_rtl_drawer.py`.
- **Tests:** `tests/test_i18n.py` (36) + `tests/test_runner_i18n.py` (37). Spec + Gap-Register: `knowledge/system/i18n.md` (+ `i18n-runner-chain.md` für Runner/MCP-Texte).

## Hardcoded-Werte (15.09.2026)
| Wert | Quelle | Status |
|---|---|---|
| DSGVO 183 Tage | Art. 17 DSGVO | ✅ offiziell |
| MiLoG 13,90 EUR/h (Stand 2026) | MiLoV5 § 1, **BGBl. 2025 I Nr. 268 v. 07.11.2025**, in Kraft 01.01.2026 (MiLoG § 1 Abs. 2 = Ermächtigung) | ✅ Primär (BGBl./BMAS, Abruf 25.09.2026) |
| Blue Card 50.700 / 45.934 EUR | BAMF/ZAV (2026) | ✅ offiziell |
| Matching 30/25/15/10/10/10/0 | keine | ❌ Design-Entscheidung |
| Score-Schwellen (≥60/70/80/90) | keine | ❌ Design-Entscheidung |
| Gehalts-Toleranz 0.8 / 1.1 | keine | ❌ Design-Entscheidung |
| Default-Werte (soft=0, bildung=0, branche=0) | keine | ❌ Design-Entscheidung (15.09.2026 gefixt: 7→0, 4→0, 6→0) |

**Recherche 15.09.2026:** 6 Quellen geprüft (ZYTHR, BambooHR, CareerPlug, Zainali8315/GitHub, SHRM, HuggingFace) — **keine** liefert validierte Matching-Gewichte; die Gewichte optimiert der Feedback-Loop (Phase 4) iterativ.

## Externe Recherche (Auszug 16.09.2026, voll: `ergebnisse/entscheidungen.md`)
- **SphinxATS** (IEEE `10.1109/ICSSAS68835.2026.11559449`, Code `github.com/MANISH-K-07/SphinxATS`, LinkedIn-Post des Autors): Resume-Screening als Multi-Attribute-Entscheidungsunterstützung + Explainability-Layer — **validiert unseren Ansatz**, aber **0 Zitationen** → nicht als Autorität zitieren. Wissenseintrag: `knowledge/lifecycle/referenz-sphinxats.md`.
- **PDF-Forense:** `questio` (Font-Session-Tracking, Trust-Score 0–100), `PDFRecon` (40+ Indikatoren), `pdforensic`, `pdf-forense` — könnten `verify_documents` ergänzen (statt nur „manuell").
- **`@shuji-bonji/pdf-verify-mcp` v0.26.0** (npm, getestet): 7 Tools; **integriert** als `_pdf_forensic_pre_scan` (Codemarke in `scripts/agent-runner.py`) — `evaluate_policy` + `verify_integrity` via npx, Trust-Verdict geht in den LLM-Prompt.
- **NVIDIA 503** + **anysearch:** siehe Tool-Fallen unten.

## Tool-Fallen & bekannte Fallstricke
- **`npx staledocs` ≠ `.venv-streamlit/bin/staledocs`:** das npm-Paket ist ein anderes Projekt (0.4.0-beta.1, ohne `ack`). Maßgeblich ist die PyPI-Version 2.1.0 im venv; `staledocs check --gate strict` muss `rc=0` liefern, bevor gepusht wird.
- **staledocs-Ack-Falle (selbst erfahren 10.10.2026):** die Analyse liefert Claims **nur bei UNACKED-Paaren** — ein zweiter Analyse-Lauf über bereits beschriebene Paare schreibt `claims=0` in die Evidence und führt zu Ack-Notes ohne Beleg. Vor jedem Re-Ack: `.staledocs/` sichern, `.staledocs/pairs/` leeren, Claims frisch analysieren, dann acken; 3 Prosa-Docs ohne Pfad-/Ident-Claims (`knowledge/language-tests.md`, `knowledge/notification-log.md`, `knowledge/onboarding-default.md`) brauchen manuellen Beleg im Note. Aktueller Verifikations-Stand: `ergebnisse/entscheidungen.md` (10.10.2026).
- **anysearch braucht keinen Schlüssel (01.10.2026):** nur `X-Anysearch-Client` in `opencode.json`; die Auth-Zeile war am 24.09.2026 wegen `invalid_auth_header` defekt und ist entfernt (Nutzerentscheidung). Wirksam erst nach OpenCode-Neustart; Arbeits-Ersatz bis dahin `fetch`.
- **E2E-Sleep-Falle (WSL):** `goto` auf `/employer/stellen` hängt den Playwright-Driver — Einladen über den Match-Seiten-Dialog (`knowledge/system/i18n-runner-chain.md` §5).
- **`.bak`-Retention-Bugfix (01.10.2026):** `_bak_timestamp` liest nur den Stempel **nach** `bak` — vorher matchte das Original-Datum im Namen und löschte **frische** Backups (wirklich eingetreten; Rollback `/tmp/opencode/bakcheck/deleted_2_20261001-2002.tar.gz`). Automatisiert: `run_bak_retention_once` (Codemarken in `webui/logic.py`, gemessen 10.10.2026) bei jedem App-Start über `app_bootstrap`; Nachweis `tests/test_bak_retention.py`.
- **Zeilenangaben-Drift:** alle 78 Code-Refs in `ergebnisse/reports/*.md` waren gedriftet (53/53 getroffen anders als beschrieben) — siehe Conventions.

## CI/CD (lokal → GitHub → Contabo VPS, seit 06.10.2026)
- **Ablauf:** lokal `git push` (RefSpec `remote.origin.push = master:main`) → GitHub-`CI` grün → `deploy-contabo.yml` (workflow_run) → SSH auf `root@169.58.83.32` → `git reset --hard $TARGET_SHA` + `git clean -fd` → `systemctl restart km-hr-agent` → Health-Check `curl 127.0.0.1:8080` → SHA-Abgleich.
- **Auth:** Key-Paar `kmhr-deploy` (ed25519) — Pub-Key = read-only Deploy-Key (id 165560904), Privat-Key = Secret `CONTABO_SSH_KEY`; Server-Remote `git@github.com:abatn/km-hr-agent.git` mit `core.sshCommand`. Spec: `knowledge/system/deploy-pipeline.md`.
- **Gilt nie als synchron** (gitignored): `.env*`, `data/`, `testdaten/`, `ergebnisse/`, `.venv-*/`. Rollback = SSH `git reset --hard <SHA>`.

## Conventions
- **Linting/Formatting:** kein Formatter konfiguriert — **aber verbindliche CI-Gates** (`.github/workflows/ci.yml`): `pyflakes` über `webui/ scripts/ connectors/ tests/` + Root-MCP-Server mit **Ausnahmen-Liste** (nur blockierende Fehler wie undefined name/Syntax; `app.py` und `docs/sphinxats-github-app.py` ausgenommen), `python -m compileall -q`, Secret-Scan, i18n-Katalog-Gleichheit (Key-Menge je Sprache == DE) und `pytest` mit den beiden DSGVO-Exklusionen (siehe Quickstart). Zusätzlich Doc-Gates `staledocs` + `docrot`.
- **Patterns:** NiceGUI-App (frameworkfreie Layer `db.py`/`logic.py`), deutsche UI, MCP-Connectors für externe Dienste, Lab-Prinzip (Skill + Knowledge + Connector, keine separate Codebasis). **Tool-Namen-Pflicht:** nur MCP-Server-Namen aus `opencode.json` (kein websearch/webfetch) — `knowledge/system/mcp-connector-config.md`.
- **Nicht tun:** Session-State-Auth nicht produktionsfähig; venv vor Tests aktivieren; `contract-check-filesystem` nie anfassen (gehört zu einem anderen Projekt).
- **Zeilenangaben-Drift (Regel ab 01.10.2026, bindend):** `Datei:Zeile` ist **kein** stabiler Verweis. Zitate daher mit **Codemarke** (`PAGE_MAP`, `_TAB_MAP`, `def berechne_match_score`) und/oder Messdatum (`PAGE_MAP` in `webui/pages/employer.py`, gemessen 10.10.2026); vor dem Zitat `grep -n "<marke>" <datei>` prüfen. Alt-Reports unangetastet lassen (datierte Messung bleibt gültig, Nachtrag am Kopf). Befund: `ergebnisse/zeilenangaben-drift-2026-10-01.md`.
- **`.bak`-Retention (Regel ab 27.09.2026, bindend, Design-Entscheidung auf Nutzerbefehl):** von Sicherungskopien bleiben nur die der **letzten 2 Kalendertage** (Datum-Stempel **im** Namen, z. B. `.bak-20261001-1955`); alles ältere und alles ohne Datum wird gelöscht. Ausführung: `run_bak_retention_once` (Scan → Rollback-Archiv `/tmp/opencode/bakcheck/deleted_*.tar.gz` → Löschung), fehlerresistent, bei jedem App-Start. Nach dem Löschen: `pytest` + Live-DB-Snapshot prüfen.
- **Changelog-Pflicht:** datierte Änderungsnarrative gehören in `ergebnisse/entscheidungen.md` (Lab-Schritt 4) — nicht in diese Datei. `git log --oneline -10` liefert den Commit-Verlauf.

## Archiv (verdichtet — Belege in `ergebnisse/entscheidungen.md`)
- **16.09.2026:** Explainability-Layer (`erklaerung`-Dict, 7 Kategorien), `_pdf_forensic_pre_scan` integriert, Forensik-Ergebnis im `verify_documents`-Prompt, Backoff + Modellkette implementiert.
- **23.09.2026:** Streamlit-Retirement (`app.py` nur noch Referenz), Onboarding-Mail #6 implementiert, `language-test`-Integration.
- **01.10.2026:** anysearch ohne Schlüssel; `.bak`-Retention-Bugfix; Drift-Register für Zeilenangaben; UI-MVP-Plan **v2** ersetzt v1 (`ergebnisse/ui-mvp-plan-v2.md`).
- **02.10.2026:** Landingpage `/` (Three.js lokal in `webui/static/three/`, kein CDN; exakt 30 s = `TOTAL = 30.0`, Loop + „Nochmal ansehen"; Reihenfolge Hero → Tour → Zielgruppen-Karten → Warum → So funktioniert's → FAQ → CTA → Footer; 10 Tests `tests/test_landing_page.py`) + Rechts-Seiten `/impressum` `/datenschutz` `/agb` `/kontakt` (`webui/pages/legal.py`, rendert MD aus `knowledge/legal/`: `impressum.md` § 5 DDG, `datenschutz.md` Art. 13 DSGVO inkl. Drittland Tunesien + 183-Tage-Löschung + TDDDG § 25, `agb.md` Plattform-AGB, `kontakt.md`; Rechtsträger Agic Tunisie GmbH, Sitz Ben Arous/Tunesien, MwSt-ID 1096754W, Kontakt contact@zedintek.com als Text (**kein** `mailto`); Footer verlinkt alle vier — **anwaltlich zu prüfen, keine Rechtsberatung**). Spec: `knowledge/system/i18n.md`, `knowledge/legal/*.{en,fr,ar}.md`.
- **03.10.2026:** i18n-Phasen 1–6b + RTL-Fix (siehe i18n-Abschnitt).
