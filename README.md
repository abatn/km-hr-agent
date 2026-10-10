# 🤖 KM-HR-Agent

KI-gestützter HR-Agent für kleine und mittlere Unternehmen: Bewerbungen werden extrahiert, gematcht, auf Compliance geprüft, eingeladen und ins Onboarding überführt — mit **Mensch-in-der-Schleife** (der Agent lädt/lehnt nie selbst ein oder ab).

Haupt-App = **NiceGUI** (`webui/`, Port 8080). Streamlit `app.py` ist seit 23.09.2026 archiviert (nur Paritäts-Referenz).

---

## Inhalt

- [Starten](#starten)
- [Architektur](#architektur)
- [Projektstruktur](#projektstruktur)
- [Tests](#tests)
- [Wissensbasis](#wissensbasis)
- [Mitwirken](#mitwirken)

---

## Starten

```bash
source .venv-streamlit/bin/activate
./start-webui.sh          # lädt ./.env, öffnet http://localhost:8080
```

Der Starter **verweigert den Start** ohne `KMHR_STORAGE_SECRET` + `KMHR_ADMIN_SEED_PASSWORD` (rc=1). Vorlage: `.env.example`. Entwicklung ohne Secrets bewusst: `KMHR_DEV=1 ./start-webui.sh`. Spec: `knowledge/system/configuration-secrets.md`.

## Architektur

- **`webui/`** – NiceGUI-App (einzige UI): `main.py`, `db.py` (SQLite-Layer), `logic.py` (frameworkfrei), `theme.py`, `components.py`, `pages/`, `i18n.py`, `locales/`.
- **`scripts/agent-runner.py`** – Hybrid-Hintergrund-Runner (Queue `agent_tasks`): deterministische Tasks über die MCP-Connectoren, LLM-Tasks über die NVIDIA-API.
- **`knowledge/`** – Wissensbasis (Specs, Index in `knowledge.md`). **`skills/`** – Skill-Definitionen (`SKILL.md`, Übersicht `skills/README.md`).
- **`connectors/`** – HR-System-Connectoren (Personio/SAP/Workday).
- **`app.py`** – archivierter Streamlit-Altstand (Paritäts-Referenz).

Datenfluss, Rollen, Scoring, Automatisierung und Datenschutz stehen in den Specs — siehe [Wissensbasis](#wissensbasis).

## Projektstruktur

```
km-hr-agent/
├── webui/                  # NiceGUI-App (main, db, logic, theme, components, pages/, i18n.py, locales/)
├── scripts/agent-runner.py # Hintergrund-Runner (Queue → Mails/LLM/Berichte)
├── skills/                 # Skill-Definitionen (SKILL.md)
├── knowledge/              # Wissensbasis (legal/, lifecycle/, portal/, system/, …)
├── connectors/             # HR-System-Connectoren
├── tests/                  # pytest + E2E (Playwright)
├── ergebnisse/             # Berichte + Entscheidungen (entscheidungen.md)
├── data/feedback.db        # SQLite
├── app.py                  # Streamlit-Archiv (Paritäts-Referenz)
├── AGENTS.md               # Projektwissen für Agenten (operativ)
└── start-webui.sh          # Dev-Starter (liest ./.env)
```

## Tests

```bash
pytest -q                       # Unit-Tests
python3 tests/e2e_isolation.py  # E2E isoliert (Playwright) — NIE gegen die Live-App
```

Zahlen, CI-Parität und Konten: `AGENTS.md` (Tests) + `knowledge/system/e2e-ci-seed.md`.

## Wissensbasis

| Thema | Ort (Quelle-der-Wahrheit) |
|---|---|
| Projektwissen für Agenten (Setup, Tests, CI-Gates, Gotchas) | `AGENTS.md` |
| Rollen & Zugriff (Agent-/Portal-Ebene, ADMIN) | `knowledge/system/access-control.md` |
| Skill-Definitionen | `skills/README.md` + `skills/*/SKILL.md` |
| Scoring & Feedback-Loop | `knowledge/lifecycle/matching-criteria.md`, `knowledge/lifecycle/feedback-schema.md` |
| Agent-Automatisierung (Runner, Mails, Trigger) | `knowledge/system/agent-automation.md` |
| MCP-Connectoren (Census/Konfiguration) | `instructions.md`, `knowledge/system/mcp-connector-config.md` |
| Datenschutz | `knowledge/legal/gdpr-policy.md`, `knowledge/legal/dsgvo-gate.md` |
| Doku-Authority (Regeln für Doku↔Code) | `knowledge/system/doku-authority.md` |
| Wissens-Index | `knowledge.md` |
| Entscheidungs-Log | `ergebnisse/entscheidungen.md` |

## Mitwirken

Siehe [`CONTRIBUTING.md`](CONTRIBUTING.md) — die **Lab-Prinzipien** sind bindend: Quelle finden, MD-first, Konsistenz, Transparenz, Iteration.
