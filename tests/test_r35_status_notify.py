"""R3-5 (Runde 3, Nutzer-GO „A: Anbinden"): Statuswechsel -> notifications
an den Kandidaten.

Zu pruefen (pytest = Spiegel aus tests/conftest.py, Live-DB wird nur gelesen):
  1. die 3 HR-Klick-Status (eingeladen/abgelehnt/eingestellt) -> je GENAU 1 Zeile
     (user_id = candidate_id, role="candidate", titel "Bewerbungsstatus",
     deutscher Text mit Firma + Stelle + Status, gelesen=0)
  2. unbeteiligte Status (angsehen/leer/None) -> 0 Zeilen
  3. unbekannte application_id -> 0 Zeilen, kein Crash
  4. Fehlerfall (conn ohne Tabellen) -> kein Exception, Handler nicht blockiert
  5. AST-Bindung: alle 4 HR-Klick-Handler rufen den Helfer NACH dem UPDATE

Ausfuehren: .venv-streamlit/bin/python3 -m pytest -q tests/test_r35_status_notify.py
"""
from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

from webui import db
from webui.pages.employer import _notify_statuswechsel, _STATUS_NOTIF

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "webui" / "pages" / "employer.py"
TITEL = "Bewerbungsstatus"


def _app_row(conn):
    """Beliebige Bewerbung mit Firma + Stellen-Titel (Mirror-DB)."""
    return conn.execute(
        "SELECT a.id, a.candidate_id, e.firma, j.titel FROM applications a "
        "JOIN jobs j ON j.id = a.job_id "
        "JOIN employers e ON e.id = j.employer_id "
        "ORDER BY a.id LIMIT 1"
    ).fetchone()


def _rows(conn, cand_id):
    return conn.execute(
        "SELECT user_id, role, titel, nachricht, gelesen FROM notifications "
        "WHERE user_id = ? AND role = 'candidate' ORDER BY id", (cand_id,)
    ).fetchall()


def _cleanup(conn, cand_id):
    conn.execute(
        "DELETE FROM notifications WHERE user_id = ? AND titel = ?",
        (cand_id, TITEL),
    )
    conn.commit()


def test_drei_status_je_genau_eine_zeile():
    conn = db.get_conn()
    try:
        app_id, cand_id, firma, titel = _app_row(conn)
        _cleanup(conn, cand_id)
        for status in ("eingeladen", "abgelehnt", "eingestellt"):
            _notify_statuswechsel(conn, app_id, status)
            rows = _rows(conn, cand_id)
            assert len(rows) == 1, f"{status}: {len(rows)} Zeilen statt 1"
            user_id, role, ntitel, msg, gelesen = rows[0]
            assert user_id == cand_id, (user_id, cand_id)
            assert role == "candidate"
            assert ntitel == TITEL
            assert gelesen == 0, gelesen
            assert firma in msg, f"{firma} fehlt in {msg!r}"
            assert titel in msg, f"{titel} fehlt in {msg!r}"
            assert status in msg, f"{status} fehlt in {msg!r}"
            assert msg.startswith("Deine Bewerbung bei"), msg
            # eine Zeile pro Aufruf, kumuliert nicht ueber die 3 Status hinweg
            assert len(rows) == 1
            _cleanup(conn, cand_id)
        assert _rows(conn, cand_id) == [], "Cleanup fehlgeschlagen"
    finally:
        conn.close()


def test_unbeteiligte_status_0_zeilen():
    conn = db.get_conn()
    try:
        app_id, cand_id, _firma, _titel = _app_row(conn)
        _cleanup(conn, cand_id)
        for status in ("angesehen", "eingegangen", "", "zurückgezogen", None):
            _notify_statuswechsel(conn, app_id, status)
            assert _rows(conn, cand_id) == [], f"Status {status!r} darf keine Zeile schreiben"
        assert _STATUS_NOTIF == ("eingeladen", "abgelehnt", "eingestellt"), _STATUS_NOTIF
    finally:
        conn.close()


def test_unbekannte_application_0_zeilen():
    conn = db.get_conn()
    try:
        _app_id, cand_id, _f, _t = _app_row(conn)
        _cleanup(conn, cand_id)
        _notify_statuswechsel(conn, 999999, "eingeladen")
        assert _rows(conn, cand_id) == []
    finally:
        conn.close()


def test_helfer_fehlerfall_blockiert_nicht():
    """Conn ohne die benoetigten Tabellen -> kein Exception (try/except print)."""
    kaputt = sqlite3.connect(":memory:")
    try:
        assert _notify_statuswechsel(kaputt, 1, "eingeladen") is None
        assert _notify_statuswechsel(kaputt, 1, "abgelehnt") is None
        assert _notify_statuswechsel(kaputt, 1, "eingestellt") is None
    finally:
        kaputt.close()


def _calls_mit_scope(src: str) -> list:
    tree = ast.parse(src)
    funcs = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_notify_statuswechsel"]
    out = []
    for c in calls:
        enthaltend = [f for f in funcs
                      if f.lineno <= c.lineno <= (f.end_lineno or f.lineno)]
        inner = min(enthaltend, key=lambda f: (f.end_lineno or f.lineno) - f.lineno) \
            if enthaltend else None
        seg_lines = (ast.get_source_segment(src, inner) or "").splitlines() \
            if inner is not None else []
        def _idx(needle: str):
            return next((i for i, l in enumerate(seg_lines) if needle in l), None)
        update_idx = _idx("UPDATE applications")
        commit_idx = _idx(".commit()")
        call_idx = _idx("_notify_statuswechsel(")
        out.append({
            "line": c.lineno,
            "inner": inner.name if inner else None,
            "chain": sorted(f.name for f in enthaltend),
            "update_vorher": (update_idx is not None and call_idx is not None
                              and update_idx < call_idx),
            "commit_vorher": (commit_idx is not None and call_idx is not None
                              and commit_idx < call_idx),
        })
    return out


def test_handler_bindung_ast():
    """Alle 3 Dialog-Handler + der Stellen-Seiten-Übergang rufen den Helfer."""
    src = SRC.read_text(encoding="utf-8")
    calls = _calls_mit_scope(src)
    assert len(calls) == 4, [(c["line"], c["chain"]) for c in calls]
    innere = {c["inner"] for c in calls}
    assert {"do_invite", "do_reject", "do_hire"} <= innere, innere
    # 4. Call-Site: generischer HR-Klick auf /employer/stellen (make_transition/_do)
    assert any("make_transition" in c["chain"] for c in calls), calls
    for c in calls:
        assert c["update_vorher"], f"Zeile {c['line']} ohne UPDATE im Handler {c['chain']}"
        assert c["commit_vorher"], f"Zeile {c['line']} nicht NACH commit in {c['chain']}"


def test_nur_drei_status_im_quelltext():
    """do_seen ('angesehen') bleibt ohne Aufruf — bewusst, Status nicht im Whitelist."""
    src = SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "do_seen":
            seg = ast.get_source_segment(src, node) or ""
            assert "_notify_statuswechsel" not in seg, "do_seen darf nicht benachrichtigen"
