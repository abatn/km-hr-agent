# AGENTS.md — KM-HR-Agent

HR-Agent für KMU (Bewerbungen extrahieren, matchen, prüfen, einladen, Onboarding). Human-in-the-loop: der Agent lädt oder lehnt nie selbst ein bzw. ab. Sprache der Repo-Doku und der UI: **Deutsch**.

## Architektur

- **UI: NiceGUI** in `webui/` (Port 8080, Override `KMHR_PORT`). Einstieg `webui/main.py`: Secrets-Gate → DB-Bootstrap → Seiten `create_*()` → ASGI-Guard → `ui.run`. Datenzugriff in `webui/db.py` (SQLite, Migrationen als `init_*`), Logik in `webui/logic.py`, Seiten in `webui/pages/`.
- **`app.py` und `start.sh` sind abgeschaltetes Streamlit** (seit 23.09.2026). Nur Paritäts-Referenz; nicht starten oder erweitern. `start.sh` bricht mit rc=1 ab.
- **Runner `scripts/agent-runner.py`**: Queue `agent_tasks`, 60-s-Loop, `MAX_ATTEMPTS = 3`. Startet mit der App (PID `data/agent-runner.pid`); Opt-out `KMHR_RUNNER_AUTOSTART=0`. Dry-Run: `.venv-streamlit/bin/python3 scripts/agent-runner.py --once --dry-run`.
- **Social-Agent** `scripts/social_agent.py` (Default Dry-Run, PII-Guard), OAuth-Bootstrap `scripts/social_oauth.py`, Spec `knowledge/system/social-automation.md`.
- **Werbe-Agent**: `scripts/ads_agent.py` (Dry-Run für Google/Microsoft; Meta live nur PAUSED über `scripts/meta_ads.py`, Video via `advideos`/`video_data`, sonst Link-Ad; Aktivierung separat per `--activate --yes`), Vorabprüfung `--check-meta`, manuelles Startpaket `--kit`; x402-Zahlungsschicht `scripts/ads_x402.py`/`scripts/jobs_x402_feed.py` (eigenes Venv `.venv-ads`, `requirements-ads.txt`, nur Testnetz). Specs: `marketing/ADS_ENTSCHEIDUNG.md`, `marketing/ads-agent.md`.
- **Entgeltmodell** (AGB § 5): `webui/billing.py` + `webui/pages/billing_ui.py`. Zahlung nur per Banküberweisung, kein Online-Zahlungsdienst. Flag `KMHR_BILLING_ENABLED` (Default 0). Ausbildung nur für Arbeitgeber (§ 296a SGB III). Spec: `knowledge/system/configuration-secrets.md` §(h), `knowledge/legal/agb.md` §5.
- **MCP-Tools**: nur die in `opencode.json` registrierten Server/Tools nutzen und in Code/Doku nur deren Namen nennen (u. a. `anysearch`, `fetch`, `pdf-reader`, `email-sender`, `hr-benchmark`, `meeting-tools`). Root-MCP-Server (`mcp-*-server.py`) laufen mit `.venv-pdf/bin/python3`; `connectors/*` und `scripts/language-test-server.py` mit System-`python3`. Externe Dienste nur über diese Wege ansprechen. Ausnahmen: NVIDIA-API im Runner, LinkedIn/Meta/Instagram im Social-Agent.
- **Wissensbasis**: `knowledge/` (Specs, Index `knowledge.md`), `skills/*/SKILL.md` (Index `skills/README.md`). `instructions.md` ist deskriptives Workflow-Handbuch/MCP-Census, keine Regelquelle. Logik gehört in Specs/Skills, Python nur wo nötig (UI, DB, API).
- **Doku-Hierarchie** (`knowledge/system/doku-authority.md`): normative Specs (`knowledge/**`, `skills/*/SKILL.md`, `AGENTS.md`) schlagen deskriptive Doku; Code schlägt deskriptive Doku. Bei Konflikt normativ vs. Code wird **entschieden** (Code anpassen oder Spec als Ist bestätigen) und in `ergebnisse/entscheidungen.md` protokolliert — nicht pauschal „die Doku korrigieren".

## Setup & Start

- Venv: `.venv-streamlit` (Prod: `requirements.txt`, Dev: `requirements-dev.txt`). Der Name „streamlit" ist historisch.
- Start: `./start-webui.sh` (führt `python3 -m webui.main` aus). Ohne `KMHR_STORAGE_SECRET` und `KMHR_ADMIN_SEED_PASSWORD` in `.env` bricht er mit rc=1 ab (fail-closed). Nur lokal ohne Secrets: `KMHR_DEV=1 ./start-webui.sh`. Andere Env-Datei: `KMHR_ENV_FILE`.
- Vier Secret-Dateien, nicht mischen:
  - `.env`: WebUI (Vorlage `.env.example`)
  - `.env-runner`: Runner und `scripts/language-test-server.py` (`NVIDIA_API_KEY`, `KMHR_LLM_MODEL`)
  - `.env-email`: `mcp-email-server.py` (`SMTP_*`)
  - `.env-social`: `scripts/social_agent.py` (Vorlage `.env-social.example`)
  - Alle `chmod 600`.
- Bindung: `KMHR_HOST` (Default `127.0.0.1`; `0.0.0.0` nur bewusst für LAN). `KMHR_COOKIE_SECURE=1` hinter HTTPS.
- Das Live-Admin-Konto trägt noch das alte Seed-Passwort. Die App **nicht aus dem lokalen Netz erreichbar machen**, bis rotiert ist (`knowledge/system/configuration-secrets.md`).
- DB: `data/feedback.db`. Pfad nur über `KMHR_DB_PATH` (WebUI und Runner teilen ihn). **Live-DB nie direkt beschreiben.**
- i18n: `.venv-streamlit/bin/pybabel compile -d webui/locales`. Es gibt kein `babel.cfg`/`.pot`; Kataloge werden gepflegt, nicht extrahiert. Compile ändert die `.mo`-Header aller 4 Sprachen (de/en/fr/ar). Ohne Inhaltsänderung: `git checkout -- webui/locales`. Key-Gleichheit: `python3 scripts/ci/checks.py i18n`.

## Tests

- Unit: `.venv-streamlit/bin/python3 -m pytest -q`. Einzeltest: `.venv-streamlit/bin/python3 -m pytest tests/test_x.py::test_name -q`.
- **CI-Parität** (`.github/workflows/ci.yml`): `mkdir -p data && cp tests/fixtures/seed.db data/feedback.db`, `mkdir -p /tmp/opencode`, `.env` mit Dummy-Secrets, dann `pytest -q --ignore=tests/test_r33_compliance_reports.py --deselect tests/test_ui_fixes_p0.py::test_profile_display_name_kein_dateiname`. Die beiden Ausschlüsse brauchen DSGVO-Daten, die nicht im Repo liegen. Lokal laufen daher mehr Tests als in CI.
- `pytest.ini`: `asyncio_mode = auto`, `testpaths = tests`, `main_file = tests/nicegui_main.py`. `pytest_plugins` steht in der Root-`conftest.py` (pytest 8+) und muss dort bleiben.
- NiceGUI-UI-Tests: Demo-Routen (`@ui.page`) gehören in `tests/nicegui_main.py`, nicht ins Testmodul. Funktionen dort nicht `test_` nennen.
- `tests/conftest.py` spiegelt `tests/fixtures/seed.db` (Fallback: Live-DB) nach `/tmp/opencode` und leitet alle `sqlite3.connect`-Zugriffe dorthin um; `KMHR_LOG_FILE` zeigt auf ein Temp-Log, damit Testfehler nicht in `logs/agent-errors.log` landen. Nicht umgehen. Migrationen, die UI-Tests brauchen, in `webui/main.py` **und** im Spiegel aufrufen.
- `tests/fixtures/seed.db` ist handgepflegt (6 Jobs, 18 Bewerbungen, 2 Arbeitgeber). Nicht mit `scripts/seed_ci_db.py` neu erzeugen, das verschiebt E2E-Baselines und ~10 Unit-Tests. Nur chirurgisch ändern (`knowledge/system/e2e-ci-seed.md`).
- Neue DB-Tabelle: `init_*` in `webui/db.py`, Aufruf in `webui/main.py` **und** `tests/conftest.py`, Tabelle in `tests/fixtures/seed.db` ergänzen und `ERWARTETE_TABELLEN` in `scripts/ci/checks.py` nachziehen — das Gate `schema` vergleicht die Tabellenmenge exakt.
- **E2E (Playwright)** nur über `python3 tests/e2e_isolation.py --port <N>` (Default 8081). Vorher `ss -ltn | grep :<N>` prüfen, sonst testet man einen Alt-Server. Einzelskript: `--only e2e_<name>`; Logs unter `/tmp/opencode/e2e-iso-*`. Nie gegen Port 8080. Einzelskripte ohne Harness brauchen `KMHR_E2E_BASE`. CI-Parität: `KMHR_E2E_SEED=1 KMHR_E2E_SKIP=e2e_m07_row_click`, Port 8097; Seed-Lauf lokal zusätzlich `KMHR_E2E_LIVE_DB=tests/fixtures/seed.db`.
- Bekannt: `goto` auf `/employer/stellen` hängt unter WSL. Einladen über den Match-Dialog nutzen (`knowledge/system/i18n-runner-chain.md` §5).

## Prüfkette vor jedem Commit

Ein roter Punkt bedeutet: kein Commit/Push.

1. `.venv-streamlit/bin/staledocs check --gate strict` (PyPI-Paket `staledocs` 2.1.0; **nicht** `npx staledocs`).
2. `npx -y docrot-cli --fail-on=error`
3. `.venv-streamlit/bin/python3 -m pytest -q`
4. `.venv-streamlit/bin/python3 -m compileall -q webui/ scripts/ connectors/`
5. pyflakes: `.venv-streamlit/bin/python3 -m pyflakes webui/ scripts/ connectors/ tests/ mcp-pdf-server.py mcp-meeting-server.py mcp-email-server.py`. Der Befehl liefert rc=1 bei jedem Hinweis. Blockierend ist nur, was nach dem CI-Filter übrig bleibt (Filter in `.github/workflows/ci.yml`). `app.py` und `docs/` sind ausgenommen.
6. Doku-Änderung: Entscheidung in `ergebnisse/entscheidungen.md` ergänzen (Was/Warum/Quelle). Danach `git status` auf gewollte Dateien prüfen.

Doku-Gates einzeln: `python3 scripts/ci/checks.py <docs|legal|mcp|i18n|schema|mdguard>` (genau ein Bereich pro Aufruf). `docs.yml` läuft auch bei Änderungen an `webui/**`, `scripts/**`, `tests/**`, weil `mdguard` Laufzeit-Schreiber prüft.

Es gibt keine Formatter- oder Linter-Konfiguration im Repo. Nicht nach ruff/black/mypy-Config suchen.

## Gotchas

- `ergebnisse/`, `data/`, `testdaten/`, `.env*`, `.venv-*/`, `logs/` sind gitignored und nicht getrackt (Ausnahmen: `.env.example`, `.env-social.example`). `ergebnisse/entscheidungen.md` landet nie im Commit.
- **NiceGUI-Callbacks**: nie eine `conn` nutzen, die der Seitenaufbau geschlossen hat. Jeder Callback öffnet seine eigene `conn` und schließt sie in `try/finally` (Muster `visa_info_section` in `webui/components.py`; Test `tests/test_conn_closure.py`).
- **i18n**: kein f-String in `_()`, sondern `_('… {x}').format(x=…)`. Modul-Konstanten mit UI-Strings erst zur Renderzeit übersetzen, sonst bricht die Babel-Extraktion.
- **Laufzeit-Schreiber** (Reports, Mails, MD-Artefakte): Ziel ist die Datei des heutigen Datums. Nie die neueste existierende nehmen, nichts aus anderen Dateien übernehmen, nichts abschneiden, nichts in `knowledge/**` oder `skills/**` schreiben (`tests/test_md_writer_discipline.py`).
- **`.bak`-Retention** beim App-Start (`webui/logic.py::run_bak_retention_once`): erlaubt sind nur Backups von heute/gestern im Muster `<original>.bak-YYYYMMDD[-HHMM]`; ältere werden nach `/tmp/opencode/bakcheck` archiviert und gelöscht.
- **Zitate in Doku**: `Datei:Zeile` driftet. Stattdessen Codemarke (`PAGE_MAP`, `def berechne_match_score`) und/oder Messdatum nennen, vorher mit `grep -n` prüfen (`knowledge/system/doku-authority.md` §4).
- **ASGI-Guard** `webui/asgi_guard.py::SocketioAbortGuard` ist vor `ui.run` registriert. Client-Abbrüche vor dem ersten Event liefern 400 statt 500. Nicht entfernen.
- **Consent**: `consents`-Tabelle (`webui/db.py`), Pflicht-Checkbox bei Registrierung, separates Recording-Gate in `candidate.py`. Die Rechtsseiten `knowledge/legal/*` sind Entwürfe und nicht anwaltlich freigegeben.
- **staledocs-Ack** ist zweistufig (`ack <doc>` → `ack <doc> --confirm <token> -m '<Prüfung>'`). Nur mit gelesener Evidence; pauschale Notizen lehnt das Tool ab. Ein zweiter Analyse-Lauf über bereits geackte Paare liefert `claims=0`. Vorher `.staledocs/` sichern und das Paar-Ledger leeren. `config.weakenings` nicht umgehen.

## Git & Deploy

- Lokaler Branch `master`; `origin.push = master:main`. Ablauf: `git push` → CI auf `main` grün → `deploy-contabo.yml` (SSH, `git reset --hard <CI-SHA>`, `systemctl restart km-hr-agent`, Health-Check). Öffentlich: Cloudflare → Caddy → `127.0.0.1:8080` (Caddy-Site `deploy/caddy/jobs.hanibal-ai.com.caddy`).
- Rollback: `git reset --hard <SHA>` auf dem VPS.
- Commits: kurz, imperativ, ein Thema, mit Spec-Bezug (`CONTRIBUTING.md` §6).
- Nie synchronisieren oder committen: `.env*` (außer den Vorlagen), `data/`, `testdaten/`, `ergebnisse/`, `.venv-*/`, `logs/`. Keine personenbezogenen Daten (CVs, Bewerbungen, Reports) ins Repo.
- Lab-Prinzipien (Quelle vor Regel, MD-first, Transparenz): `CONTRIBUTING.md`.
