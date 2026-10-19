# E2E in CI: Seed-Konten statt Live-Konten (Option A)

**Stand:** 08.10.2026 (Nachtrag F2: 09.10.2026)
**Zweck:** Den seit 05.10.2026 dauerhaft roten E2E-Workflow reparieren, ohne echte Daten ins Repo zu schreiben.
**Status:** umgesetzt (Option A) — Helfer + Skripte + Workflow.

---

## Problem (Befund ⓘ08.10.2026)

- Der E2E-Workflow (`.github/workflows/e2e.yml`) kopiert `tests/fixtures/seed.db` nach `data/feedback.db` und startet den Isolations-Harness.
- `tests/fixtures/seed.db` wird von `scripts/seed_ci_db.py` erzeugt: es **anonymisiert E-Mails** (`kandidatN@example.invalid`, `hrN@example.invalid`, `admin@example.invalid`), lässt aber die **Passwort-Hashes unverändert**.
- Die E2E-Skripte sind gegen die **Live-DB** geschrieben und melden sich mit den **Original-E-Mails** an (`hr@techvision.de`, `e2e-beweis-phase1@example.com`, `batniniabdelkader@yahoo.com`, …).
- Folge in CI: Login trifft kein Konto → keine Navigation → `Timeout 15000ms … waiting for navigation to "**/candidate**"` → **43/46 Skripte rc=1** (Läufe 05.–08.10.2026: 4/4 failure).
- Lokal grün, weil `data/feedback.db` die Original-Konten enthält.

## Lösung (Option A)

Zentrale Übersetzungsfunktion `seed_email()` in `tests/e2e_harness.py`:

- **Lokal** (kein `KMHR_E2E_SEED`): E-Mail bleibt unverändert → gegen Live-DB lauffähig.
- **CI** (`KMHR_E2E_SEED=1`, gesetzt im Workflow): lokale E-Mail → Seed-E-Mail (`kandidatN`/`hrN`/`admin`).
- **Passwörter bleiben unverändert**, weil `seed_ci_db.py` die Hashes nicht anfasst → Anmeldung gelingt in beiden Umgebungen.

Alle Skripte wickeln ihre Login-E-Mail-Konstanten in `seed_email(...)`. **Nicht** übersetzt werden dynamisch registrierte Konten (z. B. `e2e@example.org` in `e2e_i18n_full_chain.py`) — die entstehen im Testlauf selbst.

### Mapping (Quelle: `scripts/seed_ci_db.py`, Messung 08.10.2026)

| Rolle | Live (lokal) | Seed (CI) |
|---|---|---|
| Kandidat 1 | `batniniabdelkader@yahoo.com` | `kandidat1@example.invalid` |
| Kandidat 2 | `test@example.de` | `kandidat2@example.invalid` |
| Kandidat 13 | `batninitaoufik@gmail.com` | `kandidat13@example.invalid` |
| Kandidat 16 | `e2e-beweis-phase1@example.com` | `kandidat16@example.invalid` |
| Kandidat 22 | `recruiting.e2e.2809b@kmailtest.de` | `kandidat22@example.invalid` |
| Arbeitgeber 1 | `hr@techvision.de` | `hr1@example.invalid` |
| Arbeitgeber 4 | `batniniabdelkader@yahoo.com` | `hr4@example.invalid` |
| Admin 1 | `admin@km-hr-agent.local` | `admin@example.invalid` |

### Echter FR-Fall: Arbeitgeber 4 / Job #12 (18.10.2026)

**Design-Entscheidung 18.10.2026:** `tests/e2e_board_passiv_filter.py` läuft im
**Seed-Modus gegen Arbeitgeber 4 / Job #12** (echter FR-Fall: Firma „Banana",
Stelle „Agent logistique / Préparateur de commandes (H/F) – Grands comptes
industriels", Kandidat #23 mit FR-Logistik-Skills) und im **Live-Modus gegen
Arbeitgeber 1**. Der Seed bildet den echten Fall datengetrieben ab
(`scripts/seed_ci_db.py`, Codemark `WHERE job_id=12 AND status='eingestellt'`):
die reale Bewerbung wird auf `zurückgezogen` gesetzt (zurückgezogen statt DELETE —
Zeilenzahlen der Fixture bleiben stabil; `_app_ids` schließt zurückgezogene
Bewerbungen aus → Kandidat passiv), `franzoesisch='B2'` wird nur wenn leer
gefüllt und `berufserfahrung_jahre` auf 3 angehoben (Design-Entscheidung: der
reale Wert ist leer und würde das 50%-Erfahrungs-Gate von Job 12 verfehlen).

**Passwort-Normierung Employer 4 (Design-Entscheidung 18.10.2026):** das echte
Banana-Passwort ist nicht reproduzierbar — der Seed setzt Employer 4 auf den
Employer-1-Hash, damit der E2E-Wert `sicher123` (Codemark
`password_hash = (SELECT … id=1) WHERE id=4`) im Login greift. Nur Employer 4,
kein anderer Account.

## Kennzeichnung (Lab-Prinzip)

- Mapping = **Messung** (Live-DB + `seed_ci_db.py`), nicht Design-Entscheidung.
- Aktivierungs-Env `KMHR_E2E_SEED` = **Design-Entscheidung** (keine externe Quelle).
- MD-first: diese Spec vor der Code-Änderung; bei Abweichung wird die Spec korrigiert.

## Verifikation

- `pytest -q` unverändert grün (Unit-Tests berühren die E2E-Skripte nicht).
- **Lokaler pytest-Lauf spiegelt die Seed-Fixture (F2, 09.10.2026):** `tests/conftest.py`
  nimmt als Spiegel-**Quelle** `tests/fixtures/seed.db`, **wenn die Datei existiert**;
  sonst unverändertes Fallback auf die Live-DB `data/feedback.db`. Grund:
  **Reproduzierbarkeit / Parität zu CI** — dieselben datenabhängigen Baseline-Tests
  (`test_dialog_identity`, `test_r33_compliance_reports`, `test_r35_status_notify`,
  `test_tabs_render`) laufen lokal gegen denselben anonymisierten Datenstand wie der
  `tests`-Job in `.github/workflows/ci.yml`, statt gegen die seit 07./08.10.2026
  gedriftete Live-DB (Rohtext-Anlass: lokal **15 failed**, CI grün). Die Live-DB wird
  in jedem Fall nur GELESEN (`mode=ro` + `.backup`), nie geschrieben. Der Pointer
  `/tmp/opencode/kmhr-mirror-last.txt` nennt jetzt `source=` + `start_source=`/`end_source=`.
- Lokaler Seed-Modus (`KMHR_E2E_SEED=1` + `KMHR_E2E_LIVE_DB=tests/fixtures/seed.db`): **45/48 grün** (vorher in CI 3/46) — historischer Messwert (Zeile nicht neu gemessen am 16.10.2026). **Bestand final 16.10.2026: 52 Dateien `tests/e2e_*.py`, davon 50 im Isolationslauf** (+`e2e_einladen_flow.py`, Iteration „Einladungen"; +`e2e_board_passiv_filter.py`, Iteration „Hiring-Board Passiv-Filter"). Volllauf aktueller Arbeitsbaum (lokal, Spiegel-DB) 16.10.2026: **47/49 rc=0**; die 2 Ausfälle sind vorbestehend und aufgeklärt (Beweislog 16.10.2026): `e2e_applicants_first` — erwartet Stelle #11 (gehört employer_id=3) beim employer-1-Login, reproduziert unverändert auf `9f34557` (`/tmp/opencode/e2e-iso-20261016-123021/`); `e2e_apply_dialog_multi` — Navigations-Race im Volllauf, Einzel-Lauf rc=0 (`/tmp/opencode/e2e-iso-20261016-122723/`). **17.10.2026 behoben:** `e2e_applicants_first` legt seine Stelle selbst an (`employer_id=1`, Codemark `setup_fixture`) statt global `ORDER BY j.id LIMIT 1` zu wählen — Root Cause war genau dieser Scope-Mismatch zum employer-scoped Dropdown (`employer.py::_page_feedback`); Einzel-Lauf (isoliert) 2× rc=0. **Bestand aktualisiert 19.10.2026: 54 Dateien, davon 52 im Isolationslauf** (+`e2e_board_actions.py`, MVP Arbeitgeber-UI; vorher 53/51 seit 18.10.2026 mit `e2e_password_reset.py`; Gegenprobe `ls tests/e2e_*.py | wc -l` = 54). Verifikation 18.10.2026 (isoliert): `e2e_password_reset` nach Syntax-Fix rc=0 (Lauf 1 `rc=1` unterbrochen, Lauf 2 volle Kette generisch → Link → Reset → Login → Einmaligkeit, Live-sha vor==nach, `/tmp/opencode/e2e-iso-20261018-131621/`) und `e2e_applicants_first` rc=0 (`/tmp/opencode/e2e-iso-20261018-134552/`).
- Nach Push: E2E-Workflow auf GitHub grün.

## CI-Parität: Setup- und Exklusionsschritte (Messung 10.10.2026)

Wer lokal denselben Stand wie der CI haben will, braucht die vier Setup-/Exklusionsschritte des
`tests`-Jobs (`.github/workflows/ci.yml`, Schritte `Seed-DB` → `/tmp/opencode` → `.env` → `pytest`):

| # | Schritt | Befehl im Workflow | Zweck |
|---|---|---|---|
| 1 | Seed-DB statt Live-DB | `cp tests/fixtures/seed.db data/feedback.db` | DSGVO: die echte `data/feedback.db` ist (bzw. soll) nicht im Repo sein; anonymisierte Fixture statt dessen |
| 2 | Spiegel-Verzeichnis | `mkdir -p /tmp/opencode` | `tests/conftest.py` schreibt den Spiegel-Pointer `/tmp/opencode/kmhr-mirror-last.txt` |
| 3 | Dummy-`.env` | `printf 'KMHR_STORAGE_SECRET=…\nKMHR_ADMIN_SEED_PASSWORD=…\n' > .env` | R6-2.2: die App startet ohne diese beiden Variablen nicht (`start-webui.sh` + `python3 -m webui.main` verweigern) |
| 4 | Daten-Exklusionen | `--ignore=` für `tests/test_r33_compliance_reports.py` (8 Tests) + `--deselect` für `tests/test_ui_fixes_p0.py` (`test_profile_display_name_kein_dateiname`, 1 Test) | beide brauchen Dateien aus `ergebnisse/` bzw. `testdaten/`, die aus DSGVO-Gründen nicht im Repo liegen |

**Zählkonsequenz (Messung 10.10.2026):** lokal `pytest -q` = **434 passed**; mit den vier CI-Schritten
(`--ignore` + `--deselect`) = **425 passed, 1 deselected, 148,73 s**. Die Differenz von 9 = 8 (`test_r33`)
+ 1 (`deselect`) — **die CI-Testzahl ist daher systematisch niedriger als die lokal zitierte Zahl**;
kein Regression-Signal.

Weitere CI-Schritte (`quality`-Job, ohne Datenbank): `pyflakes` über `webui/ scripts/ connectors/ tests/`
+ drei Root-MCP-Server (**nur blockierende Fehler** blockieren — die Nachrichten `imported but unused`,
`f-string is missing placeholders`, `assigned to but never used`, `redefinition of unused`,
`unable to detect undefined names` werden als Hinweis geduldet; `app.py` und `docs/sphinxats-github-app.py`
bewusst ausgenommen), `python -m compileall -q webui/ scripts/ connectors/`, Secret-Scan
(`github_pat_`/`ghp_`/`AKIA…`/`PRIVATE KEY`, mit `.venv-streamlit`-Ausschluss) und der
i18n-Katalog-Check (**Key-Menge je Sprache == DE**, sonst Abbruch).

`e2e.yml` spiegelt Schritt 1–3 in einem Schritt (`Seed-DB + /tmp/opencode + .env`) und setzt zusätzlich
`KMHR_E2E_SEED: "1"` (E-Mail-Übersetzung, Option A) + `KMHR_E2E_SKIP: "e2e_m07_row_click"`; Lauf
`python3 tests/e2e_isolation.py --port 8097`, Logs als Artefakt `/tmp/opencode/e2e-iso-*`.

## Bekannte Grenzen (CI-Skip, 08.10.2026)

Zwei Skripte scheiterten **nicht** an der Anmeldung, sondern an Seed-/Umgebungs-Annahmen. **`e2e_agent_details` ist seit P8.2 behoben** (selbst-säend, liest Agent-Berichte aus der DB, s. `knowledge/system/p8-cloud-datenquellen.md`). `e2e_feedback_jobswitch` ist mit dem **committeten** Seed grün (der zwischenzeitliche Fehler kam aus einer veralteten Seed-Regeneration, die rückgängig gemacht wurde). Nur `e2e_m07_row_click` wird im CI per `KMHR_E2E_SKIP` ausgelassen (`.github/workflows/e2e.yml`), lokal bleibt es lauffähig:

| Skript | Ursache (Messung 08.10.2026) | Behebung (Backlog) |
|---|---|---|
| ~~`e2e_agent_details.py`~~ | ✅ **behoben (P8.2, 08.10.2026):** selbst-säend, `result_json["text"]` aus der DB | — |
| `e2e_m07_row_click.py` | braucht **unterscheidbare** Feedback-Zeilen; `seed_ci_db.py` anonymisiert `kandidat_name`→„Kandidat" und `stellenprofil`→„Stelle" (alle gleich) → Klick-Navigation bricht; live grün (rc=0) | Seed-Anonymisierung zeilenweise eindeutig machen |

Der Skip-Mechanismus: `e2e_isolation.py` liest `KMHR_E2E_SKIP` (kommagetrennte Skriptnamen) und lässt sie im Standardlauf aus.

## Selbst-säende Fixtures statt SKIP (13.10.2026)

**Regel (AGENTS.md Schritt 3):** Datengekoppelte E2E-Skripte dürfen eine fehlende
Vorbedingung nicht per SKIP/Fail-Abschwächung aufgeben — sie legen sie selbst in der
isolierten Spiegel-DB an (Klasse a) und rollen sie im `finally` bzw. per `atexit`
zurück (Muster `tests/e2e_cv_upload.py` Passwort-Fixture, `tests/e2e_housing.py`
`pre_flip`/Restore). FAIL-Semantik bleibt FAIL.

| Skript | Fixture (angelegt, falls Vorbedingung fehlt) | Restore |
|---|---|---|
| `e2e_ui_p0_p1.py` | 'eingeladen'-Bewerbung auf einer employer-1-Stelle, wenn im Spiegel keine Bewerbung mit ≥2 sichtbaren Recruiter-Buttons existiert (Codemark `_MATCH_ACTION_LABEL`, Messung 13.10.2026: 'angesehen'/'eingeladen' als einzige Status mit ≥2 Regex-Treffern) | `atexit` (wie PW_FIXTURES) |
| `e2e_feedback_jobswitch.py` | 'eingegangen'-Bewerbungen auf Job 1 (≥1) und Job 6 (≥2, Kandidaten ≠ Job-1-Bewerber), falls vorhandene Bewerber nicht reichen | `finally` (DELETE inkl. History) |
| `e2e_housing.py` | 'eingeladen'-Bewerbung für einen Kandidaten mit Klarnamen auf aktiver employer-1-Stelle, wenn die dynamische Pick-Query leer ist | `finally` (DELETE, nach `pre_flip`-Restore) |
| `e2e_i18n_full_chain.py` | offene Alt-Bewerbungen von Kandidat #13 werden auf 'zurückgezogen' (final) geparkt — `validate_target` verlangt nur finale Alt-Bewerbungen | `finally` in `restore()` (Status + Zeitstempel zurück) |
| `e2e_vorgemerkt.py` | kein Fixture nötig — der Select-Readback wird per Polling (24×250 ms) verifiziert statt mit festem 400-ms-Wait; Abweichung bleibt FAIL (Sondenbeweis 13.10.2026: Readback zeigt 'Vorgemerkt', Codemark `eingeladen_select`) | – |
| `e2e_apply_dialog.py` (14.10.2026) | TEST-Job 'E2E-TEST Dialog' wenn kein freier Job; Status auf 'lebenslauf_hochgeladen' falls CV-Gate blockiert | `finally` `cleanup_test_job()` |
| `e2e_apply_dialog_multi.py` (14.10.2026) | 3 TEST-Jobs 'E2E-TEST Multi N' wenn <3 aktive Stellen | `finally` `cleanup_test_jobs()` |

### Klasse d: Prüfung nie registriert → FAIL werten (14.10.2026)

| Skript | Fund | Fix |
|---|---|---|
| `e2e_candidate_ux.py` | S2–S8 Findings nur in Report-Liste, nicht in `fails` | S2/S3/S5/S7/S8 → `fails.append()`; S4/S6 bleiben konditional |
| `e2e_match_actions.py` | Button-/Expander-Counts verworfen (`_ = ...`) | `assert total_btns >= 1` (mind. 1 Aktions-Button) |
| `e2e_smoke_all_pages.py` | Log-Check optional; Admin-Fails „informativ" | Fehlendes Log → `fails.append()`; Admin-Fails werten |
| `e2e_candidate_detail*.py` | Keine Assertions, keine Exit-Logik | Als DEBUG-TOOL markiert (Docstring), kein E2E-Test |

### Klasse b: Skip härten (14.10.2026)

| Skript | Fund | Fix |
|---|---|---|
| `e2e_sprachtest_flow.py` | Skip nicht zählbar; PASS-Text hardcoded | `skipped_parts`-Liste; PASS-Text dynamisch `(n/4 Teile)` |
| `e2e_isolation.py` | Skip-Namen nicht validiert; nicht im Summary; `--no-run` ohne Live-Diff | Warnung bei unbekannten Namen; Skip-Liste im Summary; Live-Diff wird ausgewertet |

**CI-Parität:** Im Seed (`tests/fixtures/seed.db`) sind die Vorbedingungen erfüllt —
die Fixtures greifen dort als No-Op; lokal (Spiegel der Live-DB, gedriftet) stellen sie
die Vorbedingung her. Der Isolations-Lauf (`tests/e2e_isolation.py`) verwirft die
Spiegel-DB nach dem Lauf; die Skripte löschen ihre eigenen Zeilen zusätzlich, damit
`db_residue_report` und der Live-DB-Byte-Abgleich grün bleiben.

## Konsistenz / Iteration

- Abgleich Spec ↔ `tests/e2e_harness.py` (`seed_email`) ↔ `.github/workflows/e2e.yml` (`KMHR_E2E_SEED: "1"`, `KMHR_E2E_SKIP`) ↔ `tests/e2e_isolation.py` (Skip-Logik).
- Bei Abweichung zuerst diese Spec korrigieren (Lab-Schritt 3).
- Iteration: die drei Skip-Skripte nacheinander beheben (eins pro Runde).
