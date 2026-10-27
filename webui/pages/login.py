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
from uuid import uuid4

from nicegui import run, ui

from webui import db, logic
from webui.theme import C
from webui.i18n import _, apply_direction, get_language, language_switcher


def _session() -> dict:
    from nicegui import app
    return app.storage.user


def _reset_token_param() -> str | None:
    """/login?reset=<token> der Seiten-Anfrage (NiceGUI 3.17.1: die Starlette-Request
    des Seitenaufrufs haengt an `ui.context.client.request`). None, wenn kein Token
    mitgegeben wurde (Muster: employer.py::_kandidat_query_param)."""
    try:
        from nicegui import context as _ng_context
        req = _ng_context.client.request
        raw = req.query_params.get("reset")
        return str(raw).strip() if raw else None
    except Exception:
        return None


def _consent_checkbox() -> ui.checkbox:
    """Pflicht-Einwilligung in AGB + Datenschutzerklaerung (Purposes `terms`/`privacy`).

    NICHT vorangehakt: Art. 7 Abs. 2 DSGVO / Erwaegungsgrund 32+43 — ein bereits
    angekreuztes Kaestchen ist keine Einwilligung, und AGB/Datenschutz duerfen
    nicht mit der Aufnahme-Einwilligung gebuendelt werden (die holt
    `webui/pages/candidate.py` separat vor dem Videolink ein).

    Der Nachweis wird NACH dem INSERT vom Aufrufer geschrieben
    (`db.record_consent(..., text_version=db.CONSENT_VERSION)`); die Checkbox
    selbst speichert nichts.
    """
    cb = ui.checkbox(
        _("Ich akzeptiere die AGB und die Datenschutzerklärung"),
        value=False,
    ).classes("text-sm text-gray-800 dark:text-gray-200")
    with ui.row().classes("items-center gap-2 -mt-2 text-xs"):
        ui.link(_("AGB"), "/agb").classes("text-amber-800 dark:text-amber-300")
        ui.label("·").classes("text-gray-500")
        ui.link(_("Datenschutz"), "/datenschutz").classes("text-amber-800 dark:text-amber-300")
    return cb


def _record_registration_consents(subject_type: str, subject_id: int, language: str) -> None:
    """Schreibt die beiden Pflicht-Nachweise (`terms`, `privacy`) fuer ein neues Konto.

    Eine Zeile je Zweck (Art. 7 Abs. 2 DSGVO: getrennte Einwilligungen).
    `db.record_consent` committet selbst — der Aufrufer hat sein INSERT bereits
    committet, damit `subject_id` (= cursor.lastrowid) gueltig ist.
    """
    for purpose in ("terms", "privacy"):
        db.record_consent(
            subject_type,
            subject_id,
            purpose,
            text_version=db.CONSENT_VERSION,
            language=language,
        )


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
                /* Mobil: Orbs ausblenden, Login-Container und Tab-Strip auf Viewport-Breite begrenzen. */
                @media (max-width: 768px) {
                    .login-container { overflow-x: hidden; width: 100%; min-width: 0; max-width: 100%; }
                    .login-orb { display: none; }
                    .login-container .q-tabs { max-width: 100%; overflow-x: auto; }
                    .login-container .q-tab { flex: 0 0 auto; }
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
                                def _migrate_pw(user_id, password):
                                    # P2: argon2-Hash im Worker-Thread; DB-Verbindung im Thread neu erzeugen (check_same_thread).
                                    c = db.get_conn()
                                    try:
                                        logic.migrate_password_if_needed(c, user_id, password)
                                    finally:
                                        c.close()

                                if await run.io_bound(logic.verify_password_argon2id, pw.value, row[2]) or logic.verify_password_sha256(pw.value, row[2]):
                                    await run.io_bound(_migrate_pw, row[0], pw.value)
                                    conn.close()
                                    logic.login_user(_session(), email.value.strip().lower(), row[1], row[0])
                                    ui.notify(_("Willkommen, {name}!").format(name=row[1]), type="positive")
                                    ui.navigate.to("/candidate")
                                else:
                                    msg.text = _("Unbekannte E-Mail oder falsches Passwort.")
                                    conn.close()

                            ui.button(_("Einloggen"), icon="login", on_click=do_login).classes(C.BTN_PRIMARY + " w-full mt-2")
                            ui.button(_("Passwort vergessen?"), on_click=lambda: _open_forgot("candidate")).props("flat dense").classes("text-amber-800 text-xs mt-1")

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
                            # Pflicht-Einwilligung (nicht vorangehakt) — Nachweis nach dem INSERT.
                            r_consent = _consent_checkbox()
                            r_msg = ui.label("").classes("text-sm")

                            async def do_register():
                                if not r_email.value or not r_pw.value:
                                    r_msg.text = _("E-Mail und Passwort sind Pflichtfelder.")
                                    r_msg.classes(replace="text-red-400 text-sm")
                                    return
                                if not r_consent.value:
                                    r_msg.text = _("Bitte akzeptieren Sie AGB und Datenschutzerklärung, um sich zu registrieren.")
                                    r_msg.classes(replace="text-red-400 text-sm")
                                    return
                                if len(r_pw.value) < 8:
                                    r_msg.text = _("Passwort muss mindestens 8 Zeichen lang sein.")
                                    r_msg.classes(replace="text-red-400 text-sm")
                                    return
                                conn = db.get_conn()
                                try:
                                    _pw_hash = await run.io_bound(logic.hash_password_argon2id, r_pw.value)
                                    cur = conn.execute(
                                        "INSERT INTO candidates (email, name, password_hash, status) VALUES (?, ?, ?, 'registriert')",
                                        (
                                            r_email.value.strip().lower(),
                                            r_name.value.strip(),
                                            _pw_hash,
                                        ),
                                    )
                                    conn.commit()
                                    _record_registration_consents(
                                        "candidate", cur.lastrowid, get_language())
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
                                if row and await run.io_bound(logic.verify_password_argon2id, e_pw.value, row[2]):
                                    logic.login_employer(_session(), row[0], e_email.value.strip().lower(), row[1])
                                    ui.notify(_("Willkommen, {name}!").format(name=row[1]), type="positive")
                                    ui.navigate.to("/employer")
                                else:
                                    e_msg.text = _("Login fehlgeschlagen.")

                            ui.button(_("Arbeitgeber-Login"), icon="business", on_click=do_employer_login).classes(C.BTN_PRIMARY + " w-full mt-2")
                            ui.button(_("Passwort vergessen?"), on_click=lambda: _open_forgot("employer")).props("flat dense").classes("text-amber-800 text-xs mt-1")

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
                            # Pflicht-Einwilligung (nicht vorangehakt) — Nachweis nach dem INSERT.
                            er_consent = _consent_checkbox()
                            er_msg = ui.label("").classes("text-sm")

                            async def do_employer_register():
                                if not er_email.value or not er_firma.value or not er_kontakt.value or not er_pw.value:
                                    er_msg.text = _("Alle Felder sind Pflichtfelder.")
                                    er_msg.classes(replace="text-red-400 text-sm")
                                    return
                                if not er_consent.value:
                                    er_msg.text = _("Bitte akzeptieren Sie AGB und Datenschutzerklärung, um sich zu registrieren.")
                                    er_msg.classes(replace="text-red-400 text-sm")
                                    return
                                if len(er_pw.value) < 8:
                                    er_msg.text = _("Passwort muss mindestens 8 Zeichen lang sein.")
                                    er_msg.classes(replace="text-red-400 text-sm")
                                    return
                                conn = db.get_conn()
                                try:
                                    _er_pw_hash = await run.io_bound(logic.hash_password_argon2id, er_pw.value)
                                    cur = conn.execute(
                                        "INSERT INTO employers (email, password_hash, firma, kontaktperson) VALUES (?, ?, ?, ?)",
                                        (
                                            er_email.value.strip().lower(),
                                            _er_pw_hash,
                                            er_firma.value.strip(),
                                            er_kontakt.value.strip(),
                                        ),
                                    )
                                    conn.commit()
                                    _record_registration_consents(
                                        "employer", cur.lastrowid, get_language())
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
                                    _seed_hash = await run.io_bound(hash_password_argon2id, _seed_pw)
                                    conn.execute(
                                        "INSERT INTO admins (email, password_hash, name) VALUES (?, ?, ?)",
                                        (_seed_email, _seed_hash,
                                         "Betreiber (Seed)"),
                                    )
                                    conn.commit()
                                row = conn.execute(
                                    "SELECT id, email, password_hash FROM admins WHERE email = ?",
                                    (a_email.value.strip().lower(),),
                                ).fetchone()
                                conn.close()
                                if row and await run.io_bound(logic.verify_password_argon2id, a_pw.value, row[2]):
                                    logic.login_admin(_session(), row[0], row[1])
                                    ui.notify(_("Admin angemeldet"), type="positive")
                                    ui.navigate.to("/admin")
                                else:
                                    a_msg.text = _("Admin-Login fehlgeschlagen.")

                            ui.button(_("Admin-Login"), icon="shield", on_click=do_admin_login).classes(C.BTN_PRIMARY + " w-full mt-2")

        # ── Passwort-Reset (18.10.2026) — Kandidat + Arbeitgeber ─────────
        # Spec: knowledge/system/configuration-secrets.md §(g). Der Admin-Tab
        # hat BEWUSST keinen Reset (Nutzerentscheidung R6-2.1 abgelehnt).
        _reset_ctx = {"role": "candidate", "token": None}

        def _open_forgot(role: str) -> None:
            _reset_ctx["role"] = role
            forgot_email.value = ""
            forgot_msg.text = ""
            forgot_dialog.open()

        async def _do_forgot() -> None:
            email_val = (forgot_email.value or "").strip()
            if "@" not in email_val or "." not in email_val:
                forgot_msg.text = _("Bitte eine gueltige E-Mail eingeben.")
                forgot_msg.classes(replace="text-red-400 text-sm")
                return
            # Generische Antwort IMMER gleich (kein Enumeration-Loch): ob ein Konto
            # existiert und ob das Rate-Limit greift, entscheidet der Agent-Runner.
            db.queue_agent_task("send_password_reset", {
                "email": email_val,
                "role": _reset_ctx["role"],
                "req": uuid4().hex,
            })
            forgot_msg.text = _("Wenn ein Konto mit dieser E-Mail existiert, ist der Link unterwegs.")
            forgot_msg.classes(replace="text-green-400 text-sm")

        async def _do_reset() -> None:
            token = _reset_ctx.get("token")
            if not reset_pw1.value or not reset_pw2.value:
                reset_msg.text = _("Bitte alle Felder ausfuellen.")
                reset_msg.classes(replace="text-red-400 text-sm")
                return
            if reset_pw1.value != reset_pw2.value:
                reset_msg.text = _("Passwoerter stimmen nicht ueberein.")
                reset_msg.classes(replace="text-red-400 text-sm")
                return
            ok, code = await run.io_bound(logic.apply_password_reset, token, reset_pw1.value)
            texte = {
                "ok": _("Passwort neu gesetzt. Bitte einloggen."),
                "invalid": _("Ungueltiger oder abgelaufener Reset-Link."),
                "too_short": _("Passwort muss mindestens 8 Zeichen lang sein."),
                "same_as_old": _("Neues Passwort darf nicht dem alten Passwort entsprechen."),
            }
            reset_msg.text = texte.get(code, texte["invalid"])
            reset_msg.classes(replace=("text-green-400 text-sm" if ok else "text-red-400 text-sm"))
            if ok:
                reset_dialog.close()
                ui.notify(_("Passwort neu gesetzt. Bitte einloggen."), type="positive")

        with ui.dialog() as forgot_dialog, ui.card().classes("glass-strong w-full max-w-md"):
            ui.label(_("Passwort vergessen?")).classes(C.CARD_TITLE + " mb-2")
            ui.label(_("Geben Sie Ihre E-Mail ein. Wenn ein Konto existiert, senden wir einen Link zum Zuruecksetzen.")).classes("text-sm mb-2")
            forgot_email = ui.input(_("E-Mail"), placeholder=_("name@beispiel.de")).classes("w-full")
            forgot_msg = ui.label("").classes("text-sm")
            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button(_("Abbrechen"), on_click=forgot_dialog.close).props("flat")
                ui.button(_("Link senden"), on_click=_do_forgot).props("unelevated").classes(C.BTN_PRIMARY)

        with ui.dialog() as reset_dialog, ui.card().classes("glass-strong w-full max-w-md"):
            ui.label(_("Neues Passwort vergeben")).classes(C.CARD_TITLE + " mb-2")
            reset_pw1 = ui.input(_("Neues Passwort"), password=True,
                                 placeholder=_("Mindestens 8 Zeichen")).classes("w-full")
            reset_pw2 = ui.input(_("Neues Passwort wiederholen"), password=True).classes("w-full")
            reset_msg = ui.label("").classes("text-sm")
            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button(_("Abbrechen"), on_click=reset_dialog.close).props("flat")
                ui.button(_("Passwort speichern"), on_click=_do_reset).props("unelevated").classes(C.BTN_PRIMARY)

        # /login?reset=<token> → Reset-Dialog automatisch oeffnen
        _tok = _reset_token_param()
        if _tok:
            _reset_ctx["token"] = _tok
            ui.timer(0.3, reset_dialog.open, once=True)
