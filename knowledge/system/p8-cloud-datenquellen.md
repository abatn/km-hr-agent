# P8.2 — Agent-Details/Badges aus der DB (Cloud-/CI-tauglich)

> ⚰️ **TOT / ÜBERHOLT (11.10.2026) — Cloud entfällt.** Diese Spec ist **historisch**. Die
> Cloud-Instanz (Render) ist **nicht mehr im Scope**; die „Cloud-Fakten" (Render Free-FS ephemer)
> sind damit **gegenstandslos**. Der **tragende Repo-Fakt** bleibt: `ergebnisse/` ist `gitignored`
> → im CI-Checkout leer → die Anzeige darf **nicht** aus `ergebnisse/*.md` lesen. Die **gültige**
> Beschreibung (Berichtstext **vollständig/ungekappt** in `agent_tasks.result_json["text"]`, Anzeige
> **DB-primär**, Badge **inhaltsbasiert**, `notify_user` = Info-Mail → Status-Badge, Altbestand ohne
> Rückübersetzung) steht ab 11.10.2026 in **`knowledge/system/agent-automation.md` §2 + §7.1** — das
> ist die Quelle der Wahrheit. Diese Datei bleibt nur als Herkunfts-Nachweis (Portierung P8.2) erhalten.

**Stand:** 08.10.2026 (⚰️ tot/überholt seit 11.10.2026)
**Zweck (historisch):** Die Employer-Seite 🔎 Agent-Details baut ihre 9 Badges + Berichte nicht mehr aus
lokalen `ergebnisse/*.md`-Dateien, sondern aus der DB (`agent_tasks.result_json`). Grund: `ergebnisse/`
ist **gitignored** → im CI-Checkout **leer** → alle Badges ⚪, obwohl die Tasks in der DB mit Status
`done` liegen.
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
- **CLOUD-FAKT ⚰️ (nicht mehr im Scope, 11.10.2026):** Render Free-FS ist ephemer, Persistent Disks nur
  bezahlt (`render.com/docs/disks`, `render.com/docs/free`, Abruf 05.10.2026) — `ergebnisse/` wäre auf einer
  Cloud-Instanz nach Deploy/Restart leer. **Cloud entfällt** → dieser Punkt ist nur noch historisch.
- **Design-Entscheidungen (keine externe Quelle):** Feldname `result_json["text"]`, Status-Mapping
  `done→🟢/failed→🔴/sonst🟡`, Anzeige „Kein Berichtstext gespeichert (Altbestand)" für Legacy-Tasks
  ohne Text. *(Historisch war zusätzlich eine Kappung `RESULT_TEXT_MAX = 20000` vorgesehen; sie wurde
  am 11.10.2026 auf Nutzer-GO Plan(ii) **entfernt** — der Berichtstext liegt jetzt ungekappt in
  `result_json["text"]`, s. `agent-automation.md` §2/§7.1.)*

## Lösung (Schritt 2) — MD-first

1. **Runner** (`scripts/agent-runner.py` (Codemarke `def run_llm_task`, gemessen 10.10.2026)): Berichtstext **additiv** in `result_json["text"]`
   ablegen (**ab 11.10.2026 ungekappt**; die frühere Kappung `RESULT_TEXT_MAX` ist entfernt). Die
   Altfelder `result_path`/`agent_chars` bleiben unverändert (keine Aufrufer brechen).
2. **DB-Helfer** (`webui/db.py` (Codemarke `def get_candidate_agent_tasks`, gemessen 10.10.2026)): je `task_type` die **letzte** Task (höchste id)
   über **alle Bewerbungen** des Kandidaten; liefert `status`, `text` (aus `result_json`), `created_at`,
   `application_id`, `gen`. Bewusst **ohne** `json_extract` (Payload in Python parsen).
3. **UI** (`webui/pages/employer.py` (Codemarke `def _page_agent_details`, gemessen 10.10.2026)): Badges/Berichte aus dem DB-Helfer; Datei-Glob
   entfällt. Legacy-Tasks ohne `text` → Badge aus `status` + ehrlicher Hinweis (kein Fake-Inhalt).

## Kennzeichnung (Lab-Prinzip)

| Aspekt | Kennzeichnung |
|---|---|
| `ergebnisse/` fehlt im CI-Checkout | ✅ Repo-Fakt (`.gitignore`) |
| Cloud-Ephemeralität (Render Free-FS) | ⚰️ gegenstandslos (Cloud entfällt 11.10.2026) |
| Feld `result_json["text"]`, Status-Mapping | ❌ Design-Entscheidung |
| Kappung `RESULT_TEXT_MAX = 20000` | ⚰️ entfernt (11.10.2026, Plan(ii)) |
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
