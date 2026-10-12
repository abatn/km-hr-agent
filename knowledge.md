# KM-HR-Agent – Wissensübersicht (Index)

> **Doku-Authority v1.0 (`knowledge/system/doku-authority.md`):** Diese Datei ist der **deskriptive Wissens-Index** — Verweise + eine datierte Inventar-Messung. Fakten stehen in den Specs (`knowledge/**`), operative Regeln in `AGENTS.md`, Rollen/Zugriff in `knowledge/system/access-control.md`, Einstieg in `README.md`. **Ein Fakt steht an genau einem Ort** — hier stehen Zeiger, keine Duplikate.

## Überblick

Minimal-Prototyp für 23 HR-Recruiting-Skills: Profil-Extraktion aus PDF/TXT, Matching (Score 0–100), Compliance (DE/FR/CH + DSGVO), E-Mails, Kultur-Fit, Pre-Screening, Onboarding, Feedback in SQLite; Arbeitgeber-Portal mit Stellen und anonymisiertem Kandidaten-Ranking. **Mensch-in-der-Schleife:** der Agent lädt/lehnt nie selbst ein oder ab. UI und Doku primär auf Deutsch.

## Wo liegt was (Key Code)

| Ort | Inhalt |
|---|---|
| `webui/` | NiceGUI-App (einzige UI, Port 8080): `main.py`, `db.py` (SQLite-Layer), `logic.py` (frameworkfrei), `theme.py`, `components.py`, `pages/`, `i18n.py`, `locales/` |
| `scripts/agent-runner.py` | Hybrid-Hintergrund-Runner (Queue `agent_tasks`): deterministische Tasks über MCP-Connectoren, LLM-Tasks über NVIDIA-API |
| `connectors/` | HR-System-Connectoren (Personio/SAP/Workday) + `hr-api-connectors.md` |
| `mcp-*-server.py` | MCP-Server (u. a. email, pdf, meeting) — Konfiguration in `opencode.json` (14 Server) |
| `skills/` | 23 Skill-Definitionen (`skills/*/SKILL.md`, Übersicht `skills/README.md`) |
| `knowledge/` | Wissensbasis (Specs) — siehe Wissens-Index unten |
| `tests/` | pytest (Unit/Integration) + E2E (Playwright, `tests/e2e_*.py`) |
| `ergebnisse/` | Berichte + Entscheidungslog (`entscheidungen.md`, Lab-Schritt 4) |
| `data/feedback.db` | SQLite (16 Tabellen) — **Live-DB nie direkt beschreiben** |
| `app.py` | Streamlit-Archiv (Paritäts-Referenz, seit 23.09.2026 abgeschaltet) |

## Befehle (Auszug — maßgeblich: `AGENTS.md`)

```bash
# Setup
python3 -m venv .venv-streamlit && source .venv-streamlit/bin/activate
pip install -r requirements.txt
cp .env.example .env        # KMHR_STORAGE_SECRET + KMHR_ADMIN_SEED_PASSWORD setzen

# Dev (einzige UI → http://localhost:8080)
./start-webui.sh            # verweigert Start ohne Secrets (rc=1)
KMHR_DEV=1 ./start-webui.sh # Entwicklung ohne Secrets (nur lokal)

# Tests
.venv-streamlit/bin/python3 -m pytest -q          # Unit — Testzahlen maßgeblich: AGENTS.md
python3 tests/e2e_isolation.py <port>             # E2E isoliert — NIE gegen Live-App :8080

# Lint / Syntax (CI-Parität)
.venv-streamlit/bin/python3 -m pyflakes webui/ scripts/ connectors/ tests/
.venv-streamlit/bin/python3 -m compileall -q webui/ scripts/ connectors/

# Doku-Gates (Pflicht vor Commit)
./.venv-streamlit/bin/staledocs check --gate strict   # rc=0, Doku↔Code
npx -y docrot-cli --fail-on=error                    # A+, rc=0

# i18n
.venv-streamlit/bin/pybabel compile -d webui/locales
```

Kein Formatter konfiguriert — die CI-Gates (`ci.yml`, Doc-Gates) sind verbindlich. Deploy: `git push` → CI → `deploy-contabo.yml` (Spec `knowledge/system/deploy-pipeline.md`).

## Konventionen, Constraints & Gotchas (Zeiger — maßgeblich: `AGENTS.md`)

- **Lab-Prinzipien (Gesetz):** Quelle finden → MD-first → Konsistenz → Transparenz (`ergebnisse/entscheidungen.md`) → Iteration → Pflicht-Prüfkette (6 Punkte, alle rc=0) vor jedem Commit.
- **i18n:** kein f-String in `_()`; Modul-Konstanten mit UI-Strings erst zur Renderzeit übersetzen (Ruff INT001).
- **Zitate:** `Datei:Zeile` ist kein stabiler Verweis → Codemarke (`PAGE_MAP`, `_TAB_MAP`, …) und/oder Messdatum.
- **`.bak`-Retention:** nur die letzten 2 Kalendertage behalten (`run_bak_retention_once`, `webui/logic.py`).
- **staledocs-Ack-Falle (10.10.2026):** Claims nur bei UNACKED-Paaren — vor Re-Ack `.staledocs/pairs/` leeren und frisch analysieren.
- **E2E-Sleep-Falle (WSL):** `goto` auf `/employer/stellen` hängt den Playwright-Driver — Einladen über den Match-Seiten-Dialog.
- **ASGI-Socket.IO-Guard (10.10.2026):** `webui/asgi_guard.py::SocketioAbortGuard` antwortet 400 statt 500 bei Client-Abbruch/Probe (`knowledge/system/asgi-guard.md`).
- **Nicht tun:** Session-State-Auth nicht produktionsfähig; keine Secrets/Personendaten ins Repo (`.gitignore` deckt `.env*`, `data/`, `ergebnisse/`, `testdaten/`).

## Inventar (Messung 10.10.2026)

| Merkmal | Wert | Befehl |
|---|---|---|
| Skills | 23 | `ls skills/*/SKILL.md \| wc -l` |
| Knowledge-MD | 73 | `find knowledge -name '*.md' -not -name '*.bak*' \| wc -l` (Verlauf: 72 am 10.10.2026 früh, 47 am 01.10.2026) |
| DB-Tabellen | 16 | `data/feedback.db` |
| MCP-Server | 14 | `opencode.json` (Key `mcp`) |
| i18n-msgid je Sprache | 993 | `grep -c '^msgid ' webui/locales/de/LC_MESSAGES/messages.po` |
| Unit-Tests | siehe `AGENTS.md` | `.venv-streamlit/bin/python3 -m pytest -q` |
| E2E-Dateien | 50 (48 lauffähig) | `ls tests/e2e_*.py \| wc -l` |

## Wissens-Index (`knowledge/**`)

| Bereich | Specs |
|---|---|
| `system/` | `access-control.md` (Rollen/Zugriff, Source of Truth) · `agent-automation.md` (Runner, Mails, Trigger) · `configuration-secrets.md` · `deploy-pipeline.md` · `doku-authority.md` (Doku-Regeln) · `e2e-ci-seed.md` (Test-Konten) · `i18n.md` + `i18n-runner-chain.md` · `mcp-connector-config.md` · `mcp-agent-backlog.md` · `mcp-tool-lazy-gating.md` · `vdo-ninja-migration.md` · `mvp.md` · `c2-service.md` · `event-loop-blockieren.md` · `p8-cloud-datenquellen.md` · `asgi-guard.md` |
| `legal/` | `dsgvo-gate.md` · `gdpr-policy.md` · `recording-consent.md` · `compliance-rules.md` · `contract-management.md` · `contract-sources.md` · `visa-rules.md` · `document-types.md` · `datenschutz.md`/`impressum.md`/`agb.md`/`kontakt.md` (je + `.en`/`.fr`/`.ar`) |
| `lifecycle/` | `matching-criteria.md` (Scoring) · `feedback-schema.md` · `application-status.md` · `status-automation.md` · `cultural-fit-criteria.md` · `explanation-templates.md` · `relocation.md` · `mentoring.md` · `referenz-sphinxats.md` |
| `portal/` | `candidate-portal-fields.md` · `employer-portal-fields.md` · `matching-filter.md` · `cv-pflicht.md` · `applicants-first.md` · `housing-search.md` |
| `templates/` | contract- · email- · language- · onboarding-Templates (Vorlagen, kein Code) |
| `profiles/` | `README.md` |
| top-level | `language-tests.md` · `language-courses.md` · `error-statistics.md` · `notification-log.md` · `onboarding-default.md` · `ui-design-system.md` · `team-profile.md` |

Skill-Definitionen: `skills/README.md` (Übersicht) + `skills/*/SKILL.md` (je Skill eine Spec).

## Dependencies

Quelle ist **`requirements.txt`** (Stand 04.10.2026, aus den tatsächlichen Importen; enthält `streamlit` nur als Archiv-Referenz). Nichts kopieren — hier steht nur der Zeiger.

## Test-Report Index (ergebnisse/ – Milestone-Berichte)

| Bericht | Inhalt |
|---|---|
| `e2e-test-login-schutz.md` | Login-Gate, unregistrierte User, Rollen-Zugriffe |
| `schritt-1` … `schritt-8`-Tests (8 Dateien) | Schritt-Tests der 8 Skills (Extract, Match, Compliance, Contact, Culture-Fit, Pre-Screen, Onboarding, Feedback) vom 10.09. |
| `connector-test-2026-09-10.md` | Erster MCP-Connector-Testlauf (alle Connectoren, 10.09.) |
| `archiv/km-hr-agent-connector-fix.md` | Einmal-Bericht (archiviert 10.10.2026): Connector-Fix v4.0 — `filesystem` statt contract-check-Connector (Access-denied-Problem) |
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

**Index-Abdeckung:** Alle Einträge in `ergebnisse/` (Messung `ls ergebnisse | wc -l` = 366, davon 344 `.md`, ⓘ08.10.2026; war 85) sind entweder im Index genannt (Milestone-/Recherche-/Match-Berichte), gehören zu den generierten Agent-Artefakten (E-Mail-/Match-/Compliance-/Onboarding-/Einladungs-Berichte nach `ergebnisse/{type}-{name}-{date}.md`, indexed via naming convention), oder sind Unterverzeichnisse (`contact-candidate/` Mail-Entwürfe, `testdaten/`, `.ics`-Kalendereintrag).
