"""ASGI-Guard: sauberer 400 statt 500 beim Socket.IO-Client-Abbruch (10.10.2026).

Ursache (belegt): engineio `async_drivers/asgi.py::translate_request` gibt fuer ein
ERSTES ASGI-Event, das weder `http.request` noch `websocket.connect` ist (z. B.
`http.disconnect` bei Client-Abbruch/Port-Probe), ein **leeres** `environ = {}` zurueck;
`engineio/async_server.py:238` greift dann ungeschuetzt auf `environ['REQUEST_METHOD']`
zu -> `KeyError: 'REQUEST_METHOD'` -> NiceGUI-500 -> uvicorn-Log
"Exception in ASGI application". Upstream ungefixt (engineio 4.14.0, kein Issue/PR).

Fix (in-app, kein Fremd-Monkeypatch): eine ASGI-Middleware faengt genau diese Ausnahme
(auch als BaseExceptionGroup aus Starlettes BaseHTTPMiddleware) auf dem Socket.IO-Pfad
ab und antwortet mit 400, solange noch kein Response begonnen hat.
Spec: knowledge/system/asgi-guard.md. Log: ergebnisse/entscheidungen.md 10.10.2026.
"""
from __future__ import annotations

_SOCKETIO_PATH = "/socket.io/"


def _is_request_method_keyerror(exc: BaseException) -> bool:
    """True, wenn `exc` der engineio-`KeyError('REQUEST_METHOD')` ist (auch verschachtelt)."""
    if isinstance(exc, KeyError) and exc.args == ("REQUEST_METHOD",):
        return True
    if isinstance(exc, BaseExceptionGroup):  # Python >= 3.11
        return any(_is_request_method_keyerror(e) for e in exc.exceptions)
    return False


class SocketioAbortGuard:
    """Faengt den engineio-`KeyError('REQUEST_METHOD')` auf dem Socket.IO-Pfad ab."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or _SOCKETIO_PATH not in scope.get("path", ""):
            await self.app(scope, receive, send)
            return

        started = False

        async def _send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except BaseException as exc:  # bewusst breit; eng geprueft + sonst weitergereicht
            if _is_request_method_keyerror(exc) and not started:
                await send({
                    "type": "http.response.start",
                    "status": 400,
                    "headers": [(b"content-type", b"text/plain; charset=utf-8")],
                })
                await send({"type": "http.response.body", "body": b"Bad Request"})
                return
            raise
