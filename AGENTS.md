# AGENTS.md — KM-HR-Agent

HR-Agent für KMU (Bewerbungen extrahieren, matchen, prüfen, einladen, Onboarding). Mensch-in-der-Schleife: der Agent lädt/lehnt nie selbst ein oder ab. Sprache der Repo-Doku und der UI: **Deutsch**.

## Architektur

- **Einzige UI: NiceGUI** in `webui/` (Port 8080, Override `KMHR_PORT`). Einstieg `webui/main.py`: Secrets-Gate → DB-Bootstrap → Seiten `create_*()` → ASGI-Guard → `ui.run`. Frameworkfrei: `webui/db.py` (SQLite), `webui/logic.py`; Pages in `webui/pages/`.
- **Entgeltmodell** (26.10.2026, AGB § 5): `webui/billing.py` (Beträge, Deckel, Ausbildung, Idempotenz, Bankdaten aus `KMHR_BANK_*`) + `webui/pages/billing_ui.py` (Sektionen in Kandidat/Arbeitgeber, Admin-Seite „Abrechnung"). Schritte: 99 € Beratung (Kandidat, bei Terminbuchung), 500/1.000 € nach Vertrag, 1.000 € + 20 % Bruttojahresgehalt (gedeckelt 2.000 €) nach Visum; Ausbildung nur Arbeitgeber (§ 296a SGB III). Zahlung **nur per Banküberweisung**, kein Karten-/Online-Zahlungsdienst; Flag `KMHR_BILLING_ENABLED` (Default 0), Schema in `init_billing_migrations`. Spec: `knowledge/system/configuration-secrets.md` §(h), `knowledge/legal/agb.md` §5.
- **`app.py` ist archiviertes Streamlit** (seit 23.09.2026). Nur Paritäts-Referenz, nicht starten/erweitern; `start.sh` bricht bewusst mit rc=1 ab.
- **`scripts/agent-runner.py`**: Hintergrund-Runner, Queue `agent_tasks`, 60-s-Loop, max. 3 Versuche pro Task. Startet mit der App (PID `data/agent-runner.pid`), Opt-out `KMHR_RUNNER_AUTOSTART=0`. Dry-Run: `.venv-streamlit/bin/python3 scripts/agent-runner.py --once --dry-run`.
- **Social-Agent**: `scripts/social_agent.py` (7-Tage-Plan, LinkedIn/Facebook/Instagram, Dry-Run-Outbox, PII-Guard); OAuth-Bootstrap `scripts/social_oauth.py`; Spec `knowledge/system/social-automation.md`, Agent `marketing/social-agent.md`, Entscheidung `marketing/ENTSCHEIDUNG.md`.
- **MCP-Connectoren** (`connectors/`, `mcp-*-server.py`, `scripts/language-test-server.py`) sind in `opencode.json` registriert. Root-MCP-Server laufen mit `.venv-pdf/bin/python3`, `connectors/*` und Language-Test mit System-`python3`. Externe Dienste nur darüber ansprechen; direkter HTTP-Aufruf nur NVIDIA-API im Runner und LinkedIn/Meta/Instagram im Social-Agenten (`scripts/social_agent.py`, dokumentierte Ausnahme). In Code/Doku nur Tool-Namen aus `opencode.json` nennen (`fetch`, `anysearch`; `websearch`/`webfetch` gibt es dort nicht).
- **Wissensbasis**: `knowledge/` (Specs, Index `knowledge.md`), `skills/*/SKILL.md` (Übersicht `skills/README.md`). Maßgeblich je Gebiet ist die Spec, z. B. `knowledge/system/configuration-secrets.md`, `knowledge/system/agent-automation.md`, `knowledge/system/access-control.md`, `knowledge/system/i18n.md`, `knowledge/system/doku-authority.md`, `knowledge/system/md-schreib-konvention.md`.
- **Landingpage-Animation**: `webui/pages/landing.py` (5 Kapitel: Gehirn, Loop, Sub-Agenten, Werkzeuge, Ergebnis; Three.js lokal); Entscheidung/Quellen in `ui/ANIMATION_ENTSCHEIDUNG.md`.

## Setup & Start

- Venv: `source .venv-streamlit/bin/activate` (Pfad in Skripten: `.venv-streamlit/bin/python3`). Deps: `requirements.txt` (Prod) + `requirements-dev.txt` (pytest, pyflakes, playwright). Der Name „streamlit" ist historisch — die App ist NiceGUI.
- Secrets in **vier** Dateien, nicht vermischen. Falsche Datei ⇒ Fehler:
  - `.env`: `start-webui.sh` (`KMHR_STORAGE_SECRET`, `KMHR_ADMIN_SEED_PASSWORD`); Vorlage `.env.example`, danach `chmod 600`.
  - `.env-runner`: `scripts/agent-runner.py`, `scripts/language-test-server.py` (`NVIDIA_API_KEY`, `KMHR_LLM_MODEL`).
  - `.env-email`: `mcp-email-server.py` (`SMTP_*`).
  - `.env-social`: `scripts/social_agent.py` (`KMHR_SOCIAL_*`, `LINKEDIN_*`, `FACEBOOK_*`, `INSTAGRAM_*`); Vorlage `.env-social.example`, Default Dry-Run.
- Start: `./start-webui.sh` verweigert ohne die beiden `.env`-Secrets den Start (rc=1); andere Env-Datei per `KMHR_ENV_FILE`. Ohne Secrets nur lokal: `KMHR_DEV=1 ./start-webui.sh`. `python3 -m webui.main` braucht dieselben Secrets. `KMHR_HOST` steuert die Bindung (Default `127.0.0.1`; `0.0.0.0` nur bewusst für LAN); `KMHR_COOKIE_SECURE=1` setzt das Session-Cookie hinter HTTPS auf `Secure`.
- Live-Admin-Konto trägt noch das alte Seed-Passwort: App **nicht aus dem lokalen Netz erreichbar machen**, bis rotiert ist (Details `knowledge/system/configuration-secrets.md`).
- DB: `data/feedback.db` (SQLite). Pfad-Override nur über `KMHR_DB_PATH` (Runner und WebUI teilen ihn). **Live-DB nie direkt beschreiben.**
- i18n: `.venv-streamlit/bin/pybabel compile -d webui/locales`. Es gibt **kein** `babel.cfg`/`.pot` — Kataloge werden gepflegt, nicht extrahiert. Babel stempelt die aktuelle Zeit in die `.mo`-Header und macht alle 4 (de/en/fr/ar) dreckig; ohne Inhaltsänderung `git checkout -- webui/locales`. Key-Gleichheit: `python3 scripts/ci/checks.py i18n`.

## Tests

- Unit: `.venv-streamlit/bin/python3 -m pytest -q` (739 collected, 26.10.2026; Volllauf 725 passed, 5 skipped, 1 bekannte NiceGUI-RuntimeWarning `Outbox.loop`; mit CI-Ausschlüssen). Die Passed-Zahl schwankt, weil netzabhängige Language-Tests skippen — keine feste Zahl als Ziel nehmen.
- Einzeltest: `.venv-streamlit/bin/python3 -m pytest tests/test_x.py::test_name -q`.
- `pytest.ini` setzt `asyncio_mode = auto` und `main_file = tests/nicegui_main.py`. `pytest_plugins = ["nicegui.testing.user_plugin"]` muss in der **Root**-`conftest.py` stehen (pytest 8+).
- NiceGUI-UI-Tests: Demo-Routen (`@ui.page`) gehören in `tests/nicegui_main.py`, **nicht** ins Testmodul (sonst 404/Global-Reset); Funktionsnamen dort nicht mit `test_` beginnen.
- `tests/conftest.py` spiegelt `tests/fixtures/seed.db` (Fallback: Live-DB) nach `/tmp/opencode` und leitet alle `sqlite3.connect`-Zugriffe dorthin um; `KMHR_LOG_FILE` zeigt auf ein Temp-Log. Nicht umgehen. Der Spiegel bekommt zusätzlich `init_notifications_table` + `init_candidates_migrations` + `init_consents_table`; neue Migrationen, die UI-Tests brauchen, in `webui/main.py` **und** dort nachziehen.
- `tests/fixtures/seed.db` ist **handgepflegt** (6 Jobs/18 Bewerbungen/2 Arbeitgeber). Nicht mit `scripts/seed_ci_db.py` blind neu erzeugen — das verschiebt E2E-Baselines und ~10 Unit-Tests; nur chirurgisch ändern (`knowledge/system/e2e-ci-seed.md`).
- **CI-Parität** (`ci.yml`): `data/feedback.db` ← `tests/fixtures/seed.db`, `.env` mit Dummy-Secrets, `mkdir /tmp/opencode`, dann `pytest -q --ignore=tests/test_r33_compliance_reports.py --deselect tests/test_ui_fixes_p0.py::test_profile_display_name_kein_dateiname`. Beide Ausschlüsse brauchen Daten, die nicht im Repo liegen (DSGVO); CI zählt daher systematisch weniger Tests als lokal.
- **E2E (Playwright)** nur über `python3 tests/e2e_isolation.py --port <N>` (Default 8081; `--port` ist ein Flag). Vorher `ss -ltn | grep :<N>` prüfen, sonst testet man einen Alt-Server. Einzelskript: `--only e2e_<name>`; Logs bleiben unter `/tmp/opencode/e2e-iso-*`. Nie gegen Port 8080. Einzelskripte direkt brauchen `KMHR_E2E_BASE` (der Isolation-Harness setzt es selbst). CI-Parität: `KMHR_E2E_SEED=1`, `KMHR_E2E_SKIP=e2e_m07_row_click`, Port 8097; Seed-Lauf lokal zusätzlich `KMHR_E2E_LIVE_DB=tests/fixtures/seed.db`. Bekanntes Problem: `goto` auf `/employer/stellen` hängt unter WSL (Einladen über den Match-Dialog nutzen, s. `knowledge/system/i18n-runner-chain.md` §5).

## Prüfkette vor jedem Commit

Alle Punkte mit rc=0. Ein roter Punkt ⇒ kein Commit/Push.

1. `.venv-streamlit/bin/staledocs check --gate strict` (PyPI 2.1.0; **nicht** `npx staledocs`, das ist ein anderes Paket)
2. `npx -y docrot-cli --fail-on=error` (Soll: Grade A+)
3. `.venv-streamlit/bin/python3 -m pytest -q`
4. `.venv-streamlit/bin/python3 -m compileall -q webui/ scripts/ connectors/`
5. `.venv-streamlit/bin/python3 -m pyflakes webui/ scripts/ connectors/ tests/ mcp-pdf-server.py mcp-meeting-server.py mcp-email-server.py` · **rc ist 1 sobald es Hinweise gibt.** Gewertet werden nur blockierende Fehler; CI filtert „imported but unused", f-string-Hinweise u. a. heraus. `app.py` und `docs/` sind bewusst ausgenommen.
6. Doku-Änderung: `ergebnisse/entscheidungen.md` ergänzen (Was/Warum/Quelle). Dann `git status` auf gewollte Dateien prüfen.

Doku-Gates gezielt: `python3 scripts/ci/checks.py docs|legal|mcp|i18n|schema|mdguard` (je ein Bereich). `docs.yml` triggert auch bei Änderungen an `webui/**`, `scripts/**`, `tests/**`, weil `mdguard` Laufzeit-Schreiber prüft.

## Gotchas

- **`ergebnisse/` ist gitignored und nichts darin ist getrackt.** `entscheidungen.md` landet also nie im Commit. Lokal pflegen, nicht als Teil des Diffs erwarten.
- **staledocs-Ack** ist zweistufig (`ack <doc>` → `ack <doc> --confirm <token> -m '<Prüfung>'`). Ack nur mit gelesener Evidence; das Tool lehnt pauschale Notizen ab. Falle: ein zweiter Analyse-Lauf über bereits ackte Paare liefert `claims=0`. Vorher `.staledocs/` sichern, Paar-Ledger leeren, frisch analysieren. Aufweichungen (`config.weakenings`) nicht umgehen.
- **Handler-Connection**: ein NiceGUI-Callback darf nie eine `conn` nutzen, die der Seitenaufbau geschlossen hat. Jeder Callback öffnet seine eigene `conn` und schließt sie in `try/finally` (Muster `visa_info_section` in `webui/components.py`; Test `tests/test_conn_closure.py`).
- **i18n**: kein f-String in `_()`, sondern `_('… {x}').format(x=…)` (Ruff INT001). Modul-Konstanten mit UI-Strings erst zur Renderzeit übersetzen, sonst ist die Babel-Extraktion kaputt.
- **Laufzeit-Schreiber** (Reports, Mails, MD-Artefakte): Ziel ist die Datei des heutigen Datums. Nie die „neueste existierende" Datei nehmen, nichts aus anderen Dateien übernehmen, nichts abschneiden, nichts in `knowledge/**`/`skills/**` schreiben (`tests/test_md_writer_discipline.py`).
- **`.bak`-Dateien**: bei jedem App-Start bleiben nur Sicherungen der letzten 2 Kalendertage (`run_bak_retention_once`, `webui/logic.py`).
- **Zitate in Doku**: `Datei:Zeile` driftet. Stattdessen Codemarke (`PAGE_MAP`, `def berechne_match_score`) oder Messdatum nennen, vorher mit `grep -n` prüfen.
- **ASGI-Guard**: `webui/asgi_guard.py::SocketioAbortGuard` wird in `webui/main.py` vor `ui.run` registriert. Client-Abbrüche vor dem ersten Event liefern 400 statt 500. Nicht entfernen.
- **Consent**: `consents`-Tabelle (`webui/db.py`), Pflicht-Checkbox bei Registrierung, separates Recording-Gate in `candidate.py`; Rechtsseiten `knowledge/legal/*` sind Entwürfe und nicht anwaltlich freigegeben.
- **Kein Formatter/Linter-Config**: nur die Prüfkette oben zählt; nicht nach `ruff`/`black`/`mypy`-Konfiguration suchen.

## Lab-Prinzipien (bindend, aus CONTRIBUTING.md)

1. **Quelle finden** vor jeder Zahl oder Regel (Gesetz, Studie, offizielle Doku). Ohne Quelle: explizit als „Design-Entscheidung" kennzeichnen.
2. **MD-first**: Logik in `skills/*/SKILL.md` und `knowledge/`, nicht in Python. Python nur, wenn MD nicht reicht (UI, DB, API).
3. **Konsistenz**: bei Widerspruch zwischen MD und Code das **MD** korrigieren.
4. **Transparenz**: Entscheidungen in `ergebnisse/entscheidungen.md` (Was, Warum, Quelle).
5. **Iteration**: einen Skill nach dem anderen.

## Git & Deploy

- Commits: kurz, imperativ, ein Thema, Spec-Bezug (Beispiel in `CONTRIBUTING.md` §6).
- Deploy: lokal ist der Branch `master`, Push-RefSpec `origin.push = master:main` — einfach `git push` → CI grün → `deploy-contabo.yml` (`workflow_run`) → SSH auf `176.57.189.201`, `git reset --hard <CI-SHA>`, `systemctl restart km-hr-agent`, Health-Check auf `127.0.0.1:8080`. Öffentlich: Cloudflare → Caddy → `127.0.0.1:8080` auf `https://jobs.hanibal-ai.com`; Caddy-Site `deploy/caddy/jobs.hanibal-ai.com.caddy`, Spec `knowledge/system/cloudflare-deployment.md`. Rollback: `git reset --hard <SHA>` auf dem VPS.
- Nie synchronisieren oder committen: `.env*`, `data/`, `testdaten/`, `ergebnisse/`, `.venv-*/`. Keine personenbezogenen Daten (CVs, Bewerbungen, Reports) ins Repo.
