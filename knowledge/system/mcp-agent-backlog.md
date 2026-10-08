# MCP-&-Agent-Backlog (Analyse der Backup-Version `backup-vor-revert-20261005`)

**Stand:** 08.10.2026
**Auftrag (Nutzer):** „In GitHub gibt es eine Version über die MCP-&-Agent-Probleme — prüfe und analysiere das."
**Quelle (S1):** Branch `backup-vor-revert-20261005`, **22 Commits**, die in `origin/main` (`75475bf`) nicht enthalten sind; Gesamtumfang `git diff --stat origin/main backup-…` = **106 Dateien, +8810/−11701**.
**Methode:** read-only, 5 parallele Agenten (Commit-Inventar, Event-Loop, MCP-Client/Lazy-Gating, Performance/Pinning/P8, Cloud/DB). **Kein Code geändert.** Transparenz: `ergebnisse/entscheidungen.md` 08.10.2026.

---

## 1) Familienübersicht (Backup → Status auf main)

| Familie | Commits | Kern-Baustein | Status auf `main` (committet `75475bf`) |
|---|---|---|---|
| Connection lost / Event-Loop | P1–P4 | DB-Pool, `run.io_bound`, conn-Reuse, offizieller MCP-Client | **fehlt** (Revert) |
| MCP-Client / Lazy-Gating | P4/P6 | `webui/tool_catalog.py`, Runner-Gating, offizieller `mcp.Client` | **fehlt** |
| Performance / Rendering | P6.5/P6.6 | DB-Batching + Chunked/Skeleton/Score-Offload | **fehlt** |
| Dependencies | P7 | exaktes Pinning + Guard-Test | **fehlt** (unpinned) |
| P8 Cloud-Datenquellen | P8.1/P8.2 | PDF in-process; Agent-Details aus DB | **fehlt committet**; **P8.2 im Arbeitsbaum uncommitted vorhanden** |
| Cloud/DB (Supabase/Render) | Phase 3.x (10) | Postgres-Adapter, Migration, Render-Deploy | **fehlt** — für SQLite+Contabo **nicht relevant** |

## 2) Detail je Familie

### 2.1 Connection lost / Event-Loop (P1–P4) — auf main fehlt ALLES
| Phase | Backup-Lösung | Quelle/Design | Status main | Beleg |
|---|---|---|---|---|
| P1 DB-Pool | psycopg-`ConnectionPool`, `close_returns=True`, `_get_pg_pool` | Supabase/psycopg-Doku (offiziell); min/max = Design | fehlt | `webui/db.py` ohne Pool-Symbole |
| P2 Event-Loop | `run.io_bound` für argon2/PDF/Sprachtest + `_CEFR_SERVER_MOD`-Cache | NiceGUI-FAQ (offiziell); Cache = Design | fehlt | `webui/pages/login.py` argon2 synchron; `logic.py::cefr_from_avg` lädt Modul je Aufruf |
| P3 conn-Reuse | `conn`-Durchreichen in `berechne_match_score` | Design | fehlt | `webui/logic.py::berechne_match_score(k, j)` ohne `conn` |
| P4 MCP-Client | offizieller `stdio_client`+`ClientSession(read_timeout=60)`; stdout-Leck-Fix | MCP-Doku (offiziell); 60 s = Design | fehlt | `logic.py::_mcp_connector_call` = Popen-Pipe; `language-test-server.py` `print` ohne `stderr` |

> Altbestände, die überlebt haben: `get_current_weights(conn=None)`, `_GEHALT_TOL_CACHE`.

### 2.2 MCP-Client / Lazy-Gating (P4/P6)
| Baustein | Backup | Quelle/Design | Status main |
|---|---|---|---|
| `webui/tool_catalog.py` (CATALOG, BM25, `select_tools`, `render_catalog`) | vorhanden | MCP-„Progressive Tool Discovery" offiziell; BM25/Katalog = Design | fehlt |
| Runner-Gating (`_tool_gating_block`, Top-3, `KMHR_TOOL_GATING`) | vorhanden | Design | fehlt |
| offizieller MCP-Client | vorhanden | offiziell | fehlt |

**Belegter Nutzen:** Session warm ~2,8 ms vs. Ein-Schuss ~1.430 ms; **Katalog selbst spart gegenüber dem Ist nichts** (Ist-Prompts hatten 0 Katalog-Zeichen → +156–164 Tokens).

### 2.3 Performance / Rendering (P6.5/P6.6)
| Baustein | Backup | Status main |
|---|---|---|
| `get_language_tests_bulk` / `get_invitation_artifacts_bulk` | vorhanden | fehlt |
| Match-Render Bulk-Sammelpfad + `weights`-Durchreichen | vorhanden | fehlt (per-Karte-Roundtrips) |
| Skeleton + `run.io_bound`/`cpu_bound` + Chunked Rendering + Overlap-Guard | vorhanden | fehlt |

Backup-Befund: `/employer/match` 9,73 s → 7,08 s, Loop-Gap 411 ms → 12 ms (Cloud/Remote-DB-Latenz).

### 2.4 Dependencies (P7)
`mcp==2.3.0`, `fastmcp==4.0.11`, `nicegui==3.17.1`, `psycopg==3.3.6`, `psycopg-pool==3.3.3` + `tests/test_requirements_pinned.py`. Auf main **fehlt** (weiter `>=`), `mcp` nicht explizit.

### 2.5 P8 Cloud-Datenquellen (P8.1/P8.2)
- **P8.1** PDF in-process via PyMuPDF (statt `.venv-pdf`): auf main fehlt.
- **P8.2** Agent-Details/Badges aus `agent_tasks.result_json` statt `ergebnisse/*.md`: **auf main committet fehlt**, im **Arbeitsbaum vorhanden (uncommitted, ⓘ08.10.2026)** — Runner `result_json["text"]` (`RESULT_TEXT_MAX`), `db.get_candidate_agent_tasks`, `_page_agent_details` DB-basiert, `tests/test_p8_2_agent_details.py`.

### 2.6 Cloud/DB Supabase/Render (Phase 3.x)
10 Doku-Dateien, `scripts/migrate_sqlite_to_supabase.py`, DDL `supabase/migrations/0001_init_schema.sql`, `db-type-parity.md`, `render-deployment.md` — alle **auf main fehlt**. `main` betreibt **SQLite + Contabo** (`deploy-contabo.yml`). → **separate Infrastruktur-Entscheidung**, nicht Teil der MCP-&-Agent-Themen; nur bei erneutem Cloud-/Postgres-Vorhaben als Vorarbeit nutzbar.

## 3) Quellen-Kennzeichnung (S1)
| Quelle | Kennzeichnung |
|---|---|
| MCP „Client Best Practices" (modelcontextprotocol.io, 2026-07-28) | ✅ offiziell |
| Render-Docs, Supabase-Docs, psycopg-Docs, NiceGUI-FAQ | ✅ offiziell |
| Paper „Tool Attention Is All You Need" (arXiv 2604.21816) | ⚠️ Preprint; Zahlen = Projektionen (nicht als Beweis) |
| „TERSE Tool Catalog" (GitHub, 4 Stars) | ⚠️ Community |
| BM25/Katalog/Gating-Mapping, Cache-Session, Kappung, Status-Mapping | ❌ Design-Entscheidung |

## 4) Priorisierungsvorschlag (Phase 2 — noch NICHT umgesetzt)
| Prio | Baustein | Nutzen | Risiko | Empfehlung |
|---|---|---|---|---|
| 1 | P8.2 (Agent-Details aus DB) | behebt leere Badges bei gitignored `ergebnisse/` | niedrig | **übernehmen** (Arbeitsbaum vorhanden → prüfen/committen) |
| 2 | P2 `run.io_bound` + P4 stdout-Leck-Fix | UI-Reaktivität, kleiner Fix | niedrig | übernehmen |
| 3 | P7 Pinning | reproduzierbare Builds | niedrig | übernehmen |
| 4 | P1/P3/P6.5/P6.6 | nur bei messbarer Latenz (Cloud/Remote-DB) | mittel | **messen, dann entscheiden** |
| 5 | P6 MCP-Lazy-Gating | gering (Ist spart nichts) | mittel | zurückstellen |
| 6 | Cloud/DB Supabase/Render (Phase 3.x) | nur bei Cloud-Vorhaben | hoch | **separate Entscheidung** |

## 5) Regeln für die Umsetzung (S5)
Jeder Punkt **einzeln**, mit eigenem GO: S1 Quelle → S2 MD → Code (nur wo MD nicht reicht) → Test → **Beweis** (`pytest` + isolierter E2E) → S4 Log.

## 6) Phase-3-Status (ⓘ08.10.2026)
| Punkt | Backlog | Status |
|---|---|---|
| 1 | P8.2 (Agent-Details aus DB) | ✅ im Arbeitsbaum (uncommitted) |
| 2 | P2 (`run.io_bound`) + stdout-Leck | ✅ **umgesetzt** (Spec `event-loop-blockieren.md`; E2E 4/4 rc=0) |
| 3 | P7 (Dependency-Pinning) | ✅ **umgesetzt** (Spec `dependency-pinning.md`; Guard-Test 2/2) |
| 4 | P1/P3/P6.5/P6.6 | ⏭️ **entschieden (Messung):** SQLite `get_conn+select` = **0,070 ms** vs. Supavisor **130–204 ms** (~2000×) → P1 (Postgres-Pool), P3 (conn-Reuse), P6.5 (DB-Batching) für **SQLite+Contabo nicht erforderlich**. P6.6 (Chunked/Offload des Match-Renders) **nur bei Bedarf** (Render-Zeit messen, offen). |
| 5 | P6 MCP-Lazy-Gating | ⏭️ zurückgestellt (belegter Ist-Nutzen gering: Ist-Prompts hatten 0 Katalog-Zeichen) |
| 6 | Cloud/DB Supabase/Render | ⏭️ **separate Entscheidung** (main = SQLite+Contabo) |
