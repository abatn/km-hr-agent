"""
Admin pages for KM-HR-Agent NiceGUI App.
11 pages: Dashboard + Agent-Tools (0-5) + Portal pages.
"""
from __future__ import annotations

import json
from pathlib import Path

from nicegui import run, ui

from webui import db, logic
from webui.i18n import _  # S3 (12.10.2026); Spec: knowledge/system/i18n.md
from webui.theme import C, PRIMARY, SECONDARY, ACCENT, DANGER
from webui.components import (
    stat_card, status_badge, data_table, empty_state, section_header, export_candidates_pdf, info_row,
    navigate_to, prescreen_recruiting_section, onboarding_generator_section, skill8_feedback_section,
    visa_info_section,
)

# N-S2 (01.10.2026): EINZIGE Whitelist-Quelle der Statusuebergaenge liegt in
# employer.py (ALLOWED_TRANSITIONS, Quelle: knowledge/lifecycle/application-status.md
# „Erlaubte Übergänge“) — die Admin-Stellen-Seite liest dieselbe Konstante/Funktion
# statt einer eigenen erl-Kopie (Lab-Prinzip Schritt 3: keine Inkonsistenz).
from webui.pages.employer import ALLOWED_TRANSITIONS, _legal_actions

TESTDATEN = Path(__file__).resolve().parent.parent.parent / "testdaten"


def _session() -> dict:
    from nicegui import app
    return app.storage.user


def _count(table: str) -> int:
    try:
        conn = db.get_conn()
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0


def _latest_result_language(task_type: str) -> str | None:
    """S4b (12.10.2026): Sprache des letzten Task-Ergebnisses.

    Liest defensiv `result_json["language"]` der letzten Task vom Typ `task_type`
    (fehlender Task/Spalte/Key oder ungueltiges JSON -> None). Nur Lesen; keine
    Rueckuebersetzung, kein Parsen des MD-Inhalts.
    """
    if not task_type:
        return None
    conn = None
    try:
        conn = db.get_conn()
        row = conn.execute(
            "SELECT result_json FROM agent_tasks WHERE task_type = ? "
            "ORDER BY id DESC LIMIT 1",
            (task_type,),
        ).fetchone()
        if not row or not row[0]:
            return None
        data = json.loads(row[0])
        if isinstance(data, dict):
            lang = data.get("language")
            if isinstance(lang, str) and lang.strip():
                return lang
    except Exception:
        return None
    finally:
        if conn is not None:
            conn.close()
    return None


# ─── Pages ───────────────────────────────────────────────────────────

def tool_result_section(glob_pat: str, task_label: str, task_type: str = "") -> None:
    """C6 (22.09.2026): Ergebnis-Anzeige + Download je Admin-Tool.

    Paritaet zu Streamlit st.download_button (app.py:1378/1531/1641/1734/1851):
    Streamlit zeigt das frisch generierte MD inline + Download-Button. NiceGUI
    loest asynchron ueber die Agent-Queue aus — das Artefakt schreibt der
    Runner nach ergebnisse/ (agent-automation.md) und wird hier angezeigt.
    """
    files = sorted(logic.ERGEBNISSE.glob(glob_pat))
    with ui.card().classes(C.CARD + " w-full mt-3"):
        ui.label(_("Ergebnis: {0}").format(task_label)).classes(C.CARD_TITLE)
        if not files:
            ui.label(_("Noch kein Ergebnis vorhanden – Task unten ausloesen, der Runner schreibt das MD nach ergebnisse/.")).classes(C.MUTED)
            return
        latest = files[-1]
        content = latest.read_text(encoding="utf-8", errors="replace")
        ui.label(latest.name).classes(C.SMALL)
        # S4b (12.10.2026): minimaler Sprach-Badge, nur wenn result_json sie mitgibt.
        _lang = _latest_result_language(task_type)
        if _lang:
            ui.badge(_("Sprache: {0}").format(_lang.upper())).props("color=blue-1 outline")
        with ui.expansion(text=_("Vorschau")).classes("w-full"):
            ui.markdown(content)
        ui.button(
            _("Herunterladen"), icon="download",
            # Default-Args binden den Closure-Wert (C1-Lesson: Late-Binding)
            on_click=lambda _c=content, _n=latest.name: ui.download(
                _c.encode("utf-8"), _n, "text/markdown"
            ),
        ).classes(C.BTN_PRIMARY + " mt-2")


def _page_dashboard(s: dict) -> None:
    section_header(title=_("Admin Dashboard"), subtitle=_("System-Uebersicht"), icon="dashboard")

    tables = [
        (_("Kandidaten"), "candidates"),
        (_("Arbeitgeber"), "employers"),
        (_("Stellen"), "jobs"),
        (_("Bewerbungen"), "applications"),
        (_("Feedback"), "feedback"),
        (_("Agent-Tasks"), "agent_tasks"),
        (_("Dokumente"), "candidate_documents"),
        (_("Sprachtests"), "language_tests"),
        (_("Gewichtung"), "gewichtung_historie"),
    ]

    with ui.grid(columns=3).classes(C.GRID_3):
        for label, tbl in tables:
            stat_card(label, _count(tbl), "storage", color=PRIMARY)

    # ─── Admin Charts ───────────────────────────────────────────────────
    try:
        conn = db.get_conn()

        # Agent-Tasks nach Status (Pie Chart)
        task_rows = conn.execute("""
            SELECT status, COUNT(*) as cnt
            FROM agent_tasks
            GROUP BY status
        """).fetchall()
        if task_rows:
            task_data = [{"value": r[1], "name": r[0] or _("unbekannt")} for r in task_rows]
            with ui.card().classes(C.CARD + " w-full mt-4"):
                ui.label(_("Agent-Tasks nach Status")).classes(C.CARD_TITLE + " mb-2")
                ui.echart({
                    "title": {"text": _("Task-Verteilung"), "left": "center"},
                    "tooltip": {"trigger": "item"},
                    "legend": {"orient": "vertical", "left": "left"},
                    "series": [{
                        "type": "pie",
                        "radius": "50%",
                        "data": task_data,
                        "emphasis": {
                            "itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0, 0, 0, 0.5)"}
                        }
                    }]
                }).classes("w-full h-64")

        # Bewerbungen pro Monat (Balken-Charts)
        app_rows = conn.execute("""
            SELECT strftime('%Y-%m', erstellungsdatum) as monat, COUNT(*) as cnt
            FROM applications
            WHERE erstellungsdatum IS NOT NULL
            GROUP BY monat
            ORDER BY monat DESC
            LIMIT 6
        """).fetchall()
        if app_rows:
            app_rows_rev = list(reversed(app_rows))
            months = [r[0] or "?" for r in app_rows_rev]
            counts = [r[1] for r in app_rows_rev]
            with ui.card().classes(C.CARD + " w-full mt-4"):
                ui.label(_("Bewerbungen pro Monat")).classes(C.CARD_TITLE + " mb-2")
                ui.echart({
                    "title": {"text": _("Bewerbungen"), "left": "center"},
                    "xAxis": {"type": "category", "data": months},
                    "yAxis": {"type": "value"},
                    "series": [{"data": counts, "type": "bar", "itemStyle": {"color": "#3B82F6"}}]
                }).classes("w-full h-64")

        conn.close()
    except Exception:
        pass

    # PDF Export
    with ui.card().classes(C.CARD + " w-full mt-4"):
        ui.label(_("Daten exportieren")).classes(C.CARD_TITLE + " mb-3")
        ui.label(_("Kandidaten-Liste als PDF herunterladen.")).classes(C.SMALL + " mb-3")
        ui.button(_("PDF Export"), icon="picture_as_pdf", on_click=lambda: export_candidates_pdf()).classes(C.BTN_PRIMARY)

    # ── Passwort ändern (N5) ──
    with ui.expansion(_("Passwort aendern"), icon="lock").classes("w-full mt-4"):
        pw_alt = ui.input(label=_("Aktuelles Passwort"), password=True).classes("w-full")
        pw_neu = ui.input(label=_("Neues Passwort"), password=True).classes("w-full")
        pw_wdh = ui.input(label=_("Neues Passwort wiederholen"), password=True).classes("w-full")

        async def do_change_pw_admin():
            # P2 (05.10.2026): change_password enthält bis zu 3 argon2-Ops
            # (0,4–1,2 s je Op) → Worker-Thread (NiceGUI-FAQ run.io_bound).
            # SQLite-Verbindung darf die Thread-Grenze nicht überschreiten
            # (check_same_thread) → im Worker erzeugt (Design-Entscheidung).
            if not pw_alt.value or not pw_neu.value or not pw_wdh.value:
                ui.notify(_("Bitte alle Felder ausfuellen."), type="warning")
                return
            if pw_neu.value != pw_wdh.value:
                ui.notify(_("Passwoerter stimmen nicht ueberein."), type="negative")
                return

            def _work():
                conn_pw = db.get_conn()
                try:
                    admin_id = conn_pw.execute(
                        "SELECT id FROM admins WHERE email = ?", (s.get("admin_email", ""),)
                    ).fetchone()
                    if not admin_id:
                        return (None, None)
                    return logic.change_password(
                        conn_pw, "admins", admin_id[0], pw_alt.value, pw_neu.value)
                finally:
                    conn_pw.close()

            ok, msg = await run.io_bound(_work)
            if ok is None:
                ui.notify(_("Admin nicht gefunden."), type="negative")
            else:
                ui.notify(_(msg), type="positive" if ok else "negative")

        ui.button(_("Passwort aendern"), on_click=do_change_pw_admin).classes(C.BTN_PRIMARY + " mt-2")


def _page_upload(s: dict) -> None:
    section_header(title=_("Upload (Ingestion)"), subtitle=_("Lebenslaeufe hochladen"), icon="cloud_upload")

    with ui.card().classes(C.CARD):
        ui.label(_("Lebenslauf oder Stellenprofil hochladen")).classes(C.CARD_TITLE)
        ui.label(_("PDF- und TXT-Dateien werden in testdaten/ gespeichert und dem Agenten zur Extraktion zugeführt.")).classes(C.SMALL)

        async def _on_upload(e):
            try:
                fname = e.file.name or "upload"
                content = await e.file.read()
            except Exception as ex:
                ui.notify(_("Upload fehlgeschlagen: {0}").format(ex), type="negative")
                return
            if not content:
                ui.notify(_("Keine Datei empfangen."), type="warning")
                return

            save_path = TESTDATEN / fname
            save_path.parent.mkdir(parents=True, exist_ok=True)

            # Bytes (NiceGUI async read; Paritaet app.py:1246 cv_file.getvalue())
            save_path.write_bytes(content)

            ui.notify(_("Gespeichert: {0}").format(fname), type="positive")

            # Queue extract_profile if it is a CV (notstellenprofil)
            if "stellenprofil" not in fname.lower():
                tid = db.queue_agent_task(
                    "extract_profile", {"quelle": fname, "datei_pfad": str(save_path)}
                )
                if tid:
                    ui.notify(_("Extract-Task #{0} gequeued").format(tid), type="positive")
                else:
                    ui.notify(_("Bereits heute gequeued oder Fehler."), type="warning")

        upload = ui.upload(label=_("Datei auswaehlen"), on_upload=_on_upload, auto_upload=True, max_file_size=5_000_000)

    with ui.card().classes(C.CARD):
        ui.label(_("Vorhandene Dateien")).classes(C.CARD_TITLE)
        cv_files = sorted(TESTDATEN.glob("*.txt")) + sorted(TESTDATEN.glob("*.pdf"))
        if cv_files:
            for f in cv_files:
                ui.label(f.name).classes(C.SMALL)
        else:
            ui.label(_("Keine Dateien vorhanden.")).classes(C.MUTED)


def _page_extract(s: dict) -> None:
    section_header(title=_("Extract Profile"), subtitle=_("Skill 1 - Profil-Extraktion"), icon="badge")
    tool_result_section("extract_profile-*.md", _("Extract Profile"), "extract_profile")

    with ui.card().classes(C.CARD):
        ui.label(_("Profil-Extraktion aus Lebenslaeufen")).classes(C.CARD_TITLE)
        ui.label(_("Kandidaten ohne extrahiertes Profil (hard_skills IS NULL) werden dem Agenten zur Profil-Extraktion zugeführt.")).classes(C.SMALL)

        conn = db.get_conn()
        rows = conn.execute(
            "SELECT id, name, email, lebenslauf_datei FROM candidates WHERE hard_skills IS NULL AND lebenslauf_datei IS NOT NULL ORDER BY id DESC LIMIT 30"
        ).fetchall()
        conn.close()

        if not rows:
            empty_state(icon="badge", title=_("Keine Kandidaten ohne Profil"), description=_("Alle Kandidaten haben bereits ein extrahiertes Profil."))
            return

        columns = [
            {"name": "id", "label": "#", "field": "id"},
            {"name": "name", "label": _("Name"), "field": "name"},
            {"name": "email", "label": _("E-Mail"), "field": "email"},
            {"name": "datei", "label": _("Lebenslauf"), "field": "datei"},
        ]
        table_rows = [{"id": r[0], "name": r[1], "email": r[2], "datei": r[3] or "--"} for r in rows]
        data_table(columns=columns, rows=table_rows, title=_("{0} Kandidaten ohne Profil").format(len(rows)))

        def _extract_all():
            queued = 0
            for r in rows:
                tid = db.queue_agent_task("extract_profile", {
                    "candidate_id": r[0],
                    "name": r[1],
                    "quelle": r[3] or "",
                })
                if tid:
                    queued += 1
            ui.notify(_("{0} Extract-Tasks gequeued").format(queued), type="positive") if queued else ui.notify(_("Keine Tasks gequeued (bereits aktiv oder Fehler)."), type="warning")

        with ui.dialog() as extract_dialog, ui.card().classes("w-96"):
            ui.label(_("Tasks starten?")).classes("text-lg font-bold mb-4")
            ui.label(_("Moechtest du {0} Extract-Tasks wirklich starten?").format(len(rows))).classes("mb-2")
            with ui.row().classes("justify-end gap-2 mt-4"):
                ui.button(_("Abbrechen"), on_click=extract_dialog.close)
                ui.button(_("Starten"), on_click=lambda: (
                    _extract_all(),
                    extract_dialog.close(),
                )).classes("bg-blue-700 text-white")

        ui.button(_("Alle {0} extrahieren").format(len(rows)), icon="play_arrow", on_click=extract_dialog.open).classes(C.BTN_PRIMARY)


def _page_match_tool(s: dict) -> None:
    section_header(title=_("Match-Tool"), subtitle=_("Skill 2 - Kandidaten-Matching"), icon="compare_arrows")
    tool_result_section("match_candidate-*.md", _("Match Candidate"), "match_candidate")

    with ui.card().classes(C.CARD):
        ui.label(_("Kandidaten-Matching mit Stellen")).classes(C.CARD_TITLE)
        ui.label(_("Bewerbungen mit Status 'beworben' werden dem Agenten zur Score-Berechnung zugeführt.")).classes(C.SMALL)

        conn = db.get_conn()
        rows = conn.execute("""
            SELECT a.id, a.candidate_id, a.job_id, c.name, j.titel, a.status
            FROM applications a
            JOIN candidates c ON a.candidate_id = c.id
            JOIN jobs j ON a.job_id = j.id
            WHERE a.status IN ('beworben', 'eingegangen')
            ORDER BY a.erstellungsdatum DESC LIMIT 30
        """).fetchall()
        conn.close()

        if not rows:
            empty_state(icon="compare_arrows", title=_("Keine offenen Bewerbungen"), description=_("Keine Bewerbungen mit Status 'beworben' oder 'eingegangen'."))
            return

        columns = [
            {"name": "app_id", "label": _("Bewerbung"), "field": "app_id"},
            {"name": "kandidat", "label": _("Kandidat"), "field": "kandidat"},
            {"name": "stelle", "label": _("Stelle"), "field": "stelle"},
            {"name": "status", "label": _("Status"), "field": "status"},
        ]
        table_rows = [{"app_id": r[0], "kandidat": r[3], "stelle": r[4], "status": r[5]} for r in rows]
        data_table(columns=columns, rows=table_rows, title=_("{0} offene Bewerbungen").format(len(rows)))

        def _match_all():
            queued = 0
            for r in rows:
                tid = db.queue_agent_task("match_candidate", {
                    "application_id": r[0],
                    "candidate_id": r[1],
                    "job_id": r[2],
                })
                if tid:
                    queued += 1
            ui.notify(_("{0} Match-Tasks gequeued").format(queued), type="positive") if queued else ui.notify(_("Keine Tasks gequeued (bereits aktiv oder Fehler)."), type="warning")

        with ui.dialog() as match_dialog, ui.card().classes("w-96"):
            ui.label(_("Tasks starten?")).classes("text-lg font-bold mb-4")
            ui.label(_("Moechtest du {0} Match-Tasks wirklich starten?").format(len(rows))).classes("mb-2")
            with ui.row().classes("justify-end gap-2 mt-4"):
                ui.button(_("Abbrechen"), on_click=match_dialog.close)
                ui.button(_("Starten"), on_click=lambda: (
                    _match_all(),
                    match_dialog.close(),
                )).classes("bg-blue-700 text-white")

        ui.button(_("Alle {0} matchen").format(len(rows)), icon="play_arrow", on_click=match_dialog.open).classes(C.BTN_PRIMARY)


def _page_compliance_tool(s: dict) -> None:
    section_header(title=_("Compliance-Tool"), subtitle=_("Skill 3 - Rechts-Pruefung"), icon="verified")
    tool_result_section("check_compliance-*.md", _("Check Compliance"), "check_compliance")

    with ui.card().classes(C.CARD):
        ui.label(_("Compliance-Pruefung (DSGVO, AGG, BDSG)")).classes(C.CARD_TITLE)
        ui.label(_("Bewerbungen werden dem Agenten zur laenderspezifischen Rechts-Pruefung zugeführt.")).classes(C.SMALL)

        conn = db.get_conn()
        rows = conn.execute("""
            SELECT a.id, a.candidate_id, a.job_id, c.name, j.titel, a.status
            FROM applications a
            JOIN candidates c ON a.candidate_id = c.id
            JOIN jobs j ON a.job_id = j.id
            WHERE a.status IN ('beworben', 'eingegangen', 'match_berechnet')
            ORDER BY a.erstellungsdatum DESC LIMIT 30
        """).fetchall()
        conn.close()

        if not rows:
            empty_state(icon="verified", title=_("Keine Bewerbungen zur Pruefung"), description=_("Keine offenen Bewerbungen gefunden."))
            return

        columns = [
            {"name": "app_id", "label": _("Bewerbung"), "field": "app_id"},
            {"name": "kandidat", "label": _("Kandidat"), "field": "kandidat"},
            {"name": "stelle", "label": _("Stelle"), "field": "stelle"},
            {"name": "status", "label": _("Status"), "field": "status"},
        ]
        table_rows = [{"app_id": r[0], "kandidat": r[3], "stelle": r[4], "status": r[5]} for r in rows]
        data_table(columns=columns, rows=table_rows, title=_("{0} Bewerbungen zur Compliance-Pruefung").format(len(rows)))

        def _compliance_all():
            queued = 0
            for r in rows:
                tid = db.queue_agent_task("check_compliance", {
                    "application_id": r[0],
                    "candidate_id": r[1],
                    "job_id": r[2],
                })
                if tid:
                    queued += 1
            ui.notify(_("{0} Compliance-Tasks gequeued").format(queued), type="positive") if queued else ui.notify(_("Keine Tasks gequeued (bereits aktiv oder Fehler)."), type="warning")

        with ui.dialog() as compliance_dialog, ui.card().classes("w-96"):
            ui.label(_("Tasks starten?")).classes("text-lg font-bold mb-4")
            ui.label(_("Moechtest du {0} Compliance-Tasks wirklich starten?").format(len(rows))).classes("mb-2")
            with ui.row().classes("justify-end gap-2 mt-4"):
                ui.button(_("Abbrechen"), on_click=compliance_dialog.close)
                ui.button(_("Starten"), on_click=lambda: (
                    _compliance_all(),
                    compliance_dialog.close(),
                )).classes("bg-blue-700 text-white")

        ui.button(_("Alle {0} pruefen").format(len(rows)), icon="play_arrow", on_click=compliance_dialog.open).classes(C.BTN_PRIMARY)


def _page_contact(s: dict) -> None:
    section_header(title=_("Contact Candidate"), subtitle=_("Skill 4 - Kontakt"), icon="mail")
    tool_result_section("notify_user-*.md", _("Contact Candidate"), "notify_user")

    with ui.card().classes(C.CARD):
        ui.label(_("Kandidaten kontaktieren")).classes(C.CARD_TITLE)
        ui.label(_("Eingeladene Kandidaten werden dem Agenten zur E-Mail-Generierung zugeführt.")).classes(C.SMALL)

        conn = db.get_conn()
        rows = conn.execute("""
            SELECT a.id, a.candidate_id, a.job_id, c.name, c.email, j.titel, a.status
            FROM applications a
            JOIN candidates c ON a.candidate_id = c.id
            JOIN jobs j ON a.job_id = j.id
            WHERE a.status = 'eingeladen'
            ORDER BY a.aktualisiert_am DESC LIMIT 30
        """).fetchall()
        conn.close()

        if not rows:
            empty_state(icon="mail", title=_("Keine eingeladenen Kandidaten"), description=_("Kandidaten werden nach Einladung durch HR hier angezeigt."))
            return

        columns = [
            {"name": "app_id", "label": _("Bewerbung"), "field": "app_id"},
            {"name": "kandidat", "label": _("Kandidat"), "field": "kandidat"},
            {"name": "email", "label": _("E-Mail"), "field": "email"},
            {"name": "stelle", "label": _("Stelle"), "field": "stelle"},
        ]
        table_rows = [{"app_id": r[0], "kandidat": r[3], "email": r[4], "stelle": r[5]} for r in rows]
        data_table(columns=columns, rows=table_rows, title=_("{0} eingeladene Kandidaten").format(len(rows)))

        def _contact_all():
            queued = 0
            for r in rows:
                tid = db.queue_agent_task("notify_user", {
                    "application_id": r[0],
                    "candidate_id": r[1],
                    "job_id": r[2],
                    "email": r[4],
                    "name": r[3],
                    "typ": "einladung",
                })
                if tid:
                    queued += 1
            ui.notify(_("{0} Kontakt-Tasks gequeued").format(queued), type="positive") if queued else ui.notify(_("Keine Tasks gequeued (bereits aktiv oder Fehler)."), type="warning")

        with ui.dialog() as contact_dialog, ui.card().classes("w-96"):
            ui.label(_("Tasks starten?")).classes("text-lg font-bold mb-4")
            ui.label(_("Moechtest du {0} Kontakt-Tasks wirklich starten?").format(len(rows))).classes("mb-2")
            with ui.row().classes("justify-end gap-2 mt-4"):
                ui.button(_("Abbrechen"), on_click=contact_dialog.close)
                ui.button(_("Starten"), on_click=lambda: (
                    _contact_all(),
                    contact_dialog.close(),
                )).classes("bg-blue-700 text-white")

        ui.button(_("Alle {0} kontaktieren").format(len(rows)), icon="play_arrow", on_click=contact_dialog.open).classes(C.BTN_PRIMARY)


def _page_culture_fit(s: dict) -> None:
    section_header(title=_("Culture Fit"), subtitle=_("Skill 5 - Kultur-Analyse"), icon="psychology")
    tool_result_section("assess_culture_fit-*.md", _("Culture Fit"), "assess_culture_fit")

    with ui.card().classes(C.CARD):
        ui.label(_("Kultur-Fit-Analyse")).classes(C.CARD_TITLE)
        ui.label(_("Bewerbungen werden dem Agenten zur Kultur-Fit-Bewertung (0-100) zugeführt.")).classes(C.SMALL)

        conn = db.get_conn()
        rows = conn.execute("""
            SELECT a.id, a.candidate_id, a.job_id, c.name, j.titel, a.status
            FROM applications a
            JOIN candidates c ON a.candidate_id = c.id
            JOIN jobs j ON a.job_id = j.id
            WHERE a.status IN ('beworben', 'eingegangen', 'match_berechnet')
            ORDER BY a.erstellungsdatum DESC LIMIT 30
        """).fetchall()
        conn.close()

        if not rows:
            empty_state(icon="psychology", title=_("Keine Bewerbungen zur Kultur-Analyse"), description=_("Keine offenen Bewerbungen gefunden."))
            return

        columns = [
            {"name": "app_id", "label": _("Bewerbung"), "field": "app_id"},
            {"name": "kandidat", "label": _("Kandidat"), "field": "kandidat"},
            {"name": "stelle", "label": _("Stelle"), "field": "stelle"},
            {"name": "status", "label": _("Status"), "field": "status"},
        ]
        table_rows = [{"app_id": r[0], "kandidat": r[3], "stelle": r[4], "status": r[5]} for r in rows]
        data_table(columns=columns, rows=table_rows, title=_("{0} Bewerbungen zur Kultur-Analyse").format(len(rows)))

        def _culture_all():
            queued = 0
            for r in rows:
                tid = db.queue_agent_task("assess_culture_fit", {
                    "application_id": r[0],
                    "candidate_id": r[1],
                    "job_id": r[2],
                })
                if tid:
                    queued += 1
            ui.notify(_("{0} Culture-Fit-Tasks gequeued").format(queued), type="positive") if queued else ui.notify(_("Keine Tasks gequeued (bereits aktiv oder Fehler)."), type="warning")

        with ui.dialog() as culture_dialog, ui.card().classes("w-96"):
            ui.label(_("Tasks starten?")).classes("text-lg font-bold mb-4")
            ui.label(_("Moechtest du {0} Culture-Fit-Tasks wirklich starten?").format(len(rows))).classes("mb-2")
            with ui.row().classes("justify-end gap-2 mt-4"):
                ui.button(_("Abbrechen"), on_click=culture_dialog.close)
                ui.button(_("Starten"), on_click=lambda: (
                    _culture_all(),
                    culture_dialog.close(),
                )).classes("bg-blue-700 text-white")

        ui.button(_("Alle {0} analysieren").format(len(rows)), icon="play_arrow", on_click=culture_dialog.open).classes(C.BTN_PRIMARY)


def _page_prescreen(s: dict) -> None:
    section_header(title=_("Pre-Screen"), subtitle=_("Recruiting"), icon="record_voice_over")
    # C7 (22.09.2026): Slot-Stub → Skill-6-Section (Einsicht + Generator, D28)
    prescreen_recruiting_section()


def _page_onboarding(s: dict) -> None:
    section_header(title=_("Onboarding"), subtitle=_("HR"), icon="assignment")
    # C7 (22.09.2026): Slot-Stub → Skill-7-Generator (D28/D29)
    onboarding_generator_section()


def _page_feedback(s: dict) -> None:
    section_header(title=_("Feedback"), subtitle=_("Algorithmus-Feedback"), icon="feedback")
    # C7 (22.09.2026): Slot-Stub → Skill-8 (Cat-Map 'Nicht passend', app.py:2598)
    skill8_feedback_section()


def _page_stellen(s: dict) -> None:
    section_header(title=_("Stellenangebote"), subtitle=_("HR-Write"), icon="work")

    # ── Bewerbungs-Status-Verwaltung (P3.3, Port aus app.py:3075-3202 — wie Employer _page_match) ──
    conn = db.get_conn()
    applications = conn.execute("""
        SELECT a.id, a.candidate_id, a.status, a.bewerbungstext, a.erstellungsdatum,
               j.titel, j.id, e.firma
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        JOIN employers e ON j.employer_id = e.id
        ORDER BY a.erstellungsdatum DESC
    """).fetchall()
    # NICHT hier schließen: conn wird unten noch für die Visum-Count-Abfrage (Spec v6) genutzt

    AKTIV = ("eingegangen", "angesehen", "eingeladen")
    apps_aktiv = [r for r in applications if r[2] in AKTIV]
    apps_archiv = [r for r in applications if r[2] not in AKTIV]
    # N-S2 (01.10.2026): dieselbe Whitelist wie Match-Seite/Stellen-Seite des
    # Arbeitgebers — _legal_actions() aus employer.ALLOWED_TRANSITIONS (Quelle:
    # knowledge/lifecycle/application-status.md „Erlaubte Übergänge“); vorher
    # identisches lokales erl-Dict (Parität app.py:3082).
    badge = {"eingegangen": "📨", "angesehen": "👁️", "eingeladen": "✅", "eingestellt": "🎉",
             "abgelehnt": "❌", "zurückgezogen": "↩️"}
    _hook_task = {"eingeladen": "create_invitation", "abgelehnt": "send_rejection",
                  "eingestellt": "onboarding_release"}

    with ui.expansion(_("📥 Aktive Bewerber ({0})").format(len(apps_aktiv)), icon="how_to_reg").classes("w-full mb-4"):
        if not apps_aktiv:
            empty_state(icon="inbox", title=_("Keine aktiven Bewerbungen"), description=_("Bewerbungen erscheinen hier, sobald Kandidaten sich bewerben."))
        for a_id, k_id, a_status, a_text, a_dat, j_titel, j_id, e_firma in apps_aktiv:
            agent_status = db.get_agent_task_status(a_id) or {}
            _ms = agent_status.get("match_candidate", "-")
            _cs = agent_status.get("check_compliance", "-")
            _fs = agent_status.get("assess_culture_fit", "-")
            badge_txt = _("Match {0} · Compliance {1} · Culture-Fit {2}").format(_ms, _cs, _fs) if agent_status else _("(noch nicht gestartet)")

            with ui.card().classes(C.CARD_HOVER + " w-full mb-2 py-2"):
                with ui.row().classes("items-center justify-between w-full px-4"):
                    with ui.row().classes("items-center gap-3"):
                        ui.label(_("{0} #{1}").format(badge.get(a_status, '📄'), a_id)).classes(C.MUTED)
                        with ui.column():
                            ui.label(_("Kandidat #{0} – {1}").format(k_id, j_titel)).classes("font-medium")
                            ui.label(_("{0} · Eingegangen: {1}").format(e_firma, str(a_dat)[:10])).classes(C.SMALL)
                    with ui.row().classes("items-center gap-2"):
                        status_badge(a_status)
                        ui.badge(f"🤖 {badge_txt}").props("color=blue-1 outline")

                if a_text:
                    ui.label(_("Motivation: {0}").format(a_text[:200])).classes(C.SMALL + " px-4 mt-1")

                naechste = _legal_actions(a_status)
                if naechste:
                    # C1 (22.09.2026): Einladungs-Termin Inline vor → eingeladen
                    # Quelle: app.py:3173-3185 (Payload termin_*, Spec agent-automation.md §5)
                    from datetime import datetime as _dt, timedelta as _timedelta
                    _inv_datum = _inv_zeit = _inv_dauer = None
                    if "eingeladen" in naechste:
                        ui.label(_("📅 Einladungs-Termin (wird in die Automatik-Mail übernommen):")).classes(C.SMALL + " px-4")
                        with ui.row().classes("items-center gap-2 px-4"):
                            # NiceGUI ≥3.3 (offiziell, nicegui.io/documentation/date_input + time_input):
                            # ui.date/time kennen kein label → *_input-Elemente (QInput + Picker)
                            _inv_datum = ui.date_input(_("Datum"), value=str((_dt.now() + _timedelta(days=1)).date())).classes("w-40")
                            _inv_zeit = ui.time_input(_("Uhrzeit"), value="10:00").classes("w-24")
                            _inv_dauer = ui.select([15, 30, 45, 60], value=30, label=_("Dauer (Min.)")).classes("w-32")
                    with ui.row().classes("gap-2 px-4 pb-2"):
                        for ns in naechste:
                            # Termin-Widgets als Default-Args binden (Snapshot): Loop-Late-Binding
                            # würde _inv_* am Klickzeitpunkt auf None der Folge-Card zurücksetzen.
                            def make_transition(_a_id=a_id, _k_id=k_id, _j_id=j_id, _ns=ns,
                                                _inv_d=_inv_datum, _inv_z=_inv_zeit, _inv_min=_inv_dauer):
                                def _do():
                                    conn2 = db.get_conn()
                                    # N-S2 (01.10.2026): Klick-Guard wie employer `_legal` /
                                    # Stellen-Seite — Ausgangsstatus live aus der DB lesen und
                                    # gegen ALLOWED_TRANSITIONS pruefen. Bei Verstoss: kein
                                    # UPDATE, kein History-Eintrag, kein Hook-Task (Whitelist B2-5a).
                                    _row = conn2.execute(
                                        "SELECT status FROM applications WHERE id = ?", (_a_id,)).fetchone()
                                    _old = _row[0] if _row else None
                                    if _ns not in ALLOWED_TRANSITIONS.get(_old, set()):
                                        conn2.close()
                                        ui.notify(_("Ungueltiger Statusuebergang (Whitelist ALLOWED_TRANSITIONS)."),
                                                  type="negative")
                                        ui.navigate.reload()
                                        return
                                    conn2.execute("UPDATE applications SET status = ?, aktualisiert_am = CURRENT_TIMESTAMP WHERE id = ?", (_ns, _a_id))
                                    conn2.execute("INSERT INTO application_status_history (application_id, status, changed_by) VALUES (?, ?, 'admin')", (_a_id, _ns))
                                    conn2.commit()
                                    conn2.close()
                                    task = _hook_task.get(_ns)
                                    if task:
                                        _pl = {"application_id": _a_id, "candidate_id": _k_id,
                                               "job_id": _j_id, "trigger": "admin_klick"}
                                        if task == "create_invitation" and _inv_d is not None:
                                            _pl.update({
                                                "termin_datum": str(_inv_d.value),
                                                "termin_uhrzeit": str(_inv_z.value),
                                                "termin_dauer_min": int(_inv_min.value),
                                            })
                                        db.queue_agent_task(task, _pl)
                                    ui.notify(
                                        _("Status geaendert: {0}").format(_ns)
                                        + (_(", Agent-Task '{0}' gequeued").format(task) if task else ""),
                                        type="positive")
                                    navigate_to("admin", "stellen")
                                return _do
                            ui.button(_("→ {0}").format(ns), on_click=make_transition()).props(
                                # P1-4 (29.09.2026): Quasar-Semantik statt bg-*
                                # (Parität employer.py, Spec: ui-design-system.md §2.5)
                                "color=positive" if ns == "eingeladen" else
                                "color=negative" if ns == "abgelehnt" else
                                "color=primary")
                else:
                    ui.label(_("Finaler Status erreicht.")).classes("text-caption px-4 pb-2")

                # Visum-Info/Schritte (geteilter Trigger, employer-board.md §3(b))
                if a_status == "eingeladen":
                    with ui.row().classes("px-4 pb-2"):
                        visa_info_section(a_id, k_id, j_id, trigger="admin_klick",
                                          on_sent=lambda: navigate_to("admin", "stellen"),
                                          classes="bg-amber-600 text-white", props="")

    with ui.expansion(_("📋 Archiv ({0}) – eingestellt / abgelehnt / zurückgezogen").format(len(apps_archiv)), icon="archive").classes("w-full mb-4"):
        if not apps_archiv:
            ui.label(_("Keine archivierten Bewerbungen.")).classes("text-caption")
        for a_id, k_id, a_status, a_text, a_dat, j_titel, j_id, e_firma in apps_archiv:
            with ui.row().classes("items-center gap-2 w-full py-1"):
                ui.label(_("{0} Kandidat #{1} – {2} ({3}, {4})").format(
                    badge.get(a_status, '📄'), k_id, j_titel, a_status, str(a_dat)[:10])).classes(C.BODY)

    conn.close()

    ui.separator().classes("my-4")

    # ── Stellen-Status-Verwaltung (bestehend, Phase 1) ──
    section_header(title=_("Stellen-Status"), subtitle=_("HR-Write"), icon="tune")

    conn = db.get_conn()
    jobs = conn.execute(
        "SELECT j.id, j.titel, j.status, j.employer_id, e.firma FROM jobs j JOIN employers e ON j.employer_id = e.id ORDER BY j.id DESC LIMIT 30"
    ).fetchall()
    conn.close()

    if not jobs:
        empty_state(icon="work_off", title=_("Keine Stellen vorhanden"))
        return

    with ui.column().classes("w-full gap-3"):
        for j_id, titel, status, emp_id, firma in jobs:
            with ui.card().classes(C.CARD_HOVER + " w-full mb-2 py-2"):
                with ui.row().classes("items-center justify-between w-full px-4"):
                    with ui.row().classes("items-center gap-3"):
                        ui.label(f"#{j_id}").classes(C.MUTED)
                        with ui.column():
                            ui.label(titel).classes("font-medium")
                            ui.label(firma or _("Unbekannt")).classes(C.SMALL)
                    with ui.row().classes("items-center gap-2"):
                        status_badge(status or _("unbekannt"))
                        status_select = ui.select(
                            options={v: _(v) for v in ["aktiv", "pausiert", "besetzt", "abgelaufen"]},
                            value=status,
                            label=_("Status"),
                        ).classes("w-40")

                        def save_job_status(_jid=j_id, _sel=status_select):
                            db.update_job_status(_jid, _sel.value, changed_by="admin")
                            ui.notify(_("Status geaendert: {0}").format(_sel.value), type="positive")
                            refresh_stellen()

                        ui.button(icon="save", on_click=save_job_status).props("flat color=primary dense")

    def refresh_stellen():
        navigate_to("admin", "stellen")


def _page_employer_portal(s: dict) -> None:
    section_header(title=_("Arbeitgeber-Portal"), subtitle=_("Portal-Verwaltung"), icon="business")

    conn = db.get_conn()
    employers = conn.execute(
        "SELECT id, firma, branche, groesse, standort, website, beschreibung, telefon FROM employers ORDER BY id DESC LIMIT 20"
    ).fetchall()
    conn.close()

    if not employers:
        empty_state(icon="business", title=_("Keine Arbeitgeber vorhanden"))
        return

    branchen = ["IT", "Consulting", "Industrie", "Handel", "Gesundheit", "Finanzen", "Sonstiges"]
    grossen = ["1-10", "11-50", "51-200", "201-1000", "1000+"]

    with ui.column().classes("w-full gap-3"):
        for e_id, firma, branche, groesse, standort, website, beschreibung, telefon in employers:
            with ui.expansion(f"#{e_id} {firma}", icon="business").classes("w-full mb-2"):
                with ui.row().classes("items-center gap-2 w-full"):
                    info_row(_("Branche"), branche or "–", icon="business")
                    info_row(_("Groesse"), groesse or "–", icon="group")
                    info_row(_("Standort"), standort or "–", icon="location_on")

                # Write-Form (P3.3): dieselben Felder wie Employer _page_portal, db.upsert_employer
                branche_select = ui.select(
                    options={v: _(v) for v in branchen},
                    value=branche if branche in branchen else branchen[0],
                    label=_("Branche"),
                ).classes("w-full")
                groesse_select = ui.select(
                    options={v: _(v) for v in grossen},
                    value=groesse if groesse in grossen else grossen[0],
                    label=_("Mitarbeiterzahl"),
                ).classes("w-full")
                standort_input = ui.input(label=_("Hauptstandort"), value=standort or "").classes("w-full")
                website_input = ui.input(label=_("Website"), value=website or "").classes("w-full")
                telefon_input = ui.input(label=_("Telefon"), value=telefon or "").classes("w-full")
                beschreibung_input = ui.textarea(label=_("Kurzprofil (max. 500 Zeichen)"), value=beschreibung or "").classes("w-full")

                def save_employer(_e_id=e_id, _b=branche_select, _g=groesse_select,
                                  _st=standort_input, _w=website_input,
                                  _t=telefon_input, _be=beschreibung_input):
                    ok = db.upsert_employer(
                        employer_id=_e_id,
                        branche=_b.value,
                        groesse=_g.value,
                        standort=_st.value,
                        website=_w.value,
                        beschreibung=_be.value,
                        telefon=_t.value,
                    )
                    if ok:
                        ui.notify(_("Firmenprofil #{0} gespeichert.").format(_e_id), type="positive")
                    else:
                        ui.notify(_("Fehler beim Speichern."), type="negative")

                ui.button(_("💾 Profil speichern"), on_click=save_employer).classes(C.BTN_PRIMARY + " mt-2")


# ─── Page Router ─────────────────────────────────────────────────────

PAGE_MAP = {
    "dashboard": ("Dashboard", "dashboard", _page_dashboard),
    "upload": ("Upload", "cloud_upload", _page_upload),
    "extract": ("Extract Profile", "badge", _page_extract),
    "match_tool": ("Match-Tool", "compare_arrows", _page_match_tool),
    "compliance_tool": ("Compliance-Tool", "verified", _page_compliance_tool),
    "contact": ("Contact", "mail", _page_contact),
    "culture_fit": ("Culture Fit", "psychology", _page_culture_fit),
    "prescreen": ("Pre-Screen", "record_voice_over", _page_prescreen),
    "onboarding": ("Onboarding", "assignment", _page_onboarding),
    "feedback": ("Feedback", "feedback", _page_feedback),
    "stellen": ("Stellenangebote", "work", _page_stellen),
    "portal": ("Arbeitgeber-Portal", "business", _page_employer_portal),
}


def _menu_items_admin() -> list[dict]:
    """Sidebar-Einträge — Labels erst beim Rendern übersetzt
    (Importzeit = keine Session/Sprache, i18n-Regel knowledge/system/i18n.md)."""
    return [
        {"key": key, "label": _(vals[0]), "icon": vals[1]}
        for key, vals in PAGE_MAP.items()
    ]


def create() -> None:
    """Register the /admin page + Sub-Routes."""
    from nicegui import app

    def _build_admin_page(initial_tab: str = ""):
        s = app.storage.user
        role = logic.current_role(s)
        if role != "admin":
            ui.navigate.to("/login")
            return

        def render_page(page_key: str):
            entry = PAGE_MAP.get(page_key)
            if entry:
                entry[2](s)

        from webui.components import shell
        shell(
            role="admin",
            user_id=0,
            user_name=s.get("admin_email", "Admin"),
            menu_items=_menu_items_admin(),
            logout_fn=lambda: logic.logout_admin(s),
            content_fn=render_page,
            s=s,
            initial_tab=initial_tab,
        )

    @ui.page("/admin")
    def admin_page():
        _build_admin_page()

    # Sub-Routes auf Modulebene registrieren
    for _tab_key in PAGE_MAP:
        def _register_admin(k=_tab_key):
            @ui.page(f"/admin/{k}")
            def _sub_page(_k=k):
                _build_admin_page(initial_tab=_k)
        _register_admin()
