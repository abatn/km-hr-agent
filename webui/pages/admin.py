"""
Admin pages for KM-HR-Agent NiceGUI App.
11 pages: Dashboard + Agent-Tools (0-5) + Portal pages.
"""
from __future__ import annotations

from pathlib import Path

from nicegui import ui

from webui import db, logic
from webui.theme import C, PRIMARY, SECONDARY, ACCENT, DANGER
from webui.components import (
    stat_card, status_badge, data_table, empty_state, section_header, export_candidates_pdf, info_row,
    navigate_to, prescreen_recruiting_section, onboarding_generator_section, skill8_feedback_section,
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


# ─── Pages ───────────────────────────────────────────────────────────

def tool_result_section(glob_pat: str, task_label: str) -> None:
    """C6 (22.09.2026): Ergebnis-Anzeige + Download je Admin-Tool.

    Paritaet zu Streamlit st.download_button (app.py:1378/1531/1641/1734/1851):
    Streamlit zeigt das frisch generierte MD inline + Download-Button. NiceGUI
    loest asynchron ueber die Agent-Queue aus — das Artefakt schreibt der
    Runner nach ergebnisse/ (agent-automation.md) und wird hier angezeigt.
    """
    files = sorted(logic.ERGEBNISSE.glob(glob_pat))
    with ui.card().classes(C.CARD + " w-full mt-3"):
        ui.label(f"Ergebnis: {task_label}").classes(C.CARD_TITLE)
        if not files:
            ui.label("Noch kein Ergebnis vorhanden – Task unten ausloesen, der Runner schreibt das MD nach ergebnisse/.").classes(C.MUTED)
            return
        latest = files[-1]
        content = latest.read_text(encoding="utf-8", errors="replace")
        ui.label(latest.name).classes(C.SMALL)
        with ui.expansion(text="Vorschau").classes("w-full"):
            ui.markdown(content)
        ui.button(
            "Herunterladen", icon="download",
            # Default-Args binden den Closure-Wert (C1-Lesson: Late-Binding)
            on_click=lambda _c=content, _n=latest.name: ui.download(
                _c.encode("utf-8"), _n, "text/markdown"
            ),
        ).classes(C.BTN_PRIMARY + " mt-2")


def _page_dashboard(s: dict) -> None:
    section_header(title="Admin Dashboard", subtitle="System-Uebersicht", icon="dashboard")

    tables = [
        ("Kandidaten", "candidates"),
        ("Arbeitgeber", "employers"),
        ("Stellen", "jobs"),
        ("Bewerbungen", "applications"),
        ("Feedback", "feedback"),
        ("Agent-Tasks", "agent_tasks"),
        ("Dokumente", "candidate_documents"),
        ("Sprachtests", "language_tests"),
        ("Gewichtung", "gewichtung_historie"),
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
            task_data = [{"value": r[1], "name": r[0] or "unbekannt"} for r in task_rows]
            with ui.card().classes(C.CARD + " w-full mt-4"):
                ui.label("Agent-Tasks nach Status").classes(C.CARD_TITLE + " mb-2")
                ui.echart({
                    "title": {"text": "Task-Verteilung", "left": "center"},
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
                ui.label("Bewerbungen pro Monat").classes(C.CARD_TITLE + " mb-2")
                ui.echart({
                    "title": {"text": "Bewerbungen", "left": "center"},
                    "xAxis": {"type": "category", "data": months},
                    "yAxis": {"type": "value"},
                    "series": [{"data": counts, "type": "bar", "itemStyle": {"color": "#3B82F6"}}]
                }).classes("w-full h-64")

        conn.close()
    except Exception:
        pass

    # PDF Export
    with ui.card().classes(C.CARD + " w-full mt-4"):
        ui.label("Daten exportieren").classes(C.CARD_TITLE + " mb-3")
        ui.label("Kandidaten-Liste als PDF herunterladen.").classes(C.SMALL + " mb-3")
        ui.button("PDF Export", icon="picture_as_pdf", on_click=lambda: export_candidates_pdf()).classes(C.BTN_PRIMARY)

    # ── Passwort ändern (N5) ──
    with ui.expansion("Passwort aendern", icon="lock").classes("w-full mt-4"):
        pw_alt = ui.input(label="Aktuelles Passwort", password=True).classes("w-full")
        pw_neu = ui.input(label="Neues Passwort", password=True).classes("w-full")
        pw_wdh = ui.input(label="Neues Passwort wiederholen", password=True).classes("w-full")

        def do_change_pw_admin():
            if not pw_alt.value or not pw_neu.value or not pw_wdh.value:
                ui.notify("Bitte alle Felder ausfuellen.", type="warning")
                return
            if pw_neu.value != pw_wdh.value:
                ui.notify("Passwoerter stimmen nicht ueberein.", type="negative")
                return
            conn_pw = db.get_conn()
            admin_id = conn_pw.execute(
                "SELECT id FROM admins WHERE email = ?", (s.get("admin_email", ""),)
            ).fetchone()
            if admin_id:
                ok, msg = logic.change_password(conn_pw, "admins", admin_id[0], pw_alt.value, pw_neu.value)
                conn_pw.close()
                ui.notify(msg, type="positive" if ok else "negative")
            else:
                conn_pw.close()
                ui.notify("Admin nicht gefunden.", type="negative")

        ui.button("Passwort aendern", on_click=do_change_pw_admin).classes(C.BTN_PRIMARY + " mt-2")


def _page_upload(s: dict) -> None:
    section_header(title="Upload (Ingestion)", subtitle="Lebenslaeufe hochladen", icon="cloud_upload")

    with ui.card().classes(C.CARD):
        ui.label("Lebenslauf oder Stellenprofil hochladen").classes(C.CARD_TITLE)
        ui.label("PDF- und TXT-Dateien werden in testdaten/ gespeichert und dem Agenten zur Extraktion zugeführt.").classes(C.SMALL)

        async def _on_upload(e):
            try:
                fname = e.file.name or "upload"
                content = await e.file.read()
            except Exception as ex:
                ui.notify(f"Upload fehlgeschlagen: {ex}", type="negative")
                return
            if not content:
                ui.notify("Keine Datei empfangen.", type="warning")
                return

            save_path = TESTDATEN / fname
            save_path.parent.mkdir(parents=True, exist_ok=True)

            # Bytes (NiceGUI async read; Paritaet app.py:1246 cv_file.getvalue())
            save_path.write_bytes(content)

            ui.notify(f"Gespeichert: {fname}", type="positive")

            # Queue extract_profile if it is a CV (notstellenprofil)
            if "stellenprofil" not in fname.lower():
                tid = db.queue_agent_task(
                    "extract_profile", {"quelle": fname, "datei_pfad": str(save_path)}
                )
                if tid:
                    ui.notify(f"Extract-Task #{tid} gequeued", type="positive")
                else:
                    ui.notify("Bereits heute gequeued oder Fehler.", type="warning")

        upload = ui.upload(label="Datei auswaehlen", on_upload=_on_upload, auto_upload=True, max_file_size=5_000_000)

    with ui.card().classes(C.CARD):
        ui.label("Vorhandene Dateien").classes(C.CARD_TITLE)
        cv_files = sorted(TESTDATEN.glob("*.txt")) + sorted(TESTDATEN.glob("*.pdf"))
        if cv_files:
            for f in cv_files:
                ui.label(f.name).classes(C.SMALL)
        else:
            ui.label("Keine Dateien vorhanden.").classes(C.MUTED)


def _page_extract(s: dict) -> None:
    section_header(title="Extract Profile", subtitle="Skill 1 - Profil-Extraktion", icon="badge")
    tool_result_section("extract_profile-*.md", "Extract Profile")

    with ui.card().classes(C.CARD):
        ui.label("Profil-Extraktion aus Lebenslaeufen").classes(C.CARD_TITLE)
        ui.label("Kandidaten ohne extrahiertes Profil (hard_skills IS NULL) werden dem Agenten zur Profil-Extraktion zugeführt.").classes(C.SMALL)

        conn = db.get_conn()
        rows = conn.execute(
            "SELECT id, name, email, lebenslauf_datei FROM candidates WHERE hard_skills IS NULL AND lebenslauf_datei IS NOT NULL ORDER BY id DESC LIMIT 30"
        ).fetchall()
        conn.close()

        if not rows:
            empty_state(icon="badge", title="Keine Kandidaten ohne Profil", description="Alle Kandidaten haben bereits ein extrahiertes Profil.")
            return

        columns = [
            {"name": "id", "label": "#", "field": "id"},
            {"name": "name", "label": "Name", "field": "name"},
            {"name": "email", "label": "E-Mail", "field": "email"},
            {"name": "datei", "label": "Lebenslauf", "field": "datei"},
        ]
        table_rows = [{"id": r[0], "name": r[1], "email": r[2], "datei": r[3] or "--"} for r in rows]
        data_table(columns=columns, rows=table_rows, title=f"{len(rows)} Kandidaten ohne Profil")

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
            ui.notify(f"{queued} Extract-Tasks gequeued", type="positive") if queued else ui.notify("Keine Tasks gequeued (bereits aktiv oder Fehler).", type="warning")

        with ui.dialog() as extract_dialog, ui.card().classes("w-96"):
            ui.label("Tasks starten?").classes("text-lg font-bold mb-4")
            ui.label(f"Moechtest du {len(rows)} Extract-Tasks wirklich starten?").classes("mb-2")
            with ui.row().classes("justify-end gap-2 mt-4"):
                ui.button("Abbrechen", on_click=extract_dialog.close)
                ui.button("Starten", on_click=lambda: (
                    _extract_all(),
                    extract_dialog.close(),
                )).classes("bg-blue-700 text-white")

        ui.button(f"Alle {len(rows)} extrahieren", icon="play_arrow", on_click=extract_dialog.open).classes(C.BTN_PRIMARY)


def _page_match_tool(s: dict) -> None:
    section_header(title="Match-Tool", subtitle="Skill 2 - Kandidaten-Matching", icon="compare_arrows")
    tool_result_section("match_candidate-*.md", "Match Candidate")

    with ui.card().classes(C.CARD):
        ui.label("Kandidaten-Matching mit Stellen").classes(C.CARD_TITLE)
        ui.label("Bewerbungen mit Status 'beworben' werden dem Agenten zur Score-Berechnung zugeführt.").classes(C.SMALL)

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
            empty_state(icon="compare_arrows", title="Keine offenen Bewerbungen", description="Keine Bewerbungen mit Status 'beworben' oder 'eingegangen'.")
            return

        columns = [
            {"name": "app_id", "label": "Bewerbung", "field": "app_id"},
            {"name": "kandidat", "label": "Kandidat", "field": "kandidat"},
            {"name": "stelle", "label": "Stelle", "field": "stelle"},
            {"name": "status", "label": "Status", "field": "status"},
        ]
        table_rows = [{"app_id": r[0], "kandidat": r[3], "stelle": r[4], "status": r[5]} for r in rows]
        data_table(columns=columns, rows=table_rows, title=f"{len(rows)} offene Bewerbungen")

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
            ui.notify(f"{queued} Match-Tasks gequeued", type="positive") if queued else ui.notify("Keine Tasks gequeued (bereits aktiv oder Fehler).", type="warning")

        with ui.dialog() as match_dialog, ui.card().classes("w-96"):
            ui.label("Tasks starten?").classes("text-lg font-bold mb-4")
            ui.label(f"Moechtest du {len(rows)} Match-Tasks wirklich starten?").classes("mb-2")
            with ui.row().classes("justify-end gap-2 mt-4"):
                ui.button("Abbrechen", on_click=match_dialog.close)
                ui.button("Starten", on_click=lambda: (
                    _match_all(),
                    match_dialog.close(),
                )).classes("bg-blue-700 text-white")

        ui.button(f"Alle {len(rows)} matchen", icon="play_arrow", on_click=match_dialog.open).classes(C.BTN_PRIMARY)


def _page_compliance_tool(s: dict) -> None:
    section_header(title="Compliance-Tool", subtitle="Skill 3 - Rechts-Pruefung", icon="verified")
    tool_result_section("check_compliance-*.md", "Check Compliance")

    with ui.card().classes(C.CARD):
        ui.label("Compliance-Pruefung (DSGVO, AGG, BDSG)").classes(C.CARD_TITLE)
        ui.label("Bewerbungen werden dem Agenten zur laenderspezifischen Rechts-Pruefung zugeführt.").classes(C.SMALL)

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
            empty_state(icon="verified", title="Keine Bewerbungen zur Pruefung", description="Keine offenen Bewerbungen gefunden.")
            return

        columns = [
            {"name": "app_id", "label": "Bewerbung", "field": "app_id"},
            {"name": "kandidat", "label": "Kandidat", "field": "kandidat"},
            {"name": "stelle", "label": "Stelle", "field": "stelle"},
            {"name": "status", "label": "Status", "field": "status"},
        ]
        table_rows = [{"app_id": r[0], "kandidat": r[3], "stelle": r[4], "status": r[5]} for r in rows]
        data_table(columns=columns, rows=table_rows, title=f"{len(rows)} Bewerbungen zur Compliance-Pruefung")

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
            ui.notify(f"{queued} Compliance-Tasks gequeued", type="positive") if queued else ui.notify("Keine Tasks gequeued (bereits aktiv oder Fehler).", type="warning")

        with ui.dialog() as compliance_dialog, ui.card().classes("w-96"):
            ui.label("Tasks starten?").classes("text-lg font-bold mb-4")
            ui.label(f"Moechtest du {len(rows)} Compliance-Tasks wirklich starten?").classes("mb-2")
            with ui.row().classes("justify-end gap-2 mt-4"):
                ui.button("Abbrechen", on_click=compliance_dialog.close)
                ui.button("Starten", on_click=lambda: (
                    _compliance_all(),
                    compliance_dialog.close(),
                )).classes("bg-blue-700 text-white")

        ui.button(f"Alle {len(rows)} pruefen", icon="play_arrow", on_click=compliance_dialog.open).classes(C.BTN_PRIMARY)


def _page_contact(s: dict) -> None:
    section_header(title="Contact Candidate", subtitle="Skill 4 - Kontakt", icon="mail")
    tool_result_section("notify_user-*.md", "Contact Candidate")

    with ui.card().classes(C.CARD):
        ui.label("Kandidaten kontaktieren").classes(C.CARD_TITLE)
        ui.label("Eingeladene Kandidaten werden dem Agenten zur E-Mail-Generierung zugeführt.").classes(C.SMALL)

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
            empty_state(icon="mail", title="Keine eingeladenen Kandidaten", description="Kandidaten werden nach Einladung durch HR hier angezeigt.")
            return

        columns = [
            {"name": "app_id", "label": "Bewerbung", "field": "app_id"},
            {"name": "kandidat", "label": "Kandidat", "field": "kandidat"},
            {"name": "email", "label": "E-Mail", "field": "email"},
            {"name": "stelle", "label": "Stelle", "field": "stelle"},
        ]
        table_rows = [{"app_id": r[0], "kandidat": r[3], "email": r[4], "stelle": r[5]} for r in rows]
        data_table(columns=columns, rows=table_rows, title=f"{len(rows)} eingeladene Kandidaten")

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
            ui.notify(f"{queued} Kontakt-Tasks gequeued", type="positive") if queued else ui.notify("Keine Tasks gequeued (bereits aktiv oder Fehler).", type="warning")

        with ui.dialog() as contact_dialog, ui.card().classes("w-96"):
            ui.label("Tasks starten?").classes("text-lg font-bold mb-4")
            ui.label(f"Moechtest du {len(rows)} Kontakt-Tasks wirklich starten?").classes("mb-2")
            with ui.row().classes("justify-end gap-2 mt-4"):
                ui.button("Abbrechen", on_click=contact_dialog.close)
                ui.button("Starten", on_click=lambda: (
                    _contact_all(),
                    contact_dialog.close(),
                )).classes("bg-blue-700 text-white")

        ui.button(f"Alle {len(rows)} kontaktieren", icon="play_arrow", on_click=contact_dialog.open).classes(C.BTN_PRIMARY)


def _page_culture_fit(s: dict) -> None:
    section_header(title="Culture Fit", subtitle="Skill 5 - Kultur-Analyse", icon="psychology")
    tool_result_section("assess_culture_fit-*.md", "Culture Fit")

    with ui.card().classes(C.CARD):
        ui.label("Kultur-Fit-Analyse").classes(C.CARD_TITLE)
        ui.label("Bewerbungen werden dem Agenten zur Kultur-Fit-Bewertung (0-100) zugeführt.").classes(C.SMALL)

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
            empty_state(icon="psychology", title="Keine Bewerbungen zur Kultur-Analyse", description="Keine offenen Bewerbungen gefunden.")
            return

        columns = [
            {"name": "app_id", "label": "Bewerbung", "field": "app_id"},
            {"name": "kandidat", "label": "Kandidat", "field": "kandidat"},
            {"name": "stelle", "label": "Stelle", "field": "stelle"},
            {"name": "status", "label": "Status", "field": "status"},
        ]
        table_rows = [{"app_id": r[0], "kandidat": r[3], "stelle": r[4], "status": r[5]} for r in rows]
        data_table(columns=columns, rows=table_rows, title=f"{len(rows)} Bewerbungen zur Kultur-Analyse")

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
            ui.notify(f"{queued} Culture-Fit-Tasks gequeued", type="positive") if queued else ui.notify("Keine Tasks gequeued (bereits aktiv oder Fehler).", type="warning")

        with ui.dialog() as culture_dialog, ui.card().classes("w-96"):
            ui.label("Tasks starten?").classes("text-lg font-bold mb-4")
            ui.label(f"Moechtest du {len(rows)} Culture-Fit-Tasks wirklich starten?").classes("mb-2")
            with ui.row().classes("justify-end gap-2 mt-4"):
                ui.button("Abbrechen", on_click=culture_dialog.close)
                ui.button("Starten", on_click=lambda: (
                    _culture_all(),
                    culture_dialog.close(),
                )).classes("bg-blue-700 text-white")

        ui.button(f"Alle {len(rows)} analysieren", icon="play_arrow", on_click=culture_dialog.open).classes(C.BTN_PRIMARY)


def _page_prescreen(s: dict) -> None:
    section_header(title="Pre-Screen", subtitle="Recruiting", icon="record_voice_over")
    # C7 (22.09.2026): Slot-Stub → Skill-6-Section (Einsicht + Generator, D28)
    prescreen_recruiting_section()


def _page_onboarding(s: dict) -> None:
    section_header(title="Onboarding", subtitle="HR", icon="assignment")
    # C7 (22.09.2026): Slot-Stub → Skill-7-Generator (D28/D29)
    onboarding_generator_section()


def _page_feedback(s: dict) -> None:
    section_header(title="Feedback", subtitle="Algorithmus-Feedback", icon="feedback")
    # C7 (22.09.2026): Slot-Stub → Skill-8 (Cat-Map 'Nicht passend', app.py:2598)
    skill8_feedback_section()


def _page_stellen(s: dict) -> None:
    section_header(title="Stellenangebote", subtitle="HR-Write", icon="work")

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

    with ui.expansion(f"📥 Aktive Bewerber ({len(apps_aktiv)})", icon="how_to_reg").classes("w-full mb-4"):
        if not apps_aktiv:
            empty_state(icon="inbox", title="Keine aktiven Bewerbungen", description="Bewerbungen erscheinen hier, sobald Kandidaten sich bewerben.")
        for a_id, k_id, a_status, a_text, a_dat, j_titel, j_id, e_firma in apps_aktiv:
            agent_status = db.get_agent_task_status(a_id) or {}
            _ms = agent_status.get("match_candidate", "-")
            _cs = agent_status.get("check_compliance", "-")
            _fs = agent_status.get("assess_culture_fit", "-")
            badge_txt = f"Match {_ms} · Compliance {_cs} · Culture-Fit {_fs}" if agent_status else "(noch nicht gestartet)"

            with ui.card().classes(C.CARD_HOVER + " w-full mb-2 py-2"):
                with ui.row().classes("items-center justify-between w-full px-4"):
                    with ui.row().classes("items-center gap-3"):
                        ui.label(f"{badge.get(a_status, '📄')} #{a_id}").classes(C.MUTED)
                        with ui.column():
                            ui.label(f"Kandidat #{k_id} – {j_titel}").classes("font-medium")
                            ui.label(f"{e_firma} · Eingegangen: {str(a_dat)[:10]}").classes(C.SMALL)
                    with ui.row().classes("items-center gap-2"):
                        status_badge(a_status)
                        ui.badge(f"🤖 {badge_txt}").props("color=blue-1 outline")

                if a_text:
                    ui.label(f"Motivation: {a_text[:200]}").classes(C.SMALL + " px-4 mt-1")

                naechste = _legal_actions(a_status)
                if naechste:
                    # C1 (22.09.2026): Einladungs-Termin Inline vor → eingeladen
                    # Quelle: app.py:3173-3185 (Payload termin_*, Spec agent-automation.md §5)
                    from datetime import datetime as _dt, timedelta as _timedelta
                    _inv_datum = _inv_zeit = _inv_dauer = None
                    if "eingeladen" in naechste:
                        ui.label("📅 Einladungs-Termin (wird in die Automatik-Mail übernommen):").classes(C.SMALL + " px-4")
                        with ui.row().classes("items-center gap-2 px-4"):
                            # NiceGUI ≥3.3 (offiziell, nicegui.io/documentation/date_input + time_input):
                            # ui.date/time kennen kein label → *_input-Elemente (QInput + Picker)
                            _inv_datum = ui.date_input("Datum", value=str((_dt.now() + _timedelta(days=1)).date())).classes("w-40")
                            _inv_zeit = ui.time_input("Uhrzeit", value="10:00").classes("w-24")
                            _inv_dauer = ui.select([15, 30, 45, 60], value=30, label="Dauer (Min.)").classes("w-32")
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
                                        ui.notify("Ungueltiger Statusuebergang (Whitelist ALLOWED_TRANSITIONS).",
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
                                    ui.notify(f"Status geaendert: {_ns}" + (f", Agent-Task '{task}' gequeued" if task else ""), type="positive")
                                    navigate_to("admin", "stellen")
                                return _do
                            ui.button(f"→ {ns}", on_click=make_transition()).props(
                                # P1-4 (29.09.2026): Quasar-Semantik statt bg-*
                                # (Parität employer.py, Spec: ui-design-system.md §2.5)
                                "color=positive" if ns == "eingeladen" else
                                "color=negative" if ns == "abgelehnt" else
                                "color=primary")
                else:
                    ui.label("Finaler Status erreicht.").classes("text-caption px-4 pb-2")

                # Visum-Antrag-Bestaetigung (Spec v6, Payload-LIKE Guard wie app.py:3177-3179)
                if a_status == "eingeladen":
                    with ui.row().classes("px-4 pb-2"):
                        _visa_rows = conn.execute(
                            "SELECT COUNT(*) FROM agent_tasks WHERE task_type='visa_confirmation' "
                            "AND status IN ('pending','running','done') "
                            "AND json_extract(payload, '$.application_id') = ?",
                            (a_id,),
                        ).fetchone()
                        _visa_done = _visa_rows[0] > 0 if _visa_rows else False
                        if not _visa_done:
                            def send_visa(_a_id=a_id, _k_id=k_id, _j_id=j_id):
                                db.queue_agent_task("visa_confirmation", {"application_id": _a_id,
                                                                          "candidate_id": _k_id, "job_id": _j_id,
                                                                          "trigger": "admin_klick"})
                                ui.notify("Visum-Schritte-Mail an den Kandidaten ausgeloest (Agent sendet).", type="positive")
                                navigate_to("admin", "stellen")
                            ui.button("📩 Visum-Antrag bestaetigen", on_click=send_visa).classes("bg-amber-600 text-white")
                        else:
                            ui.label("✅ Visum-Schritte-Mail versendet.").classes("text-caption")

    with ui.expansion(f"📋 Archiv ({len(apps_archiv)}) – eingestellt / abgelehnt / zurückgezogen", icon="archive").classes("w-full mb-4"):
        if not apps_archiv:
            ui.label("Keine archivierten Bewerbungen.").classes("text-caption")
        for a_id, k_id, a_status, a_text, a_dat, j_titel, j_id, e_firma in apps_archiv:
            with ui.row().classes("items-center gap-2 w-full py-1"):
                ui.label(f"{badge.get(a_status, '📄')} Kandidat #{k_id} – {j_titel} ({a_status}, {str(a_dat)[:10]})").classes(C.BODY)

    conn.close()

    ui.separator().classes("my-4")

    # ── Stellen-Status-Verwaltung (bestehend, Phase 1) ──
    section_header(title="Stellen-Status", subtitle="HR-Write", icon="tune")

    conn = db.get_conn()
    jobs = conn.execute(
        "SELECT j.id, j.titel, j.status, j.employer_id, e.firma FROM jobs j JOIN employers e ON j.employer_id = e.id ORDER BY j.id DESC LIMIT 30"
    ).fetchall()
    conn.close()

    if not jobs:
        empty_state(icon="work_off", title="Keine Stellen vorhanden")
        return

    with ui.column().classes("w-full gap-3"):
        for j_id, titel, status, emp_id, firma in jobs:
            with ui.card().classes(C.CARD_HOVER + " w-full mb-2 py-2"):
                with ui.row().classes("items-center justify-between w-full px-4"):
                    with ui.row().classes("items-center gap-3"):
                        ui.label(f"#{j_id}").classes(C.MUTED)
                        with ui.column():
                            ui.label(titel).classes("font-medium")
                            ui.label(firma or "Unbekannt").classes(C.SMALL)
                    with ui.row().classes("items-center gap-2"):
                        status_badge(status or "unbekannt")
                        status_select = ui.select(
                            options=["aktiv", "pausiert", "besetzt", "abgelaufen"],
                            value=status,
                            label="Status",
                        ).classes("w-40")

                        def save_job_status(_jid=j_id, _sel=status_select):
                            db.update_job_status(_jid, _sel.value, changed_by="admin")
                            ui.notify(f"Status geaendert: {_sel.value}", type="positive")
                            refresh_stellen()

                        ui.button(icon="save", on_click=save_job_status).props("flat color=primary dense")

    def refresh_stellen():
        navigate_to("admin", "stellen")


def _page_employer_portal(s: dict) -> None:
    section_header(title="Arbeitgeber-Portal", subtitle="Portal-Verwaltung", icon="business")

    conn = db.get_conn()
    employers = conn.execute(
        "SELECT id, firma, branche, groesse, standort, website, beschreibung, telefon FROM employers ORDER BY id DESC LIMIT 20"
    ).fetchall()
    conn.close()

    if not employers:
        empty_state(icon="business", title="Keine Arbeitgeber vorhanden")
        return

    branchen = ["IT", "Consulting", "Industrie", "Handel", "Gesundheit", "Finanzen", "Sonstiges"]
    grossen = ["1-10", "11-50", "51-200", "201-1000", "1000+"]

    with ui.column().classes("w-full gap-3"):
        for e_id, firma, branche, groesse, standort, website, beschreibung, telefon in employers:
            with ui.expansion(f"#{e_id} {firma}", icon="business").classes("w-full mb-2"):
                with ui.row().classes("items-center gap-2 w-full"):
                    info_row("Branche", branche or "–", icon="business")
                    info_row("Groesse", groesse or "–", icon="group")
                    info_row("Standort", standort or "–", icon="location_on")

                # Write-Form (P3.3): dieselben Felder wie Employer _page_portal, db.upsert_employer
                branche_select = ui.select(
                    options=branchen,
                    value=branche if branche in branchen else branchen[0],
                    label="Branche",
                ).classes("w-full")
                groesse_select = ui.select(
                    options=grossen,
                    value=groesse if groesse in grossen else grossen[0],
                    label="Mitarbeiterzahl",
                ).classes("w-full")
                standort_input = ui.input(label="Hauptstandort", value=standort or "").classes("w-full")
                website_input = ui.input(label="Website", value=website or "").classes("w-full")
                telefon_input = ui.input(label="Telefon", value=telefon or "").classes("w-full")
                beschreibung_input = ui.textarea(label="Kurzprofil (max. 500 Zeichen)", value=beschreibung or "").classes("w-full")

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
                        ui.notify(f"Firmenprofil #{_e_id} gespeichert.", type="positive")
                    else:
                        ui.notify("Fehler beim Speichern.", type="negative")

                ui.button("💾 Profil speichern", on_click=save_employer).classes(C.BTN_PRIMARY + " mt-2")


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


# Menu-Items auf Modulebene (fuer Sub-Route-Registrierung)
_MENU_ITEMS_ADMIN = [
    {"key": key, "label": vals[0], "icon": vals[1]}
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
            menu_items=_MENU_ITEMS_ADMIN,
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
