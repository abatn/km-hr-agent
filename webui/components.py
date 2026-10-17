"""
Reusable UI components for KM-HR-Agent NiceGUI App.
Based on knowledge/ui-design-system.md.
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from nicegui import ui

from webui.i18n import _  # i18n Phase 6b (03.10.2026); Spec: knowledge/system/i18n.md
# 17.10.2026 (Änderung B, Notification-Sprache): get_language + tr für die
# Key/Params-Anzeige im Notifications-Drawer (tr formt intern, KEIN .format()).
from webui.i18n import get_language
from webui.i18n_core import tr

from webui.theme import (
    C,
    DANGER,
    PRIMARY,
    SECONDARY,
    STATUS_BADGE_CLASSES,
    ACCENT,
    score_badge_class,
    score_color,
    score_label,
)

# ─── SPA-Navigation (render_content + pushState) ──────────────────
# shell() baut Sidebar + Content-Bereich einmalig auf.
# navigate_to() tauscht NUR den Content-Bereich (kein Page-Reload)
# und aktualisiert die URL via history.pushState (browser history).
# popstate-Listener behandelt Browser Back/Forward.
# O1 (24.09.2026): Key = f"{client.id}:{role}" — State je Client statt global
# je Rolle, sonst ruft navigate_to() das render() eines gelöschten Clients auf
# (Multi-Tab/Prune → RuntimeError "client ... has been deleted", entscheidungen.md).
_SHELL_STATE: dict[str, dict] = {}


def navigate_to(role: str, page_key: str) -> None:
    """SPA-Navigation: echter Route-Wechsel mit URL-Update.

    M-17 (01.10.2026, E2E-Messung): `history.pushState` als Best-Effort griff aus
    Klick-Handlern NICHT — Inhalt wechselte auf den Sprachtest-Tab, die URL blieb
    aber '/candidate/prescreen'; Browser-Back sprang auf '/candidate' (Protokoll
    `ergebnisse/pushstate-protokoll-*.md`). Verlaesslich und URL+Inhalt konsistent
    ist der echte Route-Wechsel via `ui.navigate.to` — dasselbe Muster wie employer
    Kandidaten-Tabelle + Dashboard-Kacheln (E2E-belegt). Der fruehere manuelle
    render()+pushState (mit O1-Staleness-Guard) entfaellt damit.
    """
    try:
        ui.navigate.to(f"/{role}/{page_key}")
    except Exception:
        pass  # Test-Simulation / kein Client: Content bleibt unveraendert


# ─── Candidate Avatar ────────────────────────────────────────────────

def candidate_avatar(name: str, size: str = "md") -> None:
    """Avatar with initial letter and color based on name hash."""
    initial = (name or "?")[0].upper()
    colors = [
        ("bg-blue-100", "text-blue-700"),
        ("bg-green-100", "text-green-700"),
        ("bg-purple-100", "text-purple-700"),
        ("bg-orange-100", "text-orange-700"),
        ("bg-teal-100", "text-teal-700"),
    ]
    bg, fg = colors[hash(name or "") % len(colors)]
    size_map = {"xs": "w-6 h-6 text-xs", "sm": "w-8 h-8 text-sm", "md": "w-10 h-10 text-base", "lg": "w-12 h-12 text-lg", "xl": "w-16 h-16 text-xl"}
    size_cls = size_map.get(size, size_map["md"])
    with ui.element("div").classes(f"rounded-full {bg} flex items-center justify-center {size_cls}"):
        ui.label(initial).classes(f"{fg} font-bold")


# ─── Skill Chip ──────────────────────────────────────────────────────

def skill_chip(skill: str, color: str = "blue", icon: str = "code") -> None:
    """Chip for displaying a skill.

    P2 (28.09.2026): NiceGUI/Quasar kennt 'code' nicht als registriertes Icon
    und rendert den Icon-Namen als sichtbares Wort ("code Python"). Der Chip
    bekommt den Text allein, das Icon entfaellt.
    """
    ui.chip(skill, color=color)


# ─── Loading Spinner ─────────────────────────────────────────────────

def loading_spinner(text: Optional[str] = None) -> None:
    """Loading spinner with text."""
    with ui.row().classes("items-center gap-2"):
        ui.spinner(size="sm")
        ui.label(text if text is not None else _("Laden...")).classes(C.MUTED)


# ─── Stat Card ───────────────────────────────────────────────────────

def stat_card(
    label: str,
    value: Any,
    icon: str = "info",
    trend: Optional[str] = None,
    color: str = PRIMARY,
    on_click: Optional[Callable] = None,
) -> ui.card:
    """A stat card with icon, value, label, and optional trend."""
    with ui.card().classes(C.CARD_HOVER + " cursor-pointer" if on_click else C.CARD).on(
        "click", on_click or (lambda: None)
    ):
        with ui.row().classes("items-center gap-4 w-full"):
            with ui.element("div").classes(
                "flex items-center justify-center w-12 h-12 rounded-xl"
            ).style(f"background-color: {color}20; color: {color};"):
                ui.icon(icon, size="md")
            with ui.column().classes("flex-1"):
                ui.label(str(value)).classes(C.STAT_NUMBER)
                ui.label(label).classes(C.SMALL)
            if trend:
                trend_color = SECONDARY if trend.startswith("+") else DANGER
                ui.label(trend).classes("text-sm font-medium").style(
                    f"color: {trend_color}"
                )


# ─── Glass Card ──────────────────────────────────────────────────────

def glass_card(
    title: Optional[str] = None,
    subtitle: Optional[str] = None,
    icon: Optional[str] = None,
    strong: bool = False,
    hover: bool = True,
) -> ui.card:
    """Glassmorphism card with optional title and hover effect."""
    glass_class = C.CARD_STRONG if strong else C.CARD
    if hover:
        glass_class += " card-interactive"
    card = ui.card().classes(glass_class)
    with card:
        if title:
            with ui.row().classes("items-center gap-2 mb-2"):
                if icon:
                    ui.icon(icon, size="sm").classes("text-blue-600 dark:text-blue-400")
                ui.label(title).classes(C.CARD_TITLE)
        if subtitle:
            ui.label(subtitle).classes(C.SMALL + " mb-2")
    return card


# ─── Glow Stat Card ──────────────────────────────────────────────────

def glow_stat_card(
    label: str,
    value: Any,
    icon: str = "info",
    trend: Optional[str] = None,
    color: str = PRIMARY,
    glow: bool = True,
    on_click: Optional[Callable] = None,
) -> ui.card:
    """Stat card with glassmorphism and optional glow effect."""
    glow_class = f"glow-{color.split('#')[-1].lower()[:6]}" if glow else ""
    with ui.card().classes(f"{C.CARD} card-interactive cursor-pointer {glow_class}").on(
        "click", on_click or (lambda: None)
    ):
        with ui.row().classes("items-center gap-4 w-full"):
            with ui.element("div").classes(
                "flex items-center justify-center w-12 h-12 rounded-xl"
            ).style(f"background: linear-gradient(135deg, {color}40, {color}20); color: {color};"):
                ui.icon(icon, size="md")
            with ui.column().classes("flex-1"):
                ui.label(str(value)).classes(C.STAT_NUMBER)
                ui.label(label).classes(C.SMALL)
            if trend:
                trend_color = SECONDARY if trend.startswith("+") else DANGER
                ui.label(trend).classes("text-sm font-medium").style(
                    f"color: {trend_color}"
                )


# ─── Gradient Header Card ────────────────────────────────────────────

def gradient_card(
    title: str,
    subtitle: Optional[str] = None,
    gradient: str = "from-blue-600 to-purple-600",
    icon: Optional[str] = None,
) -> ui.card:
    """Card with gradient header background."""
    with ui.card().classes("glass-strong rounded-2xl overflow-hidden w-full") as card:
        with ui.element("div").classes(f"bg-gradient-to-r {gradient} p-6"):
            with ui.row().classes("items-center gap-3"):
                if icon:
                    ui.icon(icon, size="lg").classes("text-white")
                with ui.column().classes("gap-0"):
                    ui.label(title).classes("text-xl font-bold text-white")
                    if subtitle:
                        ui.label(subtitle).classes("text-sm text-white/80")
    return card


# ─── Status Badge (Glass) ────────────────────────────────────────────

# Status-Komponente (einzige Bauart fuer alle Rollen, P0 28.09.2026)
# STATUS_LABELS: DB-Slug → Klartext (UI-Regel "Klartext statt IDs/Slugs")
STATUS_LABELS = {
    "eingegangen": "Eingegangen",
    "angesehen": "Angesehen",
    "eingeladen": "Eingeladen",
    "eingestellt": "Eingestellt",
    "abgelehnt": "Abgelehnt",
    "zurückgezogen": "Zurückgezogen",
    "registriert": "Registriert",
    "lebenslauf_hochgeladen": "Lebenslauf hochgeladen",
    "zugeordnet": "Zugeordnet",
    "aktiv": "Aktiv",
    "done": "Erledigt",
    "failed": "Fehlgeschlagen",
    "running": "Läuft",
    "queued": "In Warteschlange",
    "pending": "Offen",
    "active": "Aktiv",
    "paused": "Pausiert",
    "besetzt": "Besetzt",
    "abgelaufen": "Abgelaufen",
    "profil_vollstaendig": "Profil vollständig",
    "profil_geprueft": "Profil geprüft",
    "match_berechnet": "Match berechnet",
    "pausiert": "Pausiert",
}


# Status-Icons (R5-1, 30.09.2026): EINE Definition auf Modulebene statt
# verlorengegangener Lokalkopien in candidate.py (Beweis NameError:
# tests/test_tabs_render.py, rote Ausgabe in entscheidungen.md Runde 5).
# "eingeladen": "📅" und "eingestellt": "✅" aus der letzten Lokalkopie
# (candidate.py.bak-20260930-0936:652) — Design-Entscheidung, keine externe Quelle.
STATUS_ICONS = {
    "eingegangen": "📨", "angesehen": "👁️", "eingeladen": "📅",
    "abgelehnt": "❌", "eingestellt": "✅", "zurückgezogen": "↩️",
}


def status_label(status: str) -> str:
    """DB-Slug → Klartext (fallback: underscores ersetzt, capitalized).

    i18n P9.3 (06.10.2026): Der Slug bleibt Schluessel, der zurueckgegebene
    Klartext laeuft durch `_()` (Anzeige-Layer). Der Fallback (Slug kaputt
    geschrieben) ist kein Katalog-Key und wird unveraendert durchgereicht.
    """
    if not status:
        return _("Unbekannt")
    return _(STATUS_LABELS.get(status, str(status).replace("_", " ").capitalize()))


def status_badge(status: str, pulse: bool = False) -> ui.badge:
    """A status badge with glassmorphism and color coding."""
    badge_map = {
        "done": C.BADGE_GREEN,
        "eingestellt": C.BADGE_GREEN,
        "aktiv": C.BADGE_GREEN,
        "active": C.BADGE_BLUE,
        "eingeladen": C.BADGE_BLUE,
        "pending": C.BADGE_AMBER,
        "angesehen": C.BADGE_AMBER,
        "eingegangen": C.BADGE_AMBER,
        "registriert": C.BADGE_AMBER,
        "lebenslauf_hochgeladen": C.BADGE_BLUE,
        "zugeordnet": C.BADGE_AMBER,
        "failed": C.BADGE_RED,
        "abgelehnt": C.BADGE_RED,
        "zurückgezogen": C.BADGE_RED,
        "running": C.BADGE_BLUE,
        "queued": C.BADGE_GRAY,
        "paused": C.BADGE_AMBER,
        "besetzt": C.BADGE_GREEN,
        "abgelaufen": C.BADGE_GRAY,
        "profil_vollstaendig": C.BADGE_BLUE,
        "profil_geprueft": C.BADGE_BLUE,
        "match_berechnet": C.BADGE_BLUE,
        "pausiert": C.BADGE_AMBER,  # R5-3 (30.09.2026): deutscher Job-Status
        # aus den Select-Optionen (employer.py:594, admin.py:678), bernstein
        # wie 'paused' — Design-Entscheidung für die Farbwahl
    }
    css_class = badge_map.get(status, C.BADGE_GRAY)
    if pulse and status in ("active", "running", "eingeladen"):
        css_class += " badge-pulse"
    # color=None ist Pflicht: sonst setzt Quasar bg-primary und überschreibt
    # die Theme-Hintergrundfarbe (Vorher-Messung: 2.51:1 statt 7:1)
    return ui.badge(status_label(status), color=None).classes(css_class + " status-badge")


# ─── Score Bar ───────────────────────────────────────────────────────

def score_bar(
    score: int,
    max_score: int = 100,
    color: Optional[str] = None,
    show_label: bool = True,
) -> None:
    """Animated horizontal score bar with fade-in animation."""
    if color is None:
        color = score_color(score)
    percentage = min(score / max_score * 100, 100) if max_score > 0 else 0

    with ui.row().classes("items-center gap-3 w-full"):
        # Use ui.linear_progress for proper animation support
        bar = ui.linear_progress(value=0, show_value=False, color=color).classes(
            "flex-1 h-3 bg-gray-200 dark:bg-gray-700 rounded-full score-bar-animated"
        )
        # NiceGUI 3.17.1: ui.animate existiert nicht; die CSS-Keyframe-
        # Animation 'score-fill' (theme.py:429-432) rendert den 0.8s-Effekt
        # bereits — Python-Zeile war ungültig UND redundant.
        bar.value = percentage / 100  # ui.linear_progress uses 0-1 range
        
        if show_label:
            ui.label(_('{0}/{1}').format(score, max_score)).classes("text-sm font-medium w-16 text-right")


# ─── Agent Task Badge ────────────────────────────────────────────────

TASK_ICONS = {
    "extract_profile": "badge",
    "match_candidate": "compare_arrows",
    "check_compliance": "verified",
    "assess_culture_fit": "psychology",
    "check_gdpr": "security",
    "check_visa": "flight",
    "verify_documents": "description",
    "notify_user": "notifications",
    "notify_hr": "mail",
    "create_invitation": "event",
    "export_report": "file_download",
}


def agent_badge(task_type: str, status: str) -> None:
    """Compact agent task status badge."""
    icon = TASK_ICONS.get(task_type, "smart_toy")
    status_class = STATUS_BADGE_CLASSES.get(status, C.BADGE_GRAY)
    status_icon = {
        "done": "check_circle",
        "running": "schedule",
        "failed": "error",
        "queued": "hourglass_empty",
    }.get(status, "help")

    with ui.row().classes("items-center gap-1.5"):
        ui.icon(icon, size="sm").classes("text-gray-500")
        ui.badge(task_type.replace("_", " ")).classes(status_class)
        ui.icon(status_icon, size="xs").classes(
            f"text-{status_class.split()[-1].replace('text-', '')}" if "text-" in status_class else "text-gray-400"
        )


# ─── Score Card (for match results) ─────────────────────────────────

def score_card(
    category: str,
    score: int,
    max_score: int,
    weight: Optional[int] = None,
    explanation: Optional[str] = None,
) -> None:
    """Score category card with bar, label, and optional explanation."""
    with ui.card().classes(C.CARD + " py-3"):
        with ui.row().classes("items-center justify-between w-full mb-2"):
            ui.label(category).classes("font-medium text-gray-900 dark:text-white")
            with ui.row().classes("items-center gap-2"):
                if weight is not None:
                    ui.label(_('Gewicht: {0}%').format(weight)).classes(C.MUTED)
                badge_class = score_badge_class(score)
                ui.badge(score_label(score)).classes(badge_class)
        score_bar("", score, max_score, show_label=False)
        if explanation:
            ui.label(explanation).classes(C.MUTED + " mt-1 italic")


# ─── Timeline ────────────────────────────────────────────────────────

def timeline(items: list[dict]) -> None:
    """Vertical timeline for onboarding/process flows."""
    with ui.column().classes("w-full gap-0"):
        for i, item in enumerate(items):
            status = item.get("status", "pending")
            color = {
                "done": SECONDARY,
                "active": PRIMARY,
                "pending": "#94A3B8",
            }.get(status, "#94A3B8")
            is_last = i == len(items) - 1

            with ui.row().classes("gap-4"):
                with ui.column().classes("items-center"):
                    ui.element("div").classes("w-3 h-3 rounded-full").style(
                        f"background-color: {color};"
                    )
                    if not is_last:
                        ui.element("div").classes("w-0.5 h-8 bg-gray-300 dark:bg-gray-600")
                with ui.column().classes("flex-1 pb-4"):
                    ui.label(item.get("title", "")).classes(
                        "font-medium text-gray-900 dark:text-white"
                    )
                    if item.get("date"):
                        ui.label(item["date"]).classes(C.MUTED)
                    if item.get("description"):
                        ui.label(item["description"]).classes(C.SMALL)


# ─── Upload Zone ─────────────────────────────────────────────────────

def upload_zone(
    label: Optional[str] = None,
    icon: str = "cloud_upload",
    accepted: str = ".pdf,.txt",
    on_upload: Optional[Callable] = None,
) -> ui.upload:
    """Drag & drop upload zone."""
    with ui.card().classes(C.UPLOAD_ZONE):
        ui.icon(icon, size="xl").classes("text-gray-400 mb-2")
        ui.label(label if label is not None else _("Datei hier ablegen oder klicken")).classes(C.BODY)
        ui.label(_('Akzeptiert: {0}').format(accepted)).classes(C.MUTED)
    upload = ui.upload(
        on_upload=on_upload,
        auto_upload=True,
        max_file_size=5_000_000,
    ).classes("hidden")
    return upload


# ─── Empty State ─────────────────────────────────────────────────────

def empty_state(
    icon: str = "inbox",
    title: Optional[str] = None,
    description: str = "",
    action_label: Optional[str] = None,
    on_action: Optional[Callable] = None,
) -> None:
    """Empty state placeholder with glass styling."""
    with ui.column().classes("items-center py-12 gap-4"):
        with ui.element("div").classes(
            "flex items-center justify-center w-20 h-20 rounded-full"
        ).classes("bg-gray-100/50 dark:bg-gray-800/50"):
            ui.icon(icon, size="xl").classes("text-gray-400 dark:text-gray-500")
        ui.label(title if title is not None else _("Keine Daten vorhanden")).classes(C.CARD_TITLE)
        if description:
            ui.label(description).classes(C.SMALL + " text-center max-w-md")
        if action_label and on_action:
            ui.button(action_label, on_click=on_action).classes(C.BTN_PRIMARY)


# ─── Section Header ──────────────────────────────────────────────────

def section_header(
    title: str,
    subtitle: Optional[str] = None,
    icon: Optional[str] = None,
    actions: Optional[list[dict]] = None,
) -> None:
    """Section header with glass styling."""
    with ui.row().classes("items-center justify-between w-full mb-4"):
        with ui.row().classes("items-center gap-3"):
            if icon:
                with ui.element("div").classes(
                    "flex items-center justify-center w-10 h-10 rounded-xl"
                ).classes("bg-gradient-to-br from-blue-500/20 to-purple-500/20"):
                    ui.icon(icon, size="sm").classes("text-blue-600 dark:text-blue-400")
            with ui.column().classes("gap-0"):
                ui.label(title).classes(C.SECTION_TITLE)
                if subtitle:
                    ui.label(subtitle).classes(C.SMALL)
        if actions:
            with ui.row().classes("gap-2"):
                for action in actions:
                    ui.button(
                        action.get("label", ""),
                        icon=action.get("icon"),
                        on_click=action.get("on_click", lambda: None),
                    ).classes(action.get("class", C.BTN_PRIMARY))


# ─── Breadcrumb Navigation ──────────────────────────────────────────

def breadcrumb(items: list[dict]) -> None:
    """Breadcrumb navigation.

    Each item: {"label": str, "url": str (optional)}
    Last item is rendered as plain text (current page).
    """
    with ui.row().classes("items-center gap-2 text-sm mb-4"):
        for i, item in enumerate(items):
            if i > 0:
                ui.icon("chevron_right", size="xs").classes("text-gray-400")
            if item.get("url") and i < len(items) - 1:
                ui.link(item["label"], item["url"]).classes("text-blue-600 hover:underline")
            else:
                ui.label(item["label"]).classes("text-gray-500" if i < len(items) - 1 else "font-medium text-gray-900 dark:text-white")


# ─── Skeleton Loader ────────────────────────────────────────────────

def skeleton_loader(count: int = 3, height: str = "h-20") -> ui.column:
    """Skeleton loader for tables and cards while data is loading."""
    container = ui.column().classes("w-full gap-3")
    with container:
        for _i in range(count):
            with ui.card().classes("w-full p-0"):
                ui.skeleton(type="rect", animation="wave").classes(f"w-full {height}")
    return container


# ─── Data Table ──────────────────────────────────────────────────────

def data_table(
    columns: list[dict],
    rows: list[dict],
    title: Optional[str] = None,
    pagination: int = 10,
    on_row_click: Optional[Callable] = None,
    searchable: bool = True,
) -> None:
    """Sortable, filterable data table with optional pagination."""
    if title:
        ui.label(title).classes(C.CARD_TITLE + " mb-3")

    if searchable:
        # NiceGUI 3.17.1: ui.input kennt kein icon=Kwarg (brach data_table →
        # 500 auf jeder Seite mit Daten-Tabelle); Quasar-Prop prepend-icon
        search = ui.input(placeholder=_('Suchen...')).props('prepend_icon="search"').classes("w-full mb-3")

    table = ui.table(
        columns=columns,
        rows=rows,
        pagination=pagination,
        # M-07 (01.10.2026): Ohne `selection` setzt NiceGUI den Prop auf 'none'
        # (nicegui/elements/table.py: `selection or 'none'`) — dann feuert Quasars
        # 'selection'-Event nie und `on_select` bleibt wirkungslos. Gemessen an der
        # Feedback-Tabelle: 10 Zeilen ohne Klickziel. Mit on_row_click daher 'single'.
        selection="single" if on_row_click else None,
        on_select=on_row_click,
    ).classes("w-full")
    # M-07 (01.10.2026): Rueckgabe, damit Aufrufer den Zeilen-Klick-Slot
    # (body-cell-name) ergaenzen koennen — die Zeile bleibt so sichtbar klickbar.
    result = table

    if searchable:
        def _filter():
            q = search.value.lower()
            table.rows = [r for r in rows if any(q in str(v).lower() for v in r.values())]
        search.on_value_change(lambda: _filter())

    return result


# ─── Confirm Dialog ──────────────────────────────────────────────────

def confirm_dialog(
    title: str,
    message: str,
    on_confirm: Callable,
    confirm_label: Optional[str] = None,
    cancel_label: Optional[str] = None,
) -> None:
    """Confirmation dialog."""
    confirm_label = confirm_label if confirm_label is not None else _("Bestätigen")
    cancel_label = cancel_label if cancel_label is not None else _("Abbrechen")
    with ui.dialog() as dialog, ui.card().classes("w-96"):
        ui.label(title).classes(C.CARD_TITLE)
        ui.label(message).classes(C.BODY + " mt-2")
        with ui.row().classes("justify-end gap-2 mt-4"):
            ui.button(cancel_label, on_click=dialog.close).classes(C.BTN_SECONDARY)
            ui.button(
                confirm_label,
                on_click=lambda: (on_confirm(), dialog.close()),
            ).classes(C.BTN_PRIMARY)
    dialog.open()


# ─── Info Row (for detail views) ────────────────────────────────────

def info_row(label: str, value: Any, icon: Optional[str] = None) -> None:
    """Label-value pair row for detail views."""
    with ui.row().classes("items-center gap-2 py-1"):
        if icon:
            ui.icon(icon, size="sm").classes("text-gray-400")
        ui.label(_('{0}:').format(label)).classes(C.SMALL + " font-medium")
        ui.label(str(value)).classes(C.BODY)


# ─── C7 (22.09.2026): Skill 6/7/8 Sections ─────────────────────────
# Shared Sections fuer Admin + Employer. Status-Gate entfaellt (D28):
# Streamlit-Gate war sidebar-gekoppelt und hatte Indent-Bugs
# (Buttons app.py:2263/2418/2566 rendern ausserhalb des Gates).

def _md_result_card(container, title: str, filename: str, md: str) -> None:
    """Inline-Ergebnis nach Speichern: Karte + Vorschau + Download
    (Paritaet: st.success + st.markdown + st.download_button)."""
    container.clear()
    with container:
        with ui.card().classes(C.CARD + " w-full mt-4"):
            ui.label(title).classes(C.CARD_TITLE)
            ui.label(filename).classes(C.SMALL)
            with ui.expansion(text=_('Vorschau')).classes("w-full"):
                ui.markdown(md)
            ui.button(
                _('Herunterladen'), icon="download",
                # Default-Args binden Closure-Wert (Late-Binding-Trap P2)
                on_click=lambda _c=md, _n=filename: ui.download(
                    _c.encode("utf-8"), _n, "text/markdown"
                ),
            ).classes(C.BTN_PRIMARY + " mt-2")


def prescreen_recruiting_section() -> None:
    """Skill 6 Recruiting-Modus (Employer/Admin). Paritaet: app.py:2238-2361.

    #8 Einsicht: self-presentation-kandidat-*.md — "Ansehen" oeffnet Dialog
    (_show_file, seit 30.09.2026) statt Download; kein Download-Angebot.
    #9 Generator: Profil-Select (testdaten-Profile, D29) + Stelle + Score,
    fragen-Heuristik app.py:2286-2316, MD app.py:2319-2353.
    """
    from webui import logic

    ui.label(_('Modus: 🔍 Recruiting – Screening für ausgewählten Kandidaten.')).classes(C.BODY + " mb-4")

    # ── #8 Einsicht: Selbstpräsentationen der Kandidaten ──
    self_pres = sorted(logic.ERGEBNISSE.glob("self-presentation-kandidat-*.md"))
    with ui.card().classes(C.CARD + " w-full mb-4"):
        ui.label(_('Selbstpräsentationen der Kandidaten ({0})').format(len(self_pres))).classes(C.CARD_TITLE)
        if not self_pres:
            # P1-3 (29.09.2026): Wegweiser statt toter Endpunkt — HR kann hier
            # nichts auslösen; Selbstpräsentationen entstehen im Kandidaten-
            # Sprachtest-Tab (Spec: skills/pre-screen/SKILL.md, P1-3-Regel)
            ui.label(
                _('Keine Selbstpräsentationen vorhanden. Kandidaten können ihre Video-Vorstellung im eigenen Portal (Tab 🗣️ Sprachtest) generieren.')
            ).classes(C.MUTED)
        else:
            for sp in self_pres:
                content = sp.read_text(encoding="utf-8", errors="replace")
                with ui.row().classes("items-center gap-3 w-full mb-1"):
                    ui.label(sp.name).classes(C.SMALL + " flex-1")

                    def _show_file(_c=content, _n=sp.name):
                        with ui.dialog() as _dlg, ui.card().classes("w-[640px]"):
                            ui.label(_n).classes(C.CARD_TITLE)
                            ui.markdown(_c).classes(C.BODY + " mt-2")
                            ui.button(_('Schließen'), on_click=_dlg.close).classes(C.BTN_PRIMARY + " mt-2")
                        _dlg.open()

                    ui.button(
                        _('Ansehen'), icon="visibility",
                        on_click=lambda _c=content, _n=sp.name: _show_file(_c, _n),
                    ).props("flat dense")

    # ── #9 Generator ──
    # P1-3 (29.09.2026): kein hartes `return` mehr — der Rest der Section
    # (Karte „Pre-Screen erstellen") wird sonst komplett abgewürgt; Profile
    # entstehen via Admin-Upload → extract_profile (Spec P1-3-Regel)
    profiles = logic.list_profiles()
    if not profiles:
        ui.label(
            _('Keine Profile gefunden. Profile entstehen automatisch, wenn Lebensläufe hochgeladen und extrahiert werden (Admin: Upload → Extract).')
        ).classes(C.BODY + " text-amber-600")

    with ui.card().classes(C.CARD + " w-full"):
        ui.label(_('Pre-Screen erstellen')).classes(C.CARD_TITLE + " mb-4")
        # P0 (28.09.2026): Klartext-Name statt Dateiname (vorher 'profil---**name:**-...md')
        sel = ui.select(
            options={str(p): logic.profile_display_name(p) for p in profiles},
            label=_('Kandidat:'),
            value=str(profiles[0]),
        ).classes("w-full")
        with ui.row().classes("w-full gap-4"):
            # R5-4/S3g (30.09.2026): KEINE hartcodierte Vorgabe mehr — die
            # Stelle wird aus der aktuellen Bewerbung des gewählten
            # Kandidaten vorbelegt (sonst leer, Pflichtprüfung unten).
            stelle = ui.input(
                label=_('Stelle:'),
                value=logic.aktuelle_stelle_fuer_profil(profiles[0]),
            ).classes("flex-1")
            score = ui.number(label=_('Match-Score:'), value=85, min=0, max=100).classes("w-40")

        def _stelle_bei_kandidatwechsel():
            stelle.value = logic.aktuelle_stelle_fuer_profil(sel.value)

        sel.on_value_change(lambda _e: _stelle_bei_kandidatwechsel())

        result_box = ui.column().classes("w-full")

        def create_prescreen() -> None:
            if not sel.value:
                return
            profil_path = Path(sel.value)
            profil_text = logic.read_profile_text(str(profil_path))
            profil_lower = profil_text.lower()

            import random, string
            room_code = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
            # VDO.Ninja statt Jitsi (27.09.2026, Spec: knowledge/system/vdo-ninja-migration.md);
            # keine Aufnahmeparameter – Aufzeichnung nur nach bestätigter Einwilligung.
            # Raumname alphanumerisch ohne Bindestrich seit 04.10.2026 (§2.5, Quelle:
            # docs.vdo.ninja/…/setup-parameters/room: „aLphaNumEric-characters").
            meet_url = f"https://vdo.ninja/?director=prescreening{room_code}"

            name = profil_path.stem.replace("profil-", "").replace("-", " ").title()

            # Fragen-Heuristik 1:1 app.py:2286-2316
            fragen: list[tuple[str, str]] = []
            fragen.append(("Technisch", _("Welche Cloud-Plattformen haben Sie eingesetzt?")))
            if "aws" in profil_lower:
                fragen.append(("Technisch", _("Beschreiben Sie eine AWS-Migration, die Sie geleitet haben.")))
            if "kubernetes" in profil_lower:
                fragen.append(("Technisch", _("Wie gehen Sie vor bei einem Kubernetes-Cluster-Ausfall?")))
            fragen.append(("Technisch", _("Wie implementieren Sie CI/CD-Pipelines?")))
            if "terraform" not in profil_lower:
                fragen.append(("Lücke", _("Haben Sie Erfahrung mit Infrastructure-as-Code (z.B. Terraform)?")))
            fragen.append(("Motivation", _("Was reizt Sie an dieser Position?")))
            fragen.append(("Motivation", _("Wo sehen Sie sich in 3–5 Jahren?")))
            fragen.append(("Motivation", _("Was ist Ihr bevorzugter Arbeitsstil (Remote/Hybrid/Onsite)?")))
            fragen.append(("Praktisch", _("Wann könnten Sie starten?")))
            fragen.append(("Praktisch", _("Ihre Gehaltsvorstellung?")))
            if "teamführung" in profil_lower or "mentoring" in profil_lower:
                fragen.append(("Kultur", _("Beschreiben Sie Ihren Führungsstil.")))
            if "deutsch" not in profil_lower or "muttersprache" not in profil_lower:
                fragen.append(("Sprache", _("Wie ist Ihr Deutsch-Level (B1/B2/C1)?")))

            stelle_val = (stelle.value or "").strip()
            if not stelle_val:
                # R5-4/S3g: Pflichtprüfung statt erfundener Vorgabe
                ui.notify(_('Bitte eine Stelle angeben (keine Vorbelegung gefunden).'), type="warning")
                return
            score_val = int(score.value or 85)

            # MD-Bau 1:1 app.py:2319-2353 (i18n P9.4: MD in Erzeugungs-Sprache)
            md = _("# Pre-Screening: {0}").format(name) + "\n\n"
            md += _("**Stelle:** {0}").format(stelle_val) + "\n"
            md += _("**Match-Score:** {0}/100").format(score_val) + "\n"
            md += _("**Datum:** {0}").format(datetime.now().strftime('%d.%m.%Y')) + "\n\n"
            md += "---\n\n"
            md += _("## 📹 Meeting-Details") + "\n\n"
            md += _("- **Link:** [{0}]({1})").format(meet_url, meet_url) + "\n"
            md += _("- **Datum:** {0}").format((datetime.now() + timedelta(days=7)).strftime('%A, %d. %B %Y')) + "\n"
            md += _("- **Uhrzeit:** 10:00–10:45 Uhr") + "\n"
            md += _("- **Dauer:** 45 Minuten") + "\n\n"
            md += "---\n\n"
            md += _("## 📋 Screening-Fragen") + "\n\n"

            fragen_count: dict[str, int] = {}
            for kategorie, _frage in fragen:
                fragen_count[kategorie] = fragen_count.get(kategorie, 0) + 1

            idx = 1
            aktuelle_kategorie = ""
            for kategorie, frage in fragen:
                if kategorie != aktuelle_kategorie:
                    md += f"\n### {_(kategorie)}\n\n"
                    aktuelle_kategorie = kategorie
                md += f"{idx}. {frage}\n"
                idx += 1

            md += "\n---\n\n"
            md += _("## 📊 Zusammenfassung") + "\n\n"
            md += _("- **Fragen gesamt:** {0}").format(len(fragen)) + "\n"
            md += _("- **Technische Fragen:** {0}").format(fragen_count.get('Technisch', 0)) + "\n"
            md += _("- **Lücken-Fragen:** {0}").format(fragen_count.get('Lücke', 0)) + "\n"
            md += _("- **Motivations-Fragen:** {0}").format(fragen_count.get('Motivation', 0)) + "\n"
            md += _("- **Sprach-Check:** {0}").format(_("Ja") if "Sprache" in fragen_count else _("Nein")) + "\n\n"
            md += "---\n\n"
            md += _("*Erstellt am {0} vom KM-HR-Agenten.*").format(datetime.now().strftime('%d.%m.%Y %H:%M')) + "\n"

            kandidat_name = profil_path.stem.replace("profil-", "")
            filename = f"pre-screen-{kandidat_name}-{datetime.now().strftime('%Y-%m-%d')}.md"
            logic.save_result(filename, md)
            _md_result_card(result_box, _("Pre-Screen gespeichert"), filename, md)

        ui.button(_('Pre-Screen erstellen'), icon="videocam", on_click=create_prescreen).classes(C.BTN_PRIMARY + " mt-4")


def onboarding_generator_section(default_stelle: str = "") -> None:
    """Skill 7 Generator (Employer/Admin). Paritaet: app.py:2396-2515.

    D29: profile aus testdaten (list_profiles), Dateiname
    onboarding-{stem}-{startdatum}.md.
    """
    from webui import logic

    ui.label(_('Modus: 🧰 HR – Checkliste erstellen und freigeben.')).classes(C.BODY + " mb-4")

    profiles = logic.list_profiles()
    if not profiles:
        ui.label(_('Keine Profile gefunden.')).classes(C.BODY + " text-amber-600")
        return

    with ui.card().classes(C.CARD + " w-full"):
        ui.label(_('Onboarding-Checkliste generieren')).classes(C.CARD_TITLE + " mb-4")
        # P0 (28.09.2026): Klartext-Name statt Dateiname (vorher 'profil---**name:**-...md')
        sel = ui.select(
            options={str(p): logic.profile_display_name(p) for p in profiles},
            label=_('Kandidat:'),
            value=str(profiles[0]),
        ).classes("w-full")
        with ui.row().classes("w-full gap-4"):
            stelle = ui.input(
                label=_('Stelle:'),
                value=default_stelle or logic.aktuelle_stelle_fuer_profil(profiles[0]),
            ).classes("flex-1")
            # NiceGUI 3.17.1: ui.date_input existiert (C1-Verifikation)
            startdatum = ui.date_input(
                _('Startdatum:'),
                value=str((datetime.now() + timedelta(days=30)).date()),
            ).classes("w-48")

        result_box = ui.column().classes("w-full")

        def create_onboarding() -> None:
            if not sel.value:
                return
            profil_path = Path(sel.value)
            profil_text = logic.read_profile_text(str(profil_path))
            profil_lower = profil_text.lower()
            name = profil_path.stem.replace("profil-", "").replace("-", " ").title()
            stelle_val = (stelle.value or "").strip()
            if not stelle_val:
                # R5-4/S3g: Pflichtprüfung statt erfundener Vorgabe
                ui.notify(_('Bitte eine Stelle angeben (keine Vorbelegung gefunden).'), type="warning")
                return

            # date_input kann str oder date liefern — tolerant parsen
            sd_raw = startdatum.value
            try:
                if isinstance(sd_raw, str):
                    sd = datetime.strptime(sd_raw[:10], "%Y-%m-%d")
                else:
                    sd = datetime.combine(sd_raw, datetime.min.time())
            except (ValueError, TypeError):
                sd = datetime.now() + timedelta(days=30)

            # MD-Bau 1:1 app.py:2426-2507 (i18n P9.4: MD in Erzeugungs-Sprache)
            md = _("# Onboarding-Checkliste: {0}").format(name) + "\n\n"
            md += _("**Stelle:** {0}").format(stelle_val) + "\n"
            md += _("**Startdatum:** {0}").format(sd.strftime('%d.%m.%Y')) + "\n"
            md += _("**Erstellt:** {0}").format(datetime.now().strftime('%d.%m.%Y')) + "\n\n"
            md += "---\n\n"

            # 1. Willkommens-E-Mail
            md += _("## 1. Willkommens-E-Mail") + "\n\n"
            md += _("**Empfänger:** {0}").format(name) + "\n"
            md += _("**Betreff:** Willkommen bei TechVision GmbH!") + "\n\n"
            md += _("Sehr geehrte(r) {0},").format(name) + "\n\n"
            md += _("wir freuen uns sehr, Sie ab dem **{0}** ").format(sd.strftime('%d.%m.%Y'))
            md += _("als **{0}** in unserem Team begrüßen zu dürfen.").format(stelle_val) + "\n\n"
            # Mentoring (Phase D P10, Spec §5): {MENTOR}-Materialisierung –
            # nur bei aktivem Mentor, sonst Zeile auslassen (SKILL-Regel 6)
            from webui import db as _db
            _mentor = None
            try:
                _conn = _db.get_conn()
                _mrow = _conn.execute(
                    "SELECT m.mentor_name FROM mentoring m "
                    "JOIN candidates c ON c.id = m.candidate_id "
                    "WHERE m.status = 'aktiv' AND lower(c.name) = lower(?) "
                    "ORDER BY m.changed_at DESC LIMIT 1",
                    (name,),
                ).fetchone()
                _conn.close()
                _mentor = _mrow[0] if _mrow else None
            except Exception:
                _mentor = None
            if _mentor:
                md += _("Dein Ansprechpartner: {0}").format(_mentor) + "\n\n"
            md += _("Mit freundlichen Grüßen,\nHR Team") + "\n\n"
            md += "---\n\n"

            # 2. IT-Ausstattung
            md += _("## 2. IT-Ausstattung") + "\n\n"
            md += _("| Gerät | Status | Zuständig |") + "\n"
            md += "|---|---|---|\n"
            md += _("| MacBook Pro / ThinkPad | ☐ Bestellt | IT-Abteilung |") + "\n"
            md += _("| Monitor (27 Zoll) | ☐ Bestellt | IT-Abteilung |") + "\n"
            md += _("| Tastatur + Maus | ☐ Bestellt | IT-Abteilung |") + "\n"
            md += _("| Headset | ☐ Bestellt | IT-Abteilung |") + "\n"
            md += _("| Laptop-Tasche | ☐ Bestellt | IT-Abteilung |") + "\n"
            if "linux" in profil_lower or "ubuntu" in profil_lower:
                md += _("| Linux-Workstation | ☐ Bestellt | IT-Abteilung |") + "\n"
            md += "\n"

            # 3. Systemzugänge
            md += _("## 3. Systemzugänge") + "\n\n"
            md += _("| System | Zugang | Frist |") + "\n"
            md += "|---|---|---|\n"
            md += _("| E-Mail (Google Workspace) | ☐ Angelegt | Tag 1 |") + "\n"
            md += _("| Slack | ☐ Angelegt | Tag 1 |") + "\n"
            md += _("| GitHub | ☐ Angelegt | Tag 1 |") + "\n"
            md += _("| AWS Console | ☐ Angelegt | Tag 3 |") + "\n"
            md += _("| Kubernetes Cluster | ☐ Angelegt | Tag 5 |") + "\n"
            md += _("| Jira | ☐ Angelegt | Tag 1 |") + "\n"
            md += _("| Confluence | ☐ Angelegt | Tag 1 |") + "\n"
            md += _("| VPN-Zugang | ☐ Angelegt | Tag 1 |") + "\n\n"

            # 4. Erstgespräche
            md += _("## 4. Erstgespräche") + "\n\n"
            md += _("| Termin | Person | Thema | Datum |") + "\n"
            md += "|---|---|---|---|\n"
            md += _("| 1 | Teamleitung | Willkommen + Rahmenbedingungen | Tag 1 |") + "\n"
            md += _("| 2 | HR | Vertragsunterlagen + Benefits | Tag 1 |") + "\n"
            md += _("| 3 | IT-Onboarding | Systemzugänge + Geräte | Tag 1 |") + "\n"
            md += _("| 4 | Scrum Master | Agile Prozesse | Tag 2 |") + "\n"
            md += _("| 5 | DevOps-Team | Technische Architektur | Tag 3 |") + "\n"
            md += _("| 6 | Product Owner | Produktübersicht | Tag 5 |") + "\n"
            md += _("| 7 | CTO | Technische Vision | Woche 2 |") + "\n"
            md += _("| 8 | Kollegen | Team-Lunch | Woche 1 |") + "\n\n"

            # 5. Einarbeitungsplan
            md += _("## 5. Einarbeitungsplan") + "\n\n"
            md += _("| Woche | Thema | Ziel |") + "\n"
            md += "|---|---|---|\n"
            md += _("| 1 | Orientierung | Umgebung kennenlernen, Zugänge testen |") + "\n"
            md += _("| 2 | Code-Basis | Repository durchlesen, erstes Ticket |") + "\n"
            md += _("| 3 | Infrastruktur | AWS Cluster, Monitoring, Deployments |") + "\n"
            md += _("| 4 | erstes Feature | Kleine Änderung, PR, Review |") + "\n"
            md += _("| 5 | Independence | Eigenständiges Ticket, Daily Standup |") + "\n"
            if "kubernetes" in profil_lower:
                md += _("| 6 | K8s-Audit | Cluster-Review, Optimierungsvorschläge |") + "\n"
            md += "\n"

            # 6. Arbeitsvertrag
            md += _("## 6. Arbeitsvertrag") + "\n\n"
            md += _("| Dokument | Status | Frist |") + "\n"
            md += "|---|---|---|\n"
            md += _("| Arbeitsvertrag | ☐ Zugestellt | Vor Start |") + "\n"
            md += _("| IT-Sicherheitsrichtlinie | ☐ Gelesen + unterschrieben | Tag 1 |") + "\n"
            md += _("| NDA | ☐ Unterschrieben | Tag 1 |") + "\n"
            md += _("| DSGVO-Einwilligung | ☐ Unterschrieben | Tag 1 |") + "\n"
            md += _("| Datenschutzrichtlinie | ☐ Gelesen | Tag 1 |") + "\n"
            md += _("| Betriebsvereinbarung | ☐ Gelesen | Woche 1 |") + "\n"
            md += _("| Allowlist (Versicherung) | ☐ Ausgefüllt | Woche 1 |") + "\n\n"

            md += "---\n\n"
            md += _("*Erstellt am {0} vom KM-HR-Agenten.*").format(datetime.now().strftime('%d.%m.%Y %H:%M')) + "\n"

            kandidat_name = profil_path.stem.replace("profil-", "")
            filename = f"onboarding-{kandidat_name}-{sd.strftime('%Y-%m-%d')}.md"
            logic.save_result(filename, md)
            _md_result_card(result_box, _("Onboarding-Checkliste gespeichert"), filename, md)

        ui.button(_('Onboarding generieren'), icon="assignment", on_click=create_onboarding).classes(C.BTN_PRIMARY + " mt-4")


def skill8_feedback_section() -> None:
    """Skill 8 Store Feedback (Admin-Seite + Employer nach Tab4).
    Paritaet: app.py:2522-2692. Cat-Map seit i18n P9.3 (06.10.2026)
    vereinheitlicht mit der Employer-/app.py-Paritaet
    (Weak→'Schwach' statt 'Nicht passend'; Design-Entscheidung im Log).
    D28: Status-Gate entfaellt.
    """
    from webui import db, logic

    profiles = logic.list_profiles()
    if not profiles:
        ui.label(_('Keine Profile gefunden.')).classes(C.BODY + " text-amber-600")
        return

    with ui.card().classes(C.CARD + " w-full mt-4"):
        ui.label(_('Skill 8: Feedback speichern')).classes(C.CARD_TITLE + " mb-4")
        ui.label(_('Speichert Feedback in SQLite und passt Matching-Gewichtung dynamisch an.')).classes(C.MUTED)

        with ui.row().classes("w-full gap-4"):
            # P0 (28.09.2026): Klartext-Name statt Dateiname
            sel = ui.select(
                options={str(p): logic.profile_display_name(p) for p in profiles},
                label=_('Kandidat:'),
                value=str(profiles[0]),
            ).classes("flex-1")
            score = ui.number(label=_('Match-Score (0-100)'), value=85, min=0, max=100).classes("w-44")
        stellenprofil = ui.input(label=_('Stellenprofil:'), value="").classes("w-full")
        eingeladen = ui.select(options={v: _(v) for v in ["Ja", "Nein"]}, value="Ja", label=_('Eingeladen?')).classes("w-full")

        # NiceGUI: ui.slider hat kein label → ui.label + ui.slider (Tab4-Muster)
        ui.label(_('Bewertung (0–5):')).classes(C.SMALL + " font-medium mt-2")
        with ui.grid(columns=4).classes("w-full gap-4"):
            ui.label(_('Fachlich korrekt')).classes(C.MUTED)
            fachlich = ui.slider(min=0, max=5, value=4, step=1).classes("w-full")
            ui.label(_('Skills richtig')).classes(C.MUTED)
            skills = ui.slider(min=0, max=5, value=4, step=1).classes("w-full")
            ui.label(_('Standort zutreffend')).classes(C.MUTED)
            standort = ui.slider(min=0, max=5, value=4, step=1).classes("w-full")
            ui.label(_('Empfehlung hilfreich')).classes(C.MUTED)
            empfehlung = ui.slider(min=0, max=5, value=4, step=1).classes("w-full")

        anmerkungen = ui.textarea(label=_('Anmerkungen:')).classes("w-full")
        result_box = ui.column().classes("w-full")

        def save_feedback() -> None:
            if not sel.value:
                return
            profil_path = Path(sel.value)
            name = profil_path.stem.replace("profil-", "").replace("-", " ").title()
            score_val = int(score.value or 85)
            stell = stellenprofil.value or "Unbekannt"
            eing = eingeladen.value or "Ja"
            fach = int(fachlich.value or 4)
            sk = int(skills.value or 4)
            st = int(standort.value or 4)
            emp = int(empfehlung.value or 4)
            anm = anmerkungen.value or ""

            # Kategorie: P9.3 (06.10.2026) vereinheitlicht mit der Employer-/
            # app.py-Paritaet (Strong→Hervorragend, Consider→Bedingt,
            # Weak→Schwach, ≥75→Gut) — vorher Weak→'Nicht passend' (widerspruechlich).
            # Design-Entscheidung, im Entscheidungslog 06.10.2026 belegt.
            _cat_map = {"Strong": "Hervorragend", "Consider": "Bedingt",
                        "Weak": "Schwach"}
            kategorie = _cat_map.get(logic.get_score_category_lokal(score_val), "Schwach")
            if kategorie == "Bedingt" and score_val >= 75:
                kategorie = "Gut"

            match_id = f"{profil_path.stem}-{datetime.now().strftime('%Y-%m-%d')}"

            conn = db.get_conn()
            # Unique-Index sicherstellen (Paritaet app.py:2560)
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_match_id ON feedback(match_id)")
            conn.commit()

            # Idempotent: gleicher Tag = UPDATE, neuer Tag = INSERT (app.py:2619-2638)
            existing = conn.execute(
                "SELECT id FROM feedback WHERE match_id = ?", (match_id,)
            ).fetchone()
            if existing:
                conn.execute("""UPDATE feedback SET kandidat_name=?, stellenprofil=?, score=?, kategorie=?,
                    fachlich_korrekt=?, skills_richtig=?, standort_zutreffend=?,
                    empfehlung_hilfreich=?, eingeladen=?, anmerkungen=?
                    WHERE match_id=?""",
                    (name, stell, score_val, kategorie,
                     fach, sk, st, emp, eing, anm, match_id))
            else:
                conn.execute("""INSERT INTO feedback
                    (match_id, kandidat_name, stellenprofil, score, kategorie,
                     fachlich_korrekt, skills_richtig, standort_zutreffend,
                     empfehlung_hilfreich, eingeladen, anmerkungen)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (match_id, name, stell, score_val, kategorie,
                     fach, sk, st, emp, eing, anm))
            conn.commit()

            # Phase 4: nur bei NEUEM Feedback (INSERT) (app.py:2640-2647)
            if existing:
                gewichtung_msg = _("ℹ️ Korrektur (heute bereits vorhanden) – keine neue Gewichtungsanpassung.")
            else:
                gewichtung_msg = logic.adjust_weights_from_feedback(
                    eing, score_val,
                    f"{'Erfolgreicher' if eing == 'Ja' else 'Gescheiterter'} Match {name}: Score {score_val}/100",
                    conn,
                )

            # MD-Bau 1:1 app.py:2650-2678 (i18n P9.4: MD in Erzeugungs-Sprache)
            md = _("# Feedback: {0}").format(name) + "\n\n"
            md += _("**Match-ID:** `{0}`").format(match_id) + "\n"
            md += _("**Score:** {0}/100 ({1})").format(score_val, _(kategorie)) + "\n"
            md += _("**Eingeladen:** {0}").format(_(eing)) + "\n"
            md += _("**Datum:** {0}").format(datetime.now().strftime('%d.%m.%Y %H:%M')) + "\n\n"
            md += "---\n\n"
            md += _("## Bewertung") + "\n\n"
            md += _("| Kriterium | Punkte |") + "\n"
            md += "|---|---|\n"
            md += _("| Fachlich korrekt | {0}/5 |").format(fach) + "\n"
            md += _("| Skills richtig | {0}/5 |").format(sk) + "\n"
            md += _("| Standort zutreffend | {0}/5 |").format(st) + "\n"
            md += _("| Empfehlung hilfreich | {0}/5 |").format(emp) + "\n"
            md += _("| **Durchschnitt** | **{0}/5** |").format(f"{(fach + sk + st + emp) / 4:.1f}") + "\n\n"
            if anm:
                md += _("**Anmerkungen:** {0}").format(anm) + "\n\n"
            md += _("## Gewichtungsanpassung") + "\n\n" + gewichtung_msg + "\n\n"

            hist = conn.execute(
                "SELECT kategorie, alte_gewichtung, neue_gewichtung, grund "
                "FROM gewichtung_historie ORDER BY id DESC LIMIT 5"
            ).fetchall()
            if hist:
                md += _("### Letzte Änderungen") + "\n\n"
                md += _("| Kategorie | Alt | Neu | Grund |") + "\n"
                md += "|---|---|---|---|\n"
                for h in hist:
                    md += _("| {0} | {1}% | {2}% | {3} |").format(_(h[0]), h[1], h[2], h[3]) + "\n"
            md += "\n---\n\n"
            md += _("*Erstellt am {0} vom KM-HR-Agenten.*").format(datetime.now().strftime('%d.%m.%Y %H:%M')) + "\n"

            kandidat_name = profil_path.stem.replace("profil-", "")
            filename = f"feedback-{kandidat_name}-{datetime.now().strftime('%Y-%m-%d')}.md"
            logic.save_result(filename, md)

            # Skill 16: export_report nur bei NEUEM Feedback (app.py:2688-2692)
            # D29: candidate_id = String-Stem (Streamlit-Literal)
            if not existing:
                logic.queue_agent_task("export_report", {
                    "application_id": None,
                    "candidate_id": profil_path.stem.replace("profil-", ""),
                    "job_id": None,
                    "match_id": match_id,
                })

            conn.close()
            _md_result_card(result_box, _("Feedback gespeichert"), filename, md)

        ui.button(_('Feedback speichern'), icon="save", on_click=save_feedback).classes(C.BTN_PRIMARY + " mt-4")


# ─── PDF Export ─────────────────────────────────────────────────────

def export_candidates_pdf(employer_id: Optional[int] = None) -> None:
    """Export candidates list as PDF using reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    from webui import db

    conn = db.get_conn()
    if employer_id:
        candidates = conn.execute("""
            SELECT c.id, c.name, c.hard_skills, c.berufserfahrung_jahre, c.abschluss, c.status
            FROM candidates c
            JOIN applications a ON a.candidate_id = c.id
            JOIN jobs j ON a.job_id = j.id
            WHERE j.employer_id = ?
            ORDER BY c.id DESC
        """, (employer_id,)).fetchall()
    else:
        candidates = conn.execute("""
            SELECT id, name, hard_skills, berufserfahrung_jahre, abschluss, status
            FROM candidates ORDER BY id DESC
        """).fetchall()
    conn.close()

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, _("Kandidaten-Liste"))
    c.setFont("Helvetica", 10)
    c.drawString(50, height - 70, _("Anzahl: {0} Kandidaten").format(len(candidates)))

    # Table header
    y = height - 100
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, _("ID"))
    c.drawString(80, y, _("Name"))
    c.drawString(200, y, _("Skills"))
    c.drawString(350, y, _("Erfahrung"))
    c.drawString(430, y, _("Status"))
    y -= 5
    c.line(50, y, width - 50, y)
    y -= 15

    # Table rows
    c.setFont("Helvetica", 9)
    for cand in candidates:
        if y < 50:
            c.showPage()
            y = height - 50
            c.setFont("Helvetica-Bold", 10)
            c.drawString(50, y, _("ID"))
            c.drawString(80, y, _("Name"))
            c.drawString(200, y, _("Skills"))
            c.drawString(350, y, _("Erfahrung"))
            c.drawString(430, y, _("Status"))
            y -= 5
            c.line(50, y, width - 50, y)
            y -= 15
            c.setFont("Helvetica", 9)

        c.drawString(50, y, str(cand[0] or ""))
        c.drawString(80, y, str((cand[1] or "")[:25]))
        c.drawString(200, y, str((cand[2] or "")[:30]))
        c.drawString(350, y, str(cand[3] or ""))
        c.drawString(430, y, str((cand[5] or "")[:15]))
        y -= 18

    c.save()
    buffer.seek(0)
    ui.download.content(buffer.getvalue(), "kandidaten.pdf", media_type="application/pdf")


# ─── Notifications Drawer ─────────────────────────────────────────────

def notifications_drawer(user_id: int, role: str,
                         badge_state: dict | None = None) -> ui.right_drawer:
    """Rechtsseitiger Drawer mit Benachrichtigungen.

    R3-5 (N-D2, 30.09.2026): „Alle Benachrichtigungen löschen" aktualisiert
    (a) den Drawer-Inhalt und (b) das Header-Badge OHNE Seiten-Reload.
    17.10.2026 (Löschen beim Gelesen-Markieren): Der Klick LOESCHT die
    Zeilen (db.delete_notifications) statt sie auf gelesen=1 zu setzen —
    Texte sind entsprechend ehrlich benannt.
    Technik: ui.refreshable()-Container — refresh() rebuildet den Inhalt
    sauber ueber NiceGUI-DOM (kein content.clear()+with, das paddet bei
    Event-Handlern in NG 3.17 nicht zum Client).
    Badge-Refresh ueber badge_state-Dict (Cross-Client-sicher).
    """
    from webui import db

    # 17.10.2026 (Ursache gemessen, Messreihe /tmp/opencode/bell-*.png 10/10):
    # OHNE `value` ist der NiceGUI-Default None -> Quasar `show-if-above` ->
    # der rechte Drawer stand ab Layoutbreite >= 1024 px AUTOMATISCH offen
    # (Breakpoint-Grenze 1000 zu / 1025 offen). Es gibt kein aktives show()/
    # toggle() im Code. Deshalb explizit geschlossen: value=False.
    # Sichtbar bleibt die Glocke + Badge (`badge.set_visibility(unread > 0)`);
    # geoeffnet wird nur per Glocken-Klick (`_toggle_drawer`).
    drawer = ui.right_drawer(value=False, fixed=False).props("bordered").classes("w-80")
    with drawer:
        ui.label(_('Benachrichtigungen')).classes("text-lg font-bold mb-4")

        def _mark_read():
            db.delete_notifications(user_id, role)
            _render_content.refresh()   # (a) Drawer-Inhalt neu via DOM-Refresh
            _refresh = (badge_state or {}).get("refresh")
            if callable(_refresh):
                _refresh()          # (b) Header-Badge neu zaehlen/einblenden
            ui.notify(_('Alle Benachrichtigungen gelöscht'), type="positive")

        @ui.refreshable
        def _render_content():
            notifications = db.get_notifications(user_id, role)
            if not notifications:
                ui.label(_('Keine Benachrichtigungen')).classes(C.MUTED)
            else:
                # 17.10.2026 (Änderung B, Notification-Sprache): Zeilen MIT
                # msg_key werden zur Renderzeit in der Leser-Sprache uebersetzt
                # (tr() formt intern — KEIN doppeltes .format()). Der status-
                # Param liegt als ROH-Slug in der DB und wird VOR dem Format
                # per status_label in die Leser-Sprache uebersetzt. Altbestand
                # (msg_key NULL): unveraendert verbatim aus titel/nachricht.
                lang = get_language()
                for (nid, titel, nachricht, gelesen, created_at,
                     msg_key, params_json) in notifications:
                    if msg_key:
                        params: dict = {}
                        if params_json:
                            try:
                                geladen = json.loads(params_json)
                                if isinstance(geladen, dict):
                                    params = geladen
                            except (TypeError, ValueError):
                                params = {}  # kaputter JSON-String -> Text ohne Params
                        if "status" in params:
                            params["status"] = status_label(str(params["status"]))
                        try:
                            titel = tr(f"{msg_key}.titel", lang)
                            nachricht = tr(f"{msg_key}.text", lang, **params)
                        except (KeyError, IndexError, ValueError):
                            # Platzhalter-Panne (z.B. params unvollstaendig):
                            # Fallback-Text aus DB bleibt stehen, kein Crash.
                            pass
                    with ui.card().classes(
                        "w-full mb-2 py-2 px-3"
                        + (" bg-blue-50 dark:bg-blue-900/20 border-l-4 border-blue-500"
                           if not gelesen else "")
                    ):
                        ui.label(titel).classes("font-medium text-sm")
                        if nachricht:
                            ui.label(nachricht).classes(C.SMALL + " mt-1")
                        if created_at:
                            ui.label(created_at[:16]).classes(C.MUTED + " mt-1")

            ui.separator().classes("my-3")
            ui.button(
                _('Alle Benachrichtigungen löschen'),
                icon="done_all",
                on_click=_mark_read,
            ).classes(C.BTN_SECONDARY + " w-full")

        _render_content()

    return drawer


# ─── Shell Layout ────────────────────────────────────────────────────

def shell(role: str, user_id: int, user_name: str, menu_items: list[dict],
          logout_fn: Callable, content_fn: Callable, s: dict,
          initial_tab: str = "", extra_tabs: tuple = ()) -> None:
    """Einheitliche Layout-Komponente fuer alle 3 Rollen.
    
    Args:
        role: "candidate", "employer" oder "admin"
        user_id: ID des Users (cand_id, employer_id oder admin_id)
        user_name: Anzuzeigender Name
        menu_items: Liste von dicts mit {"key": str, "label": str, "icon": str}
        logout_fn: Logout-Callback
        content_fn: Callback fuer den Content-Bereich (parameter: s dict)
        s: Session dict (app.storage.user)
    """
    from webui.theme import inject_css
    from webui import db
    from nicegui import context as ng_context
    inject_css()

    # Client-Kontext beim Shell-Bau speichern (Slot-Stack ist hier noch aktiv)
    # Nach Verlassen des with-blocks ist der Slot-Stack leer — ui.run_javascript()
    # versagt dann still (try/except pass). Deshalb nutzen wir den expliziten Client.
    _client = ng_context.client

    # R5-5 (30.09.2026): initial_tab VOR dem Sidebar-Bau anwenden — vorher
    # wurde current_page erst Z. ~1381 (nach dem Menü-Loop) gesetzt, sodass
    # der aktive Button beim Direkteinstieg über /candidate/<tab> bzw.
    # /employer/<tab> NICHT hervorgehoben war (font-bold/primary fehlten).
    # Fund: tests/test_p2_block.py::test_sidebar_aktiver_button_hervorgehoben.
    _initial = initial_tab if initial_tab and initial_tab in ({m["key"] for m in menu_items} | set(extra_tabs)) else (menu_items[0]["key"] if menu_items else "")
    current_page = {"value": _initial}

    # Notifications Drawer
    # R3-5 (N-D2): Refresh-Handle je Shell-Aufruf LOKAL (Closure statt
    # Modul-Global — Cross-Client-Lesson _SHELL_STATE). Dict zuerst anlegen
    # und dem Drawer uebergeben, den Badge-Refresh danach hineinschreiben
    # (beide lesen erst beim Klick -> Reihenfolge ist egal, Dict ist mutabel).
    badge_state: dict = {}
    drawer = notifications_drawer(user_id, role, badge_state)

    # ── Header (Glassmorphism) ──────────────────────────────────────────
    with ui.header().classes("header-glass px-6 items-center"):
        ui.button(icon="menu", on_click=lambda: nav_drawer.toggle()).classes(C.BTN_ICON)
        with ui.row().classes("items-center gap-2"):
            ui.icon("smart_toy", size="sm").classes("text-blue-600 dark:text-blue-400")
            ui.label('KM-HR-Agent').classes("text-lg font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent")
        ui.space()

        # Notifications button
        unread = db.get_unread_count(user_id, role)

        def _toggle_drawer():
            drawer.toggle()

        with ui.button(icon="notifications", on_click=_toggle_drawer).props("flat"):
            # R3-5 (N-D2): Badge IMMER anlegen (ungelesen=0 -> unsichtbar),
            # damit _refresh_badge() ohne Neuaufbau des Headers zaehlen kann.
            # A11y (02.10.2026): color=red (=#F44336) ergab mit weißem Text nur
            # 3.68:1 (< WCAG AA 4.5). red-9 (=#B71C1C) ergibt ~6.6:1.
            badge = ui.badge(str(unread)).props("color=red-9 floating")
            badge.set_visibility(unread > 0)

        def _refresh_badge():
            n = db.get_unread_count(user_id, role)
            badge.set_text(str(n))
            badge.set_visibility(n > 0)

        badge_state["refresh"] = _refresh_badge

        # User menu
        with ui.button(icon="account_circle").props("flat"):
            with ui.menu():
                ui.menu_item(user_name)
                ui.menu_item(_('Abmelden'), on_click=lambda: (logout_fn(), ui.navigate.to("/login")))

        # Sprachumschalter (i18n, Phase 1 02.10.2026) — DE/EN/FR/AR
        from webui.i18n import language_switcher, apply_direction
        apply_direction()
        language_switcher()

        # Dark Mode Toggle
        dark = ui.dark_mode()
        ui.switch(value=dark.value, on_change=lambda e: dark.set_value(e.value)).props("color=blue")

    # ── Sidebar (Glassmorphism) ─────────────────────────────────────────
    with ui.left_drawer(bordered=True).classes(C.SIDEBAR + " w-64 p-4") as nav_drawer:
        title_map = {"candidate": "Kandidaten-Portal", "employer": "Arbeitgeber-Portal", "admin": "Admin-Portal"}
        with ui.row().classes("items-center gap-2 mb-4"):
            icon_map = {"candidate": "person", "employer": "business", "admin": "shield"}
            ui.icon(icon_map.get(role, "circle"), size="sm").classes("text-blue-600 dark:text-blue-400")
            ui.label(_(title_map.get(role, "Portal"))).classes("text-lg font-bold text-gray-900 dark:text-white")
            ui.space()
            ui.button(icon="close", on_click=nav_drawer.hide).props("flat dense").classes(C.BTN_ICON)

        ui.separator().classes("border-gray-200/50 dark:border-gray-700/50")

        for item in menu_items:
            page_key = item["key"]

            def _make_click(k=page_key):
                def _click():
                    current_page["value"] = k
                    render_content()
                    # URL aktualisieren via explizitem Client (kein Slot-Stack noetig)
                    try:
                        _client.run_javascript(f"history.pushState(null, '', '/{role}/{k}')")
                    except Exception:
                        pass  # Test-Simulation: kein JS-Loop
                    # SPA: Sidebar bleibt offen (kein nav_drawer.hide())
                return _click

            _active = page_key == current_page["value"]
            _cls = "w-full justify-start text-gray-700 dark:text-gray-300" + (" font-bold" if _active else "")
            ui.button(
                item["label"], icon=item.get("icon", "circle"),
                on_click=_make_click(),
                color="primary" if _active else None,
            ).classes(_cls)

        ui.separator().classes("mt-auto border-gray-200/50 dark:border-gray-700/50")
        with ui.row().classes("items-center gap-2 w-full mt-4"):
            ui.label(user_name).classes(C.SMALL + " flex-1")
            ui.button(icon="logout", on_click=lambda: (logout_fn(), ui.navigate.to("/login"))).props("flat dense")

    # Content area
    content_container = ui.column().classes("w-full " + C.PAGE_CONTAINER)

    def render_content():
        content_container.clear()
        with content_container:
            with ui.column().classes("w-full page-transition"):
                content_fn(current_page["value"])

    # SPA-State registrieren: navigate_to() nutzt current_page + render_content
    # O1 (24.09.2026): Key je Client + Aufräumen beim Client-Delete (Prune/Multi-Tab)
    _state_key = f"{_client.id}:{role}"
    _SHELL_STATE[_state_key] = {"page": current_page, "render": render_content}
    _client.on_delete(lambda *_args, _k=_state_key: _SHELL_STATE.pop(_k, None))

    # initial_tab: bereits oben (R5-5) vor dem Sidebar-Bau angewendet;
    # die doppelte Zuweisung hier entfällt. current_page["value"] ist jetzt
    # schon der Sub-Route-Tab — render_content() rendert ihn direkt.

    render_content()
