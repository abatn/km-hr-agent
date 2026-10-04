# 🤖 KM-HR-Agent

> **Stand 04.10.2026** · Haupt-App = **NiceGUI** (`webui/`, Port 8080). Streamlit `app.py` ist seit 23.09.2026 **archiviert** (nur Paritäts-Referenz, `start.sh` verweigert den Start).
> **Inventar:** 23 Skills · 47 Knowledge-MD · 16 DB-Tabellen · 14 MCP-Server · **354 Tests** (`pytest -q`).
> **Maßgebliche Doku:** `AGENTS.md` (Projektwissen), `instructions.md`, `knowledge.md`, `skills/README.md`, `knowledge/`.

KI-gestützter HR-Agent für kleine und mittlere Unternehmen: Bewerbungen werden extrahiert, gematcht, auf Compliance geprüft, eingeladen und ins Onboarding überführt — mit **Mensch-in-der-Schleife** (der Agent lädt/lehnt nie selbst ein oder ab).

---

## Inhalt

- [Starten](#starten)
- [Architektur](#architektur)
- [Skills](#skills)
- [Portale & Rollen](#portale--rollen)
- [Agent-Automatisierung](#agent-automatisierung)
- [Meeting-Provider (VDO.Ninja)](#meeting-provider-vdoninja)
- [Mehrsprachigkeit (i18n)](#mehrsprachigkeit-i18n)
- [MCP-Connectoren](#mcp-connectoren)
- [Datenschutz (DSGVO)](#datenschutz-dsgvo)
- [Tests](#tests)
- [Projektstruktur](#projektstruktur)
- [Mitwirken](#mitwirken)

---

## Starten

```bash
source .venv-streamlit/bin/activate
./start-webui.sh          # lädt ./.env, öffnet http://localhost:8080
```

Der Starter **verweigert den Start** ohne `KMHR_STORAGE_SECRET` + `KMHR_ADMIN_SEED_PASSWORD` (rc=1). Vorlage: `.env.example`.
Entwicklung ohne Secrets bewusst: `KMHR_DEV=1 ./start-webui.sh`.
Spec: `knowledge/system/configuration-secrets.md`.

## Architektur

- **`webui/`** – NiceGUI-App (einzige UI): `main.py`, `db.py` (SQLite-Layer), `logic.py` (frameworkfrei), `theme.py`, `components.py`, `pages/`, `i18n.py`, `locales/`.
- **`scripts/agent-runner.py`** – Hybrid-Hintergrund-Runner (Queue `agent_tasks`): deterministische Tasks (Mails, ICS, Fragen, Raum-URL) über die Projekt-MCP-Connectoren, LLM-Tasks (Extract/Match/Compliance/Culture-Fit/verify_documents/check_visa) über die **direkte NVIDIA-API**.
- **`app.py`** – archivierter Streamlit-Altstand (nur Paritäts-Referenz).
- **`knowledge/`** – Wissensbasis (Recht, Lifecycle, Portal, System-Specs). **`skills/`** – 23 Skill-Definitionen (`SKILL.md`).
- **`data/feedback.db`** – SQLite (16 Tabellen: candidates, employers, jobs, applications, feedback, agent_tasks, …).

**Datenfluss (Bewerbung):** CV-Upload → `extract_profile` → `match_candidate` → `check_compliance` → `assess_culture_fit` → HR-Entscheidung → Einladung/Ablehnung → Onboarding → Feedback.

## Skills

Vollständig: `instructions.md` §Skills + `skills/README.md`.

| # | Skill | Zweck |
|---|---|---|
| 1 | `extract-profile` | Lebenslauf → strukturiertes Profil |
| 2 | `match-candidate` | Kandidat × Stelle → Score 0–100 (7 Kategorien) |
| 3 | `check-compliance` | DE/FR/CH + DSGVO (Land-Routing über `ansvar-*-law`) |
| 4 | `contact-candidate` | Personalisierte E-Mail |
| 5 | `assess-culture-fit` | Kultur-Fit |
| 6 | `pre-screen` | Screening-Fragen + Meeting-Raum (VDO.Ninja) |
| 7 | `generate-onboarding` | Onboarding-Checkliste |
| 8 | `store-feedback` | SQLite + dynamische Gewichtung |
| 9 | `handle-errors` | Fehlerprotokoll + klare Nutzermeldungen |
| 10 | `employer-portal` | Arbeitgeber: Registrierung, Stellen, Bewerber, Feedback |
| 11 | `job-application` | Kandidat: Stellen ansehen, bewerben, Status verfolgen |
| … | + `verify-documents`, `check-visa`, `check-gdpr`, `explain-match`, `notify-user`, `export-report`, `language-course`, `housing-search`, `relocation`, `contract-management`, `mentoring`, `candidate-portal` | siehe `skills/` |

## Portale & Rollen

Zwei-Ebenen-Modell (Spec: `knowledge/system/access-control.md`): Skills 0–5 laufen auf der **Agent-Ebene** (unsichtbar für Portal-Rollen).

| Rolle | Umfang |
|---|---|
| **GAST** | Landingpage + Login |
| **CANDIDATE** | 7 Tabs: 📊 Dashboard · 👤 Mein Profil (inkl. CV-Upload + Dokumente) · 💼 Stellen · 📨 Bewerbungen · 🗣️ Sprachtest · 📹 Pre-Screen · 📋 Onboarding |
| **EMPLOYER** | 11 Seiten: 📊 Dashboard · 🏢 Portal · 💼 Stellenangebote · 🔍 Kandidaten-Suche · 📄 Match-Ergebnis · ✅ Compliance · 🔎 Agent-Details · 🗂️ Dokumente · 📞 Pre-Screen · 📋 Onboarding · 💬 Feedback |
| **ADMIN** | 12 Seiten inkl. ausführbarer Agent-Tools |

**Matching-Regel:** Status ≥ `lebenslauf_hochgeladen` UND ≥ 1 Must-Have-Skill-Treffer UND ≥ 50 % der geforderten Erfahrung.
**Bewerbungs-Lifecycle:** eingegangen → angesehen → eingeladen → eingestellt (bzw. abgelehnt / zurückgezogen). Spec: `knowledge/lifecycle/application-status.md`.
**Kontaktdaten** werden erst ab Status `eingeladen` freigegeben (Art. 6(1)(b) DSGVO).

## Agent-Automatisierung

Spec (Source of Truth): `knowledge/system/agent-automation.md`.

| Event | Automatische Kette |
|---|---|
| CV-Upload | `extract_profile` (+ DB-Update der Kandidatenfelder) |
| Bewerbung | Bestätigungs-Mail + Match / Compliance / Culture-Fit + `explain_match` + `check_gdpr` + `notify_user` + `verify_documents` + `check_visa` |
| Pförtner (JA/NEIN) | Score ≥ 60 **und** COMPLIANT → Info-Mail an HR, sonst NEIN (keine Mail, Ergebnisse bleiben sichtbar) |
| HR-Klick `→ eingeladen` | VDO.Ninja-Raum + Fragen + ICS + Einladungs-Mail |
| HR-Klick `→ abgelehnt` | neutrale Absage-Mail (AGG-sicher) |
| HR-Klick `→ eingestellt` | Onboarding-Freigabe (+ Willkommens-Mail) |

**Variante A (Mensch-in-der-Schleife):** Einladung/Absage nur nach HR-Klick — der Agent entscheidet nie selbst.
**LLM:** direkte NVIDIA-API (`requests.post`), Modell `nvidia/nemotron-3-super-120b-a12b` (env-overridebar `KMHR_LLM_MODEL`), Fallback-Kette `nemotron-120b → lightning-30b → kimi-k3`, Exponential Backoff 5/10/20 s.

## Meeting-Provider (VDO.Ninja)

**VDO.Ninja only** — kein Google Meet, kein Jitsi. Spec: `knowledge/system/vdo-ninja-migration.md`.

- **HR/Director:** `https://vdo.ninja/?director=prescreening{code}`
- **Kandidat/Gast:** `https://vdo.ninja/?room=prescreening{code}&record=off`
- **Kandidaten-Selbstpräsentation (Solo-Sender):** `https://vdo.ninja/?push=<id>&record=6000`
- Raumname **alphanumerisch** (VDO-Anforderung); Aufnahme nur nach Einwilligung (`knowledge/legal/recording-consent.md`).

## Mehrsprachigkeit (i18n)

gettext + Babel, Sprachen **DE/EN/FR/AR**, Sprachumschalter im Header, **RTL** bei Arabisch.
`webui/i18n.py` (`_()`/`get_language`/`set_language`/`is_rtl`/`apply_direction`/`language_switcher`), Kataloge `webui/locales/*/LC_MESSAGES/messages.{po,mo}` (**545 Keys**).
Spec: `knowledge/system/i18n.md`. Rechts-Seiten als MD je Sprache (`knowledge/legal/<name>.<lang>.md`).

## MCP-Connectoren

**14 Server** in `opencode.json` (13 lokal + 1 remote): `playwright`, `filesystem`, `fetch`, `pdf-reader`, `meeting-tools`, `email-sender`, `ansvar-german-law`, `ansvar-french-law`, `ansvar-swiss-law`, `anysearch`, `hr-benchmark`, `salary-data`, `prescreen-config`, `language-test`.
Doku: `knowledge/system/mcp-connector-config.md`.

## Datenschutz (DSGVO)

- **Löschung:** `dsgvo_cleanup()` löscht Bewerbungen + Status-Historie **183 Tage** nach Prozessende (Art. 17 DSGVO); aktive Bewerbungen nie.
- **Datenminimierung:** Kontaktdaten erst ab `eingeladen`; HR sieht pseudonyme Kandidaten (`Kandidat #N`).
- **Aufnahme:** nur nach Einwilligung (§ 26 Abs. 2 BDSG), Härtung `&record=off` auf dem Gast-Link.
- Specs: `knowledge/legal/{gdpr-policy,dsgvo-gate,recording-consent,datenschutz}.md`.

## Tests

```bash
pytest -q                       # 354 passed (Stand 04.10.2026)
python3 tests/e2e_isolation.py  # E2E isoliert (Playwright) — NIE gegen die Live-App
```

**R6-0:** E2E nur isoliert über `tests/e2e_isolation.py` (der Harness bricht ohne `KMHR_E2E_BASE` ab). Vorher prüfen, dass der Port frei ist.

## Projektstruktur

```
km-hr-agent/
├── webui/                  # NiceGUI-App (main, db, logic, theme, components, pages/, i18n.py, locales/)
├── scripts/agent-runner.py # Hintergrund-Runner (Queue → Mails/LLM/Berichte)
├── skills/                 # 23 Skill-Definitionen (SKILL.md)
├── knowledge/              # Wissensbasis (legal/, lifecycle/, portal/, system/)
├── connectors/             # HR-Connectoren (hr-benchmark, salary-data, prescreen-config)
├── tests/                  # pytest + E2E (Playwright)
├── ergebnisse/             # Berichte + Entscheidungen (entscheidungen.md)
├── data/feedback.db        # SQLite (16 Tabellen)
├── app.py                  # Streamlit-Archiv (Paritäts-Referenz)
├── AGENTS.md               # Projektwissen + Lab-Prinzipien
└── start-webui.sh          # Dev-Starter (liest ./.env)
```

## Mitwirken

Siehe [`CONTRIBUTING.md`](CONTRIBUTING.md) — die **Lab-Prinzipien** sind bindend: Quelle finden, MD-first, Konsistenz, Transparenz, Iteration.

---

*Zahlen-/Faktenabgleich aus `AGENTS.md` + `knowledge/` am 04.10.2026.*
