# MCP-Tool-Lazy-Gating — Phase 6.1: persistente MCP-Session + Host-Tool-Cache

**Stand:** 08.10.2026
**Zweck:** Den (jetzt offiziellen) MCP-Client aus Phase P4 beschleunigen und den
NiceGUI-Event-Loop entlasten — kein Subprozess-Kaltstart und kein `tools/list`-Roundtrip
je Tool-Aufruf mehr.
**Vorgänger:** `knowledge/system/event-loop-blockieren.md` §Phase 4 (P4: offizieller
MCP-Client, Ein-Schuss je Aufruf) + P0–P5.
**Quelle/Vorlage:** Portierung aus `backup-vor-revert-20261005` (Commit `e094618`,
05.10.2026), angepasst auf `main` (P4 dort bereits portiert).

---

## Problemstellung

Der in P4 eingeführte **offizielle MCP-Client** ist korrekt, aber **teuer pro Aufruf**:

1. **Frischer Subprozess je Tool-Call** → Kaltstart **~1,5–2,2 s** (eigene Messung 05.10.2026).
2. **`tools/list`-Roundtrip je Session** (Client validiert das Ergebnis, lädt das
   Katalog-Schema neu) → zusätzliche Latenz.
3. Beides läuft **synchron** in `webui/logic.py` (Codemarke `def _mcp_connector_call`, gemessen 10.10.2026) und wird u. a. aus
   dem (synchronen) Match-Render gerufen → blockiert den Event-Loop > 2 s →
   NiceGUI-Ping-Timeout → **„Connection lost"** (live reproduziert 05.10.2026).

## Wissensgrundlage (Schritt 1: Quelle finden) — mit Kennzeichnung

- **OFFIZIELL — MCP „Client Best Practices"** (`modelcontextprotocol.io`,
  Abruf 05.10.2026):
  - *„Cache tool definitions — once fetched … memoize the definition host-side so
    re-injecting it later doesn't need another `tools/list` round trip."*
    → `list_tools` **genau 1×** je Session (Host-Cache).
  - *„Dynamic Server Management"* (Server nur bei Bedarf verbinden/trennen)
    → **lazy** Session + Reconnect.
- **Design-Entscheidung** (keine externe Quelle): Thread-/Queue-Worker-Aufbau,
  Sync-Brücke, Timeouts, Zähler, `KMHR_MCP_SESSION=0`, `atexit`-Shutdown.
  Kein neues Paket — nur das bereits installierte `mcp` + stdlib
  (`threading`, `asyncio`, `atexit`).

## Lösung (Schritt 2: MD-first)

**Persistente Session je `(server_py, python_path)` + Host-Tool-Cache.**
Ein einziger langlebiger Worker-Task öffnet `stdio_client` + `ClientSession` **einmal**,
ruft `initialize` **1×** und `list_tools` **1×** (Host-Cache) und bedient danach alle
Aufrufe über eine Queue.

| Aspekt | Umsetzung (Codemarken, `webui/logic.py`) |
|---|---|
| Ergebnis-Parsing | `_parse_mcp_tool_result` (aus `_mcp_call_async` herausgezogen → Session- und Ein-Schuss-Pfad liefern exakt dasselbe Format) |
| Ein-Schuss-Fallback (P4) | `_mcp_call_async` bleibt unverändert |
| Langlebiger Worker-Task | `_mcp_session_worker` — öffnet Verbindung einmal, `initialize`/`list_tools` je **1×** |
| Hintergrund-Thread | `_get_session_loop` (`mcp-session-loop`, `daemon=True`, eigener Event-Loop) |
| Sync-Brücke | `_session_call_blocking` → `asyncio.run_coroutine_threadsafe(...).result(timeout=…)` |
| Lebenszyklus | `_get_or_start_handle` / `_invalidate_handle` (Neustart), `_close_all_sessions` / `_shutdown_session_loop` via `atexit` |
| Diagnose | `_MCP_SESSION_STATS` — Zähler `spawn`/`initialize`/`list_tools`/`reconnect` |
| Öffentliche API | `_mcp_connector_call` unverändert synchron/signaturgleich; Session zuerst, sonst Fallback |

**Warum ein Queue-Worker (wichtige Design-Entscheidung):**
`stdio_client`/`ClientSession` sind async-Kontextmanager und **anyio-Cancel-Scopes sind
task-lokal** — ein `__aenter__` in einem Task und `__aexit__` in einem anderen wirft
„Attempted to exit cancel scope in a different task". Deshalb öffnet und schließt
**genau ein** langlebiger Worker-Task die Verbindung; ein global „gespeicherter"
`ClientSession`-Kontext wäre nicht tragfähig.

**Timeouts (Design-Entscheidung):** `_MCP_START_TIMEOUT = 25.0` (Kaltstart + Puffer),
`_MCP_CALL_TIMEOUT = 60.0` (analog `read_timeout_seconds=60` aus P4).

**Fallback / Rollback:**
- Session-Start scheitert/Timeout → `_SessionUnavailable` → `_mcp_connector_call_once`
  (P4) → bei echtem Fehler `{}` wie bisher.
- Laufzeitfehler/Timeout eines Aufrufs → `cfut.cancel()` + `_invalidate_handle`
  (Session verworfen, nächster Aufruf startet neu) → Fallback für **diesen** Aufruf.
- `KMHR_MCP_SESSION=0` → **immer** der alte Ein-Schuss-Pfad (dynamisch gelesen,
  Rollback/Test; Design-Entscheidung).
- `KMHR_MCP_DRY_RUN` bleibt vorgeschaltet (kein Subprozess).

## Kennzeichnung (Lab-Prinzip)

| Aspekt | Kennzeichnung |
|---|---|
| MCP-Doc-Patterns (Tool-Definition-Cache, Dynamic Server Management) | ✅ Offiziell (MCP „Client Best Practices") |
| Thread-/Queue-Worker, Sync-Brücke, Timeouts, Zähler, `KMHR_MCP_SESSION=0`, `atexit` | ❌ Design-Entscheidung |
| Latenzen 1,5–2,2 s / warm ~2,8 ms | Eigene Messung 05.10.2026 |

## Messwerte (eigene Messung 05.10.2026, aus dem Backup)

Tool `HR_BENCHMARK_SERVER::get_score_category({"score": 85})`, ein Prozess:

| Pfad | Latenz |
|---|---|
| **Session kalt** (Spawn + `initialize` + `list_tools`, 1. Aufruf) | **1914,4 ms** |
| **Session warm** (2.–6. Aufruf) | **Mittel 2,8 ms** (min 2,3 / max 3,4) |
| **Ein-Schuss (P4)** (`_mcp_connector_call_once`, je Aufruf Subprozess) | **Mittel 1429,9 ms** |

Zähler nach 1× kalt + 5× warm: `{spawn: 1, initialize: 1, list_tools: 1, reconnect: 0}`
→ **kein** Subprozess-Spawn und **kein** `tools/list`-Roundtrip je Aufruf.
Warm ≈ **500×** schneller als der Ein-Schuss-Pfad; der Kaltstart zahlt `initialize` +
`list_tools` einmalig (deshalb ~1,9 s statt ~1,4 s — nur beim ersten Ruf).

## Verifikation

- `tests/test_mcp_session.py` (5 Tests): (a) `KMHR_MCP_SESSION=0` → nur Altpfad,
  (b) Format-Parität Session ↔ Altpfad, (c) „kein `initialize`/`list_tools`/`spawn` je
  Aufruf" über `_MCP_SESSION_STATS`, (d) Fehlerpfad → `{}` ohne Crash, (e) daemon-Thread /
  `_close_all_sessions` / Lazy-Restart.
- Bestehende `tests/test_mcp_official_client.py` (P4) bleiben grün.
- Isoliertes E2E via `tests/e2e_isolation.py --port <frei> --only e2e_gehalt_match`
  (nie gegen die Live-App :8080) → `rc=0`.

## Warm-up der MCP-Sessions beim App-Start (Plan A, 08.10.2026)

- **Befund (Lag-Monitor 08.10.2026):** Der ERSTE `/employer/match`-Render startet die MCP-Sessions/Connector-Caches synchron im NiceGUI-Event-Loop → **2,97 s Block** (> `pingTimeout=2000 ms` → sichtbarer Timeout beim ersten Aufruf). Gegenprobe P4-only: 9,4 s Block. Warm: kein Block.
- **Lösung:** `webui/logic.py` (Codemarke `def warm_mcp_connectors`, gemessen 10.10.2026) startet beim App-Start (aus `app_bootstrap()`) einen **Daemon-Thread**, der die MCP-Sessions für hr-benchmark (`get_score_category`, score 80), salary-data (`calculate_salary_tolerance`, midpoint 50000) und prescreen-config (`get_optimal_duration`) per `_mcp_connector_call` **vorwärmt** (öffnet die persistenten Sessions + füllt die Caches). Danach ist der erste Render warm.
- **Rollback:** Env `KMHR_MCP_WARMUP=0` deaktiviert das Vorwärmen (Design-Entscheidung).
- **Quelle (S1):** Muster „Dynamic Server Management"/„pre-warm" = **Design-Entscheidung** (kein externer Zwang); die Latenz-Begründung = eigene Messung 08.10.2026.
- **Verifikation:** `tests/test_mcp_warmup.py` + Lag-Monitor (kalt kein Block >1 s).

## Per-Key-Session-Lock (Option 1, 08.10.2026)

- **Befund (py-spy 08.10.2026):** `_get_or_start_handle` hielt den **globalen** `_SESSION_LOCK` über den GESAMTEN Session-Start (inkl. `handle.ready.wait(_MCP_START_TIMEOUT)` bis 25 s) → Session-Starts verschiedener Server **serialisiert** → der erste Match-Render blockierte >2 s (Ping-Timeout).
- **Lösung:** **Per-Key-Lock** — `_SESSION_LOCKS: dict[key -> Lock]`; `_SESSION_LOCK` dient nur noch als kurzer Guard für `_SESSIONS`/`_SESSION_LOCKS`. Verschiedene Server starten **parallel**, derselbe Server bleibt serialisiert (kein Doppel-Start).
- **Wirkung:** In Kombination mit dem Warm-up (Plan A) starten die 3 Sessions **parallel** (~3 s statt ~9 s) → vor dem ersten Render bereit → kein Kalt-Block.
- **Kennzeichnung (S1):** Muster `run.io_bound`/Async = offiziell (NiceGUI-FAQ); Per-Key-Lock/Warm-up = **Design-Entscheidung**; Befund = eigene py-spy-Messung 08.10.2026.
- **Verifikation:** `tests/test_mcp_session.py` (bestehend) + neuer Parallel-Test; Lag-Monitor (kalt 0 Blocks).

## Konsistenz (Schritt 3) / Transparenz (Schritt 4) / Iteration (Schritt 5)

- Abgleich Spec ↔ `webui/logic.py` (Codemarken oben) bzw. `webui/pages/*`; bei Abweichung
  wird **zuerst das MD korrigiert** (nicht der Code), außer die Quelle ist falsch zitiert.
- Zeilenangaben sind absichtlich **nicht** zitiert (Drift-Regel ab 01.10.2026) — nur
  Codemarken + Messdatum.
- Log: `ergebnisse/entscheidungen.md` (Was/Warum/Quelle).

---
*Quelle abgerufen 05.10.2026. Keine Erfindungen: jede Zahl ist zitiert oder als Design-Entscheidung gekennzeichnet.*
