# Project knowledge

This file gives Freebuff context about your project: goals, commands, conventions, and gotchas.

> **Rolle dieser Datei (Doku-Authority v1.0):** operativ — Setup, Tests, CI-Gates, Gotchas, bindende Conventions, Zeiger auf die Specs. Kein Changelog (datierte Narrative → `ergebnisse/entscheidungen.md`), keine Detail-Specs (→ `knowledge/**`, `skills/*/SKILL.md`). Regel: **Ein Fakt steht an genau einem Ort** (`knowledge/system/doku-authority.md`).

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

## Schritt 6: Prüfen (Pflicht bei JEDER Änderung)
Jede Änderung (Code **oder** Doku) wird **vor dem Commit** durch die **Pflicht-Prüfkette** belegt — jeder Punkt mit `rc=0`:

| # | Prüfung | Befehl | Soll |
|---|---|---|---|
| 1 | Doku↔Code | `./.venv-streamlit/bin/staledocs check --gate strict` | **rc=0** (0 rot) |
| 2 | Doku-Beispiele/Links | `npx -y docrot-cli --fail-on=error` | **A+, rc=0** |
| 3 | Tests | `./.venv-streamlit/bin/python3 -m pytest -q` | grün (0 neue Fehler) |
| 4 | Syntax/Import | `./.venv-streamlit/bin/python3 -m compileall -q webui/ scripts/ connectors/` | rc=0 |
| 5 | Lint | `./.venv-streamlit/bin/python3 -m pyflakes webui/ scripts/ connectors/ tests/` | **0 blockierende** (undefined name/Syntax) — der rohe Befehl liefert **rc=1, sobald Hinweise existieren** (gemessen 106 Hinweise, 13.10.2026); gewertet wird die Ausnahmen-Liste in `ci.yml` (Codemark `echte=`), nicht der rc |
| 6 | Transparenz | `ergebnisse/entscheidungen.md` (Schritt 4) + `git status` (nur gewollte Dateien) | belegt |

**Ein roter oder fehlender Pflicht-Punkt ⇒ KEIN Commit/Push.** Bei Doku-Änderungen zusätzlich die staledocs-Baseline aktualisieren (`ack`, s. Gotchas). Bedeutung/CI-Parität der Gates: Abschnitt „## CI-Gates (verbindlich)".

---

## Setup & Betrieb

- **Venv:** `source .venv-streamlit/bin/activate` (in Automatismen `.venv-streamlit/bin/python3`).
- **DB:** SQLite `data/feedback.db` (Pfad-Override `KMHR_DB_PATH`, z. B. E2E-Isolation) — `webui/db.py` liest **nur** `KMHR_DB_PATH`; `KMHR_DB_BACKEND`/`KMHR_DATABASE_URL` werden **nicht** verwendet (inert).
- **Dev (NiceGUI, einzige UI):** `./start-webui.sh` → http://localhost:8080. Der Starter liest `./.env` (Vorlage `.env.example`) und **verweigert den Start ohne `KMHR_STORAGE_SECRET` + `KMHR_ADMIN_SEED_PASSWORD`** (rc=1); bewusst ohne Secrets: `KMHR_DEV=1 ./start-webui.sh`. Direktstart `python3 -m webui.main` braucht dieselben Secrets. Spec: `knowledge/system/configuration-secrets.md`.
- **Drei Env-Dateien — nicht vermischen** (Codemark je Loader, 13.10.2026): `.env` → `start-webui.sh` (Codemark `ENV_FILE`; `KMHR_STORAGE_SECRET`, `KMHR_ADMIN_SEED_PASSWORD`) · `.env-runner` → `scripts/agent-runner.py` **und** `scripts/language-test-server.py` (Codemark `_env_runner`; `NVIDIA_API_KEY`, `KMHR_LLM_MODEL`) · `.env-email` → `mcp-email-server.py` (Codemark `env_file`; `SMTP_*`). Der LLM-Key in der falschen Datei ⇒ `RuntimeError("NVIDIA_API_KEY nicht gesetzt – prüfe .env-runner oder Umgebungsvariable")` (Codemark in `scripts/agent-runner.py`).
- **Streamlit = abgeschaltet (23.09.2026):** `app.py` bleibt als Paritäts-Referenz, `start.sh` verweigert den Start.
- **Agent-Runner:** startet mit der App (PID-Datei `data/agent-runner.pid`); Opt-out `KMHR_RUNNER_AUTOSTART=0`; Dry-Run `python3 scripts/agent-runner.py --once --dry-run`.
- **i18n-Kataloge bauen:** `.venv-streamlit/bin/pybabel compile -d webui/locales` (kein `babel.cfg`, keine `.pot`; `pybabel --version` → 2.18.0) — läuft **seit 13.10.2026 mit rc=0, ohne Meldung** (Fix: msgid „50 % der geforderten Erfahrung" → „50 Prozent der geforderten Erfahrung" in `webui/pages/employer.py`, Codemark `Kandidat #{0} ist kein Bewerber`, + msgid/de-msgstr in allen 4 `.po`; die frühere Fehler-Ursache-Tabelle (2 Meldungen, en/ar:1112) steht datiert in `ergebnisse/entscheidungen.md`, Codemarke „I3 pybabel compile") und schreibt **alle 1141 `msgid`-Einträge** (0 Inhaltsverlust; Gegenprobe: msgid-Menge + msgstr-Vektor Frischbau == getracktes `.mo`). **Rebuild-Falle:** die `.po` enthalten kein `POT-Creation-Date` — babel stempelt beim Bauen die aktuelle Zeit in den `.mo`-Header (getrackter Stempel `2026-10-12 21:09+0200`) ⇒ ein Lauf macht die 4 getrackten `.mo` **ohne Inhaltsänderung** dreckig; `git status webui/locales` zurücksetzen, wenn nicht gewollt. Messung 13.10.2026. Spec: `knowledge/system/i18n.md`.
- **Beweislog (Pflicht, Lab-Schritt 4):** `ergebnisse/entscheidungen.md`; Änderungsverlauf `git log --oneline -10`.

## Tests

- **Unit-Tests:** `.venv-streamlit/bin/python3 -m pytest -q` → **477–482 passed, 0 failed** (Spanne statt Momentzahl, Messreihe 12.10.2026; `tests/conftest.py` spiegelt `tests/fixtures/seed.db` → deterministisch). **Flaky = Spannen-Ursache:** netz-/LLM-abhängige `test_language_scoring`-Kombinationen **skippen** (Language-Test-Server liefert 0 Fragen), wenn Server/LLM nicht erreichbar — **0–5 skipped** verschieben die Passed-Zahl (Messwerte 477 passed + 5 skipped bzw. 482 passed + 0 skipped), kein Regressionssignal.
- **CI-Parität:** mit `--ignore=` für `tests/test_r33_compliance_reports.py` + `--deselect` für `tests/test_ui_fixes_p0.py` (Test `test_profile_display_name_kein_dateiname`) = **468–473 passed, 1 deselected** (Spanne analog zur Unit-Zeile, Messreihe 12.10.2026; Differenz zur Vollliste **9** = 8 DSGVO-Tests + 1 Deselect). Spec: `knowledge/system/e2e-ci-seed.md`.
- **E2E (Playwright):** immer **isoliert** via `tests/e2e_isolation.py <port>` — `tests/e2e_harness.py` bricht ohne `KMHR_E2E_BASE` ab (R6-0), **nie** gegen die Live-App :8080. Konten: lokal Originale-Mails (Spiegel der Live-DB), in CI anonymisierte Seed-Konten (`KMHR_E2E_SEED=1`) — Voll-Mapping in `knowledge/system/e2e-ci-seed.md`. Bestand 10.10.2026 (Messung): 50 Dateien `tests/e2e_*.py`, davon 48 im Isolationslauf (Codemark `SKIP = {"e2e_harness.py", "e2e_isolation.py"}` — Harness und Wrapper sind keine Skripte; Zählung `ls tests/e2e_*.py | wc -l` = 50, 13.10.2026); letzter dokumentierter Volllauf 07.10.2026: 47/47 `rc=0` (datierte Messung).

## CI-Gates (verbindlich)

- **`ci.yml`:** `pyflakes` über `webui/ scripts/ connectors/ tests/` + Root-MCP-Server mit Ausnahmen-Liste (nur blockierende Fehler; `app.py` und `docs/sphinxats-github-app.py` ausgenommen) · `python -m compileall -q` · Secret-Scan · i18n-Katalog-Gleichheit (Key-Menge je Sprache == DE) · `pytest` mit den beiden DSGVO-Exklusionen (siehe Tests).
- **Pfad-getriggerte Workflows (leicht übersehbar — sie laufen nicht bei jedem Push):** `docs.yml`, `e2e.yml`, `i18n.yml`, `mcp.yml`, `scripts.yml` in `.github/workflows/`; die `paths:`-Muster stehen in den YMLs (nicht hier dupliziert) — `ci.yml`, `security.yml`, `docrot.yml` laufen ohne Pfadfilter. Locales Äquivalent: `python3 scripts/ci/checks.py docs|legal|mcp|i18n|schema` · `python3 scripts/ci/mcp_handshake.py` (mcp.yml) · shellcheck (scripts.yml) · `python3 tests/e2e_isolation.py --port <frei>` (e2e.yml). Alle fünf `checks.py`-Bereiche am 13.10.2026: je rc=0, 0 Fehler, 0 Warnungen (Ausgaben: „14 Server", „16 Tabellen", „4 Kataloge").
- **Doc-Gates:** `./.venv-streamlit/bin/staledocs check` (PyPI **2.1.0** — **nicht** `npx staledocs`: das ist ein anderes npm-Paket, Version `0.4.0-beta.1` (`npm view staledocs version`, Messung 13.10.2026)) + `npx -y docrot-cli`; Config `.staledocs.yaml` (`gate: strict`), Workflow `.github/workflows/docrot.yml`. **`staledocs check --gate strict` muss `rc=0` liefern, bevor gepusht wird** — seit 11.10.2026 **in der CI erzwungen**: Job „Doku↔Code (staledocs)" (`ci.yml`, `pip install staledocs==2.1.0` + `staledocs check --gate strict`, `fetch-depth: 0`).
- **Kein Formatter konfiguriert** — die CI-Gates oben sind verbindlich.
- **Deploy (lokal → GitHub → Contabo VPS):** `git push` (RefSpec `remote.origin.push = master:main`) → GitHub-`CI` grün → `deploy-contabo.yml` → VPS-Restart + Health-Check. Spec: `knowledge/system/deploy-pipeline.md`. **Nie als synchron** (gitignored): `.env*`, `data/`, `testdaten/`, `ergebnisse/`, `.venv-*/`. Rollback = SSH `git reset --hard <SHA>`.

## Doku-Tools — korrekte Nutzung & Verifikation (offiziell)

> **Quellen:** `staledocs` **2.1.0** (PyPI `Synforger/staledocs`, Apache-2.0, Python ≥3.11) · `docrot-cli` **0.2.5** (npm `getdocrot/docrot`, MIT, Node ≥18.17). Verifikation immer **read-only** (kein `ack`/`init`/`--fix`), **ein Befehl pro Call**, Soll `rc=0`.

**staledocs (Doku↔Code-Drift):**
- **Kanonische Verifikation:** `staledocs --version` → `2.1.0`; `staledocs check --gate strict --json` (Soll: `red 0 / amber 0 / green 55`; `coverage` alle Kategorien **0** — unclassified/orphans/uncovered/dead-docs; `config.weakenings: []`; `anchor_status.baseline_missing: []`); `staledocs pairs --health`; `staledocs unarmed`; `staledocs explain` (nur wenn rot).
- **Ack — zweistufig, vom Tool erzwungen:** `staledocs ack <doc>` → Evidence + Token → `staledocs ack <doc> --confirm <token> -m '<was geprüft>'` (die Note muss etwas aus der Evidence benennen; „looks fine" wird abgelehnt). **Bulk ist offiziell:** `ack --all` / `ack --broken` (Onboarding/Refactor). **Aufweichungen** (Pair/Gate/`ignore`) sind rot bis `staledocs ack --config -m '<warum>'`. Ledger `.staledocs/pairs/` **wird committet**. Exit-Codes: `0` ok · `1` Gate · `2` Usage · `3` ack pending.
- **Setup:** `staledocs init --suggest` → `.staledocs.yaml` prüfen → `check` → `ack` (§Gotcha „staledocs-Ack-Falle").

**docrot (Markdown gegen Code):**
- **Kanonische Verifikation:** `npx -y docrot-cli --json --fail-on=error` (Soll: `grade: A+`, `errors: 0`, `findings: []`). Flags: `--fail-on error|warning|never`, `--reporter pretty|github|json`, `--fix`, `--only`, `--exclude`, `--include-changelogs`.
- **CI-Action (offizielles Snippet):** `uses: getdocrot/docrot@v0` mit `with: fail-on: error` (s. `.github/workflows/docrot.yml`).

**Regel:** Prüfen stets mit den **offiziellen** Befehlen + `rc=0`. **Verboten:** unbelegtes `ack` (ohne Evidence-Lesen) oder das Umgehen der Weakenings-Sperre — das Tool erzwingt Evidence und meldet jede Aufweichung (`config.weakenings`).

## Gotchas & Tool-Fallen

- **staledocs-Ack-Falle (10.10.2026):** die Analyse liefert Claims **nur bei UNACKED-Paaren** — ein zweiter Analyse-Lauf über bereits ackte Paare schreibt `claims=0` und erzeugt Ack-Notes ohne Beleg. Vor jedem Re-Ack: `.staledocs/` sichern, `.staledocs/pairs/` leeren, Claims frisch analysieren, dann acken. Prosa-Docs ohne Pfad-/Ident-Claims (`knowledge/language-tests.md`, `knowledge/notification-log.md`, `knowledge/onboarding-default.md`) brauchen manuellen Beleg im Note.
- **anysearch braucht keinen Schlüssel (01.10.2026):** nur `X-Anysearch-Client` in `opencode.json`; die Auth-Zeile war 24.09.2026 defekt (`invalid_auth_header`) und entfernt. Wirksam erst nach OpenCode-Neustart; Arbeits-Ersatz bis dahin `fetch`.
- **E2E-Sleep-Falle (WSL):** `goto` auf `/employer/stellen` hängt den Playwright-Driver — Einladen über den Match-Seiten-Dialog (`knowledge/system/i18n-runner-chain.md` §5).
- **`.bak`-Retention-Bugfix (01.10.2026):** `_bak_timestamp` liest nur den Stempel **nach** `bak` — vorher matchte das Original-Datum und löschte frische Backups (wirklich eingetreten). Nachweis `tests/test_bak_retention.py`.
- **Zeilenangaben-Drift:** alle 78 Code-Refs in `ergebnisse/reports/*.md` waren gedriftet (53/53 getroffen anders als beschrieben) — Verweis-Regel siehe Conventions.
- **ASGI-Socket.IO-Guard (10.10.2026):** engineio wirft bei Client-Abbruch/Probe vor dem 1. Event `KeyError: 'REQUEST_METHOD'` (`engineio/async_server.py:238` greift auf `{}` zu, weil `translate_request` bei Erst-Event ≠ `http.request`/`websocket.connect` leer zurückgibt) → `webui/asgi_guard.py::SocketioAbortGuard` (registriert in `webui/main.py` **vor** `ui.run`) antwortet **400 statt 500**; Spec `knowledge/system/asgi-guard.md`.

## Conventions (verbindlich)

- **Zitate mit Codemarke + Messdatum:** `Datei:Zeile` ist **kein** stabiler Verweis (Regel ab 01.10.2026). Zitate mit **Codemarke** (`PAGE_MAP`, `_TAB_MAP`, `def berechne_match_score`) und/oder Messdatum; vor dem Zitat `grep -n "<marke>" <datei>` prüfen. Alt-Reports in `ergebnisse/` bleiben unangetastet (datierte Messung). Befund: `ergebnisse/zeilenangaben-drift-2026-10-01.md`.
- **`.bak`-Retention (ab 27.09.2026, Design-Entscheidung auf Nutzerbefehl):** von Sicherungskopien bleiben nur die der **letzten 2 Kalendertage** (Datum-Stempel im Namen); alles ältere und alles ohne Datum wird gelöscht. Ausführung `run_bak_retention_once` (`webui/logic.py`) bei jedem App-Start, fehlerresistent, mit Rollback-Archiv. Nach dem Löschen: `pytest` + Live-DB-Snapshot prüfen.
- **Changelog-Pflicht:** datierte Änderungsnarrative gehören nach `ergebnisse/entscheidungen.md` (Lab-Schritt 4) — **nicht** in diese Datei. `git log --oneline -10` liefert den Commit-Verlauf.
- **Doku-Authority:** ein Fakt steht an genau einem Ort; normativ/deskriptiv/historisch/tot + Konflikt-Hierarchie → `knowledge/system/doku-authority.md`.
- **Patterns:** NiceGUI-App (frameworkfreie Layer `db.py`/`logic.py`), deutsche UI, MCP-Connectoren für externe Dienste, Lab-Prinzip (Skill + Knowledge + Connector, keine separate Codebasis). **Tool-Namen-Pflicht:** nur MCP-Server-Namen aus `opencode.json` (kein websearch/webfetch) — `knowledge/system/mcp-connector-config.md`.
- **Nicht tun / Pflicht:** Tests immer über den venv-Interpreter (`.venv-streamlit/bin/python3`); Live-DB `data/feedback.db` nie direkt schreiben (Tests nutzen den Spiegel aus `tests/conftest.py`); **Netz-Restrisiko:** das Live-Admin-Konto trägt weiterhin das frühere Seed-Passwort → bis zur Rotation darf die App **nicht aus dem lokalen Netz erreichbar** sein (Fakt + Begründung stehen in der Spec, Abschnitt „Bekanntes Restrisiko": `knowledge/system/configuration-secrets.md`).

## Zeiger auf die Specs (Quelle-der-Wahrheit je Gebiet)

| Gebiet | Spec (maßgeblich) |
|---|---|
| Doku-Authority, Doku↔Code | `knowledge/system/doku-authority.md` |
| Access Control (Agent-/Portal-Ebene + ADMIN) | `knowledge/system/access-control.md` |
| Scoring, Gewichte, Feedback-Loop | `knowledge/lifecycle/matching-criteria.md`, `knowledge/lifecycle/feedback-schema.md` |
| Bewerbungs-Status, Status-Automatik | `knowledge/lifecycle/application-status.md`, `knowledge/lifecycle/status-automation.md` |
| Arbeitgeber-Portal (Felder, Matching-Filter, Bewerber) | `knowledge/portal/employer-portal-fields.md`, `knowledge/portal/matching-filter.md`, `knowledge/portal/applicants-first.md`, `skills/job-application/SKILL.md` |
| Candidate-Portal, CV-Pflicht | `knowledge/portal/candidate-portal-fields.md`, `knowledge/portal/cv-pflicht.md` |
| Agent-Automation (Runner, Trigger, Mails, Gatekeeper) | `knowledge/system/agent-automation.md`; Fehlerstatistik `knowledge/error-statistics.md` |
| DSGVO (Dokumenten-Gate, Löschfristen) | `knowledge/legal/dsgvo-gate.md`, `knowledge/legal/gdpr-policy.md` |
| Meetings (VDO.Ninja, Aufnahme-Einwilligung) | `knowledge/system/vdo-ninja-migration.md`, `knowledge/legal/recording-consent.md` |
| HR-/MCP-Connectoren | `connectors/hr-api-connectors.md`, `knowledge/system/mcp-connector-config.md` |
| i18n (DE/EN/FR/AR), Runner-Texte | `knowledge/system/i18n.md`, `knowledge/system/i18n-runner-chain.md` |
| E2E/CI-Seed, Test-Konten | `knowledge/system/e2e-ci-seed.md` |
| Config/Secrets, Deploy | `knowledge/system/configuration-secrets.md`, `knowledge/system/deploy-pipeline.md` |
| Hardcodierte Werte & Quellen | `knowledge/lifecycle/matching-criteria.md`, `knowledge/legal/contract-management.md`, `knowledge/legal/visa-rules.md`, `knowledge/legal/compliance-rules.md` |
| Sprachtests | `knowledge/language-tests.md`, `knowledge/language-courses.md` |
| Skill-Specs (23) | `skills/*/SKILL.md`, Übersicht `skills/README.md` |

Datierte Entwicklungsstände der früheren AGENTS.md (Phase-Archive, Messreihen, Research-Notizen) liegen in `ergebnisse/entscheidungen.md` (Abschnitt „S3: Von AGENTS.md übernommene datierte Blöcke").
