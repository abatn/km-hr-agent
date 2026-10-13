"""
Employer pages for KM-HR-Agent NiceGUI App.
11 pages (PAGE_MAP): Dashboard, Portal (Firmenprofil + Stellen ausschreiben),
Stellenangebote, Kandidaten-Suche, Match-Ergebnis, Compliance, Agent-Details,
Dokumente, Pre-Screen, Onboarding, Feedback.
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import date as _date, datetime as _dt, time as _time, timedelta as _timedelta

from nicegui import run, ui

from webui import db, logic
from webui.i18n import _  # i18n Phase 6 (03.10.2026); Spec: knowledge/system/i18n.md
from webui.theme import C, PRIMARY, SECONDARY, ACCENT, DANGER, STATUS_COLORS, score_color
from webui.components import (
    stat_card, status_badge, status_label, score_bar, score_card, agent_badge,
    data_table, empty_state, section_header, info_row, skeleton_loader,
    candidate_avatar, skill_chip, loading_spinner, export_candidates_pdf,
    notifications_drawer, timeline, navigate_to,
    prescreen_recruiting_section, onboarding_generator_section, skill8_feedback_section,
)

# R6-3 (30.09.2026): zentraler Logger für die ehemals stillen except-Blöcke
# (Dashboard-Kacheln, Charts, Task-Queue) — Muster candidate.py R5-1.
_log = logging.getLogger("kmhr.employer")

PAGE_TITLES = {
    "dashboard": "Dashboard",
    "portal": "Portal",
    "stellen": "Stellenangebote",
    "kandidaten": "Kandidaten-Suche",
    "match": "Match-Ergebnis",
    "compliance": "Compliance-Ergebnis",
    "agent_details": "Agent-Details",
    "dokumente": "Dokumente",
    "prescreen": "Pre-Screen",
    "onboarding": "Onboarding",
    "feedback": "Feedback",
}


def _session() -> dict:
    from nicegui import app
    return app.storage.user


# ─── Agent-B-Helfer (Dashboard / Kandidaten-Suche / Agent-Details / Dokumente) ──
# Reine Funktionen mit expliziter `conn` (pytest-bar gegen Spiegel-DB, tests/test_employer_agent_b.py).
# Schema-Fakt: `applications` hat KEINE employer_id -> Arbeitgeber-Bezug nur ueber
# JOIN jobs j ON j.id = a.job_id ... j.employer_id = ?
import re as _re
from pathlib import Path as _Path

# Typen exakt wie candidate.py `_doc_typen` (Upload-Dialog), "alle" = kein Filter.
DOC_TYP_OPTIONS = ["alle", "Zeugnis", "Zertifikat", "Sprachzeugnis", "Pass",
                   "Visum/Aufenthaltstitel", "Sonstiges"]
# Freigabe-Status (knowledge/legal/dsgvo-gate.md; Paritaet app.py:2053)
DOC_RELEASE_STATUS = ("eingeladen", "eingestellt")


def anzeige_name(name, k_id, status) -> str:
    """P2-8 (01.10.2026): Pseudonym „Kandidat #N" bis Status `eingeladen`.

    Quelle: `knowledge/portal/employer-portal-fields.md:110` +
    `knowledge/lifecycle/application-status.md:80` („echten Namen erst nach
    `eingeladen`", Art. 6(1)(b) Datenminimierung). Freigabe-Whitelist =
    `DOC_RELEASE_STATUS` (gleiche Logik wie die Dokumenten-Freigabe).
    Nur für die Stellenangebote-Seite (entschiedener Umfang P2-8, 01.10.2026).
    """
    if status in DOC_RELEASE_STATUS and name:
        return name
    return _('Kandidat #{0}').format(k_id)
# Kandidaten-Status mit Lebenslauf (knowledge/portal/applicants-first.md, Streamlit-Pool
# app.py:3895; webui/db.py:105)
CAND_CV_STATUS = ("lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen")
# N-K1 (01.10.2026): Sammelwert des Statusfilters (Design-Entscheidung, Befund
# ergebnisse/ui-analyse-2026-09-29.md:65 „Dropdown zeigt DB-Slug lebenslauf_hochgeladen“).
CAND_POOL_ALL_LABEL = "Alle mit Lebenslauf"


def _cand_status_options(conn) -> dict:
    """Dropdown-Optionen der Kandidaten-Suche (N-K1): {value: Klartext-Label}.

    Werte: NUR Status, die im CV-Pool (`CAND_CV_STATUS`) real in der DB vorkommen
    (COUNT > 0) — keine toten Filteroptionen. Reihenfolge = Pool-Definition.
    Labels: `status_label()` (EINE Klartext-Quelle, `components.STATUS_LABELS`) statt
    einer zweiten Label-Kopie; der rohe Slug wird nie angezeigt (Regel:
    knowledge/ui-design-system.md §11).
    Sammelwert „alle“ = CAND_POOL_ALL_LABEL (Design-Entscheidung, keine externe Quelle).
    """
    ph = ",".join("?" * len(CAND_CV_STATUS))
    rows = conn.execute(
        f"SELECT status, COUNT(*) FROM candidates WHERE status IN ({ph}) GROUP BY status",
        list(CAND_CV_STATUS)).fetchall()
    vorhanden = {s for s, n in rows if n}
    opts = {"alle": _(CAND_POOL_ALL_LABEL)}
    for st in CAND_CV_STATUS:
        if st in vorhanden:
            opts[st] = status_label(st)
    return opts
# Aktive Bewerbungen = Bewerber-Definition (applicants-first.md (d); Paritaet app.py:3630)
APPLICANT_ACTIVE = logic.APPLICANT_ACTIVE


def _visible_documents(conn, employer_id, typ: str = "alle") -> list[dict]:
    """Dokumente, die dieser Arbeitgeber sehen darf (DSGVO-Gate, dsgvo-gate.md (c)).

    Gate: Der Kandidat hat beim EIGENEN Arbeitgeber (jobs.employer_id) mindestens eine
    Bewerbung mit Status eingeladen/eingestellt. `app_status` = hoechste solche
    Bewerbung (eingestellt > eingeladen). Ein abgeleiteter JOIN (GROUP BY candidate)
    verhindert Dokument-Duplikate bei mehreren Bewerbungen.
    """
    ph = ",".join("?" * len(DOC_RELEASE_STATUS))
    sql = (
        "SELECT cd.id, cd.candidate_id, c.name, cd.datei_pfad, cd.dokumententyp, "
        "cd.hochgeladen_am, g.rk "
        "FROM candidate_documents cd "
        "JOIN candidates c ON c.id = cd.candidate_id "
        "JOIN (SELECT a.candidate_id AS cid, "
        "             MAX(CASE a.status WHEN 'eingestellt' THEN 2 ELSE 1 END) AS rk "
        "      FROM applications a JOIN jobs j ON j.id = a.job_id "
        f"      WHERE j.employer_id = ? AND a.status IN ({ph}) "
        "      GROUP BY a.candidate_id) g ON g.cid = cd.candidate_id "
    )
    args: list = [employer_id, *DOC_RELEASE_STATUS]
    if typ and typ != "alle":
        sql += "WHERE LOWER(cd.dokumententyp) = LOWER(?) "
        args.append(typ)
    sql += "ORDER BY cd.id DESC"
    return [
        {
            "id": r[0], "candidate_id": r[1],
            "kandidat": r[2] or _('Kandidat #{0}').format(r[1]),
            "datei_pfad": r[3] or "", "typ": r[4] or "", "datum": r[5] or "",
            "app_status": "eingestellt" if r[6] == 2 else "eingeladen",
        }
        for r in conn.execute(sql, args).fetchall()
    ]


def _blocked_candidates(conn, employer_id, typ: str = "alle") -> list[dict]:
    """Kandidaten mit Dokumenten, die sich beim EIGENEN Arbeitgeber beworben haben,
    aber (noch) keine freigebende Bewerbung haben -> nur fuer den 🔒-Hinweis.
    Kandidaten ohne Bewerbung bei diesem Arbeitgeber werden bewusst NICHT geliefert
    (kein Leck fremder Kandidaten). `app_status` = Status der juengsten Bewerbung."""
    ph = ",".join("?" * len(DOC_RELEASE_STATUS))
    doc_typ_sql = ""
    args: list = [employer_id]
    if typ and typ != "alle":
        doc_typ_sql = " AND LOWER(cd.dokumententyp) = LOWER(?)"
        args.append(typ)
    args += [employer_id, employer_id, *DOC_RELEASE_STATUS]
    sql = (
        "SELECT c.id, c.name, "
        "  (SELECT a2.status FROM applications a2 JOIN jobs j2 ON j2.id = a2.job_id "
        "   WHERE a2.candidate_id = c.id AND j2.employer_id = ? ORDER BY a2.id DESC LIMIT 1) "
        "FROM candidates c "
        "WHERE EXISTS (SELECT 1 FROM candidate_documents cd WHERE cd.candidate_id = c.id"
        + doc_typ_sql + ") "
        "AND EXISTS (SELECT 1 FROM applications a JOIN jobs j ON j.id = a.job_id "
        "            WHERE a.candidate_id = c.id AND j.employer_id = ?) "
        "AND NOT EXISTS (SELECT 1 FROM applications a3 JOIN jobs j3 ON j3.id = a3.job_id "
        f"               WHERE a3.candidate_id = c.id AND j3.employer_id = ? AND a3.status IN ({ph})) "
        "ORDER BY c.id DESC"
    )
    return [
        {"candidate_id": r[0], "kandidat": r[1] or _('Kandidat #{0}').format(r[0]), "app_status": r[2] or ""}
        for r in conn.execute(sql, args).fetchall()
    ]


def _resolve_doc_path(raw) -> tuple:
    """Prueft einen in candidate_documents gespeicherten Pfad fuer den Download.

    Rueckgabe (Path | None, grund): grund in {"ok", "kein_pfad", "ausserhalb", "fehlt"}.
    Erlaubt sind NUR Dateien unterhalb von db.BASE_DIR/"testdaten" (Path.resolve() +
    is_relative_to -> kein ../-Traversal, keine Symlink-Flucht). Bewusst NICHT
    BASE_DIR selbst: darunter liegen data/feedback.db und .env-runner."""
    if not raw:
        return None, "kein_pfad"
    try:
        base = _Path(db.BASE_DIR)
        p = _Path(str(raw))
        if not p.is_absolute():
            p = base / p
        rp = p.resolve()
        if not rp.is_relative_to((base / "testdaten").resolve()):
            return None, "ausserhalb"
        if not rp.is_file():
            return None, "fehlt"
        return rp, "ok"
    except (OSError, RuntimeError, ValueError):
        return None, "ausserhalb"


def _doc_basename(raw) -> str:
    """Nur der Dateiname (kein Serverpfad) fuer die Anzeige."""
    return _Path(str(raw or "").replace("\\", "/")).name or "--"


def _employer_application_ids(conn, employer_id) -> tuple[set, set]:
    """(application_ids, candidate_ids) aller Bewerbungen bei Stellen dieses Arbeitgebers."""
    rows = conn.execute(
        "SELECT a.id, a.candidate_id FROM applications a "
        "JOIN jobs j ON j.id = a.job_id WHERE j.employer_id = ?", (employer_id,)
    ).fetchall()
    return {r[0] for r in rows}, {r[1] for r in rows}


def _employer_candidates(conn, employer_id) -> list[tuple]:
    """(id, name) DISTINCT aller Bewerber dieses Arbeitgebers, nach Name."""
    return conn.execute(
        "SELECT DISTINCT c.id, c.name FROM candidates c "
        "JOIN applications a ON a.candidate_id = c.id "
        "JOIN jobs j ON j.id = a.job_id WHERE j.employer_id = ? "
        "ORDER BY c.name, c.id", (employer_id,)
    ).fetchall()


def _employer_agent_tasks(conn, employer_id, status: str = "alle", limit: int | None = 50) -> list[tuple]:
    """agent_tasks dieses Arbeitgebers: (task_type, status, payload, created_at), neueste zuerst.

    Zuordnung ueber payload (JSON in Python geparst, kein LIKE -> keine Praefix-Kollision
    application_id 1 vs 10): application_id gehoert zu eigener Bewerbung; ohne application_id
    nur, wenn candidate_id zu einem eigenen Bewerber gehoert. Tasks ohne beides: nie."""
    app_ids, cand_ids = _employer_application_ids(conn, employer_id)
    sql = "SELECT task_type, status, payload, created_at FROM agent_tasks"
    args: list = []
    if status and status != "alle":
        sql += " WHERE status = ?"
        args.append(status)
    sql += " ORDER BY id DESC"
    out = []
    for row in conn.execute(sql, args).fetchall():
        try:
            pl = json.loads(row[2]) if row[2] else {}
        except (TypeError, ValueError):
            pl = {}
        if not isinstance(pl, dict):
            continue
        aid, cid = pl.get("application_id"), pl.get("candidate_id")
        try:
            aid = int(aid) if aid is not None else None
            cid = int(cid) if cid is not None else None
        except (TypeError, ValueError):
            continue
        if aid is not None:
            ok = aid in app_ids
        else:
            ok = cid is not None and cid in cand_ids
        if ok:
            out.append(row)
            if limit and len(out) >= limit:
                break
    return out


def _find_agent_report(task_glob: str, cand_id, directory=None):
    """Neuester Agent-Bericht fuer GENAU diesen Kandidaten oder None.

    Dateischema (Runner scripts/agent-runner.py:959, ls ergebnisse):
    `<task>-kandidat-<id>-<YYYY-MM-DD>.md`. Exakter Match statt Teilstring
    ('kandidat-1' traf kandidat-10..19). Neueste = groesstes Datum im Namen
    (mtime nur als Gleichstand-Tiebreaker), nicht Alphabet."""
    directory = _Path(directory) if directory is not None else logic.ERGEBNISSE
    prefix = task_glob.rstrip("*")
    rx = _re.compile(
        rf"^{_re.escape(prefix)}kandidat-{int(cand_id)}-(\d{{4}}-\d{{2}}-\d{{2}})\.md$"
    )
    best = None
    for f in directory.glob(task_glob):
        m = rx.match(f.name)
        if not m:
            continue
        key = (m.group(1), f.stat().st_mtime)
        if best is None or key > best[0]:
            best = (key, f)
    return best[1] if best else None


def _list_candidates(conn, employer_id, status_filter: str = "alle", query: str = "") -> list[dict]:
    """Kandidaten-Suche: Bewerber des eigenen Arbeitgebers ZUERST (aelteste Bewerbung zuerst,
    applicants-first.md), danach uebrige Kandidaten mit Lebenslauf (id DESC).
    Textsuche (Name/Skills, case-insensitive) in Python. Kein LIMIT (Tabelle paginiert)."""
    ph = ",".join("?" * len(APPLICANT_ACTIVE))
    cv_ph = ",".join("?" * len(CAND_CV_STATUS))
    cols = "c.id, c.name, c.hard_skills, c.berufserfahrung_jahre, c.status"
    if status_filter and status_filter != "alle":
        cand_cond, cand_args = "c.status = ?", [status_filter]
    else:
        cand_cond, cand_args = f"c.status IN ({cv_ph})", list(CAND_CV_STATUS)
    # Aktive Bewerber dieses Arbeitgebers (ein Eintrag je Kandidat, juengster Status der
    # aeltesten aktiven Bewerbung) -- unabhaengig vom CV-Status, aber mit Statusfilter,
    # sofern ein konkreter Kandidatenstatus gewaehlt ist.
    app_sql = (
        f"SELECT {cols}, MIN(a.erstellungsdatum), "
        "  (SELECT a2.status FROM applications a2 JOIN jobs j2 ON j2.id = a2.job_id "
        f"   WHERE a2.candidate_id = c.id AND j2.employer_id = ? AND a2.status IN ({ph}) "
        "   ORDER BY a2.erstellungsdatum ASC, a2.id ASC LIMIT 1) "
        "FROM candidates c JOIN applications a ON a.candidate_id = c.id "
        "JOIN jobs j ON j.id = a.job_id "
        f"WHERE j.employer_id = ? AND a.status IN ({ph}) "
    )
    app_args: list = [employer_id, *APPLICANT_ACTIVE, employer_id, *APPLICANT_ACTIVE]
    if status_filter and status_filter != "alle":
        app_sql += "AND c.status = ? "
        app_args.append(status_filter)
    app_sql += "GROUP BY c.id ORDER BY MIN(a.erstellungsdatum) ASC, c.id ASC"
    applicants = conn.execute(app_sql, app_args).fetchall()
    app_ids = {r[0] for r in applicants}
    passive = [
        r for r in conn.execute(
            f"SELECT {cols} FROM candidates c WHERE {cand_cond} ORDER BY c.id DESC", cand_args
        ).fetchall() if r[0] not in app_ids
    ]
    rows = [
        {"id": r[0], "name": r[1] or _("Unbekannt"), "skills": r[2] or "",
         "exp": r[3] if r[3] is not None else "", "status": r[4] or _("unbekannt"),
         "bewerber": r[6] or ""}
        for r in applicants
    ] + [
        {"id": r[0], "name": r[1] or _("Unbekannt"), "skills": r[2] or "",
         "exp": r[3] if r[3] is not None else "", "status": r[4] or _("unbekannt"),
         "bewerber": ""}
        for r in passive
    ]
    q = (query or "").strip().lower()
    if q:
        rows = [r for r in rows if q in r["name"].lower() or q in str(r["skills"]).lower()]
    return rows


# ─── 1. Dashboard ────────────────────────────────────────────────────

def _page_dashboard(s: dict) -> None:
    section_header(title=_('Dashboard'), subtitle=_('Arbeitgeber-Uebersicht'), icon="dashboard")

    employer_id = s.get("employer_id")

    @ui.refreshable
    def dashboard_stats():
        try:
            conn = db.get_conn()
            job_count = conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE employer_id = ?", (employer_id,)
            ).fetchone()[0]
            app_count = conn.execute(
                "SELECT COUNT(*) FROM applications a JOIN jobs j ON a.job_id = j.id WHERE j.employer_id = ?",
                (employer_id,),
            ).fetchone()[0]
            candidate_count = conn.execute(
                "SELECT COUNT(DISTINCT a.candidate_id) FROM applications a JOIN jobs j ON a.job_id = j.id WHERE j.employer_id = ?",
                (employer_id,),
            ).fetchone()[0]
            pending_tasks = conn.execute(
                "SELECT COUNT(*) FROM agent_tasks WHERE status = 'pending'"
            ).fetchone()[0]
            conn.close()

            with ui.grid(columns=4).classes(C.GRID_4 + " mb-6"):
                # P1 (28.09.2026): Kacheln sind Einstiegspunkte (3-Klick-Regel).
                # Vorher ohne on_click → statische Karte, cursor: auto, Klick ohne
                # Wirkung (Beleg: messung-vorher.json, 'clicks: 0').
                stat_card(_('Offene Stellen'), job_count, "work", color=PRIMARY,
                          on_click=lambda: ui.navigate.to("/employer/stellen"))
                stat_card(_('Bewerbungen'), app_count, "send", color=ACCENT,
                          on_click=lambda: ui.navigate.to("/employer/stellen"))
                stat_card(_('Kandidaten'), candidate_count, "people", color=SECONDARY,
                          on_click=lambda: ui.navigate.to("/employer/kandidaten"))
                stat_card(_('Agent-Tasks'), pending_tasks, "smart_toy", color="#7C3AED",
                          on_click=lambda: ui.navigate.to("/employer/agent_details"))
        except Exception as ex:
            # R6-3 (30.09.2026): nie wieder stumm (vorher `pass`) — Dashboard-
            # Kacheln verschwanden ohne Spur bei DB-Fehlern.
            _log.exception("dashboard_stats fehlgeschlagen: %s", ex)
            ui.label(_('⚠️ Dashboard-Zahlen konnten nicht geladen werden: {0}').format(ex)) \
                .classes("text-red-600")
            ui.button(_('Neu laden'), on_click=dashboard_stats.refresh)

    dashboard_stats()
    ui.timer(interval=10.0, callback=dashboard_stats.refresh)

    # ─── Charts ─────────────────────────────────────────────────────────
    try:
        conn = db.get_conn()
        # Status-Verteilung (Pie Chart)
        status_rows = conn.execute("""
            SELECT a.status, COUNT(*) as cnt
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            WHERE j.employer_id = ?
            GROUP BY a.status
        """, (employer_id,)).fetchall()
        conn.close()

        if status_rows:
            status_data = [{"value": r[1], "name": r[0] or _("unbekannt")} for r in status_rows]
            with ui.card().classes(C.CARD + " w-full mt-4"):
                ui.label(_('Bewerbungen nach Status')).classes(C.CARD_TITLE + " mb-2")
                ui.echart({
                    "title": {"text": _("Status-Verteilung"), "left": "center"},
                    "tooltip": {"trigger": "item"},
                    "legend": {"orient": "vertical", "left": "left"},
                    "series": [{
                        "type": "pie",
                        "radius": "50%",
                        "data": status_data,
                        "emphasis": {
                            "itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0, "shadowColor": "rgba(0, 0, 0, 0.5)"}
                        }
                    }]
                }).classes("w-full h-64")
    except Exception as ex:
        # R6-3 (30.09.2026): vorher `pass` — die Status-Verteilung verschwand
        # still ohne jede Rueckmeldung.
        _log.exception("Dashboard-Charts fehlgeschlagen: %s", ex)
        with ui.card().classes(C.CARD + " w-full mt-4"):
            ui.label(_('⚠️ Charts konnten nicht geladen werden: {0}').format(ex)).classes("text-red-600")
            ui.button(_('Neu laden'), on_click=lambda: ui.navigate.reload()).classes(
                C.BTN_SECONDARY + " mt-2")

    with ui.card().classes(C.CARD_HOVER + " w-full mt-6"):
        ui.label(_('Daten exportieren')).classes(C.CARD_TITLE + " mb-3")
        ui.label(_('Kandidaten-Liste als CSV-Datei herunterladen.')).classes(C.SMALL + " mb-3")

        def export_candidates():
            conn = db.get_conn()
            candidates = conn.execute("""
                SELECT c.id, c.name, c.hard_skills, c.berufserfahrung_jahre, c.abschluss, c.status
                FROM candidates c
                JOIN applications a ON a.candidate_id = c.id
                JOIN jobs j ON a.job_id = j.id
                WHERE j.employer_id = ?
                ORDER BY c.id DESC
            """, (employer_id,)).fetchall()
            conn.close()

            output = io.StringIO()
            writer = csv.writer(output)
            # i18n P9.4 (06.10.2026): Header in Session-Sprache (Export-Artefakt
            # = Nutzer-sichtbar); Spaltenreihenfolge/Werte unverändert.
            writer.writerow([_("ID"), _("Name"), _("Skills"), _("Erfahrung (Jahre)"),
                             _("Abschluss"), _("Status")])
            for c in candidates:
                writer.writerow([
                    c[0], c[1] or "", c[2] or "", c[3] or "", c[4] or "", c[5] or ""
                ])
            ui.download.content(output.getvalue(), "kandidaten.csv", media_type="text/csv")

        with ui.row().classes("gap-2"):
            ui.button(_('CSV Export'), icon="download", on_click=export_candidates).classes(C.BTN_PRIMARY)
            ui.button(_('PDF Export'), icon="picture_as_pdf", on_click=lambda: export_candidates_pdf(employer_id)).classes(C.BTN_PRIMARY)


# ─── 2. Portal (Firmenprofil + Stellen) ──────────────────────────────

def _page_portal(s: dict) -> None:
    section_header(title=_('Portal'), subtitle=_('Firmenprofil & Stellen'), icon="business")

    employer_id = s.get("employer_id")
    conn = db.get_conn()

    # Firmenprofil
    emp = conn.execute(
        "SELECT firma, kontaktperson, branche, groesse, standort, website, beschreibung, telefon FROM employers WHERE id = ?",
        (employer_id,),
    ).fetchone()

    with ui.tabs().classes("w-full") as tabs:
        tab_profil = ui.tab(_('Firmenprofil'), icon="business")
        tab_stellen = ui.tab(_('Stellen'), icon="work")

    with ui.tab_panels(tabs, value=tab_profil).classes("w-full"):
        with ui.tab_panel(tab_profil):
            ui.label(_('Firmenprofil')).classes(C.CARD_TITLE + " mb-4")

            branchen = ["IT", "Consulting", "Industrie", "Handel", "Gesundheit", "Finanzen", "Sonstiges"]
            grossen = ["1-10", "11-50", "51-200", "201-1000", "1000+"]

            branche_select = ui.select(
                options={v: _(v) for v in branchen},
                value=emp[2] if emp and emp[2] in branchen else branchen[0],
                label=_('Branche'),
            ).classes("w-full")

            groesse_select = ui.select(
                options={v: _(v) for v in grossen},
                value=emp[3] if emp and emp[3] in grossen else grossen[0],
                label=_('Mitarbeiterzahl'),
            ).classes("w-full")

            standort_input = ui.input(
                label=_('Hauptstandort'),
                value=emp[4] if emp else "",
            ).classes("w-full")

            website_input = ui.input(
                label=_('Website'),
                value=emp[5] if emp else "",
            ).classes("w-full")

            telefon_input = ui.input(
                label=_('Telefon'),
                value=emp[7] if emp else "",
            ).classes("w-full")

            beschreibung_input = ui.textarea(
                label=_('Kurzprofil (max. 500 Zeichen)'),
                value=emp[6] if emp else "",
            ).classes("w-full")

            def save_profil():
                db.upsert_employer(
                    employer_id=employer_id,
                    branche=branche_select.value,
                    groesse=groesse_select.value,
                    standort=standort_input.value,
                    website=website_input.value,
                    beschreibung=beschreibung_input.value,
                    telefon=telefon_input.value,
                )
                ui.notify(_('✅ Firmenprofil gespeichert.'), type="positive")

            ui.button(_('💾 Firmenprofil speichern'), on_click=save_profil).classes(C.BTN_PRIMARY + " mt-4")

            # ── Passwort ändern (N5, Design-Entscheidung: knowledge/portal/employer-portal-fields.md) ──
            with ui.expansion(_('Passwort aendern'), icon="lock").classes("w-full mt-4"):
                pw_alt = ui.input(label=_('Aktuelles Passwort'), password=True).classes("w-full")
                pw_neu = ui.input(label=_('Neues Passwort'), password=True).classes("w-full")
                pw_wdh = ui.input(label=_('Neues Passwort wiederholen'), password=True).classes("w-full")

                async def do_change_pw_emp():
                    # P2 (05.10.2026): change_password enthält bis zu 3 argon2-Ops
                    # (0,4–1,2 s je Op) → Worker-Thread (NiceGUI-FAQ run.io_bound).
                    # SQLite-Verbindung darf die Thread-Grenze nicht überschreiten
                    # (check_same_thread) → im Worker erzeugt (Design-Entscheidung).
                    if not pw_alt.value or not pw_neu.value or not pw_wdh.value:
                        ui.notify(_('Bitte alle Felder ausfuellen.'), type="warning")
                        return
                    if pw_neu.value != pw_wdh.value:
                        ui.notify(_('Passwoerter stimmen nicht ueberein.'), type="negative")
                        return

                    def _work():
                        conn_pw = db.get_conn()
                        try:
                            return logic.change_password(
                                conn_pw, "employers", employer_id,
                                pw_alt.value, pw_neu.value)
                        finally:
                            conn_pw.close()

                    ok, msg = await run.io_bound(_work)
                    # S5 (12.10.2026): logic.change_password liefert deutsche
                    # msgids -> am Call-Site übersetzen (Spec: knowledge/system/i18n.md).
                    ui.notify(_(msg), type="positive" if ok else "negative")

                ui.button(_('Passwort aendern'), on_click=do_change_pw_emp).classes(C.BTN_PRIMARY + " mt-2")

        with ui.tab_panel(tab_stellen):
            ui.label(_('Stelle ausschreiben')).classes(C.CARD_TITLE + " mb-4")

            titel_input = ui.input(label=_('Titel'), placeholder=_('z.B. Senior Python Developer')).classes("w-full")
            beschreibung_input = ui.textarea(label=_('Beschreibung (min. 50 Zeichen)')).classes("w-full")

            with ui.grid(columns=2).classes("w-full gap-4"):
                standort_input = ui.input(label=_('Arbeitsort')).classes("w-full")
                land_select = ui.select(
                    options=["DE", "FR", "CH"],
                    value="DE",
                    label=_('Land'),
                ).classes("w-full")
                typ_select = ui.select(
                    options={v: _(v) for v in ["Vollzeit", "Teilzeit", "Freelance", "Hybrid", "Remote"]},
                    value="Vollzeit",
                    label=_('Stellentyp'),
                ).classes("w-full")
                hard_input = ui.input(label=_('Must-Have-Skills (kommasepariert)')).classes("w-full")
                soft_input = ui.input(label=_('Soft Skills (kommasepariert)')).classes("w-full")

            with ui.grid(columns=2).classes("w-full gap-4"):
                erfahrung_input = ui.number(label=_('Min. Berufserfahrung (Jahre)'), value=3, min=0, max=30).classes("w-full")
                de_select = ui.select(
                    options={v: _(v) for v in ["Keine Anforderung", "A1", "A2", "B1", "B2", "C1", "C2", "Muttersprache"]},
                    value="Keine Anforderung",
                    label=_('Deutsch-Level'),
                ).classes("w-full")
                en_select = ui.select(
                    options={v: _(v) for v in ["Keine Anforderung", "A1", "A2", "B1", "B2", "C1", "C2", "Muttersprache"]},
                    value="Keine Anforderung",
                    label=_('Englisch-Level'),
                ).classes("w-full")
                abschluss_select = ui.select(
                    options={v: _(v) for v in ["Egal", "Bachelor", "Master", "PhD"]},
                    value="Egal",
                    label=_('Abschluss'),
                ).classes("w-full")

            with ui.grid(columns=2).classes("w-full gap-4"):
                gehalt_min = ui.number(label=_('Gehaltsrahmen von (EUR)'), value=0, min=0, max=300000, step=1000).classes("w-full")
                gehalt_max = ui.number(label=_('Gehaltsrahmen bis (EUR)'), value=0, min=0, max=300000, step=1000).classes("w-full")

            def create_job():
                if not titel_input.value or not beschreibung_input.value or not standort_input.value or not hard_input.value:
                    ui.notify(_('❌ Titel, Beschreibung, Arbeitsort und Must-Have-Skills sind Pflichtfelder.'), type="negative")
                    return
                if len(beschreibung_input.value) < 50:
                    ui.notify(_('❌ Beschreibung muss mindestens 50 Zeichen haben.'), type="negative")
                    return

                btn_stelle.disable()
                try:
                    job_id = db.insert_job(
                        employer_id=employer_id,
                        titel=titel_input.value,
                        beschreibung=beschreibung_input.value,
                        standort=standort_input.value,
                        land=land_select.value,
                        stellentyp=typ_select.value,
                        hard_skills=hard_input.value,
                        soft_skills=soft_input.value,
                        berufserfahrung_jahre=int(erfahrung_input.value),
                        deutsch_level=de_select.value,
                        englisch_level=en_select.value,
                        abschluss=abschluss_select.value,
                        gehaltsrahmen_min=int(gehalt_min.value) if gehalt_min.value else None,
                        gehaltsrahmen_max=int(gehalt_max.value) if gehalt_max.value else None,
                    )
                    if job_id:
                        ui.notify(_('✅ Stelle ausgeschrieben: {0}. Kandidaten-Matching ist jetzt möglich.').format(titel_input.value), type="positive")
                        titel_input.value = None
                        beschreibung_input.value = None
                        standort_input.value = None
                        hard_input.value = None
                        soft_input.value = None
                        erfahrung_input.value = 3
                        gehalt_min.value = 0
                        gehalt_max.value = 0
                        refresh_jobs()
                    else:
                        ui.notify(_('❌ Fehler beim Erstellen der Stelle.'), type="negative")
                finally:
                    btn_stelle.enable()

            btn_stelle = ui.button(_('📢 Stelle ausschreiben'), on_click=create_job).classes(C.BTN_PRIMARY + " mt-4")

            ui.separator().classes("my-6")
            ui.label(_('Meine Stellen')).classes(C.CARD_TITLE + " mb-4")

            jobs_container = ui.column().classes("w-full")

            def refresh_jobs():
                jobs_container.clear()
                with jobs_container:
                    jobs = conn.execute(
                        "SELECT id, titel, standort, stellentyp, status, erstellt_am FROM jobs WHERE employer_id = ? ORDER BY id DESC",
                        (employer_id,),
                    ).fetchall()
                    if not jobs:
                        empty_state(icon="work_off", title=_('Noch keine Stellen ausgeschrieben'))
                        return

                    for j in jobs:
                        with ui.expansion(_('#{0} {1} – {2} ({3}) – {4}').format(j[0], j[1], j[2], _(j[3]), status_label(j[4]))).classes("w-full mb-2"):
                            with ui.grid(columns=2).classes("w-full gap-4"):
                                ui.label(_('Status: {0}').format(status_label(j[4]))).classes(C.BODY)
                                status_select = ui.select(
                                    options={v: status_label(v) for v in ["aktiv", "pausiert", "besetzt", "abgelaufen"]},
                                    value=j[4],
                                    label=_('Status ändern'),
                                ).classes("w-full")

                            def save_status(job_id=j[0], sel=status_select):
                                db.update_job_status(job_id, sel.value, changed_by=s.get("employer_email", "system"))
                                ui.notify(_('✅ Status geändert: {0}').format(sel.value), type="positive")
                                refresh_jobs()

                            ui.button(_('💾 Status speichern'), on_click=save_status).classes(C.BTN_PRIMARY + " mt-2")
                            ui.label(_('Erstellt: {0}').format(j[5][:10] if j[5] else '–')).classes("text-caption")

            refresh_jobs()

    conn.close()


# ─── 2b. Stellenangebote (HR-write, Port admin.py:459-554) ──────────

def _page_stellen(s: dict) -> None:
    section_header(title=_('Stellenangebote'), subtitle=_('Bewerber-Status verwalten'), icon="work")

    employer_id = s.get("employer_id")
    conn = db.get_conn()

    # Bewerbungen ueber ALLE Stellen dieses Employers (Muster: app.py:3083-3088)
    applications = conn.execute("""
        SELECT a.id, a.candidate_id, a.status, a.bewerbungstext, a.erstellungsdatum,
               j.titel, j.id, e.firma, COALESCE(c.name, '')
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        JOIN employers e ON j.employer_id = e.id
        LEFT JOIN candidates c ON c.id = a.candidate_id
        WHERE e.id = ? ORDER BY a.erstellungsdatum DESC
    """, (employer_id,)).fetchall()

    AKTIV = ("eingegangen", "angesehen", "eingeladen")
    apps_aktiv = [r for r in applications if r[2] in AKTIV]
    apps_archiv = [r for r in applications if r[2] not in AKTIV]

    # N-S2 (01.10.2026): KEINE eigene Liste mehr — dieselbe Whitelist wie die
    # Match-Seite: _legal_actions() liest ALLOWED_TRANSITIONS (Modulebene,
    # Quelle: knowledge/lifecycle/application-status.md „Erlaubte Übergänge“).
    # Endstatus liefern [] („Finaler Status erreicht.“), Reihenfolge =
    # _MATCH_ACTION_ORDER (identisch zum vorherigen erl-Dict).
    badge = {"eingegangen": "📨", "angesehen": "👁️", "eingeladen": "✅", "eingestellt": "🎉",
             "abgelehnt": "❌", "zurückgezogen": "↩️"}
    _hook_task = {"eingeladen": "create_invitation", "abgelehnt": "send_rejection",
                  "eingestellt": "onboarding_release"}

    # P1-13 (30.09.2026): standardmaessig aufgeklappt — die aktiven Bewerber sind
    # der Arbeitsvorrat der Seite und standen sonst hinter einem Klick.
    with ui.expansion(_('📥 Aktive Bewerber ({0})').format(len(apps_aktiv)), icon="how_to_reg",
                      value=True).classes("w-full mb-4"):
        if not apps_aktiv:
            empty_state(icon="inbox", title=_('Keine aktiven Bewerbungen'))
        for a_id, k_id, a_status, a_text, a_dat, j_titel, j_id, e_firma, k_name in apps_aktiv:
            agent_status = db.get_agent_task_status(a_id) or {}
            _ms = agent_status.get("match_candidate", "-")
            _cs = agent_status.get("check_compliance", "-")
            _fs = agent_status.get("assess_culture_fit", "-")
            badge_txt = _('Match {0} · Compliance {1} · Culture-Fit {2}').format(_ms, _cs, _fs) if agent_status else _('(noch nicht gestartet)')

            with ui.card().classes(C.CARD_HOVER + " w-full mb-2 py-2"):
                with ui.row().classes("items-center justify-between w-full px-4"):
                    with ui.row().classes("items-center gap-3"):
                        ui.label(_('{0} #{1}').format(badge.get(a_status, '📄'), a_id)).classes(C.MUTED)
                        with ui.column():
                            # P2-8 (01.10.2026): Pseudonym bis Status `eingeladen`
                            # (Spec employer-portal-fields.md:110). Klartext-Kern
                            # bleibt: nie rohes `#id`, sondern "Kandidat #N"
                            # (vorher P1 28.09.2026: Klarname statt "Kandidat #22")
                            ui.label(anzeige_name(k_name, k_id, a_status)).classes("font-medium")
                            ui.label(j_titel).classes(C.SMALL)
                            ui.label(_('Eingegangen: {0}').format(str(a_dat)[:10])).classes(C.SMALL)
                    with ui.row().classes("items-center gap-2"):
                        status_badge(a_status)
                        # P0 (28.09.2026): vorher ui.badge(...).props("color=blue-1
                        # outline") = #E3F2FD auf weiss → 1.14:1. Jetzt neutrale
                        # Theme-Komponente mit dunkler Schrift.
                        ui.badge(_('🤖 {0}').format(badge_txt), color=None).classes(
                            C.BADGE_GRAY + " status-badge")

                if a_text:
                    ui.label(_('Motivation: {0}').format(a_text[:200])).classes(C.SMALL + " px-4 mt-1")

                naechste = _legal_actions(a_status)
                if naechste:
                    # C1 (22.09.2026): Einladungs-Termin Inline vor → eingeladen
                    # Quelle: app.py:3173-3185 (Payload termin_*, Spec agent-automation.md §5)
                    _inv_datum = _inv_zeit = _inv_dauer = None
                    if "eingeladen" in naechste:
                        ui.label(_('📅 Einladungs-Termin (wird in die Automatik-Mail übernommen):')).classes(C.SMALL + " px-4")
                        with ui.row().classes("items-center gap-2 px-4"):
                            # NiceGUI ≥3.3 (offiziell, nicegui.io/documentation/date_input + time_input):
                            # ui.date/time kennen kein label → *_input-Elemente (QInput + Picker)
                            _inv_datum = ui.date_input(_("Datum"), value=str((_dt.now() + _timedelta(days=1)).date())).classes("w-40")
                            _inv_zeit = ui.time_input(_("Uhrzeit"), value="10:00").classes("w-24")
                            _inv_dauer = ui.select([15, 30, 45, 60], value=30, label=_('Dauer (Min.)')).classes("w-32")
                    with ui.row().classes("gap-2 px-4 pb-2"):
                        for ns in naechste:
                            # Termin-Widgets als Default-Args binden (Snapshot): Loop-Late-Binding
                            # würde _inv_* am Klickzeitpunkt auf None der Folge-Card zurücksetzen.
                            def make_transition(_a_id=a_id, _k_id=k_id, _j_id=j_id, _ns=ns,
                                                _inv_d=_inv_datum, _inv_z=_inv_zeit, _inv_min=_inv_dauer):
                                def _do():
                                    conn2 = db.get_conn()
                                    # N-S2 (01.10.2026): Klick-Guard wie Match-Seite `_legal`
                                    # — Ausgangsstatus live aus der DB lesen und gegen
                                    # ALLOWED_TRANSITIONS pruefen. Bei Verstoss: kein UPDATE,
                                    # kein History-Eintrag, kein Hook-Task (Whitelist B2-5a).
                                    _row = conn2.execute(
                                        "SELECT status FROM applications WHERE id = ?", (_a_id,)).fetchone()
                                    _old = _row[0] if _row else None
                                    if _ns not in ALLOWED_TRANSITIONS.get(_old, set()):
                                        conn2.close()
                                        ui.notify(_('Ungueltiger Statusuebergang (Whitelist ALLOWED_TRANSITIONS).'),
                                                  type="negative")
                                        ui.navigate.reload()
                                        return
                                    conn2.execute("UPDATE applications SET status = ?, aktualisiert_am = CURRENT_TIMESTAMP WHERE id = ?", (_ns, _a_id))
                                    conn2.execute("INSERT INTO application_status_history (application_id, status, changed_by) VALUES (?, ?, 'arbeitgeber')", (_a_id, _ns))
                                    conn2.commit()
                                    # R3-5: Benachrichtigung des Kandidaten NACH commit
                                    # (Stellen-Seite: eigener HR-Klick-Übergang)
                                    _notify_statuswechsel(conn2, _a_id, _ns)
                                    conn2.close()
                                    task = _hook_task.get(_ns)
                                    if task:
                                        _pl = {"application_id": _a_id, "candidate_id": _k_id,
                                               "job_id": _j_id, "trigger": "hr_klick_portal"}
                                        if task == "create_invitation" and _inv_d is not None:
                                            _pl.update({
                                                "termin_datum": str(_inv_d.value),
                                                "termin_uhrzeit": str(_inv_z.value),
                                                "termin_dauer_min": int(_inv_min.value),
                                            })
                                        db.queue_agent_task(task, _pl)
                                    ui.notify(_('Status geaendert: {0}').format(_ns)
                                      + (_(", Agent-Task '{0}' gequeued").format(task) if task else ""),
                                      type="positive")
                                    # P1-13: auf der Seite bleiben. `navigate_to("employer",
                                    # "kandidaten")` schickte den HR nach jedem Klick weg;
                                    # reload rendert dieselbe Seite mit dem neuen Status neu.
                                    ui.navigate.reload()
                                return _do
                            _colors = ("color=positive" if ns == "eingeladen" else
                                       "color=negative" if ns == "abgelehnt" else
                                       "color=primary")
                            if ns == "abgelehnt":
                                # P1-13: Bestaetigung vor "abgelehnt" — der Klick loest
                                # eine Absage-Mail und einen endgueltigen Status aus.
                                with ui.dialog() as _rej_dlg, ui.card().classes("w-[420px]"):
                                    ui.label(_('Bewerbung wirklich ablehnen?')).classes(C.CARD_TITLE)
                                    ui.label(
                                        _('{0} – {1}\n\nDer Status wird endgültig auf „Abgelehnt“ gesetzt und eine Absage-Mail an den Kandidaten ausgelöst.').format(anzeige_name(k_name, k_id, a_status), j_titel)
                                    ).classes(C.BODY)
                                    with ui.row().classes("justify-end gap-2 mt-2 w-full"):
                                        ui.button(_('Abbrechen'), on_click=_rej_dlg.close).props("flat")
                                        def _do_and_close(_f=make_transition()):
                                            _f()
                                            _rej_dlg.close()
                                        ui.button(_('Ja, ablehnen'), icon="block",
                                                  on_click=_do_and_close).props("color=negative")
                                ui.button(_('→ {0}').format(ns), on_click=_rej_dlg.open).props(_colors)
                            else:
                                ui.button(_('→ {0}').format(ns), on_click=make_transition()).props(_colors)
                else:
                    ui.label(_('Finaler Status erreicht.')).classes("text-caption px-4 pb-2")

                # Visum-Antrag-Bestaetigung (Spec v6, exakter application_id-Guard)
                if a_status == "eingeladen":
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
                                                                       "trigger": "hr_klick_portal"})
                            ui.notify(_('Visum-Schritte-Mail an Kandidaten ausgeloest.'), type="positive")
                            # P1-13: auf der Seite bleiben (siehe Statuswechsel oben)
                            ui.navigate.reload()
                        ui.button(_('📩 Visum-Antrag bestaetigen'), on_click=send_visa).props("color=primary").classes("px-4 pb-2")  # P1-4: Quasar-Semantik statt Tailwind (ui-design-system.md §2.5)
                    else:
                        ui.label(_('✅ Visum-Schritte-Mail versendet.')).classes("text-caption px-4 pb-2")

    with ui.expansion(_('📋 Archiv ({0}) – eingestellt / abgelehnt / zurückgezogen').format(len(apps_archiv)), icon="archive").classes("w-full mb-4"):
        if not apps_archiv:
            ui.label(_('Keine archivierten Bewerbungen.')).classes("text-caption")
        for a_id, k_id, a_status, a_text, a_dat, j_titel, j_id, e_firma, k_name in apps_archiv:
            with ui.row().classes("items-center gap-2 w-full py-1"):
                ui.label(_('{0} {1} – {2} ({3}, {4})').format(badge.get(a_status, '📄'), anzeige_name(k_name, k_id, a_status), j_titel, status_label(a_status), str(a_dat)[:10])).classes(C.BODY)

    conn.close()


# ─── 3. Kandidaten-Suche ────────────────────────────────────────────

def _page_kandidaten(s: dict) -> None:
    section_header(title=_('Kandidaten-Suche'), subtitle=_('Kandidaten mit Lebenslauf'), icon="search")
    employer_id = s.get("employer_id")

    # N-K1 (01.10.2026): Optionen einmal je Rendern aus der DB ableiten — nur real
    # vorkommende Pool-Status, Klartext-Labels (siehe _cand_status_options).
    _conn_opts = db.get_conn()
    try:
        _status_options = _cand_status_options(_conn_opts)
    finally:
        _conn_opts.close()

    def filter_candidates(status_filter: str, query: str = "") -> list[dict]:
        # Logik in _list_candidates (Modul-Helfer, pytest-bar): Bewerber dieses
        # Arbeitgebers zuerst (applicants-first.md), danach uebrige mit Lebenslauf.
        conn = db.get_conn()
        try:
            return _list_candidates(conn, employer_id, status_filter, query)
        finally:
            conn.close()

    with ui.column().classes("w-full gap-3"):
        with ui.row().classes("w-full items-end gap-3"):
            # N-K1: Klartext-Labels + nur real vorkommende Pool-Status
            # (Quelle: knowledge/ui-design-system.md §11 „Dropdown-/Filter-Optionen“)
            status_filter = ui.select(
                options=_status_options,
                value="alle",
                label=_('Status'),
                on_change=lambda e: render_table(),
            ).classes("w-64")
            search_input = ui.input(
                label=_('Suche (Name oder Skills)'), placeholder=_('z. B. Python'),
                on_change=lambda e: render_table(),
            ).props('clearable prepend_icon="search"').classes("w-72")

        def render_table():
            candidates = filter_candidates(status_filter.value or "alle", search_input.value or "")
            table_container.clear()
            with table_container:
                if not candidates:
                    empty_state(icon="people_off", title=_('Keine Kandidaten gefunden'))
                    return

                columns = [
                    {"name": "id", "label": _("Auswahl"), "field": "id", "sortable": True, "align": "left"},
                    {"name": "name", "label": _("Name"), "field": "name", "sortable": True, "align": "left"},
                    {"name": "bewerber", "label": _("Bewerbung"), "field": "bewerber", "sortable": True, "align": "left"},
                    {"name": "skills", "label": _("Skills"), "field": "skills", "align": "left"},
                    {"name": "exp", "label": _("Erfahrung (J.)"), "field": "exp", "sortable": True, "align": "left"},
                    {"name": "status", "label": _("Status"), "field": "status", "align": "left"},
                ]
                rows = [
                    {
                        "id": c["id"],
                        "name": c["name"],
                        "bewerber": _('📩 Bewerber ({0})').format(status_label(c['bewerber'])) if c["bewerber"] else "—",
                        "skills": c["skills"],
                        "exp": c["exp"],
                        "status": status_label(c["status"]) if c["status"] else "—",
                    }
                    for c in candidates
                ]

                table = ui.table(
                    columns=columns,
                    rows=rows,
                    row_key="id",
                    pagination=10,
                    selection="single",
                    on_select=lambda e: (
                        # P1 (28.09.2026): navigate_to() wechselte den Inhalt,
                        # aber die URL blieb stehen (gemessen: Inhalt
                        # 'Match-Ergebnis', Pfad '/employer/kandidaten') — der
                        # SPA-pushState greift aus dem Auswahl-Handler nicht.
                        # ui.navigate.to() erzwingt die echte Route.
                        # M-07 (01.10.2026): Fokus-Parameter ?kandidat=<id> mitgeben —
                        # die Match-Seite liest ihn (_parse_kandidat_param /
                        # _kandidat_query_param) und stellt den Kandidaten voran.
                        ui.navigate.to(
                            f"/employer/match?kandidat={e.selection[0]['id']}"
                            if e.selection and e.selection[0].get("id")
                            else "/employer/match"
                        )
                    ),
                ).classes("w-full")                # Custom status column rendering
                # P0 (28.09.2026): eine Status-Komponente fuer alle Rollen.
                # Vorher <q-badge :color="'blue'"> = #2196F3 mit weisser Schrift
                # → 3.12:1 (WCAG 2.1 SC 1.4.3 verlangt 4.5:1). Jetzt dieselben
                # Theme-Klassen wie status_badge() + Klartext statt DB-Slug.
                table.add_slot("body-cell-status", r'''
                    <q-td :props="props">
                        <span class="badge-glass status-badge"
                              :class="{
                                'badge-glass-green': props.value === 'aktiv',
                                'badge-glass-amber': props.value === 'zugeordnet' || props.value === 'registriert',
                                'badge-glass': props.value === 'lebenslauf_hochgeladen'
                              }">{{ {
                                'aktiv': 'Aktiv',
                                'zugeordnet': 'Zugeordnet',
                                'registriert': 'Registriert',
                                'lebenslauf_hochgeladen': 'Lebenslauf hochgeladen'
                              }[props.value] || props.value }}</span>
                    </q-td>
                ''')

                # P1 (28.09.2026): Zeile ist klickbar. NiceGUI-Slots kennen kein
                # 'parent' (gemessen: TypeError ... reading '$emit'), deshalb
                # leitet der Namens-Knopf den Klick an das Auswahl-Kästchen
                # derselben Zeile weiter — das war der einzige funktionierende
                # Weg zur Auswahl (gemessen vor der Aenderung: Klick auf die
                # Zelle tat nichts, cursor: auto).
                table.add_slot("body-cell-name", r'''
                    <q-td :props="props">
                        <q-btn flat no-caps color="primary" class="cursor-pointer self-start no-wrap"
                               :label="props.row.name"
                               @click="$el.closest('tr').querySelector('.q-checkbox').click()" />
                    </q-td>
                ''')

        table_container = ui.column().classes("w-full gap-3")
        # R5-1 (30.09.2026, pyflakes-Fund): hies 'refresh_table' — existierte
        # nicht (NameError beim Seitenrendern). Tatsaechlicher Name: render_table.
        render_table()


# ─── 3. Match-Ergebnis ──────────────────────────────────────────────

# Whitelist der Statusuebergaenge (Quelle: knowledge/lifecycle/application-status.md
# "Erlaubte Uebergaenge", knowledge/lifecycle/status-automation.md (a); Paritaet
# app.py erl_hr). Modul-Level seit 29.09.2026 (P0-3), damit die reinen Helfer
# darunter per pytest testbar sind; Inhalt unveraendert.
ALLOWED_TRANSITIONS = {
    "eingegangen": {"angesehen", "abgelehnt"},
    "angesehen": {"eingeladen", "abgelehnt"},
    "eingeladen": {"eingestellt", "abgelehnt"},
}

# Anzeige-Reihenfolge + Beschriftung der Aktionen (Design-Entscheidung 29.09.2026, P0-3)
_MATCH_ACTION_ORDER = ("angesehen", "eingeladen", "eingestellt", "abgelehnt")
_MATCH_ACTION_LABEL = {
    "angesehen": "Als angesehen markieren",
    "eingeladen": "Einladen",
    "eingestellt": "Einstellen",
    "abgelehnt": "Ablehnen",
}


def _legal_actions(status: str) -> list:
    """Ziel-Status der laut ALLOWED_TRANSITIONS erlaubten Aktionen einer Bewerbung.
    Finale/unbekannte Status (eingestellt/abgelehnt/zurückgezogen/None) -> []."""
    erlaubt = ALLOWED_TRANSITIONS.get(status, set())
    return [ns for ns in _MATCH_ACTION_ORDER if ns in erlaubt]


# R3-5 (30.09.2026, Nutzer-GO „A: Anbinden"): Statuswechsel -> Benachrichtigung
# des Kandidaten. Genau diese 3 HR-Klick-Ziel-Status duerfen eine Zeile schreiben;
# alles andere (angesehen, unbekannt, None) bleibt draussen (defensiv).
_STATUS_NOTIF = ("eingeladen", "abgelehnt", "eingestellt")


def _notify_statuswechsel(conn, app_id: int, status: str) -> None:
    """Schreibt EINE notifications-Zeile an den Kandidaten (role="candidate").

    Aufruf NACH erfolgreichem UPDATE+commit in den HR-Klick-Handlern
    (do_invite/do_reject/do_hire + make_transition auf /employer/stellen).

    Queryt selbst per `conn` (candidate_id + Firma + Job-Titel via
    JOIN jobs -> employers; `applications` hat keine employer_id) — die Handler
    liefern deshalb nur application_id und Ziel-Status.

    DESIGN-ENTSCHEIDUNG (Text, keine externe Quelle noetig — Verhalten):
      Titel "Bewerbungsstatus", Nachricht
      "Deine Bewerbung bei <Firma> für <Titel>: <Status>" — in der Erzeugungs-/Session-Sprache
      des auslösenden HR-Nutzers (E2, knowledge/system/i18n.md), nennt
      Firma und Stelle, kein Grund/Ablehnungsdetail (AGG-neutral, Paritaet zur
      neutralen Ablehnungs-Mail des Runners).
    Fehler im Helfer duerfen den Handler NICHT sprengen: alles in try/except
    mit print (db-Konvention, kein st./ui-Import noetig).
    """
    try:
        if status not in _STATUS_NOTIF:
            return
        row = conn.execute(
            "SELECT a.candidate_id, e.firma, j.titel FROM applications a "
            "JOIN jobs j ON j.id = a.job_id "
            "JOIN employers e ON e.id = j.employer_id "
            "WHERE a.id = ?", (app_id,),
        ).fetchone()
        if not row or row[0] is None:
            return
        cand_id, firma, titel = row
        db.insert_notification(
            cand_id, "candidate", _("Bewerbungsstatus"),
            _('Deine Bewerbung bei {0} für {1}: {2}').format(firma, titel, status),
        )
    except Exception as ex:  # noqa: BLE001 — Helfer darf den Handler nie brechen
        print(f"[notify_statuswechsel] Fehler application={app_id} status={status}: {ex}")


def _bar_pct(key: str, punkte) -> int:
    """Balken-Prozent einer Score-Kategorie = Punkte / KATEGORIE_MAX[key] x 100 (0..100).
    Quelle der Maxima: webui/logic.py KATEGORIE_MAX (roh_scores in berechne_match_score)."""
    maximum = logic.KATEGORIE_MAX.get(key)
    if not maximum:
        return 0
    try:
        pct = round(float(punkte or 0) / maximum * 100)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, int(pct)))


def _invite_termin_error(datum, uhrzeit, jetzt=None):
    """None wenn der Einladungstermin gueltig ist, sonst sichtbare Fehlermeldung.
    Regel (Design-Entscheidung): Datum+Uhrzeit duerfen nicht in der Vergangenheit liegen
    (Runner scripts/agent-runner.py:539-549 verwirft nur ein Datum < heute)."""
    jetzt = jetzt or _dt.now()
    if not datum:
        return _("Bitte ein Einladungsdatum waehlen.")
    try:
        d = _dt.strptime(str(datum)[:10], "%Y-%m-%d").date()
    except ValueError:
        return _("Einladungsdatum ist ungueltig (erwartet JJJJ-MM-TT).")
    try:
        t = _dt.strptime(str(uhrzeit or "").strip(), "%H:%M").time()
    except ValueError:
        return _("Uhrzeit ist ungueltig (erwartet HH:MM).")
    if _dt.combine(d, t) < jetzt.replace(second=0, microsecond=0):
        return _("Der Einladungstermin liegt in der Vergangenheit.")
    return None


def _parse_kandidat_param(raw):
    """Query-Parameter ?kandidat=<id> -> int > 0 oder None (Muell/leer/<=0 -> None)."""
    try:
        val = int(str(raw).strip())
    except (TypeError, ValueError):
        return None
    return val if val > 0 else None


def _kandidat_query_param():
    """Liest ?kandidat=<id> der Seiten-Anfrage (NiceGUI 3.17.1: ui.context.client.request ist
    die Starlette-Request des Seitenaufrufs). Einmal-Verbrauch je Seitenaufruf: der erste
    Render von _page_match liest den Wert und markiert ihn im Request-Scope als verbraucht,
    damit ein SPA-Wechsel (Sidebar weg und zurueck) den Filter nicht erneut setzt."""
    try:
        from nicegui import context as _ng_context
        req = _ng_context.client.request
        if req.scope.get("kmhr_match_kandidat_verbraucht"):
            return None
        req.scope["kmhr_match_kandidat_verbraucht"] = True
        return _parse_kandidat_param(req.query_params.get("kandidat"))
    except Exception:
        return None


def _page_match(s: dict) -> None:
    section_header(title=_('Match-Ergebnis'), subtitle=_('Live-Score aus DB'), icon="compare_arrows")

    employer_id = s.get("employer_id")

    def _legal(new_status: str, app_id: int) -> bool:
        # B2-5a (status-automation.md (c-a)1): Whitelist-Guard gegen den Ausgangs-
        # status, Parität app.py:3766 allowed_transitions.get(app_status, set())
        conn = db.get_conn()
        row = conn.execute("SELECT status FROM applications WHERE id = ?", (app_id,)).fetchone()
        conn.close()
        old = row[0] if row else None
        return new_status in ALLOWED_TRANSITIONS.get(old, set())

    def _app_info(app_id: int):
        """(candidate_id, job_id, job_titel, kandidat_name) einer Bewerbung — nur wenn sie zu
        einer Stelle DIESES Arbeitgebers gehoert, sonst None (P0-3: Dialoge tragen die
        application_id; Kandidat/Stelle werden aus der DB abgeleitet, nicht aus dem UI-Zustand)."""
        conn = db.get_conn()
        row = conn.execute("""
            SELECT a.candidate_id, a.job_id, j.titel, c.name
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            JOIN candidates c ON c.id = a.candidate_id
            WHERE a.id = ? AND j.employer_id = ?
        """, (app_id, employer_id)).fetchone()
        conn.close()
        return row

    def _data_signature():
        """Aenderungs-Signatur fuer den 15-s-Timer (P0-3 f): nur wenn sich Bewerbungen dieses
        Arbeitgebers, seine Stellen, die Kandidaten oder die Agent-Queue geaendert haben,
        wird match_content neu gerechnet (sonst bleiben offene Details stehen).
        agent_tasks hat keine employer-Spalte -> globale Signatur (Design-Entscheidung)."""
        conn = db.get_conn()
        try:
            return (
                conn.execute(
                    "SELECT COUNT(*), MAX(a.aktualisiert_am), MAX(a.id) FROM applications a "
                    "JOIN jobs j ON a.job_id = j.id WHERE j.employer_id = ?",
                    (employer_id,)).fetchone(),
                conn.execute(
                    "SELECT COUNT(*), MAX(aktualisiert_am), MAX(id) FROM jobs WHERE employer_id = ?",
                    (employer_id,)).fetchone(),
                conn.execute("SELECT COUNT(*), MAX(aktualisiert_am), MAX(id) FROM candidates").fetchone(),
                conn.execute(
                    "SELECT COUNT(*), MAX(id), MAX(finished_at), "
                    "SUM(status IN ('pending', 'running')) FROM agent_tasks").fetchone(),
            )
        except Exception:
            return object()  # Fehler -> nie "gleich" -> altes Verhalten (immer refreshen)
        finally:
            conn.close()

    _sig = {"v": None}
    # Fokus-Filter (Query-Parameter ?kandidat=<id>, Agent B / Kandidaten-Suche);
    # Zustand liegt hier (nicht im refreshable), damit der Timer ihn nicht zuruecksetzt.
    _focus = {"cid": _kandidat_query_param()}

    def _refresh_now():
        _sig["v"] = _data_signature()
        match_content.refresh()

    def _tick():
        sig = _data_signature()
        if sig != _sig["v"]:
            _sig["v"] = sig
            match_content.refresh()

    def _clear_focus():
        _focus["cid"] = None
        _refresh_now()

    # ─── Modal: Bewerber einladen (mit Termin-Auswahl, N2-Port app.py:3688-3700) ───
    # P0-3 (29.09.2026): der Dialog bekommt die application_id (nicht die candidate_id);
    # das Freitext-Feld "Nachricht" ist entfernt (create_invitation verwertet kein
    # Nachrichtenfeld: scripts/agent-runner.py:497-, grep 'nachricht' = 0 Treffer).
    _invite_ctx = {"app_id": 0}
    with ui.dialog() as invite_dialog, ui.card().classes("w-96"):
        ui.label(_('Kandidat einladen')).classes("text-lg font-bold mb-4")
        invite_name_label = ui.label('').classes("mb-2")
        # Einladungs-Termin (wird in die Automatik-Mail übernommen, app.py:3689-3700)
        ui.markdown(_('**📅 Einladungs-Termin:**')).classes("mt-2")
        with ui.row().classes("items-center gap-2 w-full"):
            invite_datum = ui.date(value=str((_dt.now() + _timedelta(days=1)).date()), mask="YYYY-MM-DD").classes("w-40")
            invite_zeit = ui.time(value="10:00").classes("w-24")
        invite_dauer = ui.select([15, 30, 45, 60], value=30, label=_('Dauer (Min.)')).classes("w-32")
        invite_error = ui.label('').classes("text-negative text-sm mt-2")
        invite_error.set_visibility(False)
        with ui.row().classes("justify-end gap-2 mt-4"):
            ui.button(_('Abbrechen'), on_click=invite_dialog.close).props("flat")
            def do_invite():
                app_id = _invite_ctx["app_id"]
                info = _app_info(app_id) if app_id else None
                if not info:
                    ui.notify(_('Bewerbung nicht gefunden.'), type="negative")
                    invite_dialog.close()
                    _refresh_now()
                    return
                cid, job_id = info[0], info[1]
                _terr = _invite_termin_error(invite_datum.value, invite_zeit.value)
                if _terr:
                    # Dialog bleibt offen, Meldung sichtbar (P0-3: Termin nicht in der Vergangenheit)
                    invite_error.set_text(_terr)
                    invite_error.set_visibility(True)
                    return
                invite_error.set_visibility(False)
                if not _legal("eingeladen", app_id):
                    ui.notify(_('Ungueltiger Statusuebergang (Whitelist ALLOWED_TRANSITIONS).'), type="negative")
                    invite_dialog.close()
                    _refresh_now()
                    return
                _inv_vals = {
                    "termin_datum": str(invite_datum.value),
                    "termin_uhrzeit": str(invite_zeit.value),
                    "termin_dauer_min": int(invite_dauer.value),
                }
                conn = db.get_conn()
                conn.execute("UPDATE applications SET status='eingeladen', aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?", (app_id,))
                conn.execute("INSERT INTO application_status_history (application_id, status, changed_by) VALUES (?, 'eingeladen', 'arbeitgeber')", (app_id,))
                conn.commit()
                _notify_statuswechsel(conn, app_id, "eingeladen")  # R3-5 nach commit
                conn.close()
                db.queue_agent_task("create_invitation", {"application_id": app_id, "candidate_id": cid, "job_id": job_id, "trigger": "hr_klick_portal", **_inv_vals})
                ui.notify(_('Eingeladen - Termin {0} {1} geplant.').format(_inv_vals['termin_datum'], _inv_vals['termin_uhrzeit']), type="positive")
                invite_dialog.close()
                _refresh_now()
            ui.button(_('Einladen'), on_click=do_invite).props("color=primary")

    def _open_invite(app_id: int, name: str, titel: str) -> None:
        _invite_ctx["app_id"] = app_id
        invite_name_label.set_text(_('Moechtest du {0} zur Stelle \u201e{1}\u201c einladen?').format(name, titel))
        invite_datum.set_value(str((_dt.now() + _timedelta(days=1)).date()))
        invite_zeit.set_value("10:00")
        invite_error.set_visibility(False)
        invite_dialog.open()

    # ─── Modal: Bewerbung ablehnen ─────────────────────────────────────
    # P0-3: wirkt nur auf die gewaehlte Bewerbung (application_id); der Grund ist eine
    # INTERNE Notiz (application_status_history.notizen), NICHT Teil der Ablehnungs-Mail
    # (Runner send_rejection: neutral/AGG-sicher, ohne Begruendung).
    _reject_ctx = {"app_id": 0}
    with ui.dialog() as reject_dialog, ui.card().classes("w-96"):
        ui.label(_('Kandidat ablehnen')).classes("text-lg font-bold mb-4")
        reject_name_label = ui.label('').classes("mb-2")
        reject_reason = ui.input(label=_('Interne Notiz (optional, nicht sichtbar fuer den Kandidaten)')).props("maxlength=500").classes("w-full")
        with ui.row().classes("justify-end gap-2 mt-4"):
            ui.button(_('Abbrechen'), on_click=reject_dialog.close).props("flat")
            def do_reject():
                app_id = _reject_ctx["app_id"]
                info = _app_info(app_id) if app_id else None
                if not info:
                    ui.notify(_('Bewerbung nicht gefunden.'), type="negative")
                    reject_dialog.close()
                    _refresh_now()
                    return
                cid, job_id = info[0], info[1]
                if not _legal("abgelehnt", app_id):
                    ui.notify(_('Unzulaessiger Statusuebergang (Bewerbung ist nicht mehr aktiv).'), type="negative")
                    reject_dialog.close()
                    _refresh_now()
                    return
                _notiz = (reject_reason.value or "").strip()[:500] or None
                conn = db.get_conn()
                conn.execute("UPDATE applications SET status='abgelehnt', aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?", (app_id,))
                conn.execute("INSERT INTO application_status_history (application_id, status, changed_by, notizen) VALUES (?, 'abgelehnt', 'arbeitgeber', ?)", (app_id, _notiz))
                conn.commit()
                _notify_statuswechsel(conn, app_id, "abgelehnt")  # R3-5 nach commit
                conn.close()
                _tid = db.queue_agent_task("send_rejection", {"application_id": app_id, "candidate_id": cid, "job_id": job_id, "trigger": "hr_klick_portal"})
                if _tid is None:
                    ui.notify(_('Bewerbung abgelehnt - Ablehnungs-Mail wurde NICHT eingereiht (heute bereits ein Task fuer diese Bewerbung oder Queue-Fehler).'), type="warning")
                else:
                    ui.notify(_('Bewerbung abgelehnt.'), type="warning")
                reject_dialog.close()
                _refresh_now()
            ui.button(_('Ablehnen'), on_click=do_reject).props("color=negative")

    def _open_reject(app_id: int, name: str, titel: str) -> None:
        _reject_ctx["app_id"] = app_id
        reject_name_label.set_text(_('{0} fuer die Stelle \u201e{1}\u201c ablehnen? (Andere Bewerbungen dieses Kandidaten bleiben unveraendert.)').format(name, titel))
        reject_reason.set_value("")
        reject_dialog.open()

    # ─── Modal: Bewerber einstellen ────────────────────────────────────
    _hire_ctx = {"app_id": 0}
    with ui.dialog() as hire_dialog, ui.card().classes("w-96"):
        ui.label(_('Kandidat einstellen')).classes("text-lg font-bold mb-4")
        hire_name_label = ui.label('').classes("mb-2")
        with ui.row().classes("justify-end gap-2 mt-4"):
            ui.button(_('Abbrechen'), on_click=hire_dialog.close).props("flat")
            def do_hire():
                app_id = _hire_ctx["app_id"]
                info = _app_info(app_id) if app_id else None
                if not info:
                    ui.notify(_('Bewerbung nicht gefunden.'), type="negative")
                    hire_dialog.close()
                    _refresh_now()
                    return
                cid, job_id = info[0], info[1]
                if not _legal("eingestellt", app_id):
                    ui.notify(_("Ungueltiger Statusuebergang: 'Einstellen' erfordert den Status 'eingeladen' (Whitelist)."), type="negative")
                    hire_dialog.close()
                    _refresh_now()
                    return
                conn = db.get_conn()
                conn.execute("UPDATE applications SET status='eingestellt', aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?", (app_id,))
                conn.execute("INSERT INTO application_status_history (application_id, status, changed_by) VALUES (?, 'eingestellt', 'arbeitgeber')", (app_id,))
                conn.commit()
                _notify_statuswechsel(conn, app_id, "eingestellt")  # R3-5 nach commit
                conn.close()
                db.queue_agent_task("onboarding_release", {"application_id": app_id, "candidate_id": cid,
                                                           "job_id": job_id, "trigger": "hr_klick_portal"})
                ui.notify(_("Bewerber eingestellt. Bitte Stellen-Status auf 'besetzt' setzen (Tab Portal)."), type="positive")
                hire_dialog.close()
                _refresh_now()
            ui.button(_('Einstellen'), on_click=do_hire).props("color=positive")

    def _open_hire(app_id: int, name: str, titel: str) -> None:
        _hire_ctx["app_id"] = app_id
        hire_name_label.set_text(_('{0} fuer die Stelle \u201e{1}\u201c einstellen?').format(name, titel))
        hire_dialog.open()

    def do_seen(app_id: int) -> None:
        # "Als angesehen markieren" (eingegangen -> angesehen): direkt, ohne Dialog, ohne
        # Agent-Task (Design-Entscheidung P0-3; Parität _page_stellen: _hook_task hat keinen
        # Eintrag fuer 'angesehen'). History changed_by 'arbeitgeber'.
        if not _app_info(app_id):
            ui.notify(_('Bewerbung nicht gefunden.'), type="negative")
            _refresh_now()
            return
        if not _legal("angesehen", app_id):
            ui.notify(_('Ungueltiger Statusuebergang (Bewerbung hat sich zwischenzeitlich geaendert).'), type="negative")
            _refresh_now()
            return
        conn = db.get_conn()
        conn.execute("UPDATE applications SET status='angesehen', aktualisiert_am=CURRENT_TIMESTAMP WHERE id=?", (app_id,))
        conn.execute("INSERT INTO application_status_history (application_id, status, changed_by) VALUES (?, 'angesehen', 'arbeitgeber')", (app_id,))
        conn.commit()
        conn.close()
        ui.notify(_('Bewerbung als angesehen markiert.'), type="positive")
        _refresh_now()

    @ui.refreshable
    def match_content():
        conn = db.get_conn()

        # Kandidaten mit Bewerbungen fuer diesen Employer
        candidates = conn.execute("""
            SELECT DISTINCT c.id, c.name, c.hard_skills, c.soft_skills,
                   c.berufserfahrung_jahre, c.abschluss, c.deutsch, c.englisch,
                   c.standort, c.gehaltsvorstellung, c.lebenslauf_text
            FROM candidates c
            JOIN applications a ON a.candidate_id = c.id
            JOIN jobs j ON a.job_id = j.id
            WHERE j.employer_id = ? AND a.status != 'zurückgezogen'
            ORDER BY c.id DESC
        """, (employer_id,)).fetchall()

        if _focus["cid"]:
            # Fokus-Filter (?kandidat=<id>): nur dieser Kandidat; Hinweis-Zeile wird unten
            # gefuellt, sobald feststeht ob er Bewerber oder passiver Match ist.
            candidates = [c for c in candidates if c[0] == _focus["cid"]]
            _hint_row = ui.row().classes("w-full items-center gap-2")
        else:
            _hint_row = None

        if not candidates and not _focus["cid"]:
            # P3 (§H-16): kein Return mehr — der Passiv-Block unten muss auch ohne Bewerber
            # rendern; conn.close() läuft am Ende von match_content (Zeile ~916).
            empty_state(icon="compare_arrows", title=_('Keine Kandidaten mit Bewerbungen'), description=_('Kandidaten erscheinen hier, sobald sie sich beworben haben. Passive Matches stehen darunter.'))

        _treffer = 0

        with ui.column().classes("w-full gap-4"):
            for cand in candidates:
                c_id, name, h_skills, s_skills, exp, abschluss, de, en, standort, gevh, cv_text = cand

                # Jobs dieses Kandidaten bei diesem Employer
                jobs = conn.execute("""
                    SELECT a.id, a.status, j.id, j.titel, j.hard_skills, j.soft_skills,
                           j.berufserfahrung_jahre, j.deutsch_level, j.englisch_level,
                           j.standort, j.stellentyp, e.branche, j.gehaltsrahmen_min, j.gehaltsrahmen_max
                    FROM applications a
                    JOIN jobs j ON a.job_id = j.id
                    JOIN employers e ON j.employer_id = e.id
                    WHERE a.candidate_id = ? AND j.employer_id = ? AND a.status != 'zurückgezogen'
                    ORDER BY CASE WHEN a.status IN ('eingegangen', 'angesehen', 'eingeladen') THEN 0 ELSE 1 END,
                             a.erstellungsdatum DESC, a.id DESC
                """, (c_id, employer_id)).fetchall()

                if not jobs:
                    continue

                # Bewerber werden IMMER gezeigt (Parität app.py:3635-3640 „Abschnitt 1:
                # Aktive Bewerber“ — kein Must-Have-Gate; app.py:3831: „Bewerber werden im
                # Abschnitt 1 angezeigt – hier nicht doppelt“). Der Must-Have/50%-Filter
                # (app.py:3844-3848) gilt NUR für passive Matches — B2-2 (c)1 hatte ihn
                # fälschlich auf Bewerber-Karten angewandt (Korrektur 25.09.2026,
                # Phase-E Runde 6; aufgedeckt durch e2e_housing: Kandidat ohne Must-Have
                # verschwand samt Einladen/Einstellen-Buttons). _matched = Ergebnis-Cache
                # für alle Jobs[:3] des Bewerbers (ungefiltert).
                _matched = []
                for _job in jobs[:3]:
                    (_a_id, _a_status, _j_id, _titel, _j_hard, _j_soft, _j_exp,
                     _j_de, _j_en, _j_stand, _j_typ, _branche, _min_g, _max_g) = _job
                    _k_data = {"hard_skills": h_skills, "soft_skills": s_skills,
                               "berufserfahrung_jahre": exp, "abschluss": abschluss,
                               "deutsch": de, "englisch": en,
                               "standort": standort, "lebenslauf_text": cv_text or ""}
                    _j_data = {"hard_skills": _j_hard, "soft_skills": _j_soft,
                               "berufserfahrung_jahre": _j_exp, "deutsch_level": _j_de,
                               "englisch_level": _j_en, "standort": _j_stand,
                               "stellentyp": _j_typ, "branche": _branche}
                    try:
                        _res = logic.berechne_match_score(_k_data, _j_data)
                    except Exception:
                        continue
                    _matched.append((_job, _res))
                if not _matched:
                    continue
                _treffer += 1

                with ui.card().classes("w-full mb-4"):
                    with ui.row().classes("items-center justify-between w-full"):
                        with ui.row().classes("items-center gap-3"):
                            candidate_avatar(name)
                        with ui.column().classes("flex-1"):
                            ui.label(name or _("Unbekannt")).classes("font-medium")
                            if h_skills:
                                # M-18 (01.10.2026): NICHT mehr still bei 4 abschneiden.
                                # Erste 4 Chips + "+N weitere" (Tooltip listet die uebrigen) —
                                # Layout bleibt erhalten (Datenprobe: bis zu 21 Skills/Kandidat),
                                # Kuerzung ist aber sichtbar. Design-Entscheidung (keine Quelle).
                                _skills = [s.strip() for s in str(h_skills).split(",") if s.strip()]
                                with ui.row().classes("gap-2 mt-1"):
                                    for skill in _skills[:4]:
                                        skill_chip(skill)
                                    if len(_skills) > 4:
                                        ui.chip(_('+{0} weitere').format(len(_skills) - 4),
                                                color="grey").props("dense").tooltip(
                                            ", ".join(_skills[4:]))
                    # P0-3 (29.09.2026, Design-Entscheidung): KEINE globalen Karten-Buttons mehr.
                    # Die Aktionen haengen an der einzelnen Bewerbung (Aktionszeile je Stelle
                    # unten) und zeigen nur die laut ALLOWED_TRANSITIONS legalen Uebergaenge.
                    # Auch bei genau einer aktiven Bewerbung keine zweite Platzierung: ein
                    # einheitlicher Ort, keine doppelten Buttons/Labels.
                    cand_name = name or _('Unbekannt')
                    if len(jobs) > 3:
                        ui.label(_('+ {0} weitere Bewerbung(en) nicht angezeigt (aktive zuerst) - vollstaendig unter Stellenangebote.').format(len(jobs) - 3)).classes("text-xs text-gray-500")

                    # Pro Job: Live-Score + Visa-Confirmation
                    # (Vorpräfung-Cache: _matched enthaelt alle Jobs[:3] des Bewerbers,
                    #  ungefiltert — Parität app.py:3640 Abschnitt 1)
                    for job, result in _matched:
                        app_id, app_status, j_id, titel, j_hard, j_soft, j_exp, j_de, j_en, j_stand, j_typ, branche, min_g, max_g = job

                        total = result["total"]
                        kategorie = result["kategorie"]
                        erklaerung = result.get("erklaerung", {})

                        # P0-3: Aktionszeile je Bewerbung = Stellentitel + Statusbadge + NUR die
                        # legalen Aktionen dieser Bewerbung (finale Status: nur Badge).
                        # Alle Loop-Variablen als Default-Argumente gebunden (Late-Binding-Falle).
                        with ui.row().classes("items-center justify-between w-full mt-2"):
                            with ui.row().classes("items-center gap-2"):
                                ui.label(titel).classes("font-medium text-sm")
                                status_badge(app_status)
                            with ui.row().classes("gap-2"):
                                # Button-Hierarchie (UI-Regel 28.09.2026): primaer (EINLADEN,
                                # gefuellt), destruktiv (ABLEHNEN, negativ flat), tertiaer
                                # (EINSTELLEN, flat); "Als angesehen markieren" outline.
                                for _ns in _legal_actions(app_status):
                                    if _ns == "angesehen":
                                        ui.button(
                                            _(_MATCH_ACTION_LABEL[_ns]), icon="visibility",
                                            on_click=lambda _a=app_id: do_seen(_a),
                                        ).props("color=primary outline no-caps")
                                    elif _ns == "eingeladen":
                                        ui.button(
                                            _(_MATCH_ACTION_LABEL[_ns]), icon="person_add",
                                            on_click=lambda _a=app_id, _n=cand_name, _t=titel: _open_invite(_a, _n, _t),
                                        ).props("color=primary")
                                    elif _ns == "eingestellt":
                                        ui.button(
                                            _(_MATCH_ACTION_LABEL[_ns]), icon="how_to_reg",
                                            on_click=lambda _a=app_id, _n=cand_name, _t=titel: _open_hire(_a, _n, _t),
                                        ).props("color=positive flat no-caps")
                                    elif _ns == "abgelehnt":
                                        ui.button(
                                            _(_MATCH_ACTION_LABEL[_ns]), icon="person_remove",
                                            on_click=lambda _a=app_id, _n=cand_name, _t=titel: _open_reject(_a, _n, _t),
                                        ).props("color=negative flat no-caps")

                        # Fix 1 (23.09.2026): pro Kandidat×Job eine Klappe (default zu),
                        # Parität app.py:3857 st.expander(f"{rank}. Kandidat … – {total}/100 …").
                        # Score-Zeile = Header (immer sichtbar), Details klappt auf.
                        # Doku: nicegui.io/documentation/expansion (add_slot("header")).
                        # ACHTUNG: ui.timer(15s) match_content.refresh setzt Klappen auf zu (wie Streamlit-Rerun).
                        _job_exp = ui.expansion(icon="query_stats").classes("w-full mt-1")
                        with _job_exp:
                            with _job_exp.add_slot("header"):
                                with ui.row().classes("items-center justify-between w-full pr-2"):
                                    ui.label(_('Match-Score')).classes("font-medium text-sm")
                                    with ui.row().classes("items-center gap-2"):
                                        score_bar(total, show_label=False)
                                        ui.label(_('{0}/100 ({1})').format(total, _(kategorie))).classes("font-bold text-sm")

                            # C3 (22.09.2026): Gehalts-Kompatibilität — bisher dead code
                            # (logic.py:248 ohne Aufruf). Quelle: app.py:3848/3867
                            # (st.metric "Gehalt"), Spec: skills/employer-portal/SKILL.md:91
                            ui.label(_('Gehalt: {0}').format(logic.gehalt_check(gevh, min_g, max_g))).classes(
                                "text-sm text-gray-500")

                            # Explainability: 7 Kategorien
                            with ui.column().classes("mt-2"):
                                kategorien = [
                                    ("Kern", result.get("kern", 0), "kern"),
                                    ("Erfahrung", result.get("erfahrung", 0), "erfahrung"),
                                    ("Bildung", result.get("bildung", 0), "bildung"),
                                    ("Standort", result.get("standort", 0), "standort"),
                                    ("Branche", result.get("branche", 0), "branche"),
                                    ("Soft", result.get("soft", 0), "soft"),
                                    ("Sprache", result.get("sprache", 0), "sprache"),
                                ]
                                with ui.column().classes("w-full"):
                                    for kat_name, kat_score, kat_key in kategorien:
                                        with ui.row().classes("items-center gap-2 w-full"):
                                            ui.label(_(kat_name)).classes("w-20 text-xs text-gray-500")
                                            # P0-3 (e): Prozent = Punkte / KATEGORIE_MAX[key] (logic.py), Beschriftung x/max
                                            pct = _bar_pct(kat_key, kat_score)
                                            with ui.element("div").classes("flex-1 bg-gray-100 rounded-full h-2"):
                                                ui.element("div").classes(f"h-2 rounded-full {'bg-green-500' if pct >= 70 else 'bg-yellow-500' if pct >= 40 else 'bg-red-500'}").style(f"width:{pct}%")
                                            ui.label(_('{0}/{1}').format(kat_score, logic.KATEGORIE_MAX.get(kat_key, '?'))).classes("text-xs w-12 text-right")

                            # Erklaerung
                            if erklaerung:
                                with ui.expansion(_('Erklaerung'), icon="info").classes("w-full mt-1"):
                                    for key, text in erklaerung.items():
                                        ui.label(_('- {0}: {1}').format(key, text)).classes("text-xs text-gray-600")

                            # Visum-Antrag-Bestaetigung (Spec v6, Quelle: app.py:3740-3757)
                            if app_status == "eingeladen":
                                # Guard: exakter application_id-Vergleich via json_extract
                                # (agent_tasks hat keine application_id-Spalte; P1-7 30.09.2026)
                                # Quelle: app.py:3177-3179 + db.py:64
                                _visa_rows = conn.execute(
                                    "SELECT COUNT(*) FROM agent_tasks WHERE task_type='visa_confirmation' "
                                    "AND status IN ('pending','running','done') "
                                    "AND json_extract(payload, '$.application_id') = ?",
                                    (app_id,),
                                ).fetchone()
                                _visa_done = _visa_rows[0] > 0 if _visa_rows else False
                                if not _visa_done:
                                    def send_visa(_a_id=app_id, _c_id=c_id, _j_id=j_id):
                                        db.queue_agent_task("visa_confirmation", {
                                            "application_id": _a_id,
                                            "candidate_id": _c_id,
                                            "job_id": _j_id,
                                            "trigger": "hr_klick_portal",
                                        })
                                        ui.notify(_('Visum-Schritte-Mail an Kandidaten ausgeloest.'), type="positive")
                                        _refresh_now()
                                    ui.button(_('Visum-Antrag bestaetigen'), icon="mail",
                                              on_click=send_visa).classes("mt-2").props("color=warning")

                                # HR-Sicht der Einladung: Meeting-Link + Termin + ICS-Download
                                # (N1-Port: app.py:502-520 render_hr_ics_download)
                                # `jitsi_url` = Legacy-Schluessel fuer Alt-Einladungen (vor 27.09.2026).
                                _art = db.get_invitation_artifacts(app_id)
                                if _art:
                                    _jitsi = (_art.get("vdo_ninja_url") or _art.get("jitsi_url")
                                              or _art.get("meet_url"))
                                    _ics = _art.get("ics_path_hr") or _art.get("ics_path")  # HR-ICS = Director-Link (seit 28.09.2026)
                                    _termin = _art.get("termin", "")
                                    with ui.card().classes("bg-blue-50 border border-blue-200 p-3 mt-2 w-full"):
                                        ui.label(_('📹 Einladung (Kandidat wurde benachrichtigt){0}').format(f" – {_termin}" if _termin else "")).classes("text-sm font-medium text-blue-800")
                                        if _jitsi:
                                            ui.link(_('🔗 {0}').format(_jitsi), _jitsi, new_tab=True).classes("text-xs text-blue-700 underline hover:text-blue-900")
                                            ui.label(_('⚠️ Aufnahme nur nach ausdrücklicher Einwilligung – HR-Prozessregel (Gate 9, knowledge/legal/recording-consent.md)')).classes("text-xs text-amber-700")
                                        if _ics and logic.Path(str(_ics)).exists():
                                            def _dl_ics(_p=str(_ics), _n=logic.Path(str(_ics)).name):
                                                ui.download(_p, _n, "text/calendar")
                                            ui.button(_('📅 Termin in Kalender speichern (.ics) – HR'),
                                                      icon="event", on_click=_dl_ics).classes("mt-1").props("color=primary flat")
                                        else:
                                            ui.label(_('ℹ️ ICS-Datei noch nicht vorhanden.')).classes("text-xs text-gray-500")

            # ── Sprachtests (S3d) ──────────────────────────────────────────────
            _lang_tests = db.get_language_tests(c_id)
            if _lang_tests:
                with ui.expansion(_('Sprachtests'), icon="translate").classes("w-full mt-1"):
                    for _lt_id, _sprache, _niveau, _punkte, _cefr, _datum in _lang_tests:
                        ui.label(
                            _('{0} {1} {2} — {3:.0f}% ({4}){5}').format('•' if _lt_id or _sprache else '', _(_sprache), _niveau, _punkte * 100, _cefr, f' · {_datum}' if _datum else '')
                        ).classes("text-sm")

            # ── P3 ((c)3 option (i), GO §H-16, 26.09.2026): Passiv-Block NACH den Bewerbern ──
            # Spec: knowledge/portal/matching-filter.md Abschnitt (g). Gate-Parität
            # app.py:3844-3848 (≥1 Must-Have + ≥50 % der geforderten Erfahrung) — NUR für Passive
            # (Bewerber bleiben ungefiltert, Korrektur (c)1 25.09.2026). Pool-Status identisch
            # app.py:3898 (Feedback-Picker). LIMIT 10 + Label = Design-Entscheidung (Abschnitt (g)).
            # DSGVO: Passiv-Karten ohne Aktionen/Kontaktdaten (dsgvo-gate.md, Freigabe erst `eingeladen`).
            _app_ids = {r[0] for r in conn.execute(
                "SELECT DISTINCT a.candidate_id FROM applications a "
                "JOIN jobs j ON a.job_id = j.id "
                "WHERE j.employer_id = ? AND a.status != 'zurückgezogen'",
                (employer_id,)).fetchall()}
            _passive_best = {}
            for _pj in conn.execute(
                "SELECT j.id, j.titel, j.hard_skills, j.soft_skills, j.berufserfahrung_jahre, "
                "j.deutsch_level, j.englisch_level, j.standort, j.stellentyp, e.branche "
                "FROM jobs j JOIN employers e ON e.id = j.employer_id "
                "WHERE j.employer_id = ? AND j.status = 'aktiv'",
                (employer_id,)).fetchall():
                (_pj_id, _pj_titel, _pj_hard, _pj_soft, _pj_exp, _pj_de, _pj_en,
                 _pj_ort, _pj_typ, _pj_br) = _pj
                # N-K2 (01.10.2026): EINE CV-Pool-Quelle — CAND_CV_STATUS
                # (Modulkonstante), keine zweite hartkodierte Status-Liste.
                for _pk in conn.execute(
                    "SELECT id, name, hard_skills, soft_skills, berufserfahrung_jahre, "
                    "abschluss, deutsch, englisch, standort, lebenslauf_text FROM candidates "
                    f"WHERE status IN ({','.join('?' * len(CAND_CV_STATUS))})",
                    list(CAND_CV_STATUS),
                ).fetchall():
                    if _pk[0] in _app_ids:
                        continue
                    try:
                        _r = logic.berechne_match_score(
                            {"hard_skills": _pk[2], "soft_skills": _pk[3],
                             "berufserfahrung_jahre": _pk[4], "abschluss": _pk[5],
                             "deutsch": _pk[6], "englisch": _pk[7], "standort": _pk[8],
                             "lebenslauf_text": _pk[9] or ""},
                            {"hard_skills": _pj_hard, "soft_skills": _pj_soft,
                             "berufserfahrung_jahre": _pj_exp, "deutsch_level": _pj_de,
                             "englisch_level": _pj_en, "standort": _pj_ort,
                             "stellentyp": _pj_typ, "branche": _pj_br})
                    except Exception:
                        continue
                    if not _r["matches"]:
                        continue
                    if _pj_exp and (_pk[4] or 0) < _pj_exp * 0.5:
                        continue
                    _alt = _passive_best.get(_pk[0])
                    if _alt is None or _r["total"] > _alt[0]:
                        _passive_best[_pk[0]] = (_r["total"], _pk[1], _pj_titel,
                                                 _r["kategorie"], _r["matches"], _pk[0])
            _passive = sorted(_passive_best.values(), key=lambda _t: _t[0],
                              reverse=True)
            if _focus["cid"]:
                # Fokus (?kandidat=<id>): nur der gewaehlte Kandidat, ohne LIMIT 10
                _passive = [_t for _t in _passive if _t[5] == _focus["cid"]]
            else:
                _passive = _passive[:10]
            if _passive:
                ui.label(_('👥 {0} passiver Match (keine aktive Bewerbung; Score absteigend)').format(len(_passive))).classes(
                    C.BODY + " font-medium mt-4")
                for _total, _pname, _ptitel, _pkat, _pmatches, _pid in _passive:
                    with ui.card().classes("w-full mb-3 border-dashed"):
                        with ui.row().classes("items-center justify-between w-full"):
                            ui.label(_('{0} → {1}').format(_pname or _('Unbekannt'), _ptitel)).classes("text-sm font-medium")
                            ui.label(_('{0}/100 ({1})').format(_total, _(_pkat))).classes("text-sm font-bold")
                        ui.label(_('Must-Have-Treffer: {0}').format(', '.join(_pmatches) if _pmatches else '–')).classes(
                            "text-xs text-gray-600")

            if _focus["cid"]:
                # Hinweiszeile "Gefiltert auf <Name> – Alle anzeigen" (P0-3 Query-Parameter kandidat)
                _fname = next((c[1] for c in candidates if c[0] == _focus["cid"]), None) \
                    or next((_t[1] for _t in _passive), None)
                with _hint_row:
                    ui.label(_('🔎 Gefiltert auf {0}').format(_fname or _('Kandidat #{0}').format(_focus['cid']))).classes(
                        C.BODY + " font-medium")
                    ui.button(_('Alle anzeigen'), icon="filter_alt_off", on_click=_clear_focus).props(
                        "flat no-caps color=primary")
                if _treffer == 0 and not _passive:
                    ui.label(_('Kandidat #{0} ist kein Bewerber dieses Arbeitgebers und erreicht kein passives Match (mind. 1 Must-Have-Skill und >= 50 Prozent der geforderten Erfahrung bei einer aktiven Stelle).').format(_focus['cid'])).classes(C.BODY + " text-amber-600")
            elif _treffer == 0 and not _passive:
                ui.label(_('⚠️ Keine passenden Kandidaten (mindestens 1 Must-Have-Skill nötig).')).classes(
                    C.BODY + " text-amber-600")

        conn.close()

    _sig["v"] = _data_signature()
    match_content()
    # P0-3 (f): Timer rechnet nur neu, wenn sich die Daten-Signatur geaendert hat
    # (vorher: bedingungslos alle 15 s -> offene Details klappten zu, Passiv-Matches
    # aller aktiven Jobs x aller Kandidaten wurden ohne Aenderung neu berechnet).
    ui.timer(interval=15.0, callback=_tick)


# ─── 4. Compliance-Ergebnis ─────────────────────────────────────────

_COMPLIANCE_MID = _re.compile(r"^employer-job-(\d+)-cand-(\d+)-(\d{4}-\d{2}-\d{2})$")

# R3-3 (30.09.2026, Nutzer-GO „A"): check_compliance-Berichts-Schema
# (verifiziert an 17 Dateien ergebnisse/check_compliance-kandidat-*.md):
#   Dateiname : check_compliance-kandidat-<kandidat_id>-<YYYY-MM-DD>.md
#   Titelzeile: "# Check Compliance – Kandidat #<id> / Stelle #<job_id>"
#   Body      : "Compliance-Status: COMPLIANT|NICHT_COMPLIANT …" + Begruendung
_BERICHT_DATEI = _re.compile(r"^check_compliance-kandidat-(\d+)-(\d{4}-\d{2}-\d{2})\.md$")
_BERICHT_STELLE = _re.compile(r"Stelle #(\d+)")
_BERICHT_STATUS = _re.compile(r"^Compliance-Status:\s*(.*)$")
# Labels, unter denen die Begruendung in den 17 Dateien wirklich steht
# (Fund: "Begründung", "Justification", "Grund", "Justierung" — teils ohne Label)
_BERICHT_LABEL = _re.compile(r"^(?:Begründung|Begruendung|Justification|Grund|Justierung)\s*:\s*",
                             _re.IGNORECASE)


def _compliance_status(text: str) -> tuple:
    """Status-Token + Begruendung aus dem Berichtstext.

    R3-3 Parser-Regeln (DESIGN-ENTSCHEIDUNG — kein externes Schema, das
    Verhalten der 17 existierenden Dateien ist die Quelle):
      * Werteverteilung der 17 Dateien (read-only gezaehlt): 15x COMPLIANT
        (davon 3 mit angehaengtem Text "COMPLIANT - Entscheidung …"),
        2x NICHT_COMPLIANT (davon 2 mit Nachzeilen).
      * NICHT_COMPLIANT wird ZUERST geprueft, sonst faellt "COMPLIANT" als
        Teilstring den Negativ-Status auf.
      * Begruendung = Text NACH dem Status-Token auf derselben Zeile
        (Fall "COMPLIANT - Entscheidung …") PLUS alle Folgezeilen bis zur
        naechsten Titelzeile; ein fuehrendes Label ("Begründung:" u.a.)
        wird entfernt, weil die Dateien dasselbe Feld uneinheitlich benennen.
    Rueckgabe: (status, begruendung); ohne "Compliance-Status:"-Zeile ("", "").
    """
    zeilen = text.splitlines()
    for i, zeile in enumerate(zeilen):
        m = _BERICHT_STATUS.match(zeile.strip())
        if not m:
            continue
        roh = m.group(1).strip()
        if roh.startswith("NICHT_COMPLIANT"):
            status, rest = "NICHT_COMPLIANT", roh[len("NICHT_COMPLIANT"):].strip(" -:")
        elif roh.startswith("COMPLIANT"):
            status, rest = "COMPLIANT", roh[len("COMPLIANT"):].strip(" -:")
        else:
            status, rest = roh, ""
        teile = [rest] if rest else []
        for folge in zeilen[i + 1:]:
            s = folge.strip()
            if s.startswith("# "):
                break
            if s:
                teile.append(s)
        begr = _BERICHT_LABEL.sub("", " ".join(teile), count=1).strip()
        return status, begr
    return "", ""


def _compliance_berichte(employer_id, ordner=None) -> list:
    """ALLE check_compliance-Berichte + Zurechnung auf den angemeldeten Arbeitgeber.

    R3-3 (30.09.2026, Nutzer-GO „A", Variante A): `compliance_protokoll` hat
    keinen Writer — die ECHTEN Ergebnisse liegen als MD-Dateien in
    `ergebnisse/`. Diese Funktion ist die neue Primarquelle; das Protokoll
    bleibt als Archiv-Teil erhalten.

    Zurechnung: Titelzeile -> job_id -> `jobs.employer_id`
    (`applications` hat KEINE employer_id, Schema-Fakt; unter pytest greift der
    Spiegel aus tests/conftest.py). Nicht existierende Jobs bzw. fremde
    Arbeitgeber werden NICHT verschwiegen: der Eintrag kommt mit
    `zugeordenbar=False` zurueck und wird in der UI als Hinweis gezaehlt.

    `ordner` (Design-Entscheidung, fuer Tests): Verzeichnis-Override,
    Default `logic.ERGEBNISSE`.
    """
    base = _Path(ordner) if ordner is not None else logic.ERGEBNISSE
    berichte = []
    conn = db.get_conn()
    try:
        for pfad in sorted(base.glob("check_compliance-kandidat-*.md")):
            m = _BERICHT_DATEI.match(pfad.name)
            if not m:
                continue
            cand_id, datum = int(m.group(1)), m.group(2)
            try:
                text = pfad.read_text(encoding="utf-8", errors="replace")
            except OSError as ex:
                print(f"[compliance_berichte] Lesefehler {pfad.name}: {ex}")
                continue
            titelzeile = next((z for z in text.splitlines() if z.startswith("# ")), "")
            ms = _BERICHT_STELLE.search(titelzeile)
            job_id = int(ms.group(1)) if ms else None
            status, begr = _compliance_status(text)
            job = (conn.execute("SELECT titel, employer_id FROM jobs WHERE id = ?",
                                (job_id,)).fetchone()
                   if job_id is not None else None)
            gehoert = bool(job) and job[1] is not None and job[1] == employer_id
            cand = conn.execute("SELECT name FROM candidates WHERE id = ?",
                                (cand_id,)).fetchone()
            berichte.append({
                "datei": pfad.name,
                "kandidat_id": cand_id,
                "kandidat_name": ((cand[0] if cand else None) or _('Kandidat #{0}').format(cand_id)),
                "job_id": job_id,
                "job_titel": ((job[0] if job else None)
                              or (_('Stelle #{0}').format(job_id) if job_id is not None
                                  else _("Stelle unbekannt"))),
                "datum": datum,
                "status": status,
                "begruendung": begr,
                "zugeordenbar": gehoert,
            })
    finally:
        conn.close()
    berichte.sort(key=lambda b: (b["datum"], b["datei"]), reverse=True)
    return berichte


def _compliance_rows(conn, employer_id) -> tuple:
    """Compliance-Protokolleintraege, die diesem Arbeitgeber zurechenbar sind.

    P1-9 (30.09.2026): `_page_compliance` zeigte global `ORDER BY id DESC LIMIT 1`
    — also den letzten Eintrag der GESAMTEN Datenbank, ohne Bezug zum angemeldeten
    Arbeitgeber. Ein fremder Eintrag konnte so als eigenes Compliance-Ergebnis
    erscheinen.

    `compliance_protokoll` hat keinen Fremdschlüssel und wird im aktuellen Code
    nirgends geschrieben (grep: 0 Writer). Zurechenbar ist deshalb nur das
    match_id-Schema `employer-job-<job_id>-cand-<cand_id>-<datum>`
    (employer.py::_page_feedback, Muster app.py:3952) — daraus wird die job_id
    gelesen und gegen die eigenen Stellen geprueft.

    Rueckgabe: (zugeordnet, nicht_zurechenbar). Legacy-Eintraege wie
    'anna-schuster-devops-2026' tragen keinen Arbeitgeber-Bezug und werden
    bewusst NICHT angezeigt (lieber ehrlich leer als fremde Daten).
    """
    zugeordnet, nicht_zurechenbar = [], 0
    # N-K (01.10.2026): application_id additiv — Altbestand/Tests ohne die Spalte
    # duerfen nicht crashen (schema-robust via PRAGMA statt festem SELECT).
    _spalten = {r[1] for r in conn.execute(
        "PRAGMA table_info(compliance_protokoll)").fetchall()}
    if not _spalten:
        return zugeordnet, nicht_zurechenbar
    _hat_appid = "application_id" in _spalten
    _sel = "id, match_id, land, pruefpunkt, status, details, datum" + (
        ", application_id" if _hat_appid else "")
    for r in conn.execute(
        f"SELECT {_sel} FROM compliance_protokoll ORDER BY id DESC"
    ).fetchall():
        m = _COMPLIANCE_MID.match(r[1] or "")
        if not m:
            nicht_zurechenbar += 1
            continue
        job_id = int(m.group(1))
        gehoert = conn.execute(
            "SELECT 1 FROM jobs WHERE id = ? AND employer_id = ?",
            (job_id, employer_id),
        ).fetchone()
        if gehoert:
            zugeordnet.append({
                "id": r[0], "match_id": r[1], "land": r[2], "pruefpunkt": r[3],
                "status": r[4], "details": r[5], "datum": r[6], "job_id": job_id,
                "cand_id": int(m.group(2)),
                "application_id": r[7] if _hat_appid and len(r) > 7 else None,
            })
    return zugeordnet, nicht_zurechenbar


def _page_compliance(s: dict) -> None:
    """Compliance-Seite mit ZWEI Bloecken (R3-3, 30.09.2026, Nutzer-GO „A").

    Block 1 (Primarquelle): MD-Berichte ergebnisse/check_compliance-*.md,
      gelesen via `_compliance_berichte` — jueste zuerst, Begrundung aufklappbar,
      NICHT zurechenbare Berichte werden als Hinweis gezaehlt (nicht verschwiegen).
    Block 2 (Archiv): `compliance_protokoll` via `_compliance_rows` (P1-9-Guard
      bleibt erhalten, Nutzer-GO: "Tabelle compliance_protokoll bleibt als
      Archiv-Teil").
    Layout = Kartenliste + ui.expansion (DESIGN-ENTSCHEIDUNG: alle eigenen
    Berichte sichtbar, Zurechnung pro Karte ausgewiesen).
    """
    section_header(title=_('Compliance-Ergebnis'), subtitle=_('Rechtliche Pruefung'), icon="verified")

    berichte = _compliance_berichte(s.get("employer_id"))
    eigene = [b for b in berichte if b["zugeordenbar"]]
    offene = len(berichte) - len(eigene)

    ui.label(_('📋 Aktuelle Berichte: check_compliance (Primärquelle)')).classes(
        "text-lg font-semibold mb-2")
    if offene:
        ui.label(
            _('ℹ️ {0} Berichte sind keiner eigenen Stelle zuzuordnen (Stelle nicht vorhanden oder anderer Arbeitgeber) und werden hier nicht angezeigt.').format(offene)
        ).classes(C.MUTED + " mb-2")

    if not eigene:
        empty_state(
            icon="verified", title=_('Noch keine Compliance-Pruefung'),
            description=_('Wird nach Agent-Ausfuehrung fuer Ihre Bewerbungen angezeigt.'),
        )
    for b in eigene:
        with ui.card().classes(C.CARD + " mb-2"):
            with ui.row().classes("items-center gap-3 mb-1"):
                ui.badge(b["status"], color=None).classes(
                    (C.BADGE_GREEN if b["status"] == "COMPLIANT" else C.BADGE_RED)
                    + " status-badge")
                ui.label(b["datum"]).classes(C.SMALL)
                ui.label(_('{0} · {1}').format(b['kandidat_name'], b['job_titel'])).classes(C.SMALL)
                ui.label(_('(Stelle #{0} · Kandidat #{1})').format(b['job_id'], b['kandidat_id'])).classes(
                    C.MUTED)
            with ui.expansion(_('Begründung'), value=False).classes("w-full"):
                ui.label(b["begruendung"] or _("(keine Begründung im Bericht)")).classes(C.BODY)

    conn = db.get_conn()
    try:
        rows, nicht_zurechenbar = _compliance_rows(conn, s.get("employer_id"))
    finally:
        conn.close()

    ui.label(_('🗄️ Archiv: compliance_protokoll (Legacy)')).classes(
        "text-lg font-semibold mt-4 mb-2")

    if nicht_zurechenbar:
        ui.label(
            _('ℹ️ {0} ältere Protokolleinträge ohne Arbeitgeber-Bezug werden nicht angezeigt (sie könnten zu fremden Bewerbungen gehören).').format(nicht_zurechenbar)
        ).classes(C.MUTED + " mb-2")

    if not rows:
        ui.label(_('Keine zurechenbaren Archiv-Einträge.')).classes(C.MUTED)
        return

    for r in rows:
        with ui.card().classes(C.CARD + " mb-2"):
            with ui.row().classes("items-center gap-3 mb-2"):
                status_badge(r["status"])
                if r["land"]:
                    ui.label(_('Land: {0}').format(r['land'])).classes(C.MUTED)
                if r["pruefpunkt"]:
                    ui.label(_('Prüfpunkt: {0}').format(r['pruefpunkt'])).classes(C.MUTED)
                if r["datum"]:
                    ui.label(r["datum"]).classes(C.MUTED)
            with ui.row().classes("items-center gap-2 mb-1"):
                ui.label(_('Stelle #{0} · Kandidat #{1}').format(r['job_id'], r['cand_id'])).classes(C.SMALL)
                if r.get("application_id"):
                    ui.label(_('· Bewerbung #{0}').format(r['application_id'])).classes(C.SMALL)
            if r["details"]:
                ui.label(r["details"]).classes(C.BODY)


# ─── 5. Agent-Details ───────────────────────────────────────────────

# P8.2 (08.10.2026): Label-/Task-Type-Quelle der 9 Agent-Ergebnis-Aufgaben.
# Vorher Glob-Muster `*-kandidat-*` (lokale `ergebnisse/*.md`); Badges/Berichte
# kommen jetzt aus der DB (`agent_tasks.result_json`).
# Spec: knowledge/system/p8-cloud-datenquellen.md.
_agent_tasks = [
    ("📋 Profil extrahieren",       "extract_profile"),
    ("🎯 Kandidat matchen",         "match_candidate"),
    ("⚖️ Compliance pruefen",       "check_compliance"),
    ("🏢 Culture Fit pruefen",      "assess_culture_fit"),
    ("📄 Dokumente verifizieren",   "verify_documents"),
    ("🛂 Visum pruefen",            "check_visa"),
    ("🔒 DSGVO pruefen",            "check_gdpr"),
    ("💡 Match erklaeren",          "explain_match"),
    ("📧 Kandidat benachrichtigen", "notify_user"),
]


def _badge_icon(content_upper: str) -> str:
    # C5 (22.09.2026): Keyword-Reihenfolge = Badge-Zeile app.py:1985-1989 +
    # Tabelle agent-details-doku.md — NICHT die Expander-Variante
    # app.py:2012-2019, wo "ERFORDERLICH" auch in "NICHT ERFORDERLICH"
    # matched (dort fälschlich 🔴 trotz MD-Spezifikation 🟢).
    if "AUFFAELLIG" in content_upper or "AUFFÄLLIG" in content_upper:
        return "🔴"
    if "NICHT ERFORDERLICH" in content_upper or "NICHT_ERFORDERLICH" in content_upper:
        return "🟢"
    if "ERFORDERLICH" in content_upper or "NICHT_COMPLIANT" in content_upper or "NICHT_KONFORM" in content_upper:
        return "🔴"
    if "PLAUSIBEL" in content_upper or "COMPLIANT" in content_upper or "KONFORM" in content_upper:
        return "🟢"
    return "🟡"


def _legacy_badge_icon(status: str) -> str:
    """P8.2 (08.10.2026): Badge für Legacy-Tasks OHNE gespeicherten Berichtstext,
    ehrlich aus dem DB-Status abgeleitet (Design-Entscheidung, keine externe
    Quelle): `done`→🟢, `failed`→🔴, sonst (pending/running/queued) 🟡."""
    s = (status or "").lower()
    if s == "done":
        return "🟢"
    if s == "failed":
        return "🔴"
    return "🟡"


def _agent_task_icon(row: dict) -> str:
    """P8.2: Icon aus dem gespeicherten Berichtstext (`result_json["text"]`),
    sonst Legacy-Status-Mapping. Gleiche Semantik wie vorher (Text-Inhalt)."""
    text = row.get("text")
    if text:
        return _badge_icon(str(text).upper())
    return _legacy_badge_icon(row.get("status"))


def _report_language(row) -> str | None:
    """S4b (12.10.2026): Sprache eines gespeicherten Agent-Berichts, defensiv.

    Liest das Row-Feld `language` oder — falls die Zeile das rohe `result_json`
    mitfuehrt — `result_json["language"]`. Rein optionaler Hinweis; es wird
    NICHTS rueckuebersetzt (kein Back-Translate des LLM-Texts)."""
    if not isinstance(row, dict):
        return None
    lang = row.get("language")
    if not lang:
        rj = row.get("result_json")
        if isinstance(rj, str):
            try:
                rj = json.loads(rj)
            except (ValueError, TypeError):
                rj = None
        if isinstance(rj, dict):
            lang = rj.get("language")
    if not lang:
        return None
    return str(lang).strip() or None


def _page_agent_details(s: dict) -> None:
    section_header(title=_('Agent-Details'), subtitle=_('Agent-Ergebnisse + Tasks'), icon="smart_toy")
    ui.label(
        _('🔒 Read-only: Alle Agent-generierten Ergebnisse für einen Kandidaten: Dokumenten-Verifizierung, Visum-Check, DSGVO, Match-Erklaerung.')
    ).classes(C.MUTED)

    # 9 Ergebnis-Tasks: Labels/Reihenfolge aus `_AGENT_RESULT_TASKS`
    # (Spec: ergebnisse/agent-details-doku.md; Muster: app.py:1976-1982).
    # i18n P9.4 (06.10.2026): Anzeige-Labels sind deutsche msgids, übersetzt erst
    # beim Konsum (Renderzeit); Erkennung läuft über `task_type` + `_agent_task_icon`.

    conn = db.get_conn()
    cands = conn.execute("SELECT id, name FROM candidates ORDER BY name").fetchall()
    conn.close()
    if not cands:
        empty_state(icon="person_off", title=_('Keine Kandidaten vorhanden'))
        return

    cand_select = ui.select(
        options={c[0]: (c[1] or _('Kandidat #{0}').format(c[0])) for c in cands},
        value=cands[0][0],
        label=_('Kandidat'),
    ).classes("w-64 mb-3")

    results_container = ui.column().classes("w-full")

    def render_results(cand_id) -> None:
        results_container.clear()
        with results_container:
            # P8.2 (08.10.2026): Datenquelle = DB statt lokaler `ergebnisse/*.md`
            # (gitignored, in CI/Cloud leer). `get_candidate_agent_tasks` liefert
            # je `task_type` die letzte Task + `result_json["text"]`.
            _rows = db.get_candidate_agent_tasks(int(cand_id))
            by_type = {r["task_type"]: r for r in _rows}
            badges = []
            for _label, _ttype in _agent_tasks:
                _row = by_type.get(_ttype)
                badges.append((_label, _agent_task_icon(_row) if _row else "⚪"))

            # Badge-Zeile (Spec: agent-details-doku.md — 6 + 3 wie Streamlit
            # st.metric-Grid, app.py:2000-2006; hier 6er-Grid, bricht um)
            ui.label(_('⚡ Status-Übersicht:')).classes(C.CARD_TITLE + " mb-2")
            with ui.grid(columns=6).classes("w-full gap-2 mb-4"):
                for _label, _icon in badges:
                    with ui.card().classes("py-2 text-center"):
                        ui.label(_icon).classes("text-2xl")
                        ui.label(_(_label.split(" ", 1)[1])).classes(C.SMALL)

            # Detaillierte Berichte (Expander, Muster: app.py:2010-2026).
            # Legacy-Tasks ohne `text` werden ehrlich als Altbestand markiert
            # (kein Fake-Inhalt); Badge dann aus dem Status.
            ui.label(_('Detaillierte Berichte')).classes(C.CARD_TITLE + " mb-2")
            for _label, _ttype in _agent_tasks:
                _row = by_type.get(_ttype)
                if not _row:
                    ui.label(_('⚪ {0}: Kein Bericht vorhanden').format(_(_label))).classes(C.MUTED)
                    continue
                _icon = _agent_task_icon(_row)
                _status = _row.get("status") or "–"
                with ui.expansion(text=_('{0} {1} ({2})').format(_icon, _(_label), _status)).classes("w-full mb-1"):
                    # S4b (12.10.2026): optionaler Sprach-Hinweis (msgid via _(),
                    # dynamischer Wert via .format — keine f-Strings, Ruff INT001).
                    _lang = _report_language(_row)
                    if _lang:
                        ui.label(_("Sprache: {0}").format(_lang.upper())).classes(C.SMALL)
                    _text = _row.get("text")
                    if _text:
                        ui.markdown(_text)
                    else:
                        ui.label(_('Kein Berichtstext gespeichert (Altbestand)')).classes(C.MUTED)

    cand_select.on_value_change(lambda e: render_results(e.value))
    render_results(cand_select.value)

    ui.separator().classes("my-4")

    TASK_LABELS = {
        "extract_profile": "Profil extrahieren",
        "match_candidate": "Kandidat matchen",
        "check_compliance": "Compliance pruefen",
        "assess_culture_fit": "Culture Fit pruefen",
        "check_gdpr": "DSGVO pruefen",
        "check_visa": "Visum pruefen",
        "verify_documents": "Dokumente verifizieren",
        "notify_user": "Kandidat benachrichtigen",
        "notify_hr": "HR benachrichtigen",
        "create_invitation": "Einladung erstellen",
        "export_report": "Report exportieren",
    }

    # Fix 3 (23.09.2026): Task-Queue einklappbar (Rollback: /tmp/opencode/rollback/employer.py.bak).
    # Quelle UI-Muster: app.py-Agent-Details ohne Queue (Queue = NiceGUI-Eigenbau C5),
    # Doku: nicegui.io/documentation/expansion (value=False = default zu).
    with ui.expansion(_('Task-Queue (Datenbank)'), icon="database", value=False).classes("w-full mt-2"):
        # N-A1 (01.10.2026): Klartext-Labels statt DB-Slugs — EINE Quelle
        # `components.status_label` (STATUS_LABELS fuehrt done/failed/running/
        # queued/pending bereits). {Wert: Label}; der Wert bleibt der Slug.
        status_filter = ui.select(
            options={"alle": _("Alle"),
                     "pending": status_label("pending"),
                     "running": status_label("running"),
                     "done": status_label("done"),
                     "failed": status_label("failed"),
                     "queued": status_label("queued")},
            value="alle",
            label=_('Task-Status'),
            on_change=lambda e: refresh_agent_tasks(e.value),
        ).classes("w-48")

        @ui.refreshable
        def refresh_agent_tasks(status_val: str = "alle"):
            try:
                conn = db.get_conn()
                if status_val == "alle":
                    tasks = conn.execute(
                        "SELECT task_type, status, payload, created_at FROM agent_tasks ORDER BY id DESC LIMIT 50"
                    ).fetchall()
                else:
                    tasks = conn.execute(
                        "SELECT task_type, status, payload, created_at FROM agent_tasks WHERE status = ? ORDER BY id DESC LIMIT 50",
                        (status_val,),
                    ).fetchall()
                conn.close()

                agent_container.clear()
                with agent_container:
                    if not tasks:
                        empty_state(icon="smart_toy", title=_('Noch keine Agent-Tasks'), description=_('Tasks werden bei Bewerbungsprozessen gestartet.'))
                        return

                    with ui.grid(columns=3).classes(C.GRID_3):
                        for task_type, status, payload, created_at in tasks:
                            with ui.card().classes(C.CARD + " py-3"):
                                with ui.row().classes("items-center gap-2 mb-2"):
                                    agent_badge(task_type, status)
                                ui.label(_(TASK_LABELS.get(task_type, task_type))).classes(C.SMALL)
                                if created_at:
                                    ui.label(created_at).classes(C.MUTED)
            except Exception as ex:
                # R6-3 (30.09.2026): vorher `pass` — die Task-Queue blieb leer
                # ohne Hinweis (Refresh-Timer wiederholte das still).
                _log.exception("refresh_agent_tasks fehlgeschlagen: %s", ex)
                agent_container.clear()
                with agent_container:
                    ui.label(_('⚠️ Agent-Tasks konnten nicht geladen werden: {0}').format(ex)) \
                        .classes("text-red-600")
                    ui.button(_('Neu laden'), on_click=refresh_agent_tasks.refresh)

        agent_container = ui.column().classes("w-full")
        refresh_agent_tasks()


# ─── 6. Dokumente ───────────────────────────────────────────────────

def _page_dokumente(s: dict) -> None:
    section_header(title=_('Dokumente'), subtitle=_('Hochgeladene Dateien'), icon="folder")

    with ui.column().classes("w-full gap-3"):
        typ_filter = ui.select(
            options={v: (_("Alle") if v == "alle" else _(v)) for v in DOC_TYP_OPTIONS},  # echte Upload-Typen (candidate.py _doc_typen); Wert bleibt deutsch
            value="alle",
            label=_('Dokumenttyp'),
            on_change=lambda e: refresh_docs(e.value),
        ).classes("w-64")

        @ui.refreshable
        def refresh_docs(typ_val: str = "alle"):
            conn = db.get_conn()
            employer_id = s.get("employer_id")
            # P0-2 (dsgvo-gate.md (c)): Gate + Sperrliste in Modul-Helfern (pytest-bar),
            # Arbeitgeber-Bezug ueber applications -> jobs.employer_id.
            docs = _visible_documents(conn, employer_id, typ_val)
            blocked = _blocked_candidates(conn, employer_id, typ_val)
            conn.close()
            docs_by_id = {d["id"]: d for d in docs}

            def open_doc(e, _docs=docs_by_id):
                """Download NUR ueber Dokument-ID aus der bereits gegateten Liste
                (der Client liefert keinen Pfad). Pfad-Pruefung: _resolve_doc_path.
                NB: `e` ohne Default, sonst ruft NiceGUI den Handler ohne Event auf."""
                _arg = e.args
                _id = _arg.get("id") if isinstance(_arg, dict) else _arg
                _d = _docs.get(_id)
                if not _d:
                    ui.notify(_('Dokument nicht (mehr) freigegeben.'), type="warning")
                    return
                _p, _grund = _resolve_doc_path(_d["datei_pfad"])
                if _p is None:
                    ui.notify(
                        _('Datei liegt nicht im freigegebenen Ordner.') if _grund == "ausserhalb"
                        else _('Datei nicht mehr auf dem Server vorhanden.'),
                        type="negative",
                    )
                    return
                ui.download.file(_p, _doc_basename(_d["datei_pfad"]))

            docs_container.clear()
            with docs_container:
                if blocked:
                    # 🔒-Hinweis nur fuer Kandidaten, die sich beim EIGENEN Arbeitgeber
                    # beworben haben; Status = Bewerbungsstatus (nicht candidates.status).
                    _st = ", ".join(
                        f"{b['kandidat']} ({status_label(b['app_status'])})" for b in blocked[:8]
                    )
                    ui.label(
                        _("🔒 DSGVO: Dokumente werden erst ab Bewerbungsstatus 'Eingeladen' sichtbar. Noch gesperrt: {0}").format(_st)
                    ).classes(C.BODY + " text-amber-600")
                if not docs:
                    if not blocked:
                        empty_state(icon="folder_off", title=_('Keine Dokumente vorhanden'))
                    return

                columns = [
                    {"name": "kandidat", "label": _("Kandidat"), "field": "kandidat", "sortable": True, "align": "left"},
                    {"name": "datei", "label": _("Datei"), "field": "datei", "sortable": True, "align": "left"},
                    {"name": "typ", "label": _("Typ"), "field": "typ", "sortable": True, "align": "left"},
                    {"name": "datum", "label": _("Hochgeladen"), "field": "datum", "sortable": True, "align": "left"},
                    {"name": "status", "label": _("Status Bewerbung"), "field": "status", "sortable": True, "align": "left"},
                    {"name": "aktion", "label": _("Aktion"), "field": "id", "align": "left"},
                ]
                rows = [{"id": d["id"], "kandidat": d["kandidat"],
                         "datei": _doc_basename(d["datei_pfad"]), "typ": _(d["typ"]) if d["typ"] else "--",
                         "datum": d["datum"] or "--", "status": status_label(d["app_status"])}
                        for d in docs]
                doc_search = ui.input(placeholder=_('Suchen...')).props('prepend_icon="search"').classes("w-full")
                table = ui.table(columns=columns, rows=rows, row_key="id", pagination=10).classes("w-full")
                doc_search.bind_value(table, "filter")
                table.add_slot("body-cell-aktion", r'''
                    <q-td :props="props">
                        <q-btn flat dense no-caps color="primary" icon="download" label="Öffnen"
                               @click="() => $parent.$emit('open_doc', {id: props.row.id})" />
                    </q-td>
                ''')
                table.on("open_doc", open_doc)

        docs_container = ui.column().classes("w-full")
        refresh_docs()


# ─── 7. Pre-Screen ──────────────────────────────────────────────────

def _page_prescreen(s: dict) -> None:
    section_header(title=_('Pre-Screen'), subtitle=_('Screening fuer Kandidaten'), icon="record_voice_over")
    # C7 (22.09.2026): Slot-Stub → Skill-6-Section (Einsicht + Generator, D28)
    prescreen_recruiting_section()


# ─── 8. Onboarding ──────────────────────────────────────────────────

def _page_onboarding(s: dict) -> None:
    section_header(title=_('Onboarding'), subtitle=_('Checkliste erstellen'), icon="assignment")

    employer_id = s.get("employer_id")

    conn = db.get_conn()
    _eingestellt = conn.execute("""
        SELECT j.titel FROM applications a
        JOIN jobs j ON a.job_id = j.id
        WHERE j.employer_id = ? AND a.status = 'eingestellt'
        ORDER BY a.aktualisiert_am DESC LIMIT 1
    """, (employer_id,)).fetchone()
    conn.close()
    _default_stelle = _eingestellt[0] if _eingestellt else ""

    # Generator ZUERST (Streamlit-Parität Skill 7),
    # danach Kandidaten-Status-Timeline.
    onboarding_generator_section(default_stelle=_default_stelle)

    ui.separator().classes("my-6")
    ui.label(_('Kandidaten-Status')).classes(C.CARD_TITLE + " mb-4")

    conn = db.get_conn()
    candidates = conn.execute("""
        SELECT DISTINCT c.id, c.name, a.status
        FROM candidates c
        JOIN applications a ON a.candidate_id = c.id
        JOIN jobs j ON a.job_id = j.id
        WHERE j.employer_id = ?
        ORDER BY c.id DESC
    """, (employer_id,)).fetchall()
    conn.close()

    if not candidates:
        empty_state(
            icon="assignment",
            title=_('Keine Kandidaten fuer Onboarding'),
            description=_('Kandidaten erscheinen hier, nachdem sie eingestellt wurden.'),
        )
        return

    for cand_id, name, status in candidates:
        with ui.card().classes(C.CARD_HOVER + " w-full mb-4"):
            with ui.row().classes("items-center gap-3 mb-4"):
                candidate_avatar(name)
                ui.label(name or _("Unbekannt")).classes("font-medium")
                status_badge(status or _("unbekannt"))

            timeline_items = []
            if status in ("eingegangen", "angesehen", "eingeladen", "eingestellt"):
                timeline_items.append({"title": _("Bewerbung eingegangen"), "status": "done", "date": ""})
            if status in ("angesehen", "eingeladen", "eingestellt"):
                timeline_items.append({"title": _("Pre-Screening abgeschlossen"), "status": "done", "date": ""})
            if status in ("eingeladen", "eingestellt"):
                timeline_items.append({"title": _("Interview geplant"), "status": "active", "date": ""})
            elif status in ("eingegangen", "angesehen"):
                timeline_items.append({"title": _("Interview"), "status": "pending"})
            if status == "eingestellt":
                timeline_items.append({"title": _("Einstellung"), "status": "done", "date": ""})
                timeline_items.append({"title": _("Onboarding"), "status": "active", "date": ""})
            else:
                timeline_items.append({"title": _("Einstellung"), "status": "pending"})
                timeline_items.append({"title": _("Onboarding"), "status": "pending"})

            timeline(timeline_items)

            # ── Mentoring / Patenschaft (Phase D P10, User-GO 24.09.2026) ──
            # §2 Option A: HR-Klick vergibt/beendet – Agent entscheidet nie selbst.
            if status == "eingestellt":
                _mentor_section(cand_id)

            # ── Contract Preflight (Phase D P8, User-GO 24.09.2026) ──
            # Skill 23: HR-Klick queued contract_preflight (kein Mailversand,
            # keine Signatur – Variante A, Spec contract-management.md §3/§4).
            # Nur bei eingestellt (Vertrag erst bei Einstellung relevant).
            if status == "eingestellt":
                _contract_preflight_section(cand_id)


def _contract_preflight_section(cand_id: int) -> None:
    # R5-1 (30.09.2026, pyflakes-Fund): der 'def'-Kopf war beim Einfuegen
    # verloren gegangen — der Koerper lief als toter Code in _page_onboarding
    # mit und der Call darueber crashte mit NameError, sobald ein Kandidat
    # 'eingestellt' war (exakt der Zweig, in dem die Sektion sichtbar sein soll).
    """HR-Button 'Vertrags-Check' → queue contract_preflight (Variante A).
    Guard/Quellen im Runner (agent-runner.py contract_preflight), Report in
    ergebnisse/contract-preflight-bewerbung-{id}.md, Sichtbar in Agent-Details."""
    ui.separator().classes("my-2")
    ui.label(_('📄 Vertragsmanagement (Contract Preflight)')).classes("font-medium")
    conn = db.get_conn()
    row = conn.execute(
        "SELECT a.id FROM applications a WHERE a.candidate_id = ? "
        "AND a.status != 'zurückgezogen' ORDER BY a.id DESC LIMIT 1",
        (cand_id,),
    ).fetchone()
    conn.close()
    if not row:
        ui.label(_('Keine Bewerbung für Preflight.')).classes(C.MUTED)
        return
    app_id = row[0]

    def _start():
        tid = db.queue_agent_task("contract_preflight", {
            "application_id": app_id, "candidate_id": cand_id,
            "trigger": "hr_onboarding_klick",
        })
        if tid:
            ui.notify(_('Vertrags-Check gequeued (Task #{0}) – Report in Agent-Details.').format(tid),
                      type="positive")
        else:
            ui.notify(_('Preflight heute bereits gequeued (idempotent).'), type="warning")
        ui.navigate.to("/employer/onboarding")

    ui.button(_('📄 Vertrags-Check starten'), icon="description", on_click=_start).props("color=primary")
    ui.label(_('Bewerbung #{0} · Gehalt/Mindestlohn + Formfall + NachwG-Checkliste (Quellen: knowledge/legal/contract-sources.md)').format(app_id)).classes(C.SMALL + " " + C.MUTED)


def _mentor_section(cand_id: int) -> None:
    """Mentor-Vergabe/-Beendigung per HR-Klick (Spec mentoring.md §2A/§4,
    User-GO 24.09.2026). Reine DB+UI, kein Agent-Task (Spec §6)."""
    ui.separator().classes("my-2")
    ui.label(_('🤝 Patenschaft (Mentoring)')).classes("font-medium")
    active = db.get_active_mentor(cand_id)
    if active:
        ui.label(_('Aktiver Mentor: {0}').format(active)).classes("text-sm text-emerald-700")

        def _end():
            if db.end_mentoring(cand_id, changed_by="arbeitgeber"):
                ui.notify(_('Patenschaft beendet.'), type="warning")
            else:
                ui.notify(_('Keine aktive Patenschaft gefunden.'), type="negative")
            ui.navigate.to("/employer/onboarding")

        ui.button(_('Patenschaft beenden'), icon="handshake", on_click=_end).props("color=negative flat")
    else:
        mentor_input = ui.input(label=_('Mentor (Name):')).classes("w-full mb-2")

        def _assign():
            val = (mentor_input.value or "").strip()
            if not val:
                ui.notify(_('Bitte Mentor-Namen eingeben.'), type="negative")
                return
            db.assign_mentor(cand_id, val, changed_by="arbeitgeber")
            ui.notify(_('Mentor {0} zugewiesen.').format(val), type="positive")
            ui.navigate.to("/employer/onboarding")

        ui.button(_('Mentor zuweisen'), icon="person_add", on_click=_assign).props("color=positive")


# ─── 9. Feedback ────────────────────────────────────────────────────

# ─── M-07 (01.10.2026): Klickziel je Feedback-Zeile ───────────────────────
_FEEDBACK_CAND_RE = _re.compile(r"-cand-(\d+)")


def _feedback_klarname(stored, name_by_id: dict) -> str:
    """Klartext-Name einer Feedback-Zeile (P1-Regel, 28.09.2026).

    '**Name:** Anna Schuster' → 'Anna Schuster'; 'Kandidat #2' → Klarname aus
    `candidates`; sonst getrimmter Text (leer → '--').
    """
    s = (stored or "").strip()
    if not s:
        return "--"
    if s.startswith("*"):  # '**Name:** Anna Schuster' (Altbestand)
        s = _re.sub(r"^[*_#\s]*[^:]*:\s*[*_#\s]*", "", s).strip()
    if s.startswith("Kandidat #"):
        cid = s.split("#", 1)[1].strip()
        if cid.isdigit():
            return name_by_id.get(int(cid), s)
    return s or "--"


def _feedback_row_cid(match_id, kandidat_name, name_by_id: dict,
                      name_to_id: dict, token_ids: dict):
    """Kandidaten-ID fuer das Klickziel einer Feedback-Zeile — 3 Stufen (M-07).

    1) Vorgangs-Nr. `employer-job-<job>-cand-<id>-<datum>` (heutige Schreibweise),
    2) exakter Klarname (case-insensitiv),
    3) Namens-Token-Menge (Reihenfolge egal: 'Abdelkader Batnini' ==
       'batnini abdelkader'; nur bei eindeutigem Treffer).
    None = kein Kandidat aufloesbar (Altbestand `profil-…`) -> die Zeile zeigt
    dann den Detail-Dialog statt einer falschen Match-Seite.
    """
    m = _FEEDBACK_CAND_RE.search(match_id or "")
    if m and int(m.group(1)) in name_by_id:
        return int(m.group(1))
    klarname = _feedback_klarname(kandidat_name, name_by_id)
    cid = name_to_id.get(klarname.strip().casefold())
    if cid:
        return cid
    toks = tuple(sorted(t for t in _re.split(r"\s+", klarname.casefold()) if t))
    ids = token_ids.get(toks) or []
    return ids[0] if len(ids) == 1 else None


def _page_feedback(s: dict) -> None:
    section_header(title=_('Feedback'), subtitle=_('Kandidaten-Feedback speichern'), icon="feedback")

    employer_id = s.get("employer_id")

    # ── Kandidaten-Picker: echtes Ranking (Bewerber zuerst, dann passive) ──
    conn = db.get_conn()

    # Stellen dieses Employers
    jobs = conn.execute(
        "SELECT id, titel FROM jobs WHERE employer_id = ?", (employer_id,)
    ).fetchall()

    if not jobs:
        conn.close()
        empty_state(icon="work_off", title=_('Keine Stellen vorhanden'), description=_('Erstelle zuerst eine Stelle.'))
        return

    with ui.card().classes(C.CARD + " w-full mb-4"):
        ui.label(_('Neues Feedback')).classes(C.CARD_TITLE + " mb-4")

        job_select = ui.select(
            options={j[0]: j[1] for j in jobs},
            label=_('Stelle'),
            value=jobs[0][0],
        ).classes("w-full")

        # Kandidaten-Picker: Bewerber + passive Matches (Muster: app.py:2503-2506)
        cand_container = ui.column().classes("w-full")

        def refresh_cands():
            cand_container.clear()
            with cand_container:
                sel_job = job_select.value
                if not sel_job:
                    return
                # Bewerber dieser Stelle
                applicants = conn.execute("""
                    SELECT c.id, c.name, a.id as app_id
                    FROM candidates c
                    JOIN applications a ON a.candidate_id = c.id
                    WHERE a.job_id = ? AND a.status IN ('eingegangen', 'angesehen', 'eingeladen')
                    ORDER BY a.erstellungsdatum ASC
                """, (sel_job,)).fetchall()
                # Passive Matches (B2-2 (c)2: Score-Filter, Paritaet app.py:3911-3914)
                _p_rows = conn.execute("""
                    SELECT c.id, c.name, c.hard_skills, c.soft_skills,
                           c.berufserfahrung_jahre, c.abschluss, c.deutsch, c.englisch,
                           c.standort, c.lebenslauf_text
                    FROM candidates c
                    WHERE c.status IN ('lebenslauf_hochgeladen', 'zugeordnet', 'aktiv')
                    AND c.id NOT IN (
                        SELECT candidate_id FROM applications
                        WHERE job_id = ? AND status IN ('eingegangen', 'angesehen', 'eingeladen')
                    )
                    ORDER BY c.id DESC LIMIT 20
                """, (sel_job,)).fetchall()
                _p_job = conn.execute("""
                    SELECT j.hard_skills, j.soft_skills, j.berufserfahrung_jahre,
                           j.deutsch_level, j.englisch_level, j.standort, j.stellentyp,
                           e.branche
                    FROM jobs j JOIN employers e ON e.id = j.employer_id
                    WHERE j.id = ?
                """, (sel_job,)).fetchone()
                passive = []
                if _p_job:
                    (_j_hard, _j_soft, _j_exp, _j_de, _j_en, _j_st, _j_typ, _j_br) = _p_job
                    for _p in _p_rows:
                        _k_data = {"hard_skills": _p[2], "soft_skills": _p[3],
                                   "berufserfahrung_jahre": _p[4], "abschluss": _p[5],
                                   "deutsch": _p[6], "englisch": _p[7], "standort": _p[8],
                                   "lebenslauf_text": _p[9] or ""}
                        _j_data = {"hard_skills": _j_hard, "soft_skills": _j_soft,
                                   "berufserfahrung_jahre": _j_exp, "deutsch_level": _j_de,
                                   "englisch_level": _j_en, "standort": _j_st,
                                   "stellentyp": _j_typ, "branche": _j_br}
                        try:
                            _res = logic.berechne_match_score(_k_data, _j_data)
                        except Exception:
                            continue
                        if not _res.get("matches"):
                            continue  # >=1 Must-Have (Paritaet app.py:3911)
                        if _j_exp and (_p[4] or 0) < _j_exp * 0.5:
                            continue  # Erfahrung >= 50% (Paritaet app.py:3913)
                        passive.append((_p[0], _p[1], None))
                # Bewerber bleiben UNGEFILTERT (Paritaet app.py:3902-3903)
                all_cands = applicants + passive
                if not all_cands:
                    ui.label(_('Keine Kandidaten verfügbar.')).classes(C.MUTED)
                    return

                return ui.select(
                    options={c[0]: ("📩 " if c[2] else "") + (c[1] or _('Kandidat #{0}').format(c[0])) for c in all_cands},
                    label=_('Kandidat'),
                    value=all_cands[0][0],
                ).classes("w-full")

        # N-F1 (29.09.2026): refresh_cands() zerstoert den alten Select
        # (cand_container.clear()) -> der Handler muss den neuen Binden,
        # sonst speichert save_feedback mit der toten Referenz (falscher
        # Kandidat der VORHERIGEN Stelle). Spec: employer-portal-fields.md
        # „Feedback-Picker-Bindung".
        def _on_job_change(_e=None):
            nonlocal cand_select
            cand_select = refresh_cands()

        job_select.on_value_change(_on_job_change)
        cand_select = refresh_cands()

        ui.separator().classes("my-4")

        # Formular (Muster: app.py:3923-3936, Employer-Tab-4)
        score_input = ui.number(label=_('Match-Score (0-100)'), value=85, min=0, max=100).classes("w-full")
        eingeladen_select = ui.select(options={v: _(v) for v in ["Ja", "Nein", "Vorgemerkt"]}, value="Ja", label=_('Eingeladen?')).classes("w-full")
        anmerkungen_input = ui.textarea(label=_('Anmerkungen')).classes("w-full")

        ui.label(_('Bewertung (1-5):')).classes(C.SMALL + " font-medium mt-2")
        with ui.grid(columns=4).classes("w-full gap-4"):
            fachlich_input = ui.slider(min=1, max=5, value=4, step=1).classes("w-full")
            ui.label(_('Fachlich')).classes(C.MUTED)
            skills_input = ui.slider(min=1, max=5, value=4, step=1).classes("w-full")
            ui.label(_('Skills')).classes(C.MUTED)
            standort_input = ui.slider(min=1, max=5, value=4, step=1).classes("w-full")
            ui.label(_('Standort')).classes(C.MUTED)
            empfehlung_input = ui.slider(min=1, max=5, value=4, step=1).classes("w-full")
            ui.label(_('Empfehlung')).classes(C.MUTED)

        def save_feedback():
            if not cand_select or not cand_select.value:
                ui.notify(_('Kandidat wählen.'), type="warning")
                return
            c_id = cand_select.value
            j_id = job_select.value
            score = int(score_input.value or 85)
            eingeladen = eingeladen_select.value or "Nein"
            anmerkungen = anmerkungen_input.value or ""
            fachlich = int(fachlich_input.value or 4)
            skills = int(skills_input.value or 4)
            standort = int(standort_input.value or 4)
            empfehlung = int(empfehlung_input.value or 4)

            # Kandidat-Name
            cand_row = conn.execute("SELECT name FROM candidates WHERE id = ?", (c_id,)).fetchone()
            kandidat_name = cand_row[0] if cand_row else f"Kandidat #{c_id}"

            # Stellenprofil
            job_row = conn.execute("SELECT titel FROM jobs WHERE id = ?", (j_id,)).fetchone()
            stellenprofil = job_row[0] if job_row else "Unbekannt"

            # Kategorie berechnen (M-16-Reststelle 01.10.2026: lokale ZYTHR-Schwelle
            # statt hr-benchmark-Subprozess - eine Quelle: logic.get_score_category_lokal)
            # C4 (22.09.2026): Cat-Map Employer-Tab-4 Parität (app.py:3939-3944:
            # default 'Schwach', Weak→'Schwach'; 'Nicht passend' war die ADMIN-
            # Map app.py:2598-2603 — falsche Quelle hier)
            _cat_map = {"Strong": "Hervorragend", "Consider": "Bedingt", "Weak": "Schwach"}
            kategorie = _cat_map.get(logic.get_score_category_lokal(score), "Schwach")
            if kategorie == "Bedingt" and score >= 75:
                kategorie = "Gut"

            # match_id: employer-job-{id}-cand-{id}-{date} (Muster: app.py:3952)
            from datetime import datetime
            match_id = f"employer-job-{j_id}-cand-{c_id}-{datetime.now().strftime('%Y-%m-%d')}"

            # Idempotenz: gleicher Tag = UPDATE, neuer Tag = INSERT (Muster: app.py:2596-2614)
            existing = conn.execute(
                "SELECT id FROM feedback WHERE match_id = ?", (match_id,)
            ).fetchone()

            if existing:
                conn.execute("""UPDATE feedback SET
                    kandidat_name=?, stellenprofil=?, score=?, kategorie=?,
                    fachlich_korrekt=?, skills_richtig=?, standort_zutreffend=?,
                    empfehlung_hilfreich=?, eingeladen=?, anmerkungen=?
                    WHERE match_id=?""",
                    (kandidat_name, stellenprofil, score, kategorie,
                     fachlich, skills, standort, empfehlung,
                     eingeladen, anmerkungen, match_id))
                conn.commit()
                ui.notify(_('Feedback aktualisiert (heute bereits vorhanden).'), type="info")
                is_new = False
            else:
                conn.execute("""INSERT INTO feedback
                    (match_id, kandidat_name, stellenprofil, score, kategorie,
                     fachlich_korrekt, skills_richtig, standort_zutreffend,
                     empfehlung_hilfreich, eingeladen, anmerkungen)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (match_id, kandidat_name, stellenprofil, score, kategorie,
                     fachlich, skills, standort, empfehlung,
                     eingeladen, anmerkungen))
                conn.commit()
                is_new = True
                ui.notify(_('Feedback gespeichert!'), type="positive")

            # Phase 4: Gewichtungsanpassung (nur bei NEUEM Feedback, Muster: app.py:2617-2624)
            if is_new:
                grund = f"{'Erfolgreicher' if eingeladen == 'Ja' else 'Gescheiterter'} Match {kandidat_name}: Score {score}/100"
                gewichtung_msg = logic.adjust_weights_from_feedback(eingeladen, score, grund, conn)
                if gewichtung_msg:
                    ui.notify(gewichtung_msg, type="info")

                # export_report Trigger (Muster: app.py:2666-2669)
                db.queue_agent_task("export_report", {
                    "application_id": None,
                    "candidate_id": c_id,
                    "job_id": None,
                    "match_id": match_id,
                })

            refresh_list()

        ui.button(_('💾 Feedback speichern'), on_click=save_feedback).classes(C.BTN_PRIMARY + " mt-4")

    # ── Bestehende Feedback-Anzeige ──
    feedback_container = ui.column().classes("w-full")

    def refresh_list():
        # Klarnamen-Mapping fuer alte Feedback-Zeilen (P1, 28.09.2026) + M-07-Resolver
        _cands = conn.execute("SELECT id, name FROM candidates").fetchall()
        _name_by_id = {cid: nm for cid, nm in _cands}
        _name_to_id: dict = {}
        _token_ids: dict = {}
        for _cid, _nm in _cands:
            if not _nm:
                continue
            _name_to_id.setdefault(_nm.strip().casefold(), _cid)
            _toks = tuple(sorted(t for t in _re.split(r"\s+", _nm.casefold()) if t))
            _token_ids.setdefault(_toks, []).append(_cid)

        def _zeile_geklickt(e):
            """M-07 (01.10.2026): JEDE Feedback-Zeile hat ein Klickziel.

            Aufloesbarer Kandidat -> Match-Seite mit Fokus (`?kandidat=<id>`,
            gelesen von `_kandidat_query_param`); sonst Detail-Dialog mit dem
            gespeicherten Datensatz (Altbestand ohne Kandidatenbezug) — kein
            Klick fuehrt ins Leere.
            """
            _sel = list(e.selection or [])
            if not _sel:
                return
            _r = _sel[0]
            if _r.get("cid"):
                ui.navigate.to(f"/employer/match?kandidat={_r['cid']}")
                return
            with ui.dialog() as _dlg, ui.card().classes("w-[520px] max-w-full"):
                ui.label(_('💬 Feedback – {0}').format(_r.get('name') or '--')).classes(C.CARD_TITLE)
                for _k, _v in (_r.get("details") or {}).items():
                    info_row(_k, _v)
                with ui.row().classes("justify-end w-full mt-3"):
                    ui.button(_('Schließen'), on_click=_dlg.close).props("flat")
            _dlg.open()

        feedback_container.clear()
        with feedback_container:
            # M-07: zusaetzlich id (Zeilen-Schluessel fuer die Auswahl) + Stelle +
            # die 4 Bewertungen (Detail-Dialog der nicht aufloesbaren Alt-Zeilen).
            feedbacks = conn.execute(
                "SELECT id, match_id, kandidat_name, stellenprofil, score, kategorie, "
                "eingeladen, anmerkungen, datum, fachlich_korrekt, skills_richtig, "
                "standort_zutreffend, empfehlung_hilfreich "
                "FROM feedback ORDER BY id DESC LIMIT 20"
            ).fetchall()
            if not feedbacks:
                empty_state(icon="feedback", title=_('Noch kein Feedback'))
                return
            columns = [
                {"name": "name", "label": _("Kandidat"), "field": "name", "align": "left"},
                {"name": "score", "label": _("Score"), "field": "score", "sortable": True, "align": "left"},
                {"name": "kategorie", "label": _("Kategorie"), "field": "kategorie", "align": "left"},
                {"name": "eingeladen", "label": _("Eingeladen"), "field": "eingeladen", "align": "left"},
                {"name": "datum", "label": _("Datum"), "field": "datum", "sortable": True, "align": "left"},
                # P1 (28.09.2026): technische Vorgangs-ID stand als erste Spalte
                # und war teils ein Markdown-Dateiname
                # ('profil---**name:**-anna-schuster-2026-09-28') → Klartext-Regel.
                # Jetzt als Kennzahl ganz rechts, ohne Dateinamen.
                {"name": "match_id", "label": _("Vorgang-Nr."), "field": "match_id", "sortable": True, "align": "left"},
            ]
            rows = []
            for f in feedbacks:
                # f = id, match_id, kandidat_name, stellenprofil, score, kategorie,
                #     eingeladen, anmerkungen, datum, 4x Bewertung
                rows.append({
                    "id": f[0],
                    "match_id": (f[1] or "").rsplit("-", 3)[0] if "-" in (f[1] or "") else (f[1] or "--"),
                    # Klartext-Regel: aeltere Feedback-Zeilen speicherten teils
                    # 'Kandidat #2' oder '**Name:** Anna Schuster' → hier einmalig
                    # gegen die Kandidatenliste aufloesen.
                    "name": _feedback_klarname(f[2], _name_by_id),
                    "score": f[4] or 0,
                    "kategorie": _(f[5]) if f[5] else "--",
                    "eingeladen": f[6] or "--",
                    "datum": (f[8] or "--")[:10],
                    # M-07 (01.10.2026): Klickziel je Zeile — cid = aufloesbarer
                    # Kandidat (Sprung zur Match-Seite), sonst Detail-Dialog.
                    "cid": _feedback_row_cid(f[1], f[2], _name_by_id, _name_to_id, _token_ids),
                    "details": {
                        _("Kandidat (gespeichert)"): _feedback_klarname(f[2], _name_by_id),
                        _("Stelle"): f[3] or "--",
                        _("Vorgangs-Nr."): f[1] or "--",
                        _("Datum"): f[8] or "--",
                        _("Score / Kategorie"): f"{f[4] if f[4] is not None else '--'} / {_(f[5]) if f[5] else '--'}",
                        _("Eingeladen"): f[6] or "--",
                        _("Bewertung fachlich"): f[9] if f[9] is not None else "--",
                        _("Bewertung Skills"): f[10] if f[10] is not None else "--",
                        _("Bewertung Standort"): f[11] if f[11] is not None else "--",
                        _("Bewertung Empfehlung"): f[12] if f[12] is not None else "--",
                        _("Anmerkungen"): f[7] or "--",
                        _("Hinweis"): _("Kein Kandidat in der DB zuordenbar (Altbestand) — "
                                   "statt einer falschen Match-Seite wird der Datensatz gezeigt."),
                    },
                })
            _fb_table = data_table(columns=columns, rows=rows, pagination=10,
                                   on_row_click=_zeile_geklickt)
            # M-07 (01.10.2026): sichtbares Klickziel je Zeile (Muster wie
            # Kandidaten-Suche, employer.py:934) — der Namens-Knopf leitet den
            # Klick an das Auswahl-Kästchen derselben Zeile weiter (NiceGUI-Slots
            # kennen kein 'parent'); das feuert on_select -> _zeile_geklickt.
            if _fb_table is not None:
                _fb_table.add_slot("body-cell-name", r'''
                    <q-td :props="props">
                        <q-btn flat no-caps color="primary" class="cursor-pointer self-start no-wrap"
                               :label="props.row.name"
                               @click="$el.closest('tr').querySelector('.q-checkbox').click()" />
                    </q-td>
                ''')

    refresh_list()
    # C4-Fix (22.09.2026): conn bewusst NICHT hier schließen — save_feedback/
    # refresh_cands/refresh_list sind Handler-Closures nach dem Page-Build und
    # nutzten eine geschlossene DB (sqlite3.ProgrammingError im E2E sichtbar).

    # C7 (22.09.2026): Skill 8 unter Tab4 (shared Section, eigener Conn)
    ui.separator().classes("my-6")
    skill8_feedback_section()
    # Lebensdauer = Page-Instance; CPython sqlite3 schließt beim GC.


# ─── Page Router ─────────────────────────────────────────────────────

PAGE_MAP = {
    "dashboard": _page_dashboard,
    "portal": _page_portal,
    "stellen": _page_stellen,
    "kandidaten": _page_kandidaten,
    "match": _page_match,
    "compliance": _page_compliance,
    "agent_details": _page_agent_details,
    "dokumente": _page_dokumente,
    "prescreen": _page_prescreen,
    "onboarding": _page_onboarding,
    "feedback": _page_feedback,
}# Menu-Items auf Modulebene (fuer Sub-Route-Registrierung)
_ICON_MAP = {
    "dashboard": "dashboard", "portal": "business",
    "stellen": "work", "kandidaten": "search", "match": "compare_arrows",
    "compliance": "verified", "agent_details": "smart_toy", "dokumente": "folder",
    "prescreen": "record_voice_over", "onboarding": "assignment", "feedback": "feedback",
}

def _menu_items_emp() -> list[dict]:
    """Sidebar-Einträge — Labels erst beim Rendern übersetzt
    (Importzeit = keine Session/Sprache, i18n-Regel knowledge/system/i18n.md)."""
    return [
        {"key": key, "label": _(title), "icon": _ICON_MAP.get(key, "circle")}
        for key, title in PAGE_TITLES.items()
    ]


def create() -> None:
    """Register the /employer page + Sub-Routes."""
    from nicegui import app

    def _build_employer_page(initial_tab: str = ""):
        s = app.storage.user
        role = logic.current_role(s)
        if role not in ("employer", "admin"):
            ui.navigate.to("/login")
            return

        def render_page(page_key: str):
            page_fn = PAGE_MAP.get(page_key, _page_dashboard)
            page_fn(s)

        from webui.components import shell
        shell(
            role="employer",
            user_id=s.get("employer_id", 0),
            user_name=s.get("employer_firma", _("Profil")),
            menu_items=_menu_items_emp(),
            logout_fn=lambda: logic.logout_employer(s),
            content_fn=render_page,
            s=s,
            initial_tab=initial_tab,
        )

    @ui.page("/employer")
    def employer_page():
        _build_employer_page()

    # Sub-Routes auf Modulebene registrieren
    for _tab_key in PAGE_MAP:
        def _register_emp(k=_tab_key):
            @ui.page(f"/employer/{k}")
            def _sub_page(_k=k):
                _build_employer_page(initial_tab=_k)
        _register_emp()
