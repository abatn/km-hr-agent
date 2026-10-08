"""i18n-Schicht (gettext) für KM-HR-Agent.

Spec + Quellen: knowledge/system/i18n.md. Methode (gettext + _() + app.storage.user +
Reload) ist der belegte NiceGUI-Community-Konsens (Discussion #5840).

Konvention: KEINE f-Strings in _() (Ruff INT001) -> _("{x} …").format(x=…).
"""
from __future__ import annotations

from nicegui import app, ui

from webui.i18n_core import DEFAULT, LOCALES_DIR, SUPPORTED, tr

LABELS = {"de": "DE", "en": "EN", "fr": "FR", "ar": "AR"}


def get_language() -> str:
    """Aktuelle Session-Sprache (Default 'de')."""
    try:
        lang = app.storage.user.get("language", DEFAULT)
    except Exception:
        lang = DEFAULT
    return lang if lang in SUPPORTED else DEFAULT


def set_language(lang: str) -> None:
    if lang in SUPPORTED:
        app.storage.user["language"] = lang


def is_rtl(lang: str | None = None) -> bool:
    return (lang or get_language()) == "ar"


def _(message: str) -> str:
    """Übersetzt `message` in die aktuelle Session-Sprache (Fallback: Original).

    Delegiert an die framework-freie Kernschicht `webui.i18n_core.tr`
    (Variante B, P1 07.10.2026) — Verhalten unverändert (`de` = Identität).
    """
    return tr(message, get_language())


def apply_direction() -> None:
    """Setzt <html lang> + dir (RTL bei Arabisch) beim Seitenaufbau.

    Zusätzlich wird **Quasars RTL-Modus** aktiviert (Fix 03.10.2026):
    Quasar leitet sein RTL NICHT aus `document.dir` ab, sondern aus seinem
    Sprachpaket. Ohne das reserviert `q-page-container` das Drawer-Padding auf
    der **logischen** statt physischen Seite (`q-drawer--left` -> `padding-left`);
    in RTL rendert dieser Drawer aber physisch rechts -> sobald das
    Benachrichtigungs-Panel geschlossen wurde, fiel das schuetzende Padding weg
    und der Content lief unter die Nav-Sidebar (Karten/Kreisdiagramm abgeschnitten).
    Nachweis: `ergebnisse/entscheidungen.md` (RTL-Padding-Bug) +
    `tests/e2e_rtl_drawer.py`.
    """
    lang = get_language()
    rtl = is_rtl(lang)
    direction = "rtl" if rtl else "ltr"
    ui.add_body_html(
        "<script>(function(){"
        f"document.documentElement.lang={lang!r};"
        f"document.documentElement.dir={direction!r};"
        # Quasar initialisiert mit dir=ltr (NiceGUI-Template); RTL-Flag nachziehen.
        "function kmhrRtl(){try{var Q=window.Quasar;"
        "if(Q&&Q.lang&&Q.lang.set&&Q.lang.enUS){"
        "Q.lang.set(Object.assign({},Q.lang.enUS,"
        f"{{isoName:{lang!r},rtl:{'true' if rtl else 'false'}}}));"
        "return true;}}catch(e){}return false;}"
        "if(!kmhrRtl()){document.addEventListener('DOMContentLoaded',kmhrRtl);"
        "var n=0,i=setInterval(function(){if(kmhrRtl()||++n>40)clearInterval(i);},250);}"
        "})();</script>"
    )


def _switch(lang: str) -> None:
    set_language(lang)
    ui.navigate.reload()


def language_switcher(compact: bool = True) -> None:
    """Sprachumschalter DE/EN/FR/AR (Header)."""
    current = get_language()
    with ui.row().classes("items-center gap-1"):
        for code in SUPPORTED:
            btn = ui.button(LABELS[code], on_click=lambda c=code: _switch(c))
            btn.props("flat dense" + (" color=primary" if code == current else ""))
            if compact:
                btn.classes("min-h-0 px-2")


# ─── Sprach-Transport (Variante B, P1 07.10.2026) ────────────────────────────
# Registriert die Session-Sprache als Resolver im framework-freien DB-Layer:
# `webui/db.py::queue_agent_task` haengt so bei jedem Portal-Trigger die
# `language` der ausloesenden Session an das Task-Payload (die eine zentrale
# Stelle deckt alle Aufrufer ab). Ohne NiceGUI-Session (Runner, Tests) faellt
# `get_language()` auf DEFAULT 'de' zurueck.
from webui import db as _db  # noqa: E402

_db.set_language_resolver(get_language)
