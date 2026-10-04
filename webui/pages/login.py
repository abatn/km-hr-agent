"""
Login page for KM-HR-Agent NiceGUI App.
Glassmorphism Design: Gradient-Background + Glass-Cards + Floating Orbs.
5-tab layout: Candidate Login, Register, Employer Login, Employer Register, Admin Login.
Quelle: app.py:891-1095 (5 Tabs), knowledge/system/access-control.md:62.
"""
from __future__ import annotations

import os
import sqlite3
import sys

from nicegui import ui

from webui import db, logic
from webui.theme import C
from webui.i18n import _, apply_direction, language_switcher


def _session() -> dict:
    from nicegui import app
    return app.storage.user


def create() -> None:
    """Register the /login page."""

    @ui.page("/login")
    def login_page():
        from webui.theme import inject_css
        inject_css()
        apply_direction()  # <html lang> + dir (RTL bei Arabisch)

        # ── Full-screen gradient background ─────────────────────────────
        ui.add_head_html('''
            <style>
                body {
                    background: linear-gradient(135deg, #92400E 0%, #B45309 50%, #D97706 100%);
                    min-height: 100vh;
                    overflow-y: auto;
                }
                .login-container {
                    position: relative;
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .login-orb {
                    position: absolute;
                    border-radius: 50%;
                    filter: blur(80px);
                    opacity: 0.5;
                    pointer-events: none;
                    animation: float 8s ease-in-out infinite;
                }
                .orb-1 {
                    width: 400px;
                    height: 400px;
                    background: #F59E0B;
                    top: -100px;
                    left: -100px;
                    animation-delay: 0s;
                }
                .orb-2 {
                    width: 300px;
                    height: 300px;
                    background: #D97706;
                    bottom: -80px;
                    right: -80px;
                    animation-delay: 2s;
                }
                .orb-3 {
                    width: 200px;
                    height: 200px;
                    background: #B45309;
                    top: 50%;
                    right: 20%;
                    animation-delay: 4s;
                }
                @keyframes float {
                    0%, 100% { transform: translateY(0px) scale(1); }
                    50% { transform: translateY(-20px) scale(1.05); }
                }
            </style>
        ''')

        with ui.element("div").classes("login-container"):
            # ── Floating Orbs (decorative) ──────────────────────────────
            ui.element("div").classes("login-orb orb-1")
            ui.element("div").classes("login-orb orb-2")
            ui.element("div").classes("login-orb orb-3")

            with ui.column().classes("items-center gap-10 z-10 w-full max-w-3xl px-12"):
                # ── Sprachumschalter (i18n, Phase 3 02.10.2026) ─────────
                language_switcher()
                # ── Logo / Title (Glass Card) ───────────────────────────
                with ui.card().classes("glass-strong w-full text-center py-14 px-12 rounded-3xl"):
                    with ui.row().classes("items-center justify-center gap-3 mb-2"):
                        ui.icon("smart_toy", size="xl").classes("text-amber-900")
                        ui.label("KM-HR-Agent").classes("text-3xl font-bold text-amber-900")
                    ui.label(_("KI-gestuetztes Recruiting-Portal")).classes("text-lg text-amber-800 mt-1")

                # ── Login Card (Glass) ──────────────────────────────────
                with ui.card().classes("glass-strong w-full rounded-3xl overflow-hidden"):
                    with ui.tabs().classes("w-full") as tabs:
                        ui.tab(_("Login"), icon="login")
                        ui.tab(_("Registrieren"), icon="person_add")
                        ui.tab(_("Arbeitgeber"), icon="business")
                        ui.tab(_("Arbeitgeber+"), icon="business_center")
                        ui.tab(_("Admin"), icon="shield")

                    with ui.tab_panels(tabs, value=_("Login")).classes("w-full"):
                        # ── Candidate Login ──────────────────────────────
                        with ui.tab_panel(_("Login")):
                            ui.label(_("Willkommen zurueck")).classes(C.CARD_TITLE + " mb-4")
                            email = ui.input(
                                _("E-Mail"),
                                placeholder=_("name@beispiel.de"),
                                validation={_("E-Mail gueltig"): lambda v: "@" in v and "." in v},
                            ).classes("w-full")
                            pw = ui.input(
                                _("Passwort"),
                                password=True,
                                placeholder=_("Mindestens 8 Zeichen"),
                                validation={_("Mindestens 8 Zeichen"): lambda v: len(v) >= 8},
                            ).classes("w-full")
                            msg = ui.label("").classes("text-red-400 text-sm")

                            async def do_login():
                                if not email.value or not pw.value:
                                    msg.text = _("E-Mail und Passwort sind Pflichtfelder.")
                                    return
                                conn = db.get_conn()
                                row = conn.execute(
                                    "SELECT id, name, password_hash FROM candidates WHERE email = ?",
                                    (email.value.strip().lower(),),
                                ).fetchone()
                                if not row:
                                    emp = conn.execute(
                                        "SELECT firma FROM employers WHERE email = ?",
                                        (email.value.strip().lower(),),
                                    ).fetchone()
                                    conn.close()
                                    if emp:
                                        msg.text = _("Dies ist ein Arbeitgeber-Account ({firma}) – bitte im Tab Arbeitgeber einloggen.").format(firma=emp[0])
                                    else:
                                        msg.text = _("Unbekannte E-Mail oder falsches Passwort.")
                                    return
                                if logic.verify_password_argon2id(pw.value, row[2]) or logic.verify_password_sha256(pw.value, row[2]):
                                    logic.migrate_password_if_needed(conn, row[0], pw.value)
                                    conn.close()
                                    logic.login_user(_session(), email.value.strip().lower(), row[1], row[0])
                                    ui.notify(_("Willkommen, {name}!").format(name=row[1]), type="positive")
                                    ui.navigate.to("/candidate")
                                else:
                                    msg.text = _("Unbekannte E-Mail oder falsches Passwort.")
                                    conn.close()

                            ui.button(_("Einloggen"), icon="login", on_click=do_login).classes(C.BTN_PRIMARY + " w-full mt-2")

                        # ── Candidate Register ───────────────────────────
                        with ui.tab_panel(_("Registrieren")):
                            ui.label(_("Neues Konto erstellen")).classes(C.CARD_TITLE + " mb-4")
                            r_email = ui.input(
                                _("E-Mail"),
                                placeholder=_("name@beispiel.de"),
                                validation={_("E-Mail gueltig"): lambda v: "@" in v and "." in v},
                            ).classes("w-full")
                            r_name = ui.input(_("Name"), placeholder=_("Vor- und Nachname")).classes("w-full")
                            r_pw = ui.input(
                                _("Passwort"),
                                password=True,
                                placeholder=_("Mindestens 8 Zeichen"),
                                validation={_("Mindestens 8 Zeichen"): lambda v: len(v) >= 8},
                            ).classes("w-full")
                            r_msg = ui.label("").classes("text-sm")

                            async def do_register():
                                if not r_email.value or not r_pw.value:
                                    r_msg.text = _("E-Mail und Passwort sind Pflichtfelder.")
                                    r_msg.classes(replace="text-red-400 text-sm")
                                    return
                                if len(r_pw.value) < 8:
                                    r_msg.text = _("Passwort muss mindestens 8 Zeichen lang sein.")
                                    r_msg.classes(replace="text-red-400 text-sm")
                                    return
                                conn = db.get_conn()
                                try:
                                    conn.execute(
                                        "INSERT INTO candidates (email, name, password_hash, status) VALUES (?, ?, ?, 'registriert')",
                                        (
                                            r_email.value.strip().lower(),
                                            r_name.value.strip(),
                                            logic.hash_password_argon2id(r_pw.value),
                                        ),
                                    )
                                    conn.commit()
                                    r_msg.text = _("Registriert! Jetzt einloggen.")
                                    r_msg.classes(replace="text-green-400 text-sm")
                                except sqlite3.IntegrityError:
                                    r_msg.text = _("E-Mail bereits registriert.")
                                    r_msg.classes(replace="text-red-400 text-sm")
                                finally:
                                    conn.close()

                            ui.button(_("Registrieren"), icon="person_add", on_click=do_register).classes(C.BTN_PRIMARY + " w-full mt-2")

                        # ── Employer Login ───────────────────────────────
                        with ui.tab_panel(_("Arbeitgeber")):
                            ui.label(_("Arbeitgeber-Login")).classes(C.CARD_TITLE + " mb-4")
                            e_email = ui.input(
                                _("E-Mail"),
                                validation={_("E-Mail gueltig"): lambda v: "@" in v and "." in v},
                            ).classes("w-full")
                            e_pw = ui.input(
                                _("Passwort"),
                                password=True,
                                validation={_("Mindestens 8 Zeichen"): lambda v: len(v) >= 8},
                            ).classes("w-full")
                            e_msg = ui.label("").classes("text-red-400 text-sm")

                            async def do_employer_login():
                                if not e_email.value or not e_pw.value:
                                    e_msg.text = _("E-Mail und Passwort sind Pflichtfelder.")
                                    return
                                conn = db.get_conn()
                                row = conn.execute(
                                    "SELECT id, firma, password_hash FROM employers WHERE email = ?",
                                    (e_email.value.strip().lower(),),
                                ).fetchone()
                                conn.close()
                                if row and logic.verify_password_argon2id(e_pw.value, row[2]):
                                    logic.login_employer(_session(), row[0], e_email.value.strip().lower(), row[1])
                                    ui.notify(_("Willkommen, {name}!").format(name=row[1]), type="positive")
                                    ui.navigate.to("/employer")
                                else:
                                    e_msg.text = _("Login fehlgeschlagen.")

                            ui.button(_("Arbeitgeber-Login"), icon="business", on_click=do_employer_login).classes(C.BTN_PRIMARY + " w-full mt-2")

                        # ── Employer Register ────────────────────────────
                        with ui.tab_panel(_("Arbeitgeber+")):
                            ui.label(_("Arbeitgeber registrieren")).classes(C.CARD_TITLE + " mb-4")
                            er_email = ui.input(
                                _("Firmen-E-Mail"),
                                validation={_("E-Mail gueltig"): lambda v: "@" in v and "." in v},
                            ).classes("w-full")
                            er_firma = ui.input(_("Firma")).classes("w-full")
                            er_kontakt = ui.input(_("Kontaktperson")).classes("w-full")
                            er_pw = ui.input(
                                _("Passwort"),
                                password=True,
                                placeholder=_("Mindestens 8 Zeichen"),
                                validation={_("Mindestens 8 Zeichen"): lambda v: len(v) >= 8},
                            ).classes("w-full")
                            er_msg = ui.label("").classes("text-sm")

                            async def do_employer_register():
                                if not er_email.value or not er_firma.value or not er_kontakt.value or not er_pw.value:
                                    er_msg.text = _("Alle Felder sind Pflichtfelder.")
                                    er_msg.classes(replace="text-red-400 text-sm")
                                    return
                                if len(er_pw.value) < 8:
                                    er_msg.text = _("Passwort muss mindestens 8 Zeichen lang sein.")
                                    er_msg.classes(replace="text-red-400 text-sm")
                                    return
                                conn = db.get_conn()
                                try:
                                    conn.execute(
                                        "INSERT INTO employers (email, password_hash, firma, kontaktperson) VALUES (?, ?, ?, ?)",
                                        (
                                            er_email.value.strip().lower(),
                                            logic.hash_password_argon2id(er_pw.value),
                                            er_firma.value.strip(),
                                            er_kontakt.value.strip(),
                                        ),
                                    )
                                    conn.commit()
                                    er_msg.text = _("Registriert! Jetzt einloggen.")
                                    er_msg.classes(replace="text-green-400 text-sm")
                                except sqlite3.IntegrityError:
                                    er_msg.text = _("E-Mail bereits registriert.")
                                    er_msg.classes(replace="text-red-400 text-sm")
                                finally:
                                    conn.close()

                            ui.button(_("Als Arbeitgeber registrieren"), icon="business", on_click=do_employer_register).classes(C.BTN_PRIMARY + " w-full mt-2")

                        # ── Admin Login ──────────────────────────────────
                        with ui.tab_panel(_("Admin")):
                            ui.label(_("Admin-Login")).classes(C.CARD_TITLE + " mb-4")
                            a_email = ui.input(
                                _("Admin-E-Mail"),
                                validation={_("E-Mail gueltig"): lambda v: "@" in v and "." in v},
                            ).classes("w-full")
                            a_pw = ui.input(
                                _("Passwort"),
                                password=True,
                                validation={_("Mindestens 8 Zeichen"): lambda v: len(v) >= 8},
                            ).classes("w-full")
                            a_msg = ui.label("").classes("text-red-400 text-sm")

                            async def do_admin_login():
                                if not a_email.value or not a_pw.value:
                                    a_msg.text = _("E-Mail und Passwort sind Pflichtfelder.")
                                    return
                                conn = db.get_conn()
                                if conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0] == 0:
                                    from webui.logic import hash_password_argon2id
                                    # P1-10 (30.09.2026, sicherheitsrelevant, Nutzer-GO):
                                    # Seed-Zugangsdaten standen im Klartext im Code.
                                    # KMHR_ADMIN_SEED_EMAIL / KMHR_ADMIN_SEED_PASSWORD
                                    # R3-4 (30.09.2026, Nutzer-GO): Das Startup-Gate in
                                    # webui.main erzwingt KMHR_ADMIN_SEED_PASSWORD jetzt
                                    # VOR dem Serverstart — dieser Klartext-Default ist
                                    # nur noch unter KMHR_DEV=1 erreichbar, sonst
                                    # Abbruch (SystemExit(1)). Spec:
                                    # knowledge/system/configuration-secrets.md.
                                    # Design-Entscheidung: Default bleibt, damit der
                                    # Erstlogin nicht blockiert, wird aber bei jedem
                                    # Seed auf stderr gewarnt.
                                    _seed_email = os.environ.get(
                                        "KMHR_ADMIN_SEED_EMAIL",
                                        "admin@km-hr-agent.local").strip().lower()
                                    _seed_pw = os.environ.get(
                                        "KMHR_ADMIN_SEED_PASSWORD", "admin-agent-2026")
                                    if not os.environ.get("KMHR_ADMIN_SEED_PASSWORD"):
                                        print(
                                            "[webui] WARNUNG: KMHR_ADMIN_SEED_PASSWORD ist nicht "
                                            "gesetzt — der Seed-Account wird mit dem "
                                            "Entwicklungs-Default angelegt.",
                                            file=sys.stderr,
                                        )
                                    conn.execute(
                                        "INSERT INTO admins (email, password_hash, name) VALUES (?, ?, ?)",
                                        (_seed_email, hash_password_argon2id(_seed_pw),
                                         "Betreiber (Seed)"),
                                    )
                                    conn.commit()
                                row = conn.execute(
                                    "SELECT id, email, password_hash FROM admins WHERE email = ?",
                                    (a_email.value.strip().lower(),),
                                ).fetchone()
                                conn.close()
                                if row and logic.verify_password_argon2id(a_pw.value, row[2]):
                                    logic.login_admin(_session(), row[0], row[1])
                                    ui.notify(_("Admin angemeldet"), type="positive")
                                    ui.navigate.to("/admin")
                                else:
                                    a_msg.text = _("Admin-Login fehlgeschlagen.")

                            ui.button(_("Admin-Login"), icon="shield", on_click=do_admin_login).classes(C.BTN_PRIMARY + " w-full mt-2")
