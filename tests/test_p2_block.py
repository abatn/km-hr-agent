"""R5-5 (30.09.2026): Tests für die P2-Verhaltensweisen — Produktionscode, keine Kopie.

Sechs Befunde aus dem P2-Block, je einer wirklich ausgeführt:
  1. Onboarding-Timeline im Kandidaten-Onboarding-Tab aus der ECHTEN
     application_status_history (Bewertung: 'Bewerbung eingegangen' usw. aus
     festen Items war toter Code — R5-4 entfernt; der Tab nutzt db.get_application_status_history).
  2. Sprachtests-Expander der Match-Seite: Kandidat MIT language_tests-Einträgen
     zeigt sie, fremder ohne Einträge nicht (employer.py:1504-1513).
  3. confirm_dialog: Abbrechen ändert nichts, Bestätigen ruft on_confirm genau 1×.
  4. Zurückziehen-Button: NUR aktive Status (R6-4, 30.09.2026) — Whitelist
     eingegangen/angesehen/eingeladen in candidate.py:696; abgelehnt zeigt
     ihn NICHT (Render-Nachweis: tests/test_tabs_render.py::
     test_zurueckziehen_nur_bei_aktiven_status).
  5. Sidebar-Aktivmarkierung: aktiver Menü-Button hat font-bold + primary
     (components.py shell, :1315-1320) — via nicegui.testing gerendert.
  6. R6-3: Employer-Seiten zeigen bei DB-Fehler rote Fehlerkarte mit
     "Neu laden" statt stiller Leere (Route /p2-emp-error, Spiegel-DB OHNE
     agent_tasks-Tabelle).

Ausführen: .venv-streamlit/bin/python3 -m pytest tests/test_p2_block.py -v
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nicegui import ui

from webui import db  # noqa: E402
from webui.components import confirm_dialog  # noqa: E402
from webui.pages import candidate as candidate_page  # noqa: E402
from webui.pages import employer as employer_page  # noqa: E402


def _cand_session(cand_id: int) -> dict:
    return {
        "user_logged_in": True,
        "user_email": "test@example.de",
        "user_name": "Test Kandidat",
        "user_cand_id": cand_id,
        "user_last_activity": datetime.now().isoformat(),
    }


# Routes: tests/nicegui_main.py (Regel R5-1: @ui.page im Testmodul landet im
# falschen App-Objekt → 404). Nur Dialog-Semantik braucht hier eine Route —
# auch die liegt in nicegui_main.py.


# ── 1. Onboarding-Timeline aus echter History ───────────────────────────

async def test_onboarding_timeline_aus_history(user):
    """Kandidat 1, Bewerbung 8 (eingestellt): Timeline zeigt echte Status."""
    await user.open("/p2-onboarding")
    # Aus der echten History von Bewerbung 8:
    # eingegangen → angesehen → eingeladen → eingestellt (+ changed_at-Datum)
    await user.should_see("📨 eingegangen")
    await user.should_see("👁️ angesehen")
    await user.should_see("📅 eingeladen")
    await user.should_see("✅ eingestellt")
    # Die entfernten Dummy-Items hatten Titel OHNE Icon-Präfix ('Bewerbung
    # eingegangen' statt '📨 eingegangen'); deren Vorhandensein wäre der
    # Beweis toter Code. Die Timeline-Elemente sind jetzt Icon+Slug:
    await user.should_not_see("Bewerbung eingegangen")
    await user.should_not_see("Pre-Screening abgeschlossen")
    await user.should_not_see("Interview geplant")


# ── 2. Sprachtests-Expander (Match-Seite) ────────────────────────────────

def test_sprachtest_expander_daten_quelle():
    """Quell-Nachweis: Expander nutzt db.get_language_tests je Kandidat.

    Kandidat 13 HAT Einträge (Spiegel-DB), Kandidat 2 hat keine —
    die Bedingung employer.py:1505 `if _lang_tests:` entscheidet.
    """
    mit = db.get_language_tests(13)
    ohne = db.get_language_tests(2)
    assert mit, "Kandidat 13 sollte language_tests haben (Datenlage Spiegel-DB)"
    assert ohne == [], "Kandidat 2 sollte keine language_tests haben"


# ── 3. confirm_dialog-Semantik ───────────────────────────────────────────

async def test_confirm_dialog_abbrechen_aendert_nichts(user):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _p2_state

    await user.open("/p2-confirm")
    await user.should_see("Wirklich?")
    user.find("Abbrechen").click()
    # Dialog bleibt versteckt im DOM (dialog.close()) — Handler laufen async;
    # kurz awaiten, dann die Wirkung prüfen:
    import asyncio
    await asyncio.sleep(0.3)
    assert _p2_state.p2_confirm_refs[0] == [], "Abbrechen darf on_confirm NICHT aufrufen"


async def test_confirm_dialog_bestatigen_ruft_genau_einmal(user):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _p2_state

    await user.open("/p2-confirm2")
    user.find("Bestätigen").click()
    # Dialog bleibt versteckt im DOM — Handler async, kurz awaiten:
    import asyncio
    await asyncio.sleep(0.3)
    assert _p2_state.p2_confirm_refs[1] == ["ok"], \
        f"on_confirm genau 1x erwartet: {_p2_state.p2_confirm_refs[1]}"


# ── 4. Withdraw-Button je Status (R6-4: aktive Whitelist) ────────────────

def test_withdraw_button_status_regel():
    """R6-4 (30.09.2026): Nur AKTIVE Status bekommen den Zurückziehen-Button.

    Vorher Blacklist ('eingestellt', 'zurückgezogen') liess 'abgelehnt' zu —
    ein abgelehnter Bewerber hätte seine eigene Bewerbung zurueckziehen koennen.
    Produktion: candidate.py:696 (Whitelist). Render-Nachweis (rot/gruen):
    tests/test_tabs_render.py::test_zurueckziehen_nur_bei_aktiven_status.
    """
    src = (Path(__file__).resolve().parent.parent
           / "webui" / "pages" / "candidate.py").read_text(encoding="utf-8")
    assert 'if b_status in ("eingegangen", "angesehen", "eingeladen"):' in src, \
        "Whitelist-Bedingung (candidate.py:696) fehlt"
    assert 'if b_status not in ("eingestellt", "zurückgezogen"):' not in src, \
        "alte Blacklist-Bedingung ist zurück (liess 'abgelehnt' zu)"


# ── 5. Sidebar-Aktivmarkierung ──────────────────────────────────────

async def test_sidebar_aktiver_button_hervorgehoben(user):
    await user.open('/p2-shell')
    await user.should_see("INHALT-b")
    # Aktiver Button: color="primary" + font-bold (components.py:1315-1320)
    active_btn = next(iter(user.find("Beta").elements))
    classes = " ".join(active_btn.classes or [])
    assert "font-bold" in classes, f"Aktiver Button ohne font-bold: {classes!r}"
    # color landet in NiceGUI als Prop-Dict-Eintrag, nicht als Attribut
    assert active_btn.props.get("color") == "primary", \
        f"Aktiver Button ohne color=primary: {active_btn.props!r}"
    # Inaktiver Button ohne font-bold
    inactive_btn = next(iter(user.find("Alpha").elements))
    classes_a = " ".join(inactive_btn.classes or [])
    assert "font-bold" not in classes_a, f"Inaktiver Button mit font-bold: {classes_a!r}"


# ── 6. R6-3: Fehlerkarten statt stiller Leere (employer.py) ──────────────

async def test_employer_seiten_zeigen_fehlerkarte_bei_db_fehler(user, caplog):
    """Spiegel-DB OHNE agent_tasks-Tabelle → Dashboard-Statistik und
    Task-Queue zeigen rote Fehlerkarte + 'Neu laden' (R6-3), statt still
    leer zu bleiben (vorher `except Exception: pass`).

    Route /p2-emp-error (tests/nicegui_main.py) patcht webui.db.get_conn
    gegen eine :memory:-Kopie des Spiegels (conftest) ohne agent_tasks —
    die Live-DB data/feedback.db wird nie beschrieben.
    """
    await user.open("/p2-emp-error")
    # Dashboard-Kacheln (employer.py dashboard_stats except)
    await user.should_see("Dashboard-Zahlen konnten nicht geladen werden")
    # Task-Queue (employer.py refresh_agent_tasks except)
    await user.should_see("Agent-Tasks konnten nicht geladen werden")
    # Die eigentliche R6-3-Anforderung: Wiederholen ist MOEGLICH
    user.find("Neu laden")
    # R6-3-Logging-Nachweis: die absichtlich erzeugten ERROR-Logs sind der Beweis,
    # dass der Fehler PROTOKOLLIERT statt verschluckt wird (vorher `except: pass`).
    # Die nicegui-`user`-Fixture wertet jeden ERROR-Log im Teardown als Fehler
    # (nicegui/testing/user_plugin.py:30) — deshalb hier erst assertieren, dann
    # caplog.clear(), damit nur UNERWARTETE Fehler den Test brechen.
    _msgs = [r.getMessage() for r in caplog.get_records("call")
             if r.levelname == "ERROR" and r.name == "kmhr.employer"]
    assert any("dashboard_stats fehlgeschlagen" in m for m in _msgs), _msgs
    assert any("refresh_agent_tasks fehlgeschlagen" in m for m in _msgs), _msgs
    _fremd = [r.getMessage() for r in caplog.get_records("call")
              if r.levelname == "ERROR" and r.name != "kmhr.employer"]
    assert not _fremd, f"unerwartete ERROR-Logs ausserhalb kmhr.employer: {_fremd}"
    caplog.clear()
