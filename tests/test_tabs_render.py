"""R5-1 (30.09.2026): Die Tabs "Bewerbungen" und "Onboarding" müssen rendern.

Befund: STATUS_ICONS wird in webui/pages/candidate.py (:678, :791, :1501)
benutzt, war aber nach einer Refaktorierung nicht mehr definiert → NameError.
Der `except Exception: pass`-Block in bewerbungen_list verschwieg den Fehler
(Tab leer), _tab_onboarding brach ab.

Der Test importiert die PRODUKTIONSFUNKTIONEN (_tab_bewerbungen,
_tab_onboarding) und rendert sie via nicegui.testing (Muster:
tests/test_drawer_click.py) mit dem Session-Dict, das login_user() setzt
(logic.py:811-816). Kandidat 1 hat in der (gespiegelten) Live-DB 3×
'eingestellt' + 1× 'zurückgezogen' — beide Zweige werden abgedeckt.

Rot-Beweis vor dem Fix: siehe ergebnisse/entscheidungen.md, Runde 5.
Ausführen: .venv-streamlit/bin/python3 -m pytest tests/test_tabs_render.py -v
"""
# Der Produktionscode (webui.pages.candidate) wird von tests/nicegui_main.py
# importiert und gerendert — Routen dort (Regel R5-1: @ui.page im Testmodul
# landet im falschen App-Objekt → 404).


async def test_bewerbungen_rendert_karten_mit_status(user):
    """Tab 'Bewerbungen': Karten mit Titel, Firma und Status-Badge sichtbar."""
    await user.open("/tabs-bewerbungen")
    # Karten der echten Bewerbungen von Kandidat 1 (Spiegel-DB)
    await user.should_see("TechVision GmbH")
    await user.should_see("Senior Cloud/DevOps Engineer")
    # Status-Klartexte der Badges (eingestellt + zurückgezogen vorhanden)
    await user.should_see("Eingestellt")
    await user.should_see("Zurückgezogen")


async def test_zurueckziehen_nur_bei_aktiven_status(user):
    """R6-4 (30.09.2026): Der Zurückziehen-Button erscheint NUR bei
    aktiven Status (eingegangen/angesehen/eingeladen) — nie bei
    abgelehnt/eingestellt/zurückgezogen.

    Datenlage (Spiegel-DB, R6-5-Refresh 01.10.2026): Kandidat 22 = abgelehnt
    (#29) + zurückgezogen (#30) → kein Button; Kandidat 17 = abgelehnt (#17) +
    eingeladen (#25) → Button da (Kandidat 13 ist seit 30.09.11:59–12:08
    komplett final eingestellt/abgelehnt und liefert keinen aktiven Fall mehr);
    Kandidat 1 = eingestellt + zurückgezogen → kein Button.
    """
    # Fall abgelehnt/zurückgezogen (R6-4: vorher zeigte auch 'abgelehnt' den Button)
    await user.open("/tabs-bewerbungen/22")
    await user.should_see("Abgelehnt")       # Badge von #29 (Status belegt)
    await user.should_not_see("Zurückziehen")

    # Fall eingeladen (aktiver Status → Button MUSS da sein)
    await user.open("/tabs-bewerbungen/17")
    await user.should_see("Eingeladen")      # Badge von #25
    await user.should_see("Zurückziehen")

    # Fall eingestellt/zurückgezogen (Kandidat 1, Bestands-Route)
    await user.open("/tabs-bewerbungen")
    await user.should_not_see("Zurückziehen")


async def test_onboarding_rendert_timeline_aus_history(user):
    """Tab 'Onboarding': Expansion je eingestellter Bewerbung + Timeline."""
    await user.open("/tabs-onboarding")
    # Expansionstitel (eingestellte Bewerbungen von Kandidat 1)
    await user.should_see("Senior Cloud/DevOps Engineer")
    # Timeline-Titel enthalten den Status-Slug (f"{icon} {status}")
    await user.should_see("eingestellt")
