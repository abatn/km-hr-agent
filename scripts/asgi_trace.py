"""ASGI-Trace-Middleware – Isolierte Diagnose der abgebrochenen
`/_nicegui_ws/socket.io/`-Anfragen (KeyError 'REQUEST_METHOD', 01.10.2026).

Warum Code (Lab-Prinzip 2, MD-first greift hier nicht): Die entscheidende
Information — Client-IP/Port aus `scope["client"]`, Pfad, Methode und das
ERSTE ASGI-Receive-Event — existiert nur in der ASGI-Schicht und wird von
uvicorn (Access-Log aus) noch nicht einmal protokolliert. python-engineio
baut sein `REMOTE_ADDR` zudem hart auf '127.0.0.1' (async_drivers/asgi.py),
ist fuer die Absender-Ermittlung also untauglich.

Kausal-Kette (im Repo verifiziert, `grep`-Belege in
ergebnisse/asgi-trace-2026-10-01.md):

  uvicorn httptools_impl.on_headers_complete  -> startet ASGI-Task VOR Body
  -> engineio translate_request() ruft receive() auf
  -> uvicorn receive(): bei connection_lost (Klient schliesst) -> liefert
     {"type": "http.disconnect"}
  -> engineio async_drivers/asgi.py:160: `if event['type'] not in
     ['http.request', 'websocket.connect']: return {}`   (leeres Environ!)
  -> engineio async_server.py:238: `method = environ['REQUEST_METHOD']`
     -> KeyError: 'REQUEST_METHOD'

Daraus folgt: **KeyError ⟺ das erste Event war `http.disconnect`
(Klienten-Abbruch)**. Diese Middleware protokolliert genau dieses Event
pro Vorgang, zusammen mit Client-IP/Port, Pfad, Methode, Antwortstatus
und Exception – als JSONL (Rohdaten) + einzeiligem Textlog (Lesefassung).

Aufruf: wird von scripts/asgi_trace_run.py vor ui.run() als äusserste
Nutzer-Middleware eingehängt (`nicegui.app.add_middleware`).
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Headers, die fuer die Absender-/Browser-Erkennung relevant sind.
INTERESTING_HEADERS = (
    "user-agent",
    "origin",
    "referer",
    "host",
    "connection",
    "content-length",
    "x-forwarded-for",
    "sec-websocket-protocol",
)


class TraceWriter:
    """Schreibt je ASGI-Vorgang EINE JSONL-Zeile + EINE Textlog-Zeile."""

    def __init__(self, jsonl: Path, log: Path) -> None:
        self.jsonl = Path(jsonl)
        self.log = Path(log)
        self._lock = threading.Lock()
        for p in (self.jsonl, self.log):
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch(exist_ok=True)

    def write(self, rec: dict) -> None:
        line = json.dumps(rec, ensure_ascii=False, default=str)
        with self._lock:
            with self.jsonl.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            with self.log.open("a", encoding="utf-8") as fh:
                fh.write(self._pretty(rec) + "\n")

    @staticmethod
    def _pretty(rec: dict) -> str:
        client = rec.get("client_ip") or "?"
        port = rec.get("client_port")
        port_s = f":{port}" if port else ""
        exc = rec.get("exc") or "-"
        ua = (rec.get("headers") or {}).get("user-agent", "-")
        # UA kuerzen (Bot-UA sind lang, Browser-UA tragen die Versionsinfo)
        ua_s = ua if len(ua) <= 90 else ua[:87] + "..."
        return (
            f"{rec.get('ts')} {client}{port_s} "
            f"{(rec.get('method') or '-'):7s} "
            f"{rec.get('path', '-')} first={rec.get('first_event', '-')} "
            f"status={rec.get('status', '-')} exc={exc} "
            f"dur={rec.get('duration_ms', '-')}ms scope={rec.get('scope_type')} "
            f"ua={ua_s}"
        )


class TraceMiddleware:
    """Reine ASGI-Middleware: protokolliert Vorgang, gibt ihn unveraendert weiter.

    `receive` wird nur BEOBSCHACHTET (Memoizing-Replay), nie gestohlen:
    der innere Aufrufer bekommt exakt dieselben Events in derselben
    Reihenfolge – die KeyError-Kette in engineio bleibt dadurch unveraendert.
    """

    def __init__(self, app: Any, writer: TraceWriter) -> None:
        self.app = app
        self.writer = writer

    async def __call__(self, scope: dict, receive, send) -> None:
        if scope.get("type") not in ("http", "websocket"):
            return await self.app(scope, receive, send)  # lifespan etc.

        headers = {}
        for name, value in scope.get("headers", ()):
            try:
                key = name.decode("latin-1").lower()
                val = value.decode("latin-1")
            except Exception:
                continue
            if key in INTERESTING_HEADERS:
                headers[key] = val

        client = scope.get("client") or (None, None)
        rec: dict = {
            "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
            "t_mono": round(time.monotonic(), 4),
            "scope_type": scope.get("type"),
            "client_ip": client[0],
            "client_port": client[1],
            "server": scope.get("server"),
            "method": scope.get("method"),
            "path": scope.get("path"),
            "query": (scope.get("query_string") or b"").decode("latin-1", "replace"),
            "root_path": scope.get("root_path"),
            "http_version": scope.get("http_version"),
            "scheme": scope.get("scheme"),
            "headers": headers,
            "first_event": None,
            "first_event_extra": None,
            "n_receive": 0,
            "n_send": 0,
            "status": None,
            "ws": None,
            "exc": None,
            "duration_ms": None,
        }

        async def observe_receive():
            event = await receive()
            rec["n_receive"] += 1
            if rec["first_event"] is None:
                rec["first_event"] = event.get("type")
                extra = {}
                if event.get("type") == "http.request":
                    body = event.get("body") or b""
                    extra = {"body_len": len(body),
                             "more_body": bool(event.get("more_body"))}
                elif event.get("type") not in ("websocket.connect",):
                    extra = {k: v for k, v in event.items() if k != "type"}
                rec["first_event_extra"] = extra or None
            return event

        async def observe_send(message):
            rec["n_send"] += 1
            mtype = message.get("type")
            if mtype == "http.response.start":
                rec["status"] = message.get("status")
            elif mtype in ("websocket.accept", "websocket.close",
                           "websocket.http.response.start"):
                rec["ws"] = mtype
            return await send(message)

        t0 = time.monotonic()
        try:
            await self.app(scope, observe_receive, observe_send)
        except BaseException as exc:  # noqa: BLE001 – wird sofort weitergereicht
            rec["duration_ms"] = round((time.monotonic() - t0) * 1000, 2)
            rec["exc"] = f"{type(exc).__name__}: {exc}"
            _safe_write(self.writer, rec)
            raise
        else:
            rec["duration_ms"] = round((time.monotonic() - t0) * 1000, 2)
            if rec["first_event"] is None:
                rec["first_event"] = "(receive nie aufgerufen)"
            _safe_write(self.writer, rec)


def _safe_write(writer: TraceWriter, rec: dict) -> None:
    """Trace-Diagnose darf die App niemals zum Stehen bringen."""
    try:
        writer.write(rec)
    except Exception as exc:  # noqa: BLE001
        print(f"[asgi-trace] Schreibfehler: {type(exc).__name__}: {exc}")
