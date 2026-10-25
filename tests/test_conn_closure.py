"""Regressionstest — Handler-Connection-Falle (21.10.2026).

Fehlerklasse: ein NiceGUI-Callback benutzt eine DB-Verbindung, die der
Seitenaufbau geschlossen hat  ->  ``sqlite3.ProgrammingError: Cannot operate
on a closed database.``

Live-Beleg 21.10.2026: `webui/pages/employer.py`, Codemarke `_page_portal` —
der Callback `refresh_jobs` las die am Seitenende geschlossene `conn`
(Stackfolge `nicegui events.handle_event` -> `create_job` -> `refresh_jobs` ->
`conn.execute`; Log `/tmp/opencode/webui-start-20261021.log`).

Regel + Referenzmuster: `skills/nicegui-migration/SKILL.md`, Codemarke
`Handler-Connection-Falle` (Muster-Implementierung: `visa_info_section` in
`webui/components.py` — der Klick-Handler oeffnet seine eigene `conn` und
schliesst sie in `try/finally`).

Tests:
  (1) Muster-Test (AST) ueber `webui/**.py`: kein Callback darf eine
      Seiten-Scope-`conn` erben — weder eine geschlossene (der Defekt) noch
      eine offene (der Conn-Leak, siehe `_page_feedback`).
  (2) Fokus-Test `_page_portal`: der Callback wird NACH dem Seitenaufbau
      ausgeloest (wie ein verspaeteter Klick) -> kein ``ProgrammingError``.

Hinweis Isolation: `tests/conftest.py` spiegelt `data/feedback.db` in ein
/tmp-Verzeichnis — dieser Test schreibt NIE in die Live-DB.
"""
from __future__ import annotations

import ast
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_WEBUI_FILES = sorted((_ROOT / "webui").rglob("*.py"))


# ─── (1) Muster-Test: statische Analyse ───────────────────────────────

def _assigned_names(node: ast.AST) -> set[str]:
    """Namen, die in `node` zugewiesen werden (Schattierung einer aeusseren Variable)."""
    out: set[str] = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Assign):
            out.update(t.id for t in n.targets if isinstance(t, ast.Name))
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, (ast.For, ast.AsyncFor)) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
        elif isinstance(n, ast.withitem) and isinstance(n.optional_vars, ast.Name):
            out.add(n.optional_vars.id)
    return out


def _loaded_names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def _is_get_conn_call(node: ast.AST) -> bool:
    """True fuer `db.get_conn()` / `get_conn()` (Call-Attribut `get_conn`)."""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get_conn"
    )


def _page_scope_conns(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Verbindungen, die die Funktion selbst oeffnet (`conn = db.get_conn()`)."""
    out: set[str] = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Assign) and _is_get_conn_call(n.value):
            out.update(t.id for t in n.targets if isinstance(t, ast.Name))
    return out


def _closes_at_page_end(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Verbindungen, die am Ende der Funktion (Top-Level-Statement) geschlossen werden."""
    out: set[str] = set()
    for stmt in fn.body:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call = stmt.value
            if (isinstance(call.func, ast.Attribute) and call.func.attr == "close"
                    and isinstance(call.func.value, ast.Name)):
                out.add(call.func.value.id)
    return out


def _callback_readers(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[tuple[str, str]]:
    """(Callback-Name, conn-Name) je Callback, der eine Seiten-Scope-`conn` liest.

    Ein Callback, der den Namen selbst zuweist (z. B. `conn = db.get_conn()`),
    schattiert die aeussere Variable — das ist das erlaubte Muster.
    """
    page_conns = _page_scope_conns(fn)
    if not page_conns:
        return []
    out: list[tuple[str, str]] = []
    for n in ast.walk(fn):
        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) or n is fn:
            continue
        shadowed = _assigned_names(n)
        read = _loaded_names(n) & page_conns - shadowed
        for conn_name in sorted(read):
            out.append((n.name, conn_name))
    return out


def _closes_anywhere(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Verbindungen, die die Funktion (an irgendeiner Stelle) schliesst."""
    out: set[str] = set()
    for n in ast.walk(fn):
        if (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                and isinstance(n.value.func, ast.Attribute)
                and n.value.func.attr == "close"
                and isinstance(n.value.func.value, ast.Name)):
            out.add(n.value.func.value.id)
    return out


def _verstoeße(path: pathlib.Path, *, nur_geschlossene: bool = False) -> list[str]:
    """Alle Fundstellen der Regel in einer Datei (leer = regelkonform)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    out: list[str] = []
    for fn in funcs:
        readers = _callback_readers(fn)
        if not readers:
            continue
        closed = _closes_anywhere(fn)
        for cb_name, conn_name in readers:
            if nur_geschlossene and conn_name not in closed:
                continue
            zustand = ("geschlossen (in derselben Funktion) -> sqlite3.ProgrammingError moeglich"
                       if conn_name in closed else
                       "nie geschlossen -> Conn-Leak pro Render")
            out.append(
                f"{path.relative_to(_ROOT)}: {fn.name} (Callback `{cb_name}`) liest "
                f"die Seiten-Scope-`{conn_name}` ({zustand})")
    return out


def test_kein_callback_erbt_eine_seiten_scope_conn():
    """Muster-Test (Handler-Connection-Falle): Callbacks oeffnen ihre eigene conn.

    Ein Callback, der die `conn` des Seitenaufbaus erbt, nutzt sie zu einem
    Zeitpunkt, zu dem sie geschlossen ist (Defekt, 21.10.2026) — oder er
    haelt sie offen (Conn-Leak, `_page_feedback`).
    """
    verstoesse: list[str] = []
    for path in _WEBUI_FILES:
        verstoesse.extend(_verstoeße(path))
    assert not verstoesse, (
        "Handler-Connection-Falle verletzt (Regel: skills/nicegui-migration/SKILL.md, "
        "Codemarke `Handler-Connection-Falle`):\n  - " + "\n  - ".join(verstoesse))


def test_kein_callback_erbt_eine_geschlossene_seiten_scope_conn():
    """Nur der Defekt-Fall: ein Callback liest eine `conn`, die geschlossen wurde.

    Genau dieser Fall erzeugte am 21.10.2026 den Live-Fehler
    `sqlite3.ProgrammingError: Cannot operate on a closed database.`
    """
    verstoesse: list[str] = []
    for path in _WEBUI_FILES:
        verstoesse.extend(_verstoeße(path, nur_geschlossene=True))
    assert not verstoesse, (
        "Handler-Connection-Falle verletzt (Defekt-Fall, Live-Beleg 21.10.2026; "
        "Regel: skills/nicegui-migration/SKILL.md):\n  - " + "\n  - ".join(verstoesse))


# ─── (2) Fokus-Test: `_page_portal` (der Live-Defekt) ────────────────

async def test_page_portal_callback_nach_seitenaufbau_keine_closed_db(monkeypatch):
    """Der Callback laeuft NACH dem Seitenaufbau — die DB muss dann noch offen sein.

    Vor dem Fix (21.10.2026) las `refresh_jobs` die am Seitenende geschlossene
    `conn` -> `sqlite3.ProgrammingError: Cannot operate on a closed database.`
    """
    from nicegui import ui
    from nicegui.client import Client
    from nicegui.page import page as Page

    from webui.pages import employer as employer_page

    callbacks: list[tuple[str, object]] = []
    notifikationen: list[str] = []

    _orig_button = ui.button
    _orig_notify = ui.notify

    def _spy_button(*args, **kwargs):
        cb = kwargs.get("on_click")
        if cb is not None:
            label = args[0] if args else kwargs.get("label", "")
            callbacks.append((str(label), cb))
        return _orig_button(*args, **kwargs)

    def _spy_notify(message, **kwargs):
        notifikationen.append(str(message))
        return _orig_notify(message, **kwargs)

    monkeypatch.setattr(ui, "button", _spy_button)
    monkeypatch.setattr(ui, "notify", _spy_notify)

    session = {"employer_id": 1, "employer_logged_in": True,
               "employer_email": "regression@example.de", "employer_firma": "Regression"}

    client = Client(Page("/test-portal-conn-closure"))
    with client.content.default_slot:
        employer_page._page_portal(session)

    # Pflichtfelder der Seite fuellen (sonst bricht `create_job` frueh ab).
    by_label: dict[str, object] = {}
    for element in client.elements.values():
        label = element._props.get("label")
        if label and label not in by_label:
            by_label[label] = element
    by_label["Titel"].value = "Regressionsstelle Conn-Closure"
    by_label["Beschreibung (min. 50 Zeichen)"].value = (
        "Beschreibung fuer den Regressionstest der Handler-Connection-Falle " + "x" * 20)
    by_label["Arbeitsort"].value = "Muenchen"
    by_label["Must-Have-Skills (kommasepariert)"].value = "Python, SQL"

    create_job = next(cb for label, cb in callbacks if "Stelle ausschreiben" in label)

    # >>> Der Click kommt NACH dem Seitenaufbau (wie im Browser).
    with client.content.default_slot:
        create_job()
    assert any("Stelle ausgeschrieben" in n for n in notifikationen), notifikationen

    # >>> "Status speichern" -> `save_status` -> `refresh_jobs` (zweiter Call-Pfad).
    save_status = next(cb for label, cb in reversed(callbacks) if "Status speichern" in label)
    with client.content.default_slot:
        save_status()
    assert any("Status geändert" in n for n in notifikationen), notifikationen
