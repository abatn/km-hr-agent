# P8.2 — Agent-Details/Badges aus der DB (Cloud-/CI-tauglich)

**Stand:** 08.10.2026
**Zweck:** Die Employer-Seite 🔎 Agent-Details baut ihre 9 Badges + Berichte nicht mehr aus lokalen
`ergebnisse/*.md`-Dateien, sondern aus der DB (`agent_tasks.result_json`). Grund: `ergebnisse/` ist
**gitignored** → im CI-Checkout und auf Cloud-Instanzen **leer** → alle Badges ⚪, obwohl die Tasks in der
DB mit Status `done` liegen.
**Herkunft:** Portierung aus der Version `backup-vor-revert-20261005` (Commit `899fc3c`, P8.2, 05.10.2026),
angepasst auf den `main`-Stand (i18n P9.4/Labels, `db.get_conn`-Muster).

---

## Problemstellung

`_page_agent_details` (`webui/pages/employer.py`) machte pro Task-Typ
`logic.ERGEBNISSE.glob("*-kandidat-{id}-*.md")` und las den Berichtstext aus der Datei. Da `ergebnisse/`
laut `.gitignore` **nicht** ins Repo gelangt, existiert das Verzeichnis im CI-Checkout nicht — die Seite
zeigt dann 9× „Kein Bericht vorhanden" (⚪), obwohl `agent_tasks` die abgeschlossenen Tasks kennt.

## Wissensgrundlage (Schritt 1) — mit Kennzeichnung

- **REPO-FAKT (verifizierbar):** `ergebnisse/` steht in `.gitignore` (AGENTS.md: „gilt nie als synchron …
  `ergebnisse/`"), ist also in CI/Cloud nicht vorhanden. Beweis: `grep -n ergebnisse .gitignore`.
- **CLOUD-FAKT (offiziell, aus dem Port übernommen):** Render Free-FS ist ephemer, Persistent Disks nur
  bezahlt (`render.com/docs/disks`, `render.com/docs/free`, Abruf 05.10.2026) — `ergebnisse/` wäre auf einer
  Cloud-Instanz nach Deploy/Restart leer.
- **Design-Entscheidungen (keine externe Quelle):** Feldname `result_json["text"]`, Kappung
  `RESULT_TEXT_MAX = 20000`, Status-Mapping `done→🟢/failed→🔴/sonst🟡`, Anzeige „Kein Berichtstext
  gespeichert (Altbestand)" für Legacy-Tasks ohne Text.

## Lösung (Schritt 2) — MD-first

1. **Runner** (`scripts/agent-runner.py::run_llm_task`): Berichtstext **additiv** in `result_json["text"]`
   ablegen (gekappt auf `RESULT_TEXT_MAX`). Die Altfelder `result_path`/`agent_chars` bleiben unverändert
   (keine Aufrufer brechen).
2. **DB-Helfer** (`webui/db.py::get_candidate_agent_tasks`): je `task_type` die **letzte** Task (höchste id)
   über **alle Bewerbungen** des Kandidaten; liefert `status`, `text` (aus `result_json`), `created_at`,
   `application_id`, `gen`. Bewusst **ohne** `json_extract` (Payload in Python parsen).
3. **UI** (`webui/pages/employer.py::_page_agent_details`): Badges/Berichte aus dem DB-Helfer; Datei-Glob
   entfällt. Legacy-Tasks ohne `text` → Badge aus `status` + ehrlicher Hinweis (kein Fake-Inhalt).

## Kennzeichnung (Lab-Prinzip)

| Aspekt | Kennzeichnung |
|---|---|
| `ergebnisse/` fehlt in CI/Cloud | ✅ Repo-Fakt (`.gitignore`) + offiziell (Render-Docs) |
| Feld `result_json["text"]`, Kappung 20000, Status-Mapping | ❌ Design-Entscheidung |
| DB-Helfer-Semantik (letzte Task/Typ, Payload-Parsing) | ❌ Design-Entscheidung |

## Konsistenz (Schritt 3) / Transparenz (Schritt 4)

- Abgleich Spec ↔ `scripts/agent-runner.py` ↔ `webui/db.py` ↔ `webui/pages/employer.py`; bei Abweichung
  zuerst diese Spec korrigieren.
- Jede Entscheidung in `ergebnisse/entscheidungen.md` (Was/Warum/Quelle).

## Verifikation

- Unit: `tests/test_p8_2_agent_details.py` (DB-Helfer + Badge-Mapping + Runner-Quelltext-Beleg).
- E2E: `tests/e2e_agent_details.py` **selbst-säend** (isoliert) — unabhängig von Live-Kandidatennamen,
  damit im CI (anonymisierter Seed) lauffähig.

## Iteration (Schritt 5)

P8.2 zuerst; P8.1/P8.3/P8.4 (aus `p8-cloud-datenquellen.md` der Backup-Version) bleiben **später**.
