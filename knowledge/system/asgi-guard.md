# ASGI-Guard: Socket.IO-Client-Abbruch (400 statt 500)

> **Stand:** 10.10.2026 · **Rolle:** normativ · **Status:** umgesetzt
> **Quelle:** engineio-Code (`async_drivers/asgi.py::translate_request`, `async_server.py:238`)
> + Analyse-Report `ergebnisse/asgi-trace-2026-10-01.md`. **Design-Entscheidung**
> (keine externe Norm) für die Guard-Wahl (400 statt 500).

## Regel

Eingehende HTTP-Anfragen auf dem Socket.IO-Pfad (`/socket.io/`, bei NiceGUI
`/_nicegui_ws/socket.io/`), deren **erstes** ASGI-Event kein `http.request` und kein
`websocket.connect` ist (typisch: **Client-Abbruch** oder Port-Scanner/Probe, die die
Verbindung vor dem Body schließt), werden mit **HTTP 400** beantwortet — **nicht** mit
einem 500 und **nicht** als Log-Zeile „Exception in ASGI application".

## Ursache (belegt ⓘ10.10.2026)

1. `engineio/async_drivers/asgi.py::translate_request`: `event = await receive(); if
   event['type'] not in ['http.request', 'websocket.connect']: return {}` → **leeres
   `environ`**.
2. `engineio/async_server.py:238` (und `base_server.py:330`, `server.py:217`): greifen
   **ungeschützt** auf `environ['REQUEST_METHOD']` zu → `KeyError: 'REQUEST_METHOD'`.
3. Der Fehler propagiert durch Starlettes `BaseHTTPMiddleware` (`create_collapsing_task_group`
   → `BaseExceptionGroup`) und NiceGUIs `_exception_handler_500` (re-raise) bis uvicorn
   → Log `Exception in ASGI application` + HTTP 500 an den (bereits getrennten) Client.

**Upstream ungefixt:** engineio 4.14.0 = neuestes Release; kein passendes Issue/PR
(GitHub-Recherche 03.10.2026, s. `ergebnisse/entscheidungen.md`).

## Umsetzung

`webui/asgi_guard.py::SocketioAbortGuard` — ASGI-Middleware, registriert in
`webui/main.py` via `app.add_middleware(SocketioAbortGuard)` **vor** `ui.run(...)`:

- Greift **nur** bei `scope["type"]=="http"` **und** `/socket.io/` im Pfad.
- Fängt `KeyError('REQUEST_METHOD')` **und** `BaseExceptionGroup`, die ihn enthält
  (Starlette-TaskGroup-Wrapping), solange noch **kein** Response begonnen hat → sendet
  `400 Bad Request`.
- **Jede andere** Ausnahme wird unverändert weitergereicht (`raise`) — keine
  Fehler-Verschleierung.

**Warum nicht** (verworfene Alternativen): Monkeypatch von `translate_request`
(update-fragil, eigene Ableitung ohne Quelle, 03.10. verworfen) · nur lokales Binden
`127.0.0.1` (kostet LAN) · Log-Filter (kaschiert) · Upstream-PR (fremdes Repo).

## Beweis

- `tests/test_asgi_guard.py`: Middleware mit Socket.IO-Scope + innerer App, die
  `KeyError('REQUEST_METHOD')` wirft → **400, kein Throw**; Nicht-Socket.IO-Scope →
  Ausnahme wird weitergereicht.
- Nach App-Neustart: Log ohne `Exception in ASGI application`/`REQUEST_METHOD`
  (Messung im S4-Log `ergebnisse/entscheidungen.md`).
