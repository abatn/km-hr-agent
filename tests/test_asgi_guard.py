"""ASGI-Guard-Test (10.10.2026): Socket.IO-Client-Abbruch -> 400 statt 500.

Spec: knowledge/system/asgi-guard.md. Deckt ab:
  1. `KeyError('REQUEST_METHOD')` auf dem Socket.IO-Pfad -> 400 (kein Throw).
  2. Dieselbe Ursache als `BaseExceptionGroup` (Starlette-TaskGroup) -> 400.
  3. Nur der Socket.IO-Pfad wird behandelt: anderer Pfad -> Ausnahme weitergereicht.
  4. Nur `REQUEST_METHOD`: andere Ausnahmen werden weitergereicht (keine Kaschierung).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webui.asgi_guard import SocketioAbortGuard  # noqa: E402

SOCKETIO = "/_nicegui_ws/socket.io/"


def _run(path, exc):
    """Ruft die Middleware mit innerer App, die `exc` wirft; gibt die gesendeten ASGI-Messages."""
    sent: list = []

    async def inner(scope, receive, send):
        raise exc

    async def receive():
        return {"type": "http.request"}

    async def send(message):
        sent.append(message)

    mw = SocketioAbortGuard(inner)
    asyncio.run(mw({"type": "http", "path": path, "method": "GET"}, receive, send))
    return sent


def test_keyerror_request_method_auf_socketio_pfad_wird_400():
    sent = _run(SOCKETIO, KeyError("REQUEST_METHOD"))
    assert sent, "Middleware hat keine Antwort gesendet"
    assert sent[0]["type"] == "http.response.start"
    assert sent[0]["status"] == 400
    assert sent[-1]["type"] == "http.response.body"


def test_baseexceptiongroup_mit_request_method_wird_400():
    eg = BaseExceptionGroup("taskgroup", [KeyError("REQUEST_METHOD")])
    sent = _run(SOCKETIO, eg)
    assert sent and sent[0]["status"] == 400


def test_anderer_pfad_reicht_ausnahme_weiter():
    with pytest.raises(KeyError):
        _run("/candidate", KeyError("REQUEST_METHOD"))


def test_andere_ausnahme_wird_weitergereicht():
    with pytest.raises(KeyError):
        _run(SOCKETIO, KeyError("etwas_anders"))
