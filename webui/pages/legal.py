"""
Rechts-Seiten für KM-HR-Agent (Impressum, Datenschutz, AGB, Kontakt).

Inhalt kommt aus knowledge/legal/*.md (MD-first, AGENTS.md Schritt 2) — hier nur
das Rendern. Entwürfe (02.10.2026), anwaltlich zu prüfen; keine Rechtsberatung.

i18n (Phase 4, 02.10.2026): pro Sprache eine Datei `<name>.<lang>.md`
(z. B. `impressum.en.md`); fehlt sie, wird auf `<name>.md` (Deutsch) zurückgefallen.
Spec: knowledge/system/i18n.md.
"""
from __future__ import annotations

from pathlib import Path

from nicegui import ui

from webui.i18n import _, apply_direction, get_language, language_switcher
from webui.theme import C

BASE_DIR = Path(__file__).resolve().parents[2]
LEGAL_DIR = BASE_DIR / "knowledge" / "legal"

PAGES = {
    "impressum": "/impressum",
    "datenschutz": "/datenschutz",
    "agb": "/agb",
    "kontakt": "/kontakt",
}


def _resolve(name: str) -> Path:
    """`<name>.<lang>.md`, sonst Fallback `<name>.md` (Deutsch)."""
    lang = get_language()
    localized = LEGAL_DIR / f"{name}.{lang}.md"
    if lang != "de" and localized.is_file():
        return localized
    return LEGAL_DIR / f"{name}.md"


def _render(name: str) -> None:
    from webui.theme import inject_css
    inject_css()
    apply_direction()
    with ui.column().classes("w-full max-w-4xl mx-auto px-4 py-10 gap-4"):
        with ui.row().classes("items-center justify-between w-full"):
            ui.label("KM-HR-Agent").classes("text-lg font-bold text-blue-700")
            language_switcher()
            ui.button(_("Zurück"), icon="arrow_back",
                      on_click=lambda: ui.navigate.to("/")).classes(C.BTN_SECONDARY)
        path = _resolve(name)
        if path.is_file():
            ui.markdown(path.read_text(encoding="utf-8")).classes("w-full legal-md")
        else:
            ui.label(_("Inhalt fehlt: {file}").format(file=path.name)).classes("text-red-600")


def create() -> None:
    """Register /impressum, /datenschutz, /agb und /kontakt."""

    @ui.page("/impressum")
    def impressum():
        _render("impressum")

    @ui.page("/datenschutz")
    def datenschutz():
        _render("datenschutz")

    @ui.page("/agb")
    def agb():
        _render("agb")

    @ui.page("/kontakt")
    def kontakt():
        _render("kontakt")
