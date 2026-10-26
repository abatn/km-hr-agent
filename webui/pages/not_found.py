"""
404 Not Found page for KM-HR-Agent NiceGUI App.
"""
from __future__ import annotations

from nicegui import ui

from webui.i18n import _
from webui.theme import C


def create() -> None:
    """Register the /404 page."""

    @ui.page("/404")
    def not_found():
        from webui.theme import inject_css
        inject_css()
        with ui.column().classes("items-center justify-center h-screen gap-4"):
            ui.icon("error_outline", size="xl").classes("text-gray-400")
            ui.label("404").classes("text-6xl font-bold text-gray-300")
            ui.label(_("Seite nicht gefunden")).classes("text-xl text-gray-500")
            ui.button(
                _("Zurueck zum Dashboard"), icon="home",
                on_click=lambda: ui.navigate.to("/login"),
            ).classes(C.BTN_PRIMARY)
