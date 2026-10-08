# Event-Loop-Entlastung / „Connection lost" (Port P2 aus der Backup-Version)

**Stand:** 08.10.2026
**Zweck:** Die NiceGUI-App ist ein **Single-Event-Loop**; blockierende Operationen (argon2, PDF-Extraktion,
Sprachtest-Modul-Import) belegen ihn und lösen bei langen Render-/Login-Pfaden Ping-Timeouts („Connection
lost") aus. P2 lagert die blockierenden Aufrufe in Threads aus.
**Quelle (S1):** Portierung des P2-Teils aus `backup-vor-revert-20261005` (Commit `cdabbed`, 05.10.2026),
angepasst auf `main`.

---

## Quellen (Schritt 1) — mit Kennzeichnung

- **OFFIZIELL NiceGUI-FAQ** (`github.com/zauberzeug/nicegui/wiki/FAQs`, Abruf 05.10.2026): blockierende
  Operationen mit `run.io_bound` (I/O) bzw. `run.cpu_bound` (CPU) auslagern.
- **Eigene Messung 05.10.2026** (aus der Backup-Spec): argon2 0,4–1,2 s pro Op, PDF 0,9–1,9 s.
- **Design-Entscheidung:** *welche* Aufrufe ausgelagert werden und der CEFR-Modul-Cache (keine externe Norm).

## Lösung (Schritt 2) — P2, umgesetzt 08.10.2026 auf `main`

| Stelle | Änderung | Codemarke |
|---|---|---|
| `webui/pages/login.py` | argon2-Prüfungen/Hashes (`verify_password_argon2id`, `hash_password_argon2id`) via `await run.io_bound(...)`; Migration im Worker-Thread mit eigener DB-Verbindung | `from nicegui import run, ui` |
| `webui/pages/candidate.py` | PDF-Extraktion (`extract_pdf_text`) und Sprachtest-Modul-Import (`_spec.loader.exec_module`) via `await run.io_bound(...)`; `do_change_pw` → `async` (`run.io_bound`) | `async def do_change_pw` |
| `webui/pages/employer.py`, `webui/pages/admin.py` | `do_change_pw_emp` / `do_change_pw_admin` → `async` (`run.io_bound`) | — |
| `webui/logic.py` | CEFR-Server-Modul **einmal** laden + cachen (`_CEFR_SERVER_MOD`); stdout-hygiene (Debug-`print` → `file=sys.stderr`) | `_CEFR_SERVER_MOD` |
| `scripts/language-test-server.py` | stdout-Leck behoben: `print(...)` → `print(..., file=sys.stderr)` (+ `import sys`) — stdout ist der JSON-RPC-Kanal des stdio-Servers | `_call_nvidia` |

**NICHT in diesem Schritt (später, eigenes GO):** P1 DB-Pool, P3 conn-Reuse, P4 offizieller MCP-Client.

## Kennzeichnung (Lab-Prinzip)

| Aspekt | Kennzeichnung |
|---|---|
| `run.io_bound`-Muster | ✅ offiziell (NiceGUI-FAQ) |
| Auswahl der Stellen, CEFR-Cache | ❌ Design-Entscheidung |
| Latenzen 0,4–1,9 s | eigene Messung 05.10.2026 |

## Konsistenz (Schritt 3) / Transparenz (Schritt 4)

- Abgleich Spec ↔ `webui/pages/*`, `webui/logic.py`, `scripts/language-test-server.py`; bei Abweichung zuerst diese Spec korrigieren.
- Log: `ergebnisse/entscheidungen.md` 08.10.2026.

## Verifikation

- `pytest -q` (insb. `tests/test_secrets_from_env.py` — Assertion auf `run.io_bound(hash_password_argon2id, …)`).
- Isoliertes E2E (Login + CV-Upload + Sprachtest) → `rc=0`, Server-Log ohne unerwartete Disconnects.

---

## Phase 4 — Offizieller MCP-Client (P4) — umgesetzt 08.10.2026
- **Problem:** `webui/logic.py::_mcp_connector_call` startete je Aufruf einen Subprozess (handgeschriebene Popen-Pipe) OHNE Aufruf-Timeout → ein hängender Server blockierte den Aufrufer unbegrenzt (im NiceGUI-Render: Event-Loop-Block → Timeout/„Connection lost").
- **Lösung:** offizieller `mcp.Client` (stdio): `_mcp_call_async` nutzt `stdio_client` + `ClientSession(read_timeout_seconds=60)`; `_run_coro_blocking` führt die Coroutine in einem **eigenen Thread** mit eigenem Event-Loop aus (weil der Aufruf aus dem NiceGUI-Loop-Thread kommt → `asyncio.run` dort unzulässig). `env=dict(os.environ)` ist Pflicht (sonst fehlen den Servern NVIDIA_API_KEY/KMHR_LLM_MODEL).
- **Signatur/Aufrufer unverändert** (`_mcp_connector_call(server_py, tool, args, python_path=None) -> dict`); Fehlerpfad → `{}`.
- **DRY-RUN-Guard:** `KMHR_MCP_DRY_RUN` → Log auf stderr + `{}` (kein Subprozess).
- **Quelle (S1):** offizieller MCP-Client (installiertes `mcp`-Paket, `ClientSession`/`stdio_client`) = offiziell; `read_timeout_seconds=60` / Thread-Offload = **Design-Entscheidung**. Portierung aus `backup-vor-revert-20261005` (Commit `cdabbed`).
- **Verifikation:** `tests/test_mcp_official_client.py` (Integration hr-benchmark/salary-data/prescreen-config + Event-Loop-Kern + DRY-RUN + Fehlerpfad); isoliertes E2E `e2e_gehalt_match` rc=0.
