"""NiceGUI-Main-Datei NUR für Tests (pytest.ini: main_file).
Definiert die /test-Route mit der shell()-Komponente, damit die
user_simulation die Seite öffnen kann — isoliert von webui/main.py.

R5-1 (30.09.2026): Demo-Routen, die die ECHTEN Tab-Funktionen
_tab_bewerbungen/_tab_onboarding (webui/pages/candidate.py) rendern.
Warum hier und nicht im Testmodul: user_simulation führt NUR diese Datei
via runpy aus — @ui.page im Testmodul läuft vor dem Global-Reset und
registriert ins falsche App-Objekt (Beweis: 404 in Runde 5).
"""
from datetime import datetime

from nicegui import ui

from webui.components import confirm_dialog, shell
from webui.pages import candidate as candidate_page

import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent))
import _p2_state as _st  # stabiler Speicher über runpy-Läufe (s. Modul-Doku)


def _cand_session(cand_id: int) -> dict:
    """Session-Dict exakt wie logic.login_user() es setzt (logic.py:811-816)."""
    return {
        "user_logged_in": True,
        "user_email": "test@example.de",
        "user_name": "Test Kandidat",
        "user_cand_id": cand_id,
        "user_last_activity": datetime.now().isoformat(),
    }


@ui.page('/tabs-bewerbungen')
def demo_bewerbungen():  # bewusst NICHT test_* benannt (sonst sammelt pytest sie als Test ein)
    candidate_page._tab_bewerbungen(_cand_session(1))


@ui.page('/tabs-onboarding')
def demo_onboarding():  # bewusst NICHT test_* benannt
    candidate_page._tab_onboarding(_cand_session(1))


@ui.page('/tabs-bewerbungen/{cand_id}')
def demo_bewerbungen_any(cand_id: int):  # R6-4: Statusregel je Kandidat pruefbar
    candidate_page._tab_bewerbungen(_cand_session(int(cand_id)))


# ── R5-5 (30.09.2026): P2-Block-Routen (gleiche Regel: hier, nicht im Modul) ──

@ui.page('/p2-shell')
def p2_shell():
    shell(
        role="candidate", user_id=1, user_name="Test Nutzer",
        menu_items=[
            {"key": "a", "label": "Alpha", "icon": "home"},
            {"key": "b", "label": "Beta", "icon": "work"},
        ],
        logout_fn=lambda: None,
        content_fn=lambda key: ui.label(f"INHALT-{key}"),
        s={},
        initial_tab="b",
    )


@ui.page('/p2-onboarding')
def p2_onboarding():
    candidate_page._tab_onboarding(_cand_session(1))


# ── R6-3 (30.09.2026): Seiten-Fehlerkarten bei defekter DB ──

@ui.page('/p2-emp-error')
def p2_emp_error():
    """Rendert Dashboard + Agent-Details gegen eine Spiegel-DB OHNE
    agent_tasks-Tabelle — die Query schlaegt fehl, die Seiten muessen
    Fehlerkarten mit 'Neu laden' zeigen statt stiller Leere."""
    import sqlite3 as _sq
    from unittest.mock import patch as _p
    from webui import db as _db
    from webui.pages import employer as _ep

    def _broken_conn():
        dst = _sq.connect(":memory:")
        # conftest leitet data/feedback.db in den Spiegel um → wir spiegeln
        # den Spiegel (NIE die Live-DB) und loeschen EINE Tabelle
        src = _sq.connect(str(_db.DB_PATH))
        src.backup(dst)
        src.close()
        dst.execute("DROP TABLE IF EXISTS agent_tasks")
        return dst

    s = {"employer_id": 1, "employer_logged_in": True,
         "employer_firma": "TechVision GmbH"}
    with _p.object(_db, "get_conn", _broken_conn):
        _ep._page_dashboard(s)
        _ep._page_agent_details(s)


# R5-5: Dialog-Semantik (Abbrechen/Bestätigen). Pro Test EIGENE Route +
# EIGENE Liste (Gemessen: zwei Tests auf einer Route teilen sich im
# Sammellauf die nicegui-App; die zweite Simulation schrieb in die Liste
# der ersten → 'genau einmal' flaschte leer).


@ui.page('/p2-confirm')
def p2_confirm():
    aufrufe: list = []
    _st.p2_confirm_refs[0] = aufrufe
    confirm_dialog(
        "Test?", "Wirklich?",
        on_confirm=lambda: aufrufe.append("ok"),
        confirm_label="Bestätigen",
    )


@ui.page('/p2-confirm2')
def p2_confirm2():
    aufrufe: list = []
    _st.p2_confirm_refs[1] = aufrufe
    confirm_dialog("Test2?", "Wirklich2?", on_confirm=lambda: aufrufe.append("ok"))


@ui.page('/test')
def demo_page():  # bewusst NICHT test_* benannt (sonst sammelt pytest sie als Test ein)
    shell(
        role="candidate", user_id=1, user_name="Test Nutzer",
        menu_items=[
            {"key": "p1", "label": "Seite Eins", "icon": "home"},
            {"key": "p2", "label": "Seite Zwei", "icon": "search"},
            {"key": "p3", "label": "Seite Drei", "icon": "work"},
        ],
        logout_fn=lambda: None,
        content_fn=lambda key: ui.label(f"AKTIV-{key}"),
        s={},
    )


# ── A4 (16.10.2026): Crash-Pfad Sprachtests-Block (Regel R5-1: Route hier) ──

@ui.page('/a4-match-focus')
def a4_match_focus():
    """A4-Crashpfad: ?kandidat=<Nicht-Bewerber> leert die Kandidaten-Liste;
    der Sprachtests-Block (Codemark db.get_language_tests) laeuft trotzdem.
    Rendert die echte _page_match gegen die Spiegel-DB (conftest) — nie die
    Live-DB. Vor dem Guard: UnboundLocalError (c_id) als ERROR-Log."""
    from webui.pages import employer as _ep
    s = {"employer_id": 1, "employer_logged_in": True,
         "employer_firma": "TechVision GmbH"}
    _ep._page_match(s)


# user_simulation führt diese Datei via runpy mit run_name='__main__' aus und
# erwartet ui.run() (NICEGUI_USER_SIMULATION=true verhindert den echten Serverstart).
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title="KM-HR-Agent Tests", reload=False, show=False)
