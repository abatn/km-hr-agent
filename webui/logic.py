"""
KM-HR-Agent – logic.py (framework-unabhängiger Business-Logik-Layer)
====================================================================
Phase 0 der NiceGUI-Migration (ergebnisse/nicegui-phase-0.md).

Enthält die aus app.py extrahierte Logik (Scoring, Gewichte, DSGVO,
Agent-Runner-Autostart, Passwort-Hashing, Rollen-Checks). Keine
Streamlit-/NiceGUI-Importe — session-gebundene Anteile sind als
Callback-Parameter entkoppelt (siehe _session_getter).

Quellen: app.py (Zeilen in ergebnisse/nicegui-phase-0-bereinigung.md).
"""
from __future__ import annotations

import os
import asyncio
import atexit
import json
import re
import sqlite3
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from webui.db import (
    BASE_DIR, DATA_DIR, DB_PATH,
    get_conn, init_agent_tasks_table, queue_agent_task,
)

TESTDATEN = BASE_DIR / "testdaten"
ERGEBNISSE = BASE_DIR / "ergebnisse"

# Quelle/Parität: webui/pages/employer.py (APPLICANT_ACTIVE dort vorhanden, 01.10.2026 gemessen)
APPLICANT_ACTIVE = ("eingegangen", "angesehen", "eingeladen")


# ─── Upload-Dateinamen bereinigen (R5-2 / S3c, 30.09.2026) ──────────

# Transliteration statt stillschweigendem Löschen (Design-Entscheidung,
# keine externe Quelle: Umlaute sollen erkennbar bleiben — 'ä' → 'ae'
# ist die im Deutschen übliche ASCII-Umschrift).
_UMLAUT_MAP = str.maketrans({
    "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
    "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
    "á": "a", "à": "a", "â": "a", "é": "e", "è": "e", "ê": "e",
    "í": "i", "ì": "i", "ó": "o", "ò": "o", "ô": "o",
    "ú": "u", "ù": "u", "ç": "c", "ñ": "n",
})


def safe_upload_name(name: str) -> str:
    """Upload-Dateiname → sicherer flacher Name (R5-2/S3c).

    Regeln:
    - Pfadanteile ('../', 'C:\\', UNC) werden entfernt — nur der Basename bleibt.
    - Umlaute werden transliteriert (ä→ae), nicht gelöscht (s. _UMLAUT_MAP).
    - Nur [A-Za-z0-9._-] bleiben; Rest → '_'; Mehrfach-'_' kollabieren.
    - Endung bleibt erhalten; ohne gültige Endung (.pdf/.txt) wird sie
      NICHT gefälscht (die Endungsprüfung im Upload-Tab lehnt dann ab).
    - Leer/nur Sonderzeichen → 'unnamed'; Länge > 80 Zeichen → gekürzt
      (Endung bleibt). Grenze 80: Design-Entscheidung (Dateisystem-sicher).
    """
    if not name or not str(name).strip():
        return "unnamed"
    text = str(name).replace("\\", "/")
    base = text.split("/")[-1] or "unnamed"
    base = base.translate(_UMLAUT_MAP)
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    cleaned = re.sub(r"_{2,}", "_", cleaned).strip("._")
    if not cleaned:
        return "unnamed"
    stem, dot, ext = cleaned.rpartition(".")
    if dot and ext:
        stem = stem[:80 - (len(ext) + 1)]
        return f"{stem}.{ext}" if stem else f"unnamed.{ext}"
    return cleaned[:80]


# ─── PDF-Textextraktion (GAP-1, Quelle: app.py:92-111) ─────────────
# pymupdf läuft in .venv-pdf, NICHT im System-Python.
# Quelle: opencode.json pdf-reader command + mcp-pdf-server.py (pymupdf).
# Der Streamlit-Original (app.py:92) versucht `from mcp_pdf_server import`,
# das im .venv-streamlit fehlschlägt → fitz(pymupdf)-Fallback.
# Im NiceGUI rufen wir pymupdf direkt als Subprocess mit .venv-pdf-Python auf
# (MCP-Stdio-Protokoll hat Timing-Probleme mit FastMCP 4.x).

PDF_READER_PY = BASE_DIR / ".venv-pdf" / "bin" / "python3"


def extract_pdf_text(pdf_path: str) -> str:
    """Extrahiert Text aus PDF via pymupdf in .venv-pdf.
    Quelle: app.py:92-111 (fitz-Fallback) + opencode.json pdf-reader config.
    Bei Fehlschlag: leerer String (kein Müll in die DB)."""
    if not Path(pdf_path).exists():
        return ""
    try:
        script = (
            "import pymupdf\n"
            f"doc = pymupdf.open({pdf_path!r})\n"
            "for i, page in enumerate(doc):\n"
            "    print(f'--- Seite {i+1} ---')\n"
            "    print(page.get_text())\n"
            "doc.close()\n"
        )
        proc = subprocess.run(
            [str(PDF_READER_PY), "-c", script],
            capture_output=True, text=True, timeout=30,
        )
        text = proc.stdout.strip()
        if proc.returncode == 0 and text:
            return text
    except Exception:
        pass
    return ""

# ─── Datei-Hilfen (C7, 22.09.2026) ──────────────────────────────────
# 1:1 aus app.py:82-129 (read_file / save_result / list_profiles).

def read_profile_text(path) -> str:
    """Liest eine Datei (TXT/MD) oder extrahiert Text aus PDF.
    Quelle: app.py:82-89."""
    p = Path(path)
    if not p.exists():
        return f"[FEHLT] Datei nicht gefunden: {path}"
    if p.suffix.lower() == ".pdf":
        return extract_pdf_text(str(p))
    return p.read_text(encoding="utf-8", errors="replace")


def save_result(filename: str, content: str) -> str:
    """Speichert Ergebnis-Datei in ergebnisse/.
    Quelle: app.py:114-121 (subdir/base_dir entfallen — NiceGUI nutzt
    immer ERGEBNISSE wie der Streamlit-Default)."""
    ERGEBNISSE.mkdir(parents=True, exist_ok=True)
    filepath = ERGEBNISSE / filename
    filepath.write_text(content, encoding="utf-8")
    return str(filepath)


def list_profiles() -> list:
    """Listet alle Profile in testdaten/ auf.
    Quelle: app.py:124-129."""
    return sorted(TESTDATEN.glob("profil-*.md"))


def aktuelle_stelle_fuer_profil(profil_path, employer_id: int | None = None) -> str:
    """Stellentitel der aktuellen Bewerbung des Kandidaten (R5-4/S3g).

    Ersetzt die hartcodierte Vorgabe "Senior Cloud/DevOps Engineer" in den
    Pre-Screen-/Onboarding-Generatoren. Vorbelegung = Stelle aus der
    neuesten Bewerbung des gewählten Kandidaten (bei diesem Arbeitgeber,
    wenn employer_id gegeben), sonst leer — der Generator verlangt dann
    eine Eingabe (Pflichtprüfung), statt eine fremde Stelle zu erfinden.

    Zuordnung Profil-Datei → Kandidat über einen toleranten Namensschlüssel:
    Dateistamm UND Kandidatenname werden auf sortierte Buchstabenfolge
    normiert ('Abdelkader Batnini' und 'batnini-abdelkader' →
    'aabdeeklinrt'), matching case-insensitiv (Design-Entscheidung; DB-Namen
    sind nicht normiert, gemessen: 'batnini abdelkader' vs. Datei
    'abdelkader-batnini').
    """
    try:
        stem = Path(profil_path).stem.replace("profil-", "").lower()
        slug = "".join(sorted(re.sub(r"[^a-z0-9]+", "", stem)))
        if not slug:
            return ""
        conn = get_conn()
        try:
            # Kandidat-Namen in der DB sind NICHT normiert ('batnini
            # abdelkader' vs. Datei 'abdelkader-batnini') — Vergleich über
            # sortierte Buchstabenfolge beider Seiten (Design-Entscheidung,
            # toleranter Namensschlüssel statt exaktem Match).
            if employer_id:
                rows = conn.execute(
                    """SELECT j.titel, c.name FROM candidates c
                       JOIN applications a ON a.candidate_id = c.id
                       JOIN jobs j ON j.id = a.job_id
                       WHERE j.employer_id = ?
                       ORDER BY a.id DESC""",
                    (employer_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT j.titel, c.name FROM candidates c
                       JOIN applications a ON a.candidate_id = c.id
                       JOIN jobs j ON j.id = a.job_id
                       ORDER BY a.id DESC""",
                ).fetchall()
            for titel, name in rows:
                nslug = "".join(sorted(re.sub(r"[^a-z0-9]+", "", (name or "").lower())))
                if nslug == slug:
                    return titel or ""
            return ""
        finally:
            conn.close()
    except Exception:
        # Bewusst defensiv: Vorbefüllung ist Komfort — beim Fehler leer
        # bleiben (Pflichtprüfung greift), die Section darf nicht crashen.
        return ""


def profile_display_name(path) -> str:
    """Klartext-Name fuer eine Profil-MD (NIEMALS der Dateiname).

    P0 (28.09.2026): Pre-Screen-/Onboarding-Auswahlfelder zeigten
    "profil---**name:**-anna-schuster.md" als Personenangabe (Beleg:
    ergebnisse/reports/screenshots/vorher/messung-vorher.json,
    'dateinamen_im_label' x3). Reihenfolge: **Name:** aus dem Dokument,
    dann # Profil: - **Name:**, dann aufgeraeumter Dateistamm.
    """
    import re as _re
    p = Path(path)
    try:
        head = p.read_text(encoding="utf-8", errors="ignore")[:4000]
    except Exception:
        head = ""
    m = _re.search(r"\*\*\s*Name\s*:?\s*\*\*\s*:?\s*(.+)", head)
    if m:
        # Profil-MDs fuehren den Namen teils als Markdown-Tabellenzeile
        # ('| Abdelkader Batnini |') → erste gefuellte Zelle nehmen.
        raw = m.group(1).splitlines()[0]
        for cell in raw.split("|"):
            name = cell.strip().strip("*").strip()
            if name and not set(name) <= set("-: "):
                return name
    stem = p.stem
    stem = _re.sub(r"^profil-+", "", stem)
    stem = _re.sub(r"-\*\*name:\*\*-?", "", stem, flags=_re.I)
    stem = _re.sub(r"^-+|-+$", "", stem)
    return stem.replace("-", " ").title() or "Unbenanntes Profil"


# HR-Connector-Pfade (verifiziert 15.09.2026, app.py:24-27)
HR_BENCHMARK_SERVER = BASE_DIR / "connectors" / "hr-benchmark-server.py"
SALARY_DATA_SERVER = BASE_DIR / "connectors" / "salary-data-server.py"
PRESCREEN_CONFIG_SERVER = BASE_DIR / "connectors" / "prescreen-config-server.py"


def _run_coro_blocking(coro):
    """Führt `coro` synchron aus — in einem EIGENEN Thread mit eigenem Event-Loop.

    Design-Entscheidung (kein `asyncio.run(coro)` im aufrufenden Thread, P4
    05.10.2026): `_mcp_connector_call` wird u. a. aus dem NiceGUI-Event-Loop-
    Thread aufgerufen (`match_content` → `berechne_match_score`/`gehalt_check`).
    Dort läuft bereits ein Event-Loop → `asyncio.run` wirft RuntimeError
    ("cannot be called from a running event loop"). Ein frischer Thread hat
    keinen laufenden Loop und darf `asyncio.run` gefahrlos ausführen; das
    funktioniert symmetrisch aus Event-Loop- und normalen Threads.
    """
    result: dict = {}
    error: dict = {}

    def _target():
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as ex:  # noqa: BLE001 — an Aufrufer weiterreichen
            error["exc"] = ex

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error["exc"]
    return result.get("value", {})


def _parse_mcp_tool_result(result) -> dict:
    """Extrahiert das dict aus einem `CallToolResult` (P4-Verhalten, P6.1).

    Quelle: installierte `mcp 2.2.0` (`CallToolResult.content`/`is_error`).
    Identisch zum bisherigen Inline-Parsing in `_mcp_call_async`, damit
    Session- und Altpfad exakt dasselbe Ergebnisformat liefern.
    """
    if getattr(result, "is_error", False):
        return {}
    text = ""
    for block in getattr(result, "content", []) or []:
        candidate_text = getattr(block, "text", None)
        if candidate_text is not None:
            text = candidate_text
            break
    if text:
        if text.startswith("FEHLER") or text.startswith("DRY-RUN"):
            return {}
        return json.loads(text)
    structured = getattr(result, "structured_content", None)
    if structured:
        return structured
    return {}


async def _mcp_call_async(server_py: Path, tool: str, args: dict,
                          python_path: str = None) -> dict:
    """Async-Kern: offizieller MCP-Client (stdio) — P4, 05.10.2026.

    Spez: knowledge/system/event-loop-blockieren.md §Phase 4.
    Quelle: installierte `mcp 2.2.0` (ClientSession/stdin_client-API).
    `env=dict(os.environ)` ist PFLICHT: `StdioServerParameters(env=None)`
    vererbt nur DEFAULT_INHERITED_ENV_VARS (HOME/LOGNAME/PATH/SHELL/TERM/USER)
    → NVIDIA_API_KEY/KMHR_LLM_MODEL fehlten den Servern sonst.
    `read_timeout_seconds=60` = Design-Entscheidung (§Phase 4).

    P6.1 (05.10.2026): bleibt als **Ein-Schuss-Fallback** erhalten (wird
    genutzt, wenn `KMHR_MCP_SESSION=0` oder die persistente Session
    scheitert). Signatur/Verhalten unverändert.
    """
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    params = StdioServerParameters(
        command=python_path or sys.executable,
        args=[str(server_py)],
        env=dict(os.environ),
        cwd=str(BASE_DIR),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=60) as session:
            await session.initialize()
            result = await session.call_tool(tool, args)
            return _parse_mcp_tool_result(result)


# ─── P6.1 (05.10.2026): persistente MCP-Session + Host-Cache ────────────────
# Spec: knowledge/system/mcp-tool-lazy-gating.md §Phase 6.1.
# Quelle (offiziell, MCP „Client Best Practices", abgerufen 05.10.2026):
#   * „Cache tool definitions — once fetched … memoize the definition
#     host-side so re-injecting it later doesn't need another tools/list
#     round trip."   → `list_tools` genau EINMAL je Session.
#   * „Dynamic Server Management" (Server nur bei Bedarf verbinden/trennen).
# Implementierung (ein Hintergrund-Thread + Event-Loop, Queue-Worker je
# Server, Sync-Brücke, Reconnect/Fallback, `KMHR_MCP_SESSION=0`) =
# Design-Entscheidung (kein Paket nötig, nur `mcp` + stdlib).
#
# Warum ein Queue-Worker-Task und nicht „offene Session global speichern":
# `stdio_client`/`ClientSession` sind async-Kontextmanager; anyio-Cancel-Scopes
# sind TASK-LOKAL. Ein `__aenter__` in Task A und `__aexit__` in Task B wirft
# „Attempted to exit cancel scope in a different task". Deshalb öffnet und
# schließt genau EIN langlebiger Worker-Task die Verbindung und bedient alle
# Aufrufe über seine Queue.

_MCP_START_TIMEOUT = 25.0   # Design-Entscheidung: Kaltstart 1,5–2,2 s + Puffer
_MCP_CALL_TIMEOUT = 60.0    # Design-Entscheidung: wie `read_timeout_seconds` (P4)

# Test-/Diagnosezähler: beweist, dass initialize/list_tools/spawn NICHT je
# Aufruf passieren (siehe tests/test_mcp_session.py).
_MCP_SESSION_STATS: dict = {
    "spawn": 0, "initialize": 0, "list_tools": 0, "reconnect": 0,
}

_SESSION_LOCK = threading.Lock()
# Per-Key-Locks (Option 1, 08.10.2026): Session-Start je Server serialisieren,
# aber verschiedene Server parallel. `_SESSION_LOCK` ist nur noch kurzer
# Guard fuer _SESSIONS/_SESSION_LOCKS.
_SESSION_LOCKS: dict = {}
_LOOP_LOCK = threading.Lock()
_SESSION_LOOP = None
_SESSION_THREAD = None
_SESSIONS: dict = {}


class _SessionUnavailable(RuntimeError):
    """Intern: Session nicht (mehr) nutzbar → Aufrufer fällt auf den Altpfad."""


class _McpServerSession:
    __slots__ = ("server_py", "python_path", "loop", "queue", "ready",
                 "done", "alive", "error", "tools")

    def __init__(self, server_py: Path, python_path, loop):
        self.server_py = server_py
        self.python_path = python_path
        self.loop = loop
        self.queue = None
        self.ready = threading.Event()
        self.done = threading.Event()
        self.alive = False
        self.error = None
        self.tools = None


def _session_enabled() -> bool:
    # KMHR_MCP_SESSION=0 → immer der alte Ein-Schuss-Pfad (Rollback/Test;
    # Design-Entscheidung). Dynamisch gelesen, damit Tests per Env umschalten.
    return os.environ.get("KMHR_MCP_SESSION") != "0"


def _get_session_loop():
    """Startet (einmalig) den Hintergrund-Thread mit eigenem Event-Loop."""
    global _SESSION_LOOP, _SESSION_THREAD
    with _LOOP_LOCK:
        if (_SESSION_LOOP is not None and _SESSION_THREAD is not None
                and _SESSION_THREAD.is_alive()):
            return _SESSION_LOOP
        loop = asyncio.new_event_loop()
        ready = threading.Event()

        def _run():
            asyncio.set_event_loop(loop)
            ready.set()
            loop.run_forever()

        thread = threading.Thread(target=_run, name="mcp-session-loop",
                                  daemon=True)
        thread.start()
        ready.wait(5)
        _SESSION_LOOP = loop
        _SESSION_THREAD = thread
        return loop


async def _mcp_session_worker(handle: _McpServerSession) -> None:
    """Hält EINE offene stdio/ClientSession-Verbindung (ein Task = ein Scope).

    Öffnet → `initialize` (1×) → `list_tools` (1×, Host-Cache) → bedient die
    Queue. Transportfehler beenden den Worker, damit die Session beim nächsten
    Aufruf frisch aufgebaut wird.
    """
    from mcp import ClientSession
    from mcp.client.stdio import stdio_client, StdioServerParameters

    params = StdioServerParameters(
        command=handle.python_path or sys.executable,
        args=[str(handle.server_py)],
        env=dict(os.environ),
        cwd=str(BASE_DIR),
    )
    queue: asyncio.Queue = asyncio.Queue()
    handle.queue = queue
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write,
                                     read_timeout_seconds=60) as session:
                await session.initialize()
                _MCP_SESSION_STATS["initialize"] += 1
                handle.tools = await session.list_tools()
                _MCP_SESSION_STATS["list_tools"] += 1
                handle.alive = True
                handle.ready.set()
                while True:
                    item = await queue.get()
                    if item is None:
                        break
                    tool, args, fut = item
                    if fut.done():      # Aufrufer hat aufgegeben (Timeout)
                        continue
                    try:
                        result = await session.call_tool(tool, args)
                        if not fut.done():
                            fut.set_result(_parse_mcp_tool_result(result))
                    except BaseException as ex:  # noqa: BLE001
                        if not fut.done():
                            fut.set_exception(ex)
                        break                    # Transportfehler → neu starten
    except BaseException as ex:  # noqa: BLE001 — niemals nach außen crashen
        handle.error = ex
    finally:
        handle.alive = False
        handle.ready.set()   # weckt wartende Startaufrufe AUCH im Fehlerfall
        handle.done.set()


async def _mcp_session_submit(handle: _McpServerSession, tool: str,
                              args: dict) -> dict:
    queue = handle.queue
    if queue is None or not handle.alive:
        raise _SessionUnavailable("Session nicht bereit")
    fut: asyncio.Future = asyncio.get_running_loop().create_future()
    await queue.put((tool, args, fut))
    return await fut


def _key_lock(key):
    with _SESSION_LOCK:
        lk = _SESSION_LOCKS.get(key)
        if lk is None:
            lk = threading.Lock()
            _SESSION_LOCKS[key] = lk
        return lk


def _get_or_start_handle(server_py: Path, python_path):
    """Liefert eine lebende Session oder startet sie.

    Option 1 (08.10.2026): **Per-Key-Lock** statt globalem Lock — Session-Starts
    fuer UNTERSCHIEDLICHE Server laufen parallel; nur derselbe Server wird
    serialisiert (kein Doppel-Start). Der globale `_SESSION_LOCK` ist nur noch
    kurzer Guard fuer `_SESSIONS`/`_SESSION_LOCKS` (nicht mehr ueber den Start).
    """
    key = (str(server_py), python_path)
    with _SESSION_LOCK:
        handle = _SESSIONS.get(key)
        if handle is not None and handle.alive:
            return handle
    with _key_lock(key):
        with _SESSION_LOCK:
            handle = _SESSIONS.get(key)
            if handle is not None and handle.alive:
                return handle
        loop = _get_session_loop()
        handle = _McpServerSession(server_py, python_path, loop)
        with _SESSION_LOCK:
            _SESSIONS[key] = handle
        _MCP_SESSION_STATS["spawn"] += 1
        asyncio.run_coroutine_threadsafe(_mcp_session_worker(handle), loop)
        if not handle.ready.wait(_MCP_START_TIMEOUT) or not handle.alive:
            with _SESSION_LOCK:
                _SESSIONS.pop(key, None)
            raise _SessionUnavailable(
                f"MCP-Session {getattr(server_py, 'name', server_py)} "
                f"nicht bereit")
        return handle


def _invalidate_handle(handle: _McpServerSession) -> None:
    """Markiert eine Session als tot und bittet den Worker zu beenden."""
    handle.alive = False
    with _SESSION_LOCK:
        key = (str(handle.server_py), handle.python_path)
        if _SESSIONS.get(key) is handle:
            _SESSIONS.pop(key, None)
    if handle.queue is not None:
        try:
            asyncio.run_coroutine_threadsafe(handle.queue.put(None),
                                             handle.loop)
        except Exception:
            pass


def _session_call_blocking(server_py: Path, tool: str, args: dict,
                           python_path: str = None) -> dict:
    """Sync-Brücke zum Session-Thread (Timeout + Reconnect beim nächsten Ruf)."""
    handle = _get_or_start_handle(server_py, python_path)
    cfut = asyncio.run_coroutine_threadsafe(
        _mcp_session_submit(handle, tool, args), handle.loop)
    try:
        return cfut.result(timeout=_MCP_CALL_TIMEOUT)
    except Exception:
        cfut.cancel()
        _invalidate_handle(handle)
        raise


def _close_all_sessions() -> None:
    """Stoppt alle Session-Worker sauber (gleicher Task → korrekter Scope-Exit)."""
    with _SESSION_LOCK:
        handles = list(_SESSIONS.values())
        _SESSIONS.clear()
    for handle in handles:
        handle.alive = False
        if handle.queue is not None:
            try:
                asyncio.run_coroutine_threadsafe(handle.queue.put(None),
                                                 handle.loop)
            except Exception:
                pass
    for handle in handles:
        handle.done.wait(5)   # Kontextmanager-Exit abwarten (Subprozess-Reap)


def _shutdown_session_loop() -> None:
    """atexit: Sessions schließen, dann Loop-Thread beenden (kein Hang)."""
    _close_all_sessions()
    loop = _SESSION_LOOP
    if loop is not None:
        try:
            loop.call_soon_threadsafe(loop.stop)
        except Exception:
            pass


atexit.register(_shutdown_session_loop)


def _mcp_connector_call_once(server_py: Path, tool: str, args: dict,
                             python_path: str = None) -> dict:
    """Bisheriger Ein-Schuss-Pfad (P4): frischer Thread + Subprozess je Ruf."""
    try:
        return _run_coro_blocking(
            _mcp_call_async(server_py, tool, args, python_path))
    except Exception:
        return {}


def _mcp_connector_call(server_py: Path, tool: str, args: dict,
                         python_path: str = None) -> dict:
    """Ruft ein Tool eines lokalen FastMCP-Servers auf (MCP-Protokoll).

    P4 (05.10.2026): Popen-Pipe ersetzt durch den offiziellen `mcp.Client`
    (stdio). Signatur/Aufrufer unverändert. python_path: optionaler
    Interpreter (default: sys.executable), z. B. .venv-pdf für pdf-reader.

    P6.1 (05.10.2026): nutzt zuerst die persistente Session (Host-Cache,
    kein Subprozess-/`tools/list`-Roundtrip je Aufruf). Bei Fehler/Timeout
    wird die Session verworfen und der Aufruf über den P4-Ein-Schuss-Pfad
    wiederholt — niemals crashen, bei echtem Fehler `{}`. Mit
    `KMHR_MCP_SESSION=0` wird immer der Altpfad benutzt.
    """
    if os.environ.get("KMHR_MCP_DRY_RUN"):
        # Laufzeit-Guard (Design-Entscheidung): analog Runner-`--dry-run`,
        # aber per Env, da die NiceGUI-App kein argv-Flag besitzt.
        print(f"[DRY-RUN] MCP {server_py.name}::{tool} "
              f"args={json.dumps(args, default=str)[:120]}", file=sys.stderr)
        return {}
    if _session_enabled():
        try:
            return _session_call_blocking(server_py, tool, args, python_path)
        except _SessionUnavailable:
            pass
        except Exception:
            _MCP_SESSION_STATS["reconnect"] += 1
    return _mcp_connector_call_once(server_py, tool, args, python_path)


# C3 (22.09.2026): Cache für statische hr-benchmark-Tools — get_score_category
# liefert pro score deterministisch dieselbe Antwort (ZYTHR-Schwellen,
# knowledge: hr-benchmark), kostet aber ~2s (subprocess + FastMCP-Import).
# Match-View rechnet ~10 Scores pro Render → erstes Laden einmal zahlt den
# Connector, danach identische Werte sofort. Fehler ({}) werden NICHT gecacht,
# damit der Connector-Retry-Vorbehalt (Fallback-Design-Entscheidung) bleibt.
_STATIC_TOOL_CACHE: dict = {}


def _static_connector_call(server_py: Path, tool: str, args: dict) -> dict:
    key = (str(server_py), tool, json.dumps(args, sort_keys=True, default=str))
    if key in _STATIC_TOOL_CACHE:
        return _STATIC_TOOL_CACHE[key]
    result = _mcp_connector_call(server_py, tool, args)
    if result:  # nur Erfolge cachen
        _STATIC_TOOL_CACHE[key] = result
    return result


# ─── Scoring (Phase 2, Spec: knowledge/lifecycle/matching-criteria.md) ──

SKILL_SYNONYME = {
    "kubernetes": "k8s", "k8s": "kubernetes",
    "javascript": "js", "js": "javascript",
    "typescript": "ts", "ts": "typescript",
    "ci/cd": "ci-cd", "ci-cd": "ci/cd", "ci cd": "ci/cd",
    "github actions": "github-actions", "github-actions": "github actions",
    "node.js": "nodejs", "nodejs": "node.js", "node": "node.js",
    "postgresql": "postgres", "postgres": "postgresql",
    "amazon web services": "aws", "aws": "amazon web services",
    "google cloud platform": "gcp", "gcp": "google cloud platform",
    "microsoft azure": "azure", "azure": "microsoft azure",
}

KATEGORIE_MAX = {
    "kern": 30, "erfahrung": 30, "bildung": 15, "standort": 10,
    "branche": 10, "soft": 10, "sprache": 10,
}
BASELINE_GEWINCHTE = {
    "kern": 30, "erfahrung": 25, "bildung": 15, "standort": 10,
    "branche": 10, "soft": 10, "sprache": 0,
}
GEWICHT_CAP_ABWEICHUNG = 15
GEWICHT_CAP_SPRACHE_MAX = 15
DB_KATEGORIE_MAP = {
    "Berufserfahrung": "erfahrung",
    "Sprache": "sprache",
}


def normalize_skill(skill: str) -> str:
    """app.py:154-160"""
    s = (skill or "").strip().lower()
    s = s.replace(".", "").replace("/", "-").replace("_", "-")
    s = " ".join(s.split())
    return s


def skills_match(job_skill: str, cand_skill: str) -> bool:
    """app.py:162-171"""
    nj, nc = normalize_skill(job_skill), normalize_skill(cand_skill)
    if nj == nc:
        return True
    syn = SKILL_SYNONYME.get(nj)
    if syn and normalize_skill(syn) == nc:
        return True
    return False


def score_kernkompetenzen(must_haves: list, k_skills: list) -> tuple:
    """app.py:173-180"""
    if not must_haves:
        return 15, []
    matches = [m for m in must_haves if any(skills_match(m, ks) for ks in k_skills)]
    score = int(round(len(matches) / len(must_haves) * 30))
    return score, matches


def score_berufserfahrung(k_erf: float, job_erf: float, k_text: str = "") -> int:
    """app.py:182-203"""
    job_erf = job_erf or 0
    basis = job_erf if job_erf > 0 else 3
    j = k_erf or 0
    if j >= basis + 2:
        score = 25
    elif j >= basis:
        score = 22
    elif j >= basis * 0.6:
        score = 15
    elif j >= basis * 0.3:
        score = 10
    else:
        score = 5
    t = (k_text or "").lower()
    if any(w in t for w in ("teamführung", "mentoring", "team lead", "führung")):
        score += 3
    if any(w in t for w in ("agil", "scrum", "kanban")):
        score += 2
    return min(score, 30)


def score_bildung(k_abschluss: str) -> int:
    """app.py:205-215"""
    a = (k_abschluss or "").strip().lower()
    if a in ("master", "m.sc", "m.sc.", "m.sc.", "diplom", "phd", "promotion", "dr."):
        return 15
    if a in ("bachelor", "b.sc", "b.sc.", "b.a", "b.a."):
        return 12
    if a:
        return 8
    return 0


def score_sprache(k_deutsch: str, k_englisch: str, job_deutsch: str, job_englisch: str) -> int:
    """app.py:217-234"""
    de_req = (job_deutsch or "").strip()
    en_req = (job_englisch or "").strip()
    de_order = ["", "keine anforderung", "a1", "a2", "b1", "b2", "c1", "c2", "muttersprache"]
    def lvl(v):
        return de_order.index((v or "").strip().lower()) if (v or "").strip().lower() in de_order else 0
    k_de = lvl(k_deutsch)
    r_de = lvl(de_req)
    de_pts = 6 if r_de <= 1 or k_de >= r_de else (4 if k_de >= lvl("b1") else 0)
    if en_req and en_req.lower() != "keine anforderung":
        en_pts = 4 if lvl(k_englisch) >= lvl(en_req) else 0
    else:
        en_pts = 3 if lvl(k_englisch) >= lvl("b1") else 0
    return de_pts + en_pts


def score_standort(k_standort: str, job_standort: str, stellentyp: str = "") -> int:
    """app.py:236-248"""
    k = (k_standort or "").strip().lower()
    j = (job_standort or "").strip().lower()
    if "remote" in j or (stellentyp or "").lower() == "remote":
        return 10
    if k and j and k == j:
        return 8
    if k and j and (j in k or k in j):
        return 6
    return 2


def score_soft_skills(job_soft: str, k_soft: str) -> int:
    """app.py:250-257"""
    job_list = [s for s in (job_soft or "").split(",") if s.strip()]
    if not job_list:
        return 0
    k_list = [s for s in (k_soft or "").split(",") if s.strip()]
    hits = sum(1 for js in job_list if any(skills_match(js, ks) for ks in k_list))
    return int(round(hits / len(job_list) * 10))


# C3 (22.09.2026): Toleranz-Cache — Connector kostet ~2s pro Call (subprocess),
# Match-View rief gehalt_check ~11x pro Render auf → ~20s Block. Ergebnis ist
# deterministisch pro Midpoint → Cache liefert exakt dieselben Werte.
_GEHALT_TOL_CACHE: dict = {}


def gehalt_check(k_gehalt, gmin, gmax) -> str:
    """app.py:260-311 (Connector salary-data → calculate_salary_tolerance).

    i18n P9.3 (06.10.2026): Rueckgabe-Klartexte laufen durch `_()` (Anzeige-
    Layer). Der Import erfolgt bewusst funktionslokal, damit logic.py weiter
    ohne NiceGUI-Import auf Modulebene auskommt (frameworkfreie Layer).
    """
    from webui.i18n import _
    gmin = gmin or 0
    gmax = gmax or 0
    if k_gehalt is None or (k_gehalt or 0) <= 0:
        return _("❓ unbekannt") if (gmin or gmax) else _("✅ offen")
    if not gmin and not gmax:
        return _("✅ passt (offen)")
    if gmax == 0 or gmax is None:
        return _("✅ passt") if k_gehalt >= gmin * 0.8 else _("⚠️ außerhalb Rahmen")
    if gmin == 0:
        return _("✅ passt") if k_gehalt <= gmax * 1.1 else _("⚠️ außerhalb Rahmen")
    toleranz_min = 0.8  # Fallback (Design-Entscheidung)
    toleranz_max = 1.1  # Fallback (Design-Entscheidung)
    midpoint = (gmin + gmax) / 2
    if midpoint in _GEHALT_TOL_CACHE:
        toleranz_min, toleranz_max = _GEHALT_TOL_CACHE[midpoint]
    else:
        try:
            tol = _mcp_connector_call(SALARY_DATA_SERVER, "calculate_salary_tolerance",
                                       {"midpoint": midpoint, "tolerance_percent": 0.15})
            if tol and "tolerance_min" in tol and "tolerance_max" in tol:
                toleranz_min = tol["tolerance_min"] / midpoint if midpoint else 0.8
                toleranz_max = tol["tolerance_max"] / midpoint if midpoint else 1.1
        except Exception:
            pass
        _GEHALT_TOL_CACHE[midpoint] = (toleranz_min, toleranz_max)
    return _("✅ passt") if (k_gehalt <= gmax * toleranz_max and k_gehalt >= gmin * toleranz_min) else _("⚠️ außerhalb Rahmen")


def kategorie_label(key: str) -> str:
    """app.py:410-411"""
    return {v: k for k, v in DB_KATEGORIE_MAP.items()}.get(key, key)


# N-F2 (01.10.2026): Signatur-Cache — `berechne_match_score` ruft diese Funktion
# je Kandidat (Feedback-Picker: bis zu 20 Passivkandidaten je Render) und oeffnete
# ohne Cache je Aufruf eine DB-Verbindung + Query. Signatur = (COUNT(*), MAX(id))
# der gewichtung_historie; der Feedback-Loop INSERTet neue Zeilen → MAX(id) steigt
# → Cache invalidiert automatisch (Signatur-Muster wie M-16).
_WEIGHTS_CACHE: dict = {}


def get_current_weights(conn: sqlite3.Connection | None = None) -> dict:
    """Phase 4: Rohgewichte aus gewichtung_historie, normalisiert auf 100.
    app.py:313-345. (N-F2: mit Signatur-Cache, nur bei eigener Verbindung.)"""
    own_conn = False
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH))
        own_conn = True
    sig = None
    if own_conn:
        try:
            sig = conn.execute(
                "SELECT COUNT(*), COALESCE(MAX(id), 0) FROM gewichtung_historie").fetchone()
        except sqlite3.Error:
            sig = None
        if sig is not None:
            _hit = _WEIGHTS_CACHE.get(sig)
            if _hit is not None:
                conn.close()
                return dict(_hit)
    roh = dict(BASELINE_GEWINCHTE)
    try:
        cur = conn.execute("""SELECT kategorie, neue_gewichtung FROM gewichtung_historie gh
            WHERE id = (SELECT MAX(id) FROM gewichtung_historie WHERE kategorie = gh.kategorie)""")
        for kategorie_db, neue in cur.fetchall():
            key = DB_KATEGORIE_MAP.get(kategorie_db)
            if key and isinstance(neue, (int, float)) and neue >= 0:
                roh[key] = int(neue)
    except sqlite3.Error:
        pass
    finally:
        if own_conn:
            conn.close()
    for key, base in BASELINE_GEWINCHTE.items():
        if key == "sprache":
            roh[key] = max(0, min(roh[key], GEWICHT_CAP_SPRACHE_MAX))
        else:
            roh[key] = max(max(0, base - GEWICHT_CAP_ABWEICHUNG), min(roh[key], base + GEWICHT_CAP_ABWEICHUNG))
    s = sum(roh.values()) or 1
    anteile = {k: v / s * 100 for k, v in roh.items()}
    if own_conn and sig is not None:
        _WEIGHTS_CACHE[sig] = dict(anteile)
    return anteile


def adjust_weights_from_feedback(eingeladen: str, score: int, grund: str, conn) -> str:
    """Phase 4 (4.2/4.3): Geschlossener Feedback-Loop. app.py:347-408.

    i18n P9.4 (06.10.2026): Die *Rückgabe* (Anzeige im Feedback-MD) wird in der
    Erzeugungs-Sprache übersetzt; der übergebene `grund` wird unübersetzt in
    `gewichtung_historie` persistiert (Record, Absicht).
    """
    from webui.i18n import _
    roh = dict(BASELINE_GEWINCHTE)
    try:
        cur = conn.execute("""SELECT kategorie, neue_gewichtung FROM gewichtung_historie gh
            WHERE id = (SELECT MAX(id) FROM gewichtung_historie WHERE kategorie = gh.kategorie)""")
        for kategorie_db, neue in cur.fetchall():
            key = DB_KATEGORIE_MAP.get(kategorie_db)
            if key and isinstance(neue, (int, float)) and neue >= 0:
                roh[key] = int(neue)
    except sqlite3.Error:
        pass

    ziel, delta = None, 0
    # ⚠️ Design-Entscheidung (15.09.2026): Schwellen 80/70 haben keine externe Quelle.
    erfahrungs_schwelle = 80  # Fallback
    sprache_schwelle = 70     # Fallback
    try:
        cat = _static_connector_call(HR_BENCHMARK_SERVER, "get_score_category", {"score": score})
        if cat and "category" in cat:
            if cat["category"] == "Strong":
                erfahrungs_schwelle = 80
            elif cat["category"] == "Consider":
                erfahrungs_schwelle = 60
                sprache_schwelle = 60
    except Exception:
        pass
    if eingeladen == "Ja" and score >= erfahrungs_schwelle:
        ziel, delta = "erfahrung", 5
    elif eingeladen == "Nein" and score < sprache_schwelle:
        ziel, delta = "sprache", 10
    if ziel is None:
        return ""

    base = BASELINE_GEWINCHTE[ziel]
    if ziel == "sprache":
        cap = GEWICHT_CAP_SPRACHE_MAX
    else:
        cap = base + GEWICHT_CAP_ABWEICHUNG
    neu = roh[ziel] + delta
    if neu > cap:
        if roh[ziel] >= cap:
            return _("ℹ️ Cap erreicht ({0} = {1}) – keine Anpassung.").format(_(kategorie_label(ziel)), cap)
        neu = cap
    if neu == roh[ziel]:
        return ""

    label = {v: k for k, v in DB_KATEGORIE_MAP.items()}[ziel]
    conn.execute("""INSERT INTO gewichtung_historie
        (kategorie, alte_gewichtung, neue_gewichtung, grund, feedback_anzahl)
        VALUES (?, ?, ?, ?, 1)""", (label, roh[ziel], neu, grund))
    conn.commit()
    return _("✅ {0}: {1} → {2} (Rohgewicht, normalisiert auf 100)").format(_(label), roh[ziel], neu)


def score_branche(branche: str, k_text: str) -> int:
    """Phase 4.6: Branchen-Score. app.py:631-650."""
    lt = (k_text or "").lower()
    it_treff = any(w in lt for w in ("devops", "cloud", "it-projekt", "software",
                                     "netzwerk", "infrastruktur", "datenbank", "entwickl"))
    if not lt:
        return 0
    b = (branche or "").strip().lower()
    if not b:
        return 10 if it_treff else 6
    it_nahe = ("telekom", "telekommunikation", "engineering", "technolog", "informatik", "software")
    if b == "it" or any(w in b for w in it_nahe):
        return 10 if it_treff else 4
    return 6 if it_treff else 2


# M-16-Fix (29.09.2026, Nutzer-GO): Kategorie-Schwellen lokal statt Subprozess.
# Quelle (Lab-Prinzip 1): ZYTHR-Schwellen aus dem Connector-Quelltext selbst
# (connectors/hr-benchmark-server.py:44-53, get_score_category, verifiziert 15.09.2026):
# >=80 = "Strong", >=60 = "Consider", <60 = "Weak" — identische Werte, identische Ausgabe.
# Grund: 82,06 s kalte Match-Seite durch 19 hr-benchmark-Spawns je Render
# (Messung: ergebnisse/m16-timing-20260929.md, Eintrag #93). Connector bleibt in
# opencode.json registriert; Runner-Nutzung unberührt (separater Punkt).
# Spec: knowledge/lifecycle/matching-criteria.md §4a.
def get_score_category_lokal(score: int) -> str:
    if score >= 80:
        return "Strong"
    if score >= 60:
        return "Consider"
    return "Weak"


def berechne_match_score(k: dict, j: dict) -> dict:
    """Gesamt-Score 0–100 + Kategorie + Explainability. app.py:652-763."""
    anteile = get_current_weights()
    must_haves = [s for s in (j.get("hard_skills") or "").split(",") if s.strip()]
    k_skills = [s for s in (k.get("hard_skills") or "").split(",") if s.strip()]
    kern, matches = score_kernkompetenzen(must_haves, k_skills)
    erfahrung = score_berufserfahrung(k.get("berufserfahrung_jahre"), j.get("berufserfahrung_jahre"), k.get("lebenslauf_text") or "")
    bildung = score_bildung(k.get("abschluss"))
    standort = score_standort(k.get("standort"), j.get("standort"), j.get("stellentyp"))
    soft = score_soft_skills(j.get("soft_skills"), k.get("soft_skills"))
    sprache = score_sprache(k.get("deutsch"), k.get("englisch"), j.get("deutsch_level"), j.get("englisch_level"))
    branche = score_branche(j.get("branche"), k.get("lebenslauf_text") or "")
    roh_scores = {"kern": kern, "erfahrung": erfahrung, "bildung": bildung,
                  "standort": standort, "branche": branche, "soft": soft, "sprache": sprache}
    skaliert = {key: (val / KATEGORIE_MAX[key]) * anteile.get(key, 0)
                for key, val in roh_scores.items()}
    total = min(int(round(sum(skaliert.values()))), 100)
    # Connector: hr-benchmark → get_score_category() (ZYTHR-Schwellen)
    hervorragend_schwelle = 90  # Fallback (Design-Entscheidung)
    gut_schwelle = 75           # Fallback (Design-Entscheidung)
    bedingt_schwelle = 60       # Fallback (Design-Entscheidung)
    schwach_schwelle = 40       # Fallback (Design-Entscheidung)
    # Kategorie: lokal (M-16-Fix 29.09.2026) — ZYTHR-Schwellen aus Connector-Quelltext,
    # kein Subprozess je Score (Spec: matching-criteria.md §4a; vorher 1×
    # _static_connector_call(HR_BENCHMARK_SERVER, "get_score_category", …) je Aufruf)
    cat_label = get_score_category_lokal(total)
    if cat_label == "Strong":
        hervorragend_schwelle = 90
    elif cat_label == "Consider":
        bedingt_schwelle = 60
    if total >= hervorragend_schwelle:
        kategorie = "Hervorragend"
    elif total >= gut_schwelle:
        kategorie = "Gut"
    elif total >= bedingt_schwelle:
        kategorie = "Bedingt"
    elif total >= schwach_schwelle:
        kategorie = "Schwach"
    else:
        kategorie = "Nicht passend"
    # Explainability Layer (SphinxATS-Pattern, 16.09.2026)
    must_haves_str = ", ".join(f"{m} {'✅' if m in matches else '❌'}" for m in must_haves[:6]) if must_haves else "–"
    erf_j = k.get("berufserfahrung_jahre") or 0
    erf_req = j.get("berufserfahrung_jahre") or 0
    erklaerung = {
        "kern": f"{len(matches)}/{len(must_haves)} Skills: {must_haves_str}" if must_haves else "Keine Skills gefordert",
        "erfahrung": f"{erf_j}J Erfahrung, Stelle: {erf_req}J → {int(erf_j/max(erf_req,1)*100)}%" if erf_req else f"{erf_j}J Erfahrung (keine Angabe)",
        "bildung": f"{(k.get('abschluss') or '–')} → {bildung}/15",
        "standort": f"{'Remote' if 'remote' in (j.get('standort') or '').lower() else k.get('standort') or '–'} → {standort}/10",
        "branche": f"Branche '{j.get('branche') or '–'}' → {branche}/10",
        "soft": f"{soft}/10 ({len([s for s in (j.get('soft_skills') or '').split(',') if s.strip()])} gefordert)" if j.get("soft_skills") else "Keine Soft-Skills gefordert",
        "sprache": f"DE {k.get('deutsch') or '–'}/{j.get('deutsch_level') or '–'}, EN {k.get('englisch') or '–'}/{j.get('englisch_level') or '–'} → {sprache}/10",
    }
    return {
        "total": total, "kategorie": kategorie, "matches": matches,
        "kern": kern, "erfahrung": erfahrung, "bildung": bildung,
        "standort": standort, "branche": branche, "soft": soft, "sprache": sprache,
        "anteile": {kk: round(vv, 1) for kk, vv in anteile.items()},
        "erklaerung": erklaerung,
    }


# ─── DSGVO-Cleanup (Phase 4.5) ────────────────────────────────────────

DSGVO_FRIST_TAGE = 183  # 6 Monate (Spec: knowledge/legal/gdpr-policy.md)
DSGVO_FINALE_STATUS = ("abgelehnt", "eingestellt", "zurückgezogen")


def dsgvo_cleanup() -> dict:
    """Phase 4.5: Löscht Bewerbungsdaten 6 Monate nach Prozessende. app.py:565-614."""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("""SELECT id FROM applications
        WHERE status IN (?, ?, ?)
          AND aktualisiert_am IS NOT NULL
          AND CAST(strftime('%s', 'now') AS INTEGER) - CAST(strftime('%s', aktualisiert_am) AS INTEGER) >= ?""",
        (*DSGVO_FINALE_STATUS, DSGVO_FRIST_TAGE * 86400))
    ids = [r[0] for r in c.fetchall()]
    if ids:
        marks = ",".join("?" for _ in ids)
        c.execute(f"DELETE FROM application_status_history WHERE application_id IN ({marks})", ids)
        c.execute(f"DELETE FROM applications WHERE id IN ({marks})", ids)
        # P1-7 (30.09.2026): `payload LIKE '%"application_id": 16%'` war UNSCHARF und
        # LOESCHTE mit: jeder Task, dessen application_id mit "16" BEGINNT (160-169)
        # oder die "16" enthaelt (126, 216, ...) — also Tasks lebender Bewerbungen.
        # json_extract vergleicht den Zahlenwert exakt; eine Liste, kein Praefix.
        c.execute("DELETE FROM agent_tasks "
                  f"WHERE json_extract(payload, '$.application_id') IN ({marks})", ids)
        conn.commit()
    try:
        gel_doks = 0
        c.execute("""SELECT cd.id, cd.datei_pfad FROM candidate_documents cd
            WHERE cd.candidate_id NOT IN (
                SELECT DISTINCT candidate_id FROM applications
                WHERE status NOT IN (?, ?, ?))
              AND CAST(strftime('%s', 'now') AS INTEGER)
                  - CAST(strftime('%s', cd.hochgeladen_am) AS INTEGER) >= ?""",
            (*DSGVO_FINALE_STATUS, DSGVO_FRIST_TAGE * 86400))
        for d_id, d_pfad in c.fetchall():
            try:
                Path(d_pfad).unlink(missing_ok=True)
            except Exception:
                pass
            c.execute("DELETE FROM candidate_documents WHERE id = ?", (d_id,))
            gel_doks += 1
        if gel_doks:
            conn.commit()
    except Exception:
        pass
    try:
        # 17.10.2026 (Änderung B, DSGVO-Retention): UNGELESENE notifications
        # nach der Frist loeschen (Muster der bestehenden Deletes: strftime-
        # Sekundenvergleich gegen created_at, UTC "YYYY-MM-DD HH:MM:SS").
        # gelesen=1-Zeilen bleiben ANGEFASST-UNVERAENDERT (Design): sie
        # werden beim Lesen bereits per delete_notifications geloescht —
        # die Spalte ist vestigial.
        c.execute("""DELETE FROM notifications
            WHERE gelesen = 0
              AND CAST(strftime('%s', 'now') AS INTEGER)
                  - CAST(strftime('%s', created_at) AS INTEGER) >= ?""",
            (DSGVO_FRIST_TAGE * 86400,))
        gel_notifs = c.rowcount
        if gel_notifs:
            conn.commit()
    except Exception:
        gel_notifs = 0
    conn.close()
    return {"geloeschte_bewerbungen": len(ids), "geloeschte_dokumente": gel_doks,
            "geloeschte_notifications": gel_notifs}


def run_dsgvo_cleanup_once(_done_marker: dict | None = None) -> dict:
    """Führt den Cleanup max. 1x pro Tag aus. Streamlit-Fassung nutzt
    st.session_state als Marker; hier entkoppelt via _done_marker-Dict
    (die App übergibt ihren Session-Speicher)."""
    heute = datetime.now().strftime("%Y-%m-%d")
    if _done_marker is not None and _done_marker.get("dsgvo_cleanup_done") == heute:
        return {"geloeschte_bewerbungen": 0, "skip": True}
    try:
        result = dsgvo_cleanup()
        if _done_marker is not None:
            _done_marker["dsgvo_cleanup_done"] = heute
        if result["geloeschte_bewerbungen"]:
            print(f"[DSGVO-Cleanup] {result['geloeschte_bewerbungen']} Bewerbungen gelöscht (6-Monats-Frist)")
        return result
    except Exception as e:
        print(f"[DSGVO-Cleanup] Fehler (App läuft weiter): {e}")
        return {"geloeschte_bewerbungen": 0, "fehler": str(e)}


# ─── .bak-Retention (AGENTS.md:177, automatisiert 28.09.2026) ─────────

def _bak_timestamp(name: str) -> str | None:
    """Backup-Datum aus dem Dateinamen — NUR der Teil direkt nach `bak`.

    Fix 01.10.2026 (Nebenbefund Drift-Register): `re.search(r"(20\\d{6})", name)`
    nahm den ERSTEN 8-stelligen Treffer. Bei Namen mit kompaktem Datum im
    Original (z. B. `m16-timing-20260929.md.bak-20261001-1955`) matchte es das
    Original-Datum `20260929` statt den Backup-Stempel `20261001` → ein frisches
    Backup galt als Verstoß und wurde gelöscht (Beleg:
    `/tmp/opencode/bakcheck/deleted_2_20261001-2002.tar.gz`).
    Konvention: `<original>.bak-YYYYMMDD[-HHMM]`; `.bak_`/`.bak.` werden toleriert.
    Kein Treffer → None (gilt als „ohne Datum" = Verstoß)."""
    import re
    m = re.search(r"bak[._-]?(20\d{6})", name)
    return m.group(1) if m else None


def bak_retention_scan() -> list:
    """Liefert Pfade (relativ zu BASE_DIR) aller *.bak*-Dateien, die gegen die
    Retention-Regel verstoßen: kein Backup-Datum nach `bak` im Namen ODER Datum
    älter als die letzten 2 Kalendertage (heute + gestern).
    Ausgeschlossen: .venv*, backups/, .git/, __pycache__ (kein Regel-Target)."""
    from datetime import timedelta
    heute = datetime.now().date()
    erlaubt = {heute.strftime("%Y%m%d"), (heute - timedelta(days=1)).strftime("%Y%m%d")}
    verstoss = []
    for p in BASE_DIR.rglob("*.bak*"):
        rel = str(p.relative_to(BASE_DIR))
        if any(x in rel for x in (".venv", "backups/", ".git/", "__pycache__")):
            continue
        if not p.is_file():
            continue
        ts = _bak_timestamp(p.name)
        if ts is None or ts not in erlaubt:
            verstoss.append(rel)
    return sorted(verstoss)


def run_bak_retention_once() -> dict:
    """Führt die .bak-Retention aus (Regel-Ablauf: scannen → Rollback-Archiv → löschen).
    Fehlerresistent wie run_dsgvo_cleanup_once — die App läuft bei Fehlern weiter."""
    try:
        verstoss = bak_retention_scan()
        if not verstoss:
            return {"verstoesse": 0, "archiviert": 0}
        import tarfile
        ts = datetime.now().strftime("%Y%m%d-%H%M")
        ziel_dir = Path("/tmp/opencode/bakcheck")
        ziel_dir.mkdir(parents=True, exist_ok=True)
        tar_pfad = ziel_dir / f"deleted_{len(verstoss)}_{ts}.tar.gz"
        with tarfile.open(tar_pfad, "w:gz") as tar:
            for rel in verstoss:
                tar.add(BASE_DIR / rel, arcname=rel)
        for rel in verstoss:
            (BASE_DIR / rel).unlink()
        print(f"[Bak-Retention] {len(verstoss)} Verstoße archiviert + gelöscht → {tar_pfad}")
        return {"verstoesse": len(verstoss), "archiviert": len(verstoss), "archiv": str(tar_pfad)}
    except Exception as e:
        print(f"[Bak-Retention] Fehler (App läuft weiter): {e}")
        return {"verstoesse": 0, "archiviert": 0, "fehler": str(e)}


# ─── Agent-Runner-Autostart (Phase 5) ─────────────────────────────────

def ensure_agent_runner() -> None:
    """Startet den Hintergrund-Runner einmalig. app.py:521-547.
    F1-Autostart-Guard (agent-automation.md §4 Start, 23.09.2026):
    (a) pidfile + PID lebt + /proc/cmdline = agent-runner.py → kein Spawn, Log.
    (b) PID tot/stale → stale pidfile unlink(), dann Spawn.
    (c) KMHR_RUNNER_AUTOSTART=0 → harter Stopp.
    """
    if os.environ.get("KMHR_RUNNER_AUTOSTART") == "0":
        return
    pid_file = DATA_DIR / "agent-runner.pid"
    if pid_file.exists():
        alive = False
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\x00", b" ").decode(errors="replace")
            if "agent-runner.py" in cmdline:
                alive = True
                print(f"[Agent-Runner] vorhandener Runner genutzt (PID {pid})")
            else:
                print(f"[Agent-Runner] PID {pid} lebt, ist aber kein agent-runner → stale pidfile")
        except (ProcessLookupError, ValueError, PermissionError):
            print("[Agent-Runner] stale pidfile (PID tot/unlesbar) → wird entfernt")
        except OSError:
            alive = True  # /proc nicht lesbar, aber kill ok → nicht doppelt starten
        if alive:
            return
        try:
            pid_file.unlink()
        except OSError as e:
            print(f"[Agent-Runner] stale pidfile unlink fehlgeschlagen: {e}")
            return
    try:
        venv_py = BASE_DIR / ".venv-streamlit/bin/python3"
        py = str(venv_py) if venv_py.exists() else "python3"
        subprocess.Popen([py, str(BASE_DIR / "scripts/agent-runner.py")],
                         cwd=str(BASE_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        print("[Agent-Runner] Hintergrund-Runner gestartet")
    except Exception as e:
        print(f"[Agent-Runner] Autostart fehlgeschlagen (App läuft weiter): {e}")


# ─── Passwort-Hashing (Phase 3.2: SHA256 → argon2id Migration) ─────────

def hash_password_argon2id(password: str) -> str:
    """app.py:847-851"""
    from argon2 import PasswordHasher
    return PasswordHasher().hash(password)


def verify_password_argon2id(password: str, hash_str: str) -> bool:
    """app.py:853-861"""
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, InvalidHashError
    try:
        return PasswordHasher().verify(hash_str, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def is_sha256_hash(hash_str: str) -> bool:
    """app.py:863-865"""
    return len(hash_str) == 64 and all(c in "0123456789abcdef" for c in hash_str)


def verify_password_sha256(password: str, hash_str: str) -> bool:
    """Prueft SHA256-Hash (Migration-Pfad fuer alte Hashes)."""
    import hashlib
    return is_sha256_hash(hash_str) and hashlib.sha256(password.encode()).hexdigest() == hash_str


def migrate_password_if_needed(conn, user_id: int, password: str, table: str = "candidates") -> None:
    """app.py:867-877 (Spalte: password_hash, wie im DB-Schema)."""
    import hashlib
    c = conn.cursor()
    c.execute(f"SELECT password_hash FROM {table} WHERE id = ?", (user_id,))
    row = c.fetchone()
    if row and is_sha256_hash(row[0]):
        if hashlib.sha256(password.encode()).hexdigest() == row[0]:
            new_hash = hash_password_argon2id(password)
            c.execute(f"UPDATE {table} SET password_hash = ? WHERE id = ?", (new_hash, user_id))
            conn.commit()


# ─── Passwort ändern (N5, 20.09.2026) ──────────────────────────────
# Design-Entscheidung: knowledge/portal/candidate-portal-fields.md
# Mindestlänge 8 Zeichen (OWASP: Länge > Komplexität).
# Keine externen Quellen für Policy → als Design-Entscheidung markiert.

MIN_PASSWORD_LENGTH = 8  # Design-Entscheidung (s.o.)


def change_password(conn, table: str, user_id: int,
                    altes_pw: str, neues_pw: str) -> tuple[bool, str]:
    """Passwort ändern. Framework-unabhängig (Streamlit + NiceGUI).
    Verifiziert altes PW (argon2id + SHA256-Migrations-Pfad), prüft Policy,
    schreibt neuen argon2id-Hash. Gibt (ok, Meldung) zurück."""
    # 1. Aktuellen Hash laden
    c = conn.cursor()
    c.execute(f"SELECT password_hash FROM {table} WHERE id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        return (False, "Benutzer nicht gefunden.")
    old_hash = row[0]

    # 2. Altes Passwort verifizieren (argon2id oder SHA256-Migrations-Pfad)
    if is_sha256_hash(old_hash):
        import hashlib
        pw_ok = hashlib.sha256(altes_pw.encode()).hexdigest() == old_hash
    else:
        pw_ok = verify_password_argon2id(altes_pw, old_hash)

    if not pw_ok:
        return (False, "Altes Passwort ist nicht korrekt.")

    # 3. Neue Policy prüfen
    if len(neues_pw) < MIN_PASSWORD_LENGTH:
        return (False, f"Neues Passwort muss mindestens {MIN_PASSWORD_LENGTH} Zeichen lang sein.")

    # 4. Alten Hash mit neuem PW vergleichen (kein Backdoor: altes PW = neues PW)
    if is_sha256_hash(old_hash):
        import hashlib
        if hashlib.sha256(neues_pw.encode()).hexdigest() == old_hash:
            return (False, "Neues Passwort darf nicht dem alten Passwort entsprechen.")
    else:
        if verify_password_argon2id(neues_pw, old_hash):
            return (False, "Neues Passwort darf nicht dem alten Passwort entsprechen.")

    # 5. Neuen Hash schreiben
    new_hash = hash_password_argon2id(neues_pw)
    c.execute(f"UPDATE {table} SET password_hash = ? WHERE id = ?", (new_hash, user_id))
    conn.commit()
    return (True, "Passwort geändert.")


# ─── Rollen-Login (framework-unabhängig über Session-Dict) ────────────
# Streamlit: st.session_state | NiceGUI: app.storage.user — beides sind
# dict-ähnliche Speicher. Die App übergibt ihren Speicher als `session`.

SESSION_TIMEOUT_MIN = 30  # Phase 3.1 (Design-Entscheidung, app.py:819-831)


def login_user(session, email, name, cand_id) -> None:
    session["user_logged_in"] = True
    session["user_email"] = email
    session["user_name"] = name
    session["user_cand_id"] = cand_id
    session["user_last_activity"] = datetime.now().isoformat()


def logout_user(session) -> None:
    for key in ("user_logged_in", "user_email", "user_name", "user_cand_id", "user_last_activity"):
        session[key] = None if key != "user_logged_in" else False


def check_login(session) -> bool:
    """Login-Prüfung mit 30-Min-Timeout (app.py:819-831)."""
    if not session.get("user_logged_in"):
        return False
    last = session.get("user_last_activity")
    if last:
        try:
            elapsed = (datetime.now() - datetime.fromisoformat(last)).total_seconds() / 60
        except (ValueError, TypeError):
            elapsed = 0
        if elapsed > SESSION_TIMEOUT_MIN:
            logout_user(session)
            return False
    session["user_last_activity"] = datetime.now().isoformat()
    return True


def login_employer(session, employer_id, email, firma) -> None:
    session["employer_logged_in"] = True
    session["employer_id"] = employer_id
    session["employer_email"] = email
    session["employer_firma"] = firma


def logout_employer(session) -> None:
    for key in ("employer_logged_in", "employer_id", "employer_email", "employer_firma"):
        session[key] = None if key != "employer_logged_in" else False


def check_employer_login(session) -> bool:
    return bool(session.get("employer_logged_in"))


def login_admin(session, admin_id, email) -> None:
    session["admin_logged_in"] = True
    session["admin_id"] = admin_id
    session["admin_email"] = email


def logout_admin(session) -> None:
    for key in ("admin_logged_in", "admin_id", "admin_email"):
        session[key] = None if key != "admin_logged_in" else False


def check_admin_login(session) -> bool:
    return bool(session.get("admin_logged_in"))


def current_role(session) -> str:
    """Rollenmodell v4.5/v3.1: guest | candidate | employer | admin. app.py:834-842."""
    if check_admin_login(session):
        return "admin"
    if check_employer_login(session):
        return "employer"
    if check_login(session):
        return "candidate"
    return "guest"


# ─── App-Start-Hooks (kopieren die app.py-Boot-Sequenz) ───────────────

# ─── CEFR-Berechnung (MCP get_cefr_level als Quelle der Wahrheit) ──────
# Refactor 20.09.2026: Beide Apps (app.py + webui) nutzen denselben Helper.
# Schwellen-Standort: scripts/language-test-server.py:get_cefr_level() — die
# Inline-Tabellen in app.py:2987 und candidate.py:467 sind GESCHLOSSEN.

# P2: Modul einmal laden, dann wiederverwenden; Änderungen am Server erst nach App-Neustart wirksam — Design-Entscheidung
_CEFR_SERVER_MOD = None


def cefr_from_avg(avg: float) -> dict:
    """CEFR-Level + Beschreibung + Empfehlung aus durchschnittlichem Score (0.0–1.0).

    Lädt die Schwellen-Lookup-Tabelle AUS DEM MCP-Server (scripts/language-test-server.py,
    Funktion get_cefr_level) via importlib — eine Quelle der Wahrheit. Fallback bei
    Fehler: identische Schwellen (Beweis: Boundary-Test 16/16 identisch, 20.09.2026,
    ergebnisse/nicegui-phase-1-portierung.md).
    """
    global _CEFR_SERVER_MOD
    try:
        import importlib.util
        if _CEFR_SERVER_MOD is None:
            p = BASE_DIR / "scripts" / "language-test-server.py"
            spec = importlib.util.spec_from_file_location("language_test_server", p)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            _CEFR_SERVER_MOD = mod
        res = _CEFR_SERVER_MOD.get_cefr_level(float(avg), "")
        d = json.loads(res)
        return {
            "level": d["level"],
            "beschreibung": d.get("beschreibung", ""),
            "empfehlung": d.get("empfehlung", ""),
        }
    except Exception:
        # Fallback: identische Schwellen wie get_cefr_level (verifiziert 20.09.2026)
        if avg >= 0.8:
            lv = "C1"
        elif avg >= 0.6:
            lv = "B2"
        elif avg >= 0.4:
            lv = "B1"
        elif avg >= 0.2:
            lv = "A2"
        else:
            lv = "A1"
        return {"level": lv, "beschreibung": "", "empfehlung": ""}


# ─── Warm-up der MCP-Sessions (Plan A, 08.10.2026) ──────────────────────────
# Der erste Match-Render startete die MCP-Sessions/Caches synchron im Event-Loop
# (Lag-Monitor: 2,97 s Block > pingTimeout 2 s). Diese Liste wärmt sie beim
# App-Start in einem Daemon-Thread vor. Rollback: KMHR_MCP_WARMUP=0.
_MCP_WARMUP_JOBS = (
    (HR_BENCHMARK_SERVER, "get_score_category", {"score": 80}),
    (SALARY_DATA_SERVER, "calculate_salary_tolerance", {"midpoint": 50000}),
    (PRESCREEN_CONFIG_SERVER, "get_optimal_duration", {}),
)


def _warm_mcp_connectors_blocking() -> list:
    """Ruft die Warm-up-Jobs PARALLEL auf (je ein Thread) — kürzere Gesamtdauer
    (~3 s statt ~10 s), damit das Vorwärmen vor dem ersten Render fertig ist und
    nicht mit ihm um den globalen `_SESSION_LOCK` konkurriert. Fehler ignorieren."""
    results: list = [None] * len(_MCP_WARMUP_JOBS)

    def _one(i, server_py, tool, args):
        try:
            results[i] = _mcp_connector_call(server_py, tool, args)
        except Exception:
            results[i] = None

    threads = [threading.Thread(target=_one, args=(i, s, t, a),
                                name=f"mcp-warmup-{i}", daemon=True)
               for i, (s, t, a) in enumerate(_MCP_WARMUP_JOBS)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    return results


def warm_mcp_connectors():
    """Startet das Vorwärmen im Hintergrund-Thread; None bei KMHR_MCP_WARMUP=0."""
    if os.environ.get("KMHR_MCP_WARMUP") == "0":
        return None
    th = threading.Thread(target=_warm_mcp_connectors_blocking, name="mcp-warmup", daemon=True)
    th.start()
    return th


def app_bootstrap() -> None:
    """Wird von beiden Apps beim Start aufgerufen (app.py:855-863):
    DSGVO-Cleanup 1x/Tag + agent_tasks-Tabelle + Runner-Autostart."""
    run_dsgvo_cleanup_once()
    run_bak_retention_once()  # .bak-Retention (AGENTS.md:177), automatisiert 28.09.2026
    try:
        init_agent_tasks_table()
    except Exception as e:
        print(f"[Agent-Queue] Tabellen-Init fehlgeschlagen (App läuft weiter): {e}")
    ensure_agent_runner()
    warm_mcp_connectors()
