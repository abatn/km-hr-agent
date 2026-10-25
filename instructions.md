# Rolle: KM-HR-Agent (Recruiting-Match) – v4.5

> **Version:** 4.5 (Zwei-Ebenen-Modell: Agent-Ebene vs. Portal-Ebene, Matching/Feedback Phase 2–4.6) · **Stand:** September 2026
> **Doku-Authority (`knowledge/system/doku-authority.md`):** diese Datei = **Workflow-Handbuch + MCP-Connector-Census** (deskriptiv). Rollen-/Zugriffsregeln → `knowledge/system/access-control.md` (Source of Truth) · Skill-Definitionen → `skills/README.md` + `skills/*/SKILL.md` · Scoring/Feedback → `knowledge/lifecycle/matching-criteria.md` + `knowledge/lifecycle/feedback-schema.md` · Automatisierung → `knowledge/system/agent-automation.md` · Connector-Konfiguration → `knowledge/system/mcp-connector-config.md`.

## Funktionierende MCP-Connectoren & Tools — **49 dokumentiert (instructions.md) / 181 live (Handshake 26.09.2026)** (Censusstand 26.09.2026; §G-Nachzug 26.09.2026 ergänzt anysearch 4 + create_meeting_link 1 → vorher 44; Rest-Differenz 132 = undokumentierte Live-Tools, Voll-Liste `ergebnisse/mcp-connector-audit-2026-09-25.md` §6.3)

### Core Connector ( alle funktionieren)

| Connector | Tool | Typ | Status | Verwendung |
|---|---|---|---|---|
| `hr-benchmark` | `calculate_weighted_score`, `get_score_category`, `get_weight_ranges` | MCP (Python) | ✅ FUNKTIONIERT | ZYTHR-Formel: (score/max) × weight |
| `salary-data` | `calculate_salary_band`, `calculate_salary_position`, `calculate_salary_tolerance` | MCP (Python) | ✅ FUNKTIONIERT | BambooHR: Min/Mid/Max = 25th/50th/75th |
| `prescreen-config` | `get_optimal_duration`, `get_screening_questions`, `get_screening_structure` | MCP (Python) | ✅ FUNKTIONIERT | CareerPlug: 15-30 Minuten |
| `language-test` | `generate_test`, `score_answer`, `get_cefr_level` | MCP (Python) | ✅ FUNKTIONIERT | CEFR-Niveautests: 732 Fragen (DE 120, EN 522, FR 90) + LLM-generierte Zusatzfragen (hybrid), LLM-Bewertung via NVIDIA API |
| `filesystem` | `read_text_file` | MCP (local) | ✅ FUNKTIONIERT | TXT/MD-Dateien lesen |
| `filesystem` | `write_file` | MCP (local) | ✅ FUNKTIONIERT | Ergebnisse speichern |
| `filesystem` | `list_directory` | MCP (local) | ✅ FUNKTIONIERT | Verzeichnisse durchsuchen |
| `filesystem` | `search_files` | MCP (local) | ✅ FUNKTIONIERT | Dateien/Muster suchen (26.09.2026 korrigiert: `glob` existiert in `tools/list` nicht mehr — Phantom, Ist `search_files`) |
| `ansvar-german-law` | `search`, `validate_citation`, `get_provision` | MCP (mcp-remote) | ✅ FUNKTIONIERT | DE-Recht (6.870 Gesetze) |
| `ansvar-french-law` | `search`, `validate_citation`, `get_provision` | MCP (mcp-remote) | ✅ FUNKTIONIERT | FR-Recht (3.958 Gesetze) |
| `ansvar-swiss-law` | `search`, `validate_citation`, `get_provision` | MCP (mcp-remote) | ✅ FUNKTIONIERT | CH-Recht (4.873 Gesetze) |
| `pdf-reader` | `read_pdf_text`, `get_pdf_info`, `analyze_pdf_structure` | MCP (Python) | ✅ FUNKTIONIERT | PDF-Text extrahieren |
| `meeting-tools` | `generate_screening_questions`, `generate_ics_file`, `create_meeting_link` | MCP (Python) | ✅ FUNKTIONIERT | Screening-Fragen + ICS generieren (`create_meeting_link` = LEGACY, wird nicht genutzt; URL seit 27.09.2026 VDO.Ninja statt Jitsi) |
| ~~`jitsi-meeting`~~ | — | — | **ENTFERNT 27.09.2026** | 0 Aufrufe im Code; VDO.Ninja-Migration (Spec `knowledge/system/vdo-ninja-migration.md`) |
| `email-sender` | `send_email`, `send_interview_invitation`, `send_pre_screen_invitation` | MCP (Python) | ✅ FUNKTIONIERT | E-Mails via SMTP (Server aus `.env-email`; **seit 24.09.2026 Gmail** smtp.gmail.com:587 STARTTLS, davor Yahoo) |
| `playwright` | `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_fill_form`, `browser_find`, `browser_close` | MCP (npx) | ✅ FUNKTIONIERT | Browser-Automation (Chromium), Webseiten laden und auslesen |
| `fetch` | `fetch` | MCP (uvx) | ✅ FUNKTIONIERT | HTTP-Fetch (Web-Inhalte laden) |
| `anysearch` | `search`, `extract`, `batch_search`, `get_sub_domains` | MCP (remote) | ✅ **anonym/schlüsselfrei seit 01.10.2026** (nur `X-Anysearch-Client`; die `Authorization`-Zeile wurde am 01.10.2026 aus `opencode.json` **entfernt**, H9 geschlossen; wirksam nach OpenCode-Neustart) | Websuche (Heimatland-Suche, Kurse) |

### PDF-Extraktion (CLI, nicht MCP)

| Tool | Typ | Status | Verwendung |
|---|---|---|---|
| `resume-parser-ats` | CLI (npm) | ✅ Installiert | PDF → strukturierte Daten |

### HR-Aggregator / Jobboard-API (optional, nicht aktiv)

| Connector | Tool | Typ | Status | Voraussetzung |
|---|---|---|---|---|
| `arbeitsamt` | Jobsuche-API (Bund-Jobboard) | REST (öffentlich) | ⏳ Configuriert (nicht aktiv) | OAuth (öffentliche APIs) |
| `arbeitnow` | Europe/Remote Job Aggregator | REST (öffentlich) | ⏳ Configuriert (nicht aktiv) | Kein Key nötig |

## Nicht verfügbare Connectors

| Tool | Status | Notiz |
|---|---|---|
| `aspose-pdf-foss-mcp` | Nicht installiert | Nicht benötigt (pdf-reader vorhanden) |
| `excel-mcp` | Nicht installiert | Nicht benötigt |
| `email-mcp` / `slack-mcp` | Nicht installiert | Nicht benötigt (E-Mail-Vorlage vorhanden) |
| `arbeitsamt` | Nicht konfiguriert | OAuth nötig (öffentlich) |
| `arbeitnow` | Nicht konfiguriert | REST-API, kein Key nötig |

## Entfernte Connectors (aus opencode.json gelöscht)

| Alter Connector | Grund der Entfernung |
|---|---|
| `pdf-connector` (@sylphx/citra) | Citra erwartet Base64, kein direkter Pfad → resume-parser-ats als Alternative |
| `prismhr-mcp` | Nicht installiert, proprietäre API-Zugangsdaten nötig → arbeitsamt/arbeitnow als Alternative |
| `breathehr-mcp` | Nicht installiert, API-Key nötig → arbeitnow als Alternative |
| `swagger-mcp` | Kein HR-Fokus, braucht Swagger-URL → nicht benötigt |
| `citycompliance-mcp` | Nicht in npm/Registry vorhanden |
| `france-legal-mcp` | Nicht in npm/Registry vorhanden |
| `swiss-legal-mcp` | Nicht in npm/Registry vorhanden |
| `fallback-config` | Falsche Quelle (SSRN-ID 4893265 existiert nicht) – entfernt 15.09.2026 |
| `gewicht-cap` | Falsche Quelle (Nature-Artikel = AlphaFold 3, nicht HR) – entfernt 15.09.2026 |

## Skills

**23 Stück – alle aktiv** (Stand 24.09.2026). Die Skill-Tabelle mit Tool-Zuordnung und Nummern-Nachweis steht in `skills/README.md`, jede Detail-Spec in `skills/<name>/SKILL.md`.

## Jobportal-Prinzip (Zugriffskontrolle)

UNREGISTRIERT → nichts · REGISTRIERT → Profil · LEBENSLAUF → Matching · MATCHING → Ergebnis sehen. Eine Session = eine Rolle (GAST / CANDIDATE / EMPLOYER / ADMIN); die Agent-Skills 0–5 laufen auf der Agent-Ebene (opencode + MCP) und sind für Portal-Rollen unsichtbar.

**Maßgeblich ist `knowledge/system/access-control.md` (Source of Truth)** — Rollen-Matrix, Seiten-Matrix, ADMIN-Regeln und Umsetzungsstatus stehen dort; hier steht nur die Prinzip-Kurzfassung.

### Profil-Check (Skills 2–8)

Regel: Matching (Skill 2) und alle darauf aufbauenden Skills (3–8) nur bei Kandidat-Status ≥ `lebenslauf_hochgeladen`. Status-Whitelist, SQL, Fehlermeldung und die CV-Pflicht-Geschichte: `knowledge/portal/cv-pflicht.md` (Quelle-der-Wahrheit).

## Workflow (MCP-konform)

### Standard-Workflow (ohne HR-Integration)

1. **Lebenslauf lesen** → `filesystem` → `read_text_file` (TXT/MD)
2. **PDF parsen (falls PDF)** → `pdf-reader` → `read_pdf_text` (Python MCP)
3. **Profil extrahieren** → `extract-profile` Skill (MCP-konform)
4. **Compliance prüfen** → `check-compliance` Skill (`read_text_file` + ansvar-*-law)
5. **DSGVO prüfen** → `check-gdpr` Skill (`read_text_file` + knowledge/)
6. **Kultur-Fit bewerten** → `assess-culture-fit` Skill (`read_text_file` + Logik)
7. **Match berechnen** → `match-candidate` Skill (`read_text_file` + LLM)
8. **Pre-Screening** → `meeting-tools` → `generate_screening_questions` (Python MCP)
9. **Screening-Fragen** → `meeting-tools` → `generate_screening_questions`
10. **Onboarding generieren** → `generate-onboarding` Skill (`write_file`)
11. **Feedback speichern** → `store-feedback` Skill (`write_file`)
12. **Ergebnis speichern** → `write_file` in ergebnisse/

### Optional: Mit öffentlichen Job-APIs

1. **Job-API auswählen** → arbeitnow (kein Key) oder arbeitsamt (OAuth)
2. **API-Aufruf** → HTTP GET (REST)
3. **Stellen abrufen** → Jobs aus dem API-Feed
4. **Daten speichern** → write_file → ergebnisse/jobs/{JJJJ-MM-TT}.md (Laufzeit-Artefakt; `knowledge/**` ist normativ und wird nur redaktionell gepflegt — Spec `knowledge/system/md-schreib-konvention.md` §0, R-S4)
5. **Profil erstellen** → extract-profile (aus Lebenslauf)
6. **Matching** → match-candidate (Profil vs. Stelle)
7. **Ergebnis speichern** → write_file → ergebnisse/

### Automatisiert: Agent-Queue + Hybrid-Runner

Portal-Ereignis → Task in `agent_tasks` → `scripts/agent-runner.py` (60-s-Loop, max. 3 Versuche): deterministische Tasks (Mails, ICS, Fragen, VDO.Ninja-Raum) direkt über die Projekt-MCP-Connectoren, LLM-Tasks über die direkte NVIDIA-API. Trigger, Pförtner-Regel, Variante A und E-Mail-Matrix: **`knowledge/system/agent-automation.md`** (Quelle-der-Wahrheit).

## Speicherorte

| Inhalt | Pfad |
|---|---|
| Testdaten | `testdaten/` |
| Knowledge | `knowledge/` |
| Ergebnisse | `ergebnisse/` |
| Feedback | SQLite `feedback`-Tabelle in `data/feedback.db` (**Datei `data/feedback.md` existiert nicht** — frühere Angabe falsch; Claude-Altlog unter `ergebnisse/feedback-log.md`) |
| SQLite (Kandidaten, Arbeitgeber, Stellen, **Bewerbungen**, Feedback) | `data/feedback.db` |
| Error-Log | `logs/agent-errors.log` |

## Historische Hinweise

- **Streamlit-Ära (`app.py`, abgeschaltet 23.09.2026):** der frühere Login-Schutz-Code und die Umsetzungsnarrative stehen im Fakten-Backup `ergebnisse/entscheidungen.md` (Abschnitt „S3: Aus Root-Dokus entfernte/verdichtete Blöcke"). Das laufende Login-Gate ist in `knowledge/system/access-control.md` dokumentiert.
- **Matching & Feedback (Phase 2–4.6):** die frühere Phasen-Tabelle dieser Datei ist im selben Fakten-Backup; maßgeblich sind die Specs (`knowledge/lifecycle/matching-criteria.md`, `feedback-schema.md`, `application-status.md`, `knowledge/system/agent-automation.md`).
