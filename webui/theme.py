"""
Design Tokens for KM-HR-Agent NiceGUI App.
Based on knowledge/ui-design-system.md.
"""
from dataclasses import dataclass, field
from typing import Optional


# ─── Colors ──────────────────────────────────────────────────────────

PRIMARY = "#1E40AF"
PRIMARY_LIGHT = "#3B82F6"
PRIMARY_DARK = "#1E3A8A"
SECONDARY = "#059669"
ACCENT = "#F59E0B"
DANGER = "#DC2626"
INFO = "#0EA5E9"

BG_PAGE_LIGHT = "#F8FAFC"
BG_CARD_LIGHT = "#FFFFFF"
BG_ELEVATED_LIGHT = "#F1F5F9"
BORDER_LIGHT = "#E2E8F0"
TEXT_PRIMARY_LIGHT = "#0F172A"
TEXT_SECONDARY_LIGHT = "#64748B"
TEXT_MUTED_LIGHT = "#94A3B8"

BG_PAGE_DARK = "#0F172A"
BG_CARD_DARK = "#1E293B"
BG_ELEVATED_DARK = "#334155"
BORDER_DARK = "#475569"
TEXT_PRIMARY_DARK = "#F8FAFC"
TEXT_SECONDARY_DARK = "#94A3B8"

# Role colors
ROLE_COLORS = {
    "candidate": "#3B82F6",
    "employer": "#7C3AED",
    "admin": "#DC2626",
}


# ─── Status Colors ───────────────────────────────────────────────────

STATUS_COLORS = {
    "done": "#059669",
    "eingestellt": "#059669",
    "active": "#3B82F6",
    "eingeladen": "#3B82F6",
    "pending": "#F59E0B",
    "angesehen": "#F59E0B",
    "eingegangen": "#F59E0B",
    "failed": "#DC2626",
    "abgelehnt": "#DC2626",
    "zurückgezogen": "#DC2626",
    "running": "#3B82F6",
    "queued": "#94A3B8",
    "paused": "#F59E0B",
    "besetzt": "#059669",
    "abgelaufen": "#94A3B8",
}

STATUS_BADGE_CLASSES = {
    "done": "bg-green-100 text-green-800",
    "eingestellt": "bg-green-100 text-green-800",
    "active": "bg-blue-100 text-blue-800",
    "eingeladen": "bg-blue-100 text-blue-800",
    "pending": "bg-amber-100 text-amber-800",
    "angesehen": "bg-amber-100 text-amber-800",
    "eingegangen": "bg-gray-100 text-gray-800",
    "failed": "bg-red-100 text-red-800",
    "abgelehnt": "bg-red-100 text-red-800",
    "zurückgezogen": "bg-red-100 text-red-800",
    "running": "bg-blue-100 text-blue-800",
    "queued": "bg-gray-100 text-gray-600",
    "paused": "bg-amber-100 text-amber-800",
    "besetzt": "bg-green-100 text-green-800",
    "abgelaufen": "bg-gray-100 text-gray-600",
}


# ─── Score Thresholds ────────────────────────────────────────────────

def score_color(score: int) -> str:
    if score >= 80:
        return SECONDARY
    elif score >= 60:
        return ACCENT
    else:
        return DANGER


def score_badge_class(score: int) -> str:
    if score >= 80:
        return "bg-green-100 text-green-800"
    elif score >= 60:
        return "bg-amber-100 text-amber-800"
    else:
        return "bg-red-100 text-red-800"


def score_label(score: int) -> str:
    if score >= 90:
        return "Hervorragend"
    elif score >= 80:
        return "Sehr gut"
    elif score >= 70:
        return "Gut"
    elif score >= 60:
        return "Befriedigend"
    elif score >= 40:
        return "Ausreichend"
    else:
        return "Schwach"


# ─── CSS ─────────────────────────────────────────────────────────────

CUSTOM_CSS = """
/* ═══════════════════════════════════════════════════════════════════════
   GLASSMORPHISM DESIGN SYSTEM – KM-HR-Agent
   Quelle: knowledge/ui-design-system.md (Glassmorphism-Section)
   ═══════════════════════════════════════════════════════════════════════ */

/* ── Gradient Backgrounds ────────────────────────────────────────────── */
.bg-gradient-hero {
    background: linear-gradient(135deg, #92400E 0%, #D97706 100%);
}
.bg-gradient-primary {
    background: linear-gradient(135deg, #1E40AF 0%, #3B82F6 50%, #06B6D4 100%);
}
.bg-gradient-warm {
    background: linear-gradient(135deg, #D97706 0%, #F59E0B 100%);
}
.bg-gradient-ocean {
    background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
}
.bg-gradient-sunset {
    background: linear-gradient(135deg, #fa709a 0%, #fee140 100%);
}
.bg-gradient-mesh {
    background:
        radial-gradient(at 40% 20%, hsla(228, 67%, 65%, 0.4) 0px, transparent 50%),
        radial-gradient(at 80% 0%, hsla(189, 64%, 50%, 0.3) 0px, transparent 50%),
        radial-gradient(at 0% 50%, hsla(355, 85%, 63%, 0.2) 0px, transparent 50%),
        radial-gradient(at 80% 50%, hsla(340, 68%, 55%, 0.2) 0px, transparent 50%),
        radial-gradient(at 0% 100%, hsla(22, 78%, 60%, 0.3) 0px, transparent 50%);
}

/* ── Glass Card ──────────────────────────────────────────────────────── */
.glass {
    background: rgba(255, 255, 255, 0.7);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid rgba(255, 255, 255, 0.3);
    box-shadow:
        0 4px 6px -1px rgba(0, 0, 0, 0.1),
        0 2px 4px -2px rgba(0, 0, 0, 0.1),
        inset 0 1px 0 0 rgba(255, 255, 255, 0.5);
}
.glass:hover {
    background: rgba(255, 255, 255, 0.8);
    border-color: rgba(255, 255, 255, 0.5);
    box-shadow:
        0 10px 25px -5px rgba(0, 0, 0, 0.15),
        0 8px 10px -6px rgba(0, 0, 0, 0.1),
        inset 0 1px 0 0 rgba(255, 255, 255, 0.6);
}
.glass-strong {
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1px solid rgba(255, 255, 255, 0.4);
}
.glass-subtle {
    background: rgba(255, 255, 255, 0.5);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.2);
}

/* ── Dark Mode Glass ─────────────────────────────────────────────────── */
.dark .glass {
    background: rgba(30, 41, 59, 0.7);
    border-color: rgba(255, 255, 255, 0.1);
    box-shadow:
        0 4px 6px -1px rgba(0, 0, 0, 0.3),
        inset 0 1px 0 0 rgba(255, 255, 255, 0.05);
}
.dark .glass:hover {
    background: rgba(30, 41, 59, 0.8);
    border-color: rgba(255, 255, 255, 0.15);
}
.dark .glass-strong {
    background: rgba(30, 41, 59, 0.9);
}
.dark .glass-subtle {
    background: rgba(30, 41, 59, 0.5);
}

/* ── Glow Effects ────────────────────────────────────────────────────── */
.glow-blue {
    box-shadow: 0 0 20px rgba(59, 130, 246, 0.4), 0 0 40px rgba(59, 130, 246, 0.2);
}
.glow-green {
    box-shadow: 0 0 20px rgba(16, 185, 129, 0.4), 0 0 40px rgba(16, 185, 129, 0.2);
}
.glow-purple {
    box-shadow: 0 0 20px rgba(139, 92, 246, 0.4), 0 0 40px rgba(139, 92, 246, 0.2);
}
.glow-amber {
    box-shadow: 0 0 20px rgba(245, 158, 11, 0.4), 0 0 40px rgba(245, 158, 11, 0.2);
}
.glow-red {
    box-shadow: 0 0 20px rgba(239, 68, 68, 0.4), 0 0 40px rgba(239, 68, 68, 0.2);
}

/* ── Gradient Buttons ────────────────────────────────────────────────── */
.btn-glass {
    background: rgba(59, 130, 246, 0.9);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: white;
    font-weight: 600;
    padding: 0.625rem 1.5rem;
    border-radius: 0.75rem;
    transition: all 0.2s ease;
    box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3);
}
.btn-glass:hover {
    background: rgba(37, 99, 235, 0.95);
    box-shadow: 0 6px 20px rgba(59, 130, 246, 0.4);
    transform: translateY(-1px);
}
.btn-glass:active {
    transform: translateY(0);
    box-shadow: 0 2px 10px rgba(59, 130, 246, 0.3);
}
.btn-glass-green {
    background: rgba(16, 185, 129, 0.9);
    box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
}
.btn-glass-green:hover {
    background: rgba(5, 150, 105, 0.95);
    box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
}
.btn-glass-red {
    background: rgba(239, 68, 68, 0.9);
    box-shadow: 0 4px 15px rgba(239, 68, 68, 0.3);
}
.btn-glass-red:hover {
    background: rgba(220, 38, 38, 0.95);
    box-shadow: 0 6px 20px rgba(239, 68, 68, 0.4);
}
.btn-glass-purple {
    background: rgba(139, 92, 246, 0.9);
    box-shadow: 0 4px 15px rgba(139, 92, 246, 0.3);
}
.btn-glass-purple:hover {
    background: rgba(124, 58, 237, 0.95);
    box-shadow: 0 6px 20px rgba(139, 92, 246, 0.4);
}
.btn-glass-ghost {
    background: rgba(255, 255, 255, 0.1);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.2);
    color: #1E40AF;
}
.btn-glass-ghost:hover {
    background: rgba(59, 130, 246, 0.1);
    border-color: rgba(59, 130, 246, 0.3);
}
.dark .btn-glass-ghost {
    color: #93c5fd;
}

/* ── Translucent Badges ──────────────────────────────────────────────── */
.badge-glass {
    background: rgba(59, 130, 246, 0.15);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(59, 130, 246, 0.2);
    color: #1E40AF;
    font-weight: 500;
    padding: 0.25rem 0.75rem;
    border-radius: 9999px;
    font-size: 0.75rem;
}
.badge-glass-green {
    background: rgba(16, 185, 129, 0.15);
    border-color: rgba(16, 185, 129, 0.2);
    color: #065f46;
}
.badge-glass-amber {
    background: rgba(245, 158, 11, 0.15);
    border-color: rgba(245, 158, 11, 0.2);
    color: #92400e;
}
.badge-glass-red {
    background: rgba(239, 68, 68, 0.15);
    border-color: rgba(239, 68, 68, 0.2);
    color: #991b1b;
}
.dark .badge-glass {
    background: rgba(59, 130, 246, 0.25);
    color: #93c5fd;
}
.dark .badge-glass-green {
    background: rgba(16, 185, 129, 0.25);
    color: #6ee7b7;
}
.dark .badge-glass-amber {
    background: rgba(245, 158, 11, 0.25);
    color: #fcd34d;
}
.dark .badge-glass-red {
    background: rgba(239, 68, 68, 0.25);
    color: #fca5a5;
}

/* ── Glass Header ────────────────────────────────────────────────────── */
.header-glass {
    background: rgba(255, 255, 255, 0.8);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-bottom: 1px solid rgba(255, 255, 255, 0.3);
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}
.dark .header-glass {
    background: rgba(15, 23, 42, 0.85);
    border-bottom-color: rgba(255, 255, 255, 0.08);
}

/* ── Glass Sidebar ───────────────────────────────────────────────────── */
.sidebar-glass {
    background: rgba(248, 250, 252, 0.9);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-right: 1px solid rgba(255, 255, 255, 0.4);
}
.dark .sidebar-glass {
    background: rgba(15, 23, 42, 0.9);
    border-right-color: rgba(255, 255, 255, 0.08);
}

/* ── Glass Input ─────────────────────────────────────────────────────── */
.input-glass {
    background: rgba(255, 255, 255, 0.6);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(226, 232, 240, 0.8);
    border-radius: 0.75rem;
    transition: all 0.2s ease;
}
.input-glass:focus {
    background: rgba(255, 255, 255, 0.8);
    border-color: rgba(59, 130, 246, 0.5);
    box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}
.dark .input-glass {
    background: rgba(30, 41, 59, 0.6);
    border-color: rgba(71, 85, 105, 0.5);
}
.dark .input-glass:focus {
    background: rgba(30, 41, 59, 0.8);
    border-color: rgba(96, 165, 250, 0.5);
}

/* ── Glass Table ─────────────────────────────────────────────────────── */
.table-glass th {
    background: rgba(248, 250, 252, 0.8);
    backdrop-filter: blur(8px);
    font-weight: 600;
    text-transform: uppercase;
    font-size: 0.75rem;
    letter-spacing: 0.05em;
    color: #64748B;
}
.table-glass tr:hover td {
    background: rgba(59, 130, 246, 0.04);
}
.dark .table-glass th {
    background: rgba(30, 41, 59, 0.8);
    color: #94A3B8;
}
.dark .table-glass tr:hover td {
    background: rgba(59, 130, 246, 0.08);
}

/* ── Score Bar (Glass) ───────────────────────────────────────────────── */
.score-bar-glass {
    background: rgba(226, 232, 240, 0.5);
    border-radius: 9999px;
    overflow: hidden;
    height: 0.5rem;
}
.score-bar-glass .fill {
    height: 100%;
    border-radius: 9999px;
    transition: width 0.8s ease-out;
}

/* ── Floating Orb (decorative) ───────────────────────────────────────── */
.orb {
    position: absolute;
    border-radius: 50%;
    filter: blur(60px);
    opacity: 0.4;
    pointer-events: none;
}
.orb-blue {
    background: #3B82F6;
}
.orb-purple {
    background: #8B5CF6;
}
.orb-pink {
    background: #EC4899;
}
.orb-cyan {
    background: #06B6D4;
}

/* ── Animations ──────────────────────────────────────────────────────── */
@keyframes score-fill {
    from { transform: scaleX(0); }
    to { transform: scaleX(1); }
}
.score-bar-animated .q-linear-progress__track {
    background-color: transparent;
}
.score-bar-animated .q-linear-progress__model {
    transform-origin: left;
    animation: score-fill 0.8s ease-out;
}

@keyframes badge-pulse {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.05); }
}
.badge-pulse {
    animation: badge-pulse 2s ease-in-out infinite;
}

@keyframes glow-pulse {
    0%, 100% { box-shadow: 0 0 20px rgba(59, 130, 246, 0.3); }
    50% { box-shadow: 0 0 30px rgba(59, 130, 246, 0.5), 0 0 60px rgba(59, 130, 246, 0.2); }
}
.glow-pulse {
    animation: glow-pulse 3s ease-in-out infinite;
}

.card-interactive {
    transition: all 0.25s ease;
}
.card-interactive:hover {
    transform: translateY(-2px);
    box-shadow:
        0 10px 25px -5px rgba(0, 0, 0, 0.1),
        0 8px 10px -6px rgba(0, 0, 0, 0.1);
}

.upload-zone {
    border: 2px dashed rgba(148, 163, 184, 0.6);
    border-radius: 1rem;
    transition: all 0.2s ease;
    background: rgba(255, 255, 255, 0.3);
}
.upload-zone:hover {
    border-color: #3B82F6;
    background: rgba(59, 130, 246, 0.05);
}

/* ─── UI-Regel: Klickziele ≥ 44 px (28.09.2026, Master-Befundliste) ───
   Vorher-Messung (ergebnisse/reports/screenshots/vorher/messung-vorher.json):
   5 Verstöße (34 px Paginator, 42 px Icon-Knöpfe). Quelle der Regel: WCAG 2.2
   SC 2.5.8 Target Size (Minimum) 24×24 px — hier als 44 px Hausnorm. */
.q-btn {
    min-height: 44px;
}
.q-btn.q-btn--round,
.q-btn.btn-icon-only {
    min-width: 44px;
}

/* ─── UI-Regel: Status-Komponente (eine Bauart für alle Rollen) ─────
   Vorher: drei Varianten (Quasar-q-badge 'blue' = 3.12:1, Quasar-bg-primary
   + Theme-Textfarbe = 2.51:1, Theme-'badge-glass*'). Messung siehe
   ergebnisse/reports/screenshots/{vorher,nachher}/messung-*.json */
.q-badge.status-badge {
    font-size: 0.875rem;
    font-weight: 600;
    padding: 0.3rem 0.7rem;
    border-radius: 9999px;
    border: 1px solid transparent;
}


@keyframes shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
.skeleton-shimmer {
    background: linear-gradient(90deg, rgba(255,255,255,0.1) 25%, rgba(255,255,255,0.2) 50%, rgba(255,255,255,0.1) 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
}

.nav-item {
    transition: all 0.15s ease;
    border-radius: 0.5rem;
}
.nav-item:hover {
    background: rgba(59, 130, 246, 0.08);
}
.nav-item.active {
    background: rgba(59, 130, 246, 0.12);
    color: #1E40AF;
    font-weight: 600;
    box-shadow: inset 3px 0 0 #3B82F6;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
.page-fade-in {
    animation: fadeIn 0.3s ease-out;
}

@keyframes pageTransition {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}
.page-transition {
    animation: pageTransition 0.3s ease-out;
}

@keyframes checkmark {
    0% { transform: scale(0); }
    50% { transform: scale(1.2); }
    100% { transform: scale(1); }
}
.success-check {
    animation: checkmark 0.5s ease-out;
}

@keyframes float {
    0%, 100% { transform: translateY(0px); }
    50% { transform: translateY(-10px); }
}
.float-animation {
    animation: float 6s ease-in-out infinite;
}

@keyframes gradient-shift {
    0% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
.animated-gradient {
    background-size: 200% 200%;
    animation: gradient-shift 8s ease infinite;
}

/* ── Responsive ──────────────────────────────────────────────────────── */
@media (max-width: 768px) {
    .grid-4 { grid-template-columns: repeat(1, 1fr) !important; }
    .grid-3 { grid-template-columns: repeat(1, 1fr) !important; }
    .grid-2 { grid-template-columns: repeat(1, 1fr) !important; }
}
@media (min-width: 769px) and (max-width: 1024px) {
    .grid-4 { grid-template-columns: repeat(2, 1fr) !important; }
    .grid-3 { grid-template-columns: repeat(2, 1fr) !important; }
}
"""


# ─── Tailwind Classes ────────────────────────────────────────────────

class C:
    """Convenience class for common Tailwind class strings."""

    # Layout
    PAGE_CONTAINER = "max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6"
    CARD = "glass rounded-2xl p-6"
    CARD_HOVER = CARD + " card-interactive"
    CARD_STRONG = "glass-strong rounded-2xl p-6"
    GRID_2 = "grid grid-cols-1 md:grid-cols-2 gap-4"
    GRID_3 = "grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
    GRID_4 = "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"

    # Typography
    PAGE_TITLE = "text-2xl font-bold text-gray-900 dark:text-white"
    SECTION_TITLE = "text-xl font-semibold text-gray-900 dark:text-white"
    CARD_TITLE = "text-lg font-medium text-gray-900 dark:text-white"
    BODY = "text-base text-gray-700 dark:text-gray-300"
    SMALL = "text-sm text-gray-600 dark:text-gray-400"
    MUTED = "text-xs text-gray-500 dark:text-gray-500"
    STAT_NUMBER = "text-3xl font-bold text-gray-900 dark:text-white"

    # Buttons (Glassmorphism)
    BTN_PRIMARY = "btn-glass"
    BTN_SECONDARY = "btn-glass-ghost"
    BTN_DANGER = "btn-glass-red"
    BTN_SUCCESS = "btn-glass-green"
    BTN_PURPLE = "btn-glass-purple"
    BTN_GHOST = "btn-glass-ghost"
    BTN_ICON = "rounded-xl p-2 hover:bg-white/20 dark:hover:bg-gray-700/50 transition-all"

    # Badges (Translucent)
    BADGE = "badge-glass"
    BADGE_GREEN = "badge-glass badge-glass-green"
    BADGE_AMBER = "badge-glass badge-glass-amber"
    BADGE_RED = "badge-glass badge-glass-red"
    BADGE_BLUE = "badge-glass"
    BADGE_GRAY = "badge-glass bg-gray-100/50 text-gray-600 border-gray-200/50"

    # Upload
    UPLOAD_ZONE = "upload-zone flex flex-col items-center justify-center p-8 cursor-pointer"

    # Sidebar
    SIDEBAR = "sidebar-glass"
    NAV_ITEM = "nav-item flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm text-gray-700 dark:text-gray-300 cursor-pointer"
    NAV_ITEM_ACTIVE = NAV_ITEM + " active"

    # Glass variants
    GLASS = "glass"
    GLASS_STRONG = "glass-strong"
    GLASS_SUBTLE = "glass-subtle"


# ─── CSS Injection (pro @ui.page) ────────────────────────────────────
# Quelle: nicegui.io/documentation/section_pages_routing#add_html_to_the_page
# Muss in jedem @ui.page aufgerufen werden (modularized mode).

def apply_brand_colors() -> None:
    """Setzt Quasars Markenfarben (client-scoped, pro Seite).

    P0 (28.09.2026): Quasars Default-Primary #5898D4 ergab mit weisser Schrift
    nur 3.06:1 — 337 Kontrastverstoesse in der Vorher-Messung (Buttons,
    Sidebar, Kopfzeile, Icons). Quellen: WCAG 2.1 SC 1.4.3 (>=4.5:1),
    AAA-Ziel 7:1. Gewaehlte Werte: Primary #1D4ED8 (6.7:1), Negative
    #B91C1C (6.47:1), Positive #15803D (5.02:1) — alle >= 4.5:1 in beide
    Richtungen (weisser Text auf Farbe und Farbe als Text auf Weiss).

    Aufruf in inject_css() (nicht auf Modulebene): ui.colors() ist
    client-scoped; ein Aufruf im globalen Scope laesst NiceGUI mit
    "ui.page cannot be used ... UI defined in the global scope" abbrechen.
    """
    from nicegui import ui
    ui.colors(primary="#1D4ED8", secondary="#15803D", positive="#15803D",
              negative="#B91C1C", amber="#B45309", dark="#0F172A")


def inject_css():
    """Fuegt globalen CSS-Inhalt zum <head> der aktuellen Seite hinzu.

    WICHTIG (Bug-Fix 21.09.2026): KEIN One-shot-Modul-Flag verwenden!
    In NiceGUI (modularized mode) ist ui.add_head_html seiten-scoped — ein
    Modul-Flag wuerde das CSS nur in die ERSTE gebaute Seiten-Instanz
    injizieren; jede weitere Seite bleibt ungestylt (Beweis: curl /login
    enthielt 0x '.glass', backdrop-filterComputed='none').
    """
    from nicegui import ui
    apply_brand_colors()
    ui.add_head_html(f"<style>{CUSTOM_CSS}</style>")
