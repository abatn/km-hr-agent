"""Regressionstests: Drawer-Klick + SPA-Navigation via _SHELL_STATE + pushState.

Bug 1 (20.09.2026): LeftDrawer.close() existiert nicht (NiceGUI 3.17.1)
Bug 2 (21.09.2026): ui.navigate.to() im Content-Bereich -> Full-Page-Redirect
Fix: _SHELL_STATE + render_content() + history.pushState (clientseitiges Routing)

Ausfuehren: .venv-streamlit/bin/python3 -m pytest tests/test_drawer_click.py -v
"""
from nicegui import ui

from webui.components import shell, navigate_to, _SHELL_STATE


@ui.page('/test')
def demo_page():  # R5-1: hies frueher test_page — wurde von pytest als Test
    # eingesammelt und ging nur in Kombination mit anderen user_simulation-
    # Modulen auf (slot-stack leer). Kein Test, sondern die Demo-Route.
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


async def test_shell_renders_with_sidebar(user):
    """Shell rendert Sidebar + Header + Content."""
    await user.open('/test')
    await user.should_see('Kandidaten-Portal')   # Sidebar-Titel
    await user.should_see('Seite Eins')          # Sidebar-Button 1
    await user.should_see('Seite Zwei')          # Sidebar-Button 2
    await user.should_see('Seite Drei')          # Sidebar-Button 3
    await user.should_see('KM-HR-Agent')         # Header
    await user.should_see('AKTIV-p1')            # Initiale Seite


async def test_sidebar_click_switches_content_inline(user):
    """Sidebar-Klick -> render_content() tauscht Content inline (kein Reload)."""
    await user.open('/test')
    await user.should_see('AKTIV-p1')

    # Klick auf Sidebar-Button -> render_content() tauscht Content
    user.find('Seite Zwei').click()
    await user.should_see('AKTIV-p2')
    await user.should_not_see('AKTIV-p1')

    user.find('Seite Drei').click()
    await user.should_see('AKTIV-p3')
    await user.should_not_see('AKTIV-p2')


async def test_navigate_to_updates_content(user):
    """navigate_to() tauscht Content via _SHELL_STATE."""
    await user.open('/test')
    await user.should_see('AKTIV-p1')

    # navigate_to() via _SHELL_STATE (O1: Key = f"{client.id}:{role}" seit 24.09.2026)
    states = [v for k, v in _SHELL_STATE.items() if k.endswith(":candidate")]
    assert states, "_SHELL_STATE[*:candidate] nicht registriert"
    state = states[-1]
    state['page']['value'] = 'p3'
    state['render']()

    await user.should_see('AKTIV-p3')
    await user.should_not_see('AKTIV-p1')
