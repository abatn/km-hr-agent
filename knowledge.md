# KM-HR-Agent – Wissensübersicht (Index)

> **Doku-Authority v1.0 (`knowledge/system/doku-authority.md`):** Diese Datei ist der **deskriptive Wissens-Index** — Verweise + eine datierte Inventar-Messung. Fakten stehen in den Specs (`knowledge/**`), operative Regeln in `AGENTS.md`, Rollen/Zugriff in `knowledge/system/access-control.md`, Einstieg in `README.md`.

## Inventar (Messung 10.10.2026)

| Merkmal | Wert | Befehl |
|---|---|---|
| Skills | 23 | `ls skills/*/SKILL.md \| wc -l` |
| Knowledge-MD | 73 | `find knowledge -name '*.md' -not -name '*.bak*' \| wc -l` (Verlauf: 72 am 10.10.2026 früh, 47 am 01.10.2026) |
| DB-Tabellen | 16 | `data/feedback.db` |
| MCP-Server | 14 | `opencode.json` (`mcpServers`) |
| i18n-msgid je Sprache | 993 | `grep -c '^msgid ' webui/locales/de/LC_MESSAGES/messages.po` |
| Unit-Tests | 434 passed | `.venv-streamlit/bin/python3 -m pytest -q` |
| E2E-Dateien | 50 (48 lauffähig) | `ls tests/e2e_*.py \| wc -l` |

## Überblick

Minimal-Prototyp für 23 HR-Recruiting-Skills: Profil-Extraktion aus PDF/TXT, Matching (Score 0–100), Compliance (DE/FR/CH + DSGVO), E-Mails, Kultur-Fit, Pre-Screening, Onboarding, Feedback in SQLite; Arbeitgeber-Portal mit Stellen und anonymisiertem Kandidaten-Ranking. UI und Doku primär auf Deutsch.

## Wissens-Index (`knowledge/**`)

| Bereich | Specs |
|---|---|
| `system/` | `access-control.md` (Rollen/Zugriff, Source of Truth) · `agent-automation.md` (Runner, Mails, Trigger) · `configuration-secrets.md` · `deploy-pipeline.md` · `doku-authority.md` (Doku-Regeln) · `e2e-ci-seed.md` (Test-Konten) · `i18n.md` + `i18n-runner-chain.md` · `mcp-connector-config.md` · `mcp-agent-backlog.md` · `mcp-tool-lazy-gating.md` · `vdo-ninja-migration.md` · `mvp.md` · `c2-service.md` · `event-loop-blockieren.md` · `p8-cloud-datenquellen.md` |
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
