# E2E in CI: Seed-Konten statt Live-Konten (Option A)

**Stand:** 08.10.2026
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
| Admin 1 | `admin@km-hr-agent.local` | `admin@example.invalid` |

## Kennzeichnung (Lab-Prinzip)

- Mapping = **Messung** (Live-DB + `seed_ci_db.py`), nicht Design-Entscheidung.
- Aktivierungs-Env `KMHR_E2E_SEED` = **Design-Entscheidung** (keine externe Quelle).
- MD-first: diese Spec vor der Code-Änderung; bei Abweichung wird die Spec korrigiert.

## Verifikation

- `pytest -q` unverändert grün (Unit-Tests berühren die E2E-Skripte nicht).
  - **Hinweis:** Lokal spiegelt `tests/conftest.py` die **Live-DB** (`data/feedback.db`); enthält sie E2E-Reste („E2E-Ketten-Beweis"), schlagen datenabhängige Baseline-Tests lokal fehl. Das ist **kein** CI-Problem (CI spiegelt den Seed) und **nicht** durch diese Änderung verursacht.
- Lokaler Seed-Modus (`KMHR_E2E_SEED=1` + `KMHR_E2E_LIVE_DB=tests/fixtures/seed.db`): **45/48 grün** (vorher in CI 3/46).
- Nach Push: E2E-Workflow auf GitHub grün.

## Bekannte Grenzen (CI-Skip, 08.10.2026)

Zwei Skripte scheiterten **nicht** an der Anmeldung, sondern an Seed-/Umgebungs-Annahmen. **`e2e_agent_details` ist seit P8.2 behoben** (selbst-säend, liest Agent-Berichte aus der DB, s. `knowledge/system/p8-cloud-datenquellen.md`). `e2e_feedback_jobswitch` ist mit dem **committeten** Seed grün (der zwischenzeitliche Fehler kam aus einer veralteten Seed-Regeneration, die rückgängig gemacht wurde). Nur `e2e_m07_row_click` wird im CI per `KMHR_E2E_SKIP` ausgelassen (`.github/workflows/e2e.yml`), lokal bleibt es lauffähig:

| Skript | Ursache (Messung 08.10.2026) | Behebung (Backlog) |
|---|---|---|
| ~~`e2e_agent_details.py`~~ | ✅ **behoben (P8.2, 08.10.2026):** selbst-säend, `result_json["text"]` aus der DB | — |
| `e2e_m07_row_click.py` | braucht **unterscheidbare** Feedback-Zeilen; `seed_ci_db.py` anonymisiert `kandidat_name`→„Kandidat" und `stellenprofil`→„Stelle" (alle gleich) → Klick-Navigation bricht; live grün (rc=0) | Seed-Anonymisierung zeilenweise eindeutig machen |

Der Skip-Mechanismus: `e2e_isolation.py` liest `KMHR_E2E_SKIP` (kommagetrennte Skriptnamen) und lässt sie im Standardlauf aus.

## Konsistenz / Iteration

- Abgleich Spec ↔ `tests/e2e_harness.py` (`seed_email`) ↔ `.github/workflows/e2e.yml` (`KMHR_E2E_SEED: "1"`, `KMHR_E2E_SKIP`) ↔ `tests/e2e_isolation.py` (Skip-Logik).
- Bei Abweichung zuerst diese Spec korrigieren (Lab-Schritt 3).
- Iteration: die drei Skip-Skripte nacheinander beheben (eins pro Runde).
