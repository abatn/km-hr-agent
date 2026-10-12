"""
Candidate pages for KM-HR-Agent NiceGUI App.
7 tabs (Quelle: _TAB_MAP candidate.py): Dashboard, Mein Profil, Stellen,
Bewerbungen, Sprachtest, Pre-Screen, Onboarding.
Upload und Dokumente wurden am 02.10.2026 in „Mein Profil" fusioniert.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
from pathlib import Path

from nicegui import background_tasks, run, ui

from webui import db, logic
from webui.i18n import _  # i18n Phase 5 (03.10.2026); Spec: knowledge/system/i18n.md

_log = logging.getLogger("kmhr.candidate")
from webui.theme import C, PRIMARY, SECONDARY, ACCENT, score_color, score_label, score_badge_class
from webui.components import (
    stat_card, status_badge, status_label, score_bar, score_card, timeline,
    upload_zone, empty_state, section_header, data_table, info_row,
    skill_chip, loading_spinner, candidate_avatar,
    notifications_drawer, navigate_to, STATUS_ICONS,
)


def _session() -> dict:
    from nicegui import app
    return app.storage.user


# ─── R3-5: Neue Bewerbung -> Benachrichtigung des Arbeitgebers ────────

def _notify_neue_bewerbung(job_id: int, kandidaten_name: str = "",
                           candidate_id: int | None = None) -> None:
    """Benachrichtigt den Arbeitgeber ueber eine NEUE Bewerbung (R3-5, N-D1).

    Lest (read-only) employer_id + titel aus jobs und schreibt per
    db.insert_notification(employer_id, "employer", ...) eine Zeile in
    notifications — die erste echte Nutzerin von insert_notification()
    (vorher 0 Aufrufer, Tabelle leer).

    Design-Entscheidungen (KEINE externe Quelle, dokumentiert in
    knowledge/portal/candidate-portal-fields.md §Benachrichtigungen):
      * Textmuster "<Name> hat sich beworben: <Stellentitel>".
      * Reaktivierung einer zurueckgezogenen Bewerbung ist ein NEUES Ereignis
        -> erneute Benachrichtigung (HR soll jeden Zusendungs-Vorgang sehen).
      * Fehler im Insert duerfen die Bewerbung NIE brechen: try/except +
        print (db-Konvention, streamlit-frei).
    """
    try:
        conn = db.get_conn()
        try:
            row = conn.execute(
                "SELECT employer_id, titel FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            name = (kandidaten_name or "").strip()
            if not name and candidate_id is not None:
                c_row = conn.execute(
                    "SELECT name FROM candidates WHERE id = ?", (candidate_id,)
                ).fetchone()
                name = (c_row[0] if c_row else "") or ""
        finally:
            conn.close()
        if not row or not row[0]:
            return  # Stelle ohne Arbeitgeber: nichts zu benachrichtigen
        db.insert_notification(
            int(row[0]), "employer", _("Neue Bewerbung"),
            _('{0} hat sich beworben: {1}').format(name or _('Ein Bewerber'), row[1]),
        )
    except Exception as ex:
        print(f"[R3-5] Benachrichtigung fehlgeschlagen (job={job_id}): {ex}")


def _bewerbung_senden(cand_id: int, job_id: int, bew_text: str | None,
                      kandidaten_name: str = "") -> int:
    """Bewerbung senden UND Arbeitgeber benachrichtigen (R3-5, N-D1).

    Reihenfolge ist die Sicherheitsregel: erst db.apply_to_job, und die
    notifications-Zeile entsteht NUR wenn eine application_id zurueckkommt.
    Gesperrte Kandidaten-Status (ValueError, CV-Pflicht) und Doppelbewerbung
    (sqlite3.IntegrityError) werfen VOR dem Insert — dort KEINE notifications-
    Zeile. Testbar: tests/test_r35_apply_notify.py (Spiegel-DB).
    """
    app_id = db.apply_to_job(cand_id, job_id, bew_text)
    if app_id:
        _notify_neue_bewerbung(job_id, kandidaten_name, cand_id)
    return app_id


# ─── Tab 1: Lebenslauf hochladen ─────────────────────────────────────

def _upload_section(s: dict) -> None:
    with ui.card().classes(C.CARD + " w-full"):
        with ui.column().classes("items-center py-8 gap-4"):
            ui.icon("description", size="xl").classes("text-gray-400")
            ui.label(_('PDF oder TXT-Datei ablegen')).classes(C.BODY)
            ui.label(_('Maximale Größe: 5 MB')).classes(C.MUTED)

            uploaded_file = {"path": None}

            async def on_upload(e):
                try:
                    file_bytes = await e.file.read()
                    file_name = e.file.name or "upload"
                    # Endungsprüfung (serverseitig, R5-2/S3c)
                    if not file_name.lower().endswith(('.pdf', '.txt')):
                        ui.notify(_('Nur .pdf/.txt erlaubt'), type="negative")
                        return
                    # Dateinamen bereinigen (R5-2: logik in logic.safe_upload_name,
                    # transliteriert Umlaute statt sie zu löschen)
                    clean_name = logic.safe_upload_name(file_name)
                    # Datei nach testdaten/ speichern (Muster: app.py:1222-1223)
                    save_path = logic.TESTDATEN / f"kandidat-{s['user_cand_id']}-{clean_name}"
                    save_path.write_bytes(file_bytes)

                    # Text extrahieren (PDF vs TXT)
                    if file_name.lower().endswith(".pdf"):
                        # P2 (Spec: knowledge/system/event-loop-blockieren.md):
                        # PDF-Extraktion (subprocess, 0,9–1,9 s) vom Event-Loop
                        # entkoppeln (NiceGUI-FAQ run.io_bound).
                        cv_text = await run.io_bound(logic.extract_pdf_text, str(save_path))
                    else:
                        cv_text = file_bytes.decode("utf-8", errors="replace")

                    # DB: lebenslauf_datei + lebenslauf_text + status (Muster: app.py:1228-1233)
                    conn = db.get_conn()
                    conn.execute(
                        """UPDATE candidates SET
                            lebenslauf_datei=?, lebenslauf_text=?,
                            status='lebenslauf_hochgeladen', aktualisiert_am=CURRENT_TIMESTAMP
                            WHERE id=?""",
                        (str(save_path), cv_text[:5000], s["user_cand_id"]),
                    )
                    conn.commit()
                    conn.close()
                    uploaded_file["path"] = True
                    ui.notify(_('Lebenslauf hochgeladen ({0} Zeichen).').format(len(cv_text)), type="positive")

                    # Trigger: extract_profile (Muster: app.py:1236-1237)
                    db.queue_agent_task("extract_profile", {
                        "candidate_id": s["user_cand_id"],
                        "cv_path": str(save_path),
                    })
                    # SPA-Refresh: Upload-Box bleibt aktiv (kein Page-Reload)
                    # Toast-vor-Navigation-Regel (06.10.2026,
                    # knowledge/ui-design-system.md): navigate_to()
                    # loest window.open(url,"_self") aus und wuerde
                    # den Toast sofort zerstoeren.
                    await asyncio.sleep(1.5)
                    navigate_to("candidate", "profil")
                except Exception as ex:
                    ui.notify(_('Fehler: {0}').format(ex), type="negative")

            ui.upload(
                on_upload=on_upload,
                auto_upload=True,
                max_file_size=5_000_000,
                label=_('Datei auswählen'),
            ).props('accept=".pdf,.txt"').classes("w-64")

            # Current status
            conn = db.get_conn()
            row = conn.execute(
                "SELECT lebenslauf_text, status FROM candidates WHERE id = ?",
                (s["user_cand_id"],),
            ).fetchone()
            conn.close()

            if row and row[0]:
                with ui.row().classes("items-center gap-2 mt-4"):
                    status_badge(row[1] or "unbekannt")
                    ui.label(_('Lebenslauf vorhanden')).classes(C.SMALL)
            else:
                ui.label(_('Noch kein Lebenslauf hochgeladen')).classes(C.MUTED + " mt-4")


# ─── Tab 2: Mein Profil ──────────────────────────────────────────────

# A3 (30.09.2026): feste Auswahllisten. Quelle: Streamlit-Original app.py:2781/2788-2790
# (Visum, Verfügbarkeit, Abschluss, Sprachniveaus) + knowledge/portal/candidate-portal-fields.md
# (Abschluss: Bachelor/Master/Diplom/PhD/Sonstiges). Die Auswahl der Listen selbst ist eine
# Design-Entscheidung (keine externe Quelle); bestehende Freitext-Werte des Nutzers werden
# über profil_optionen() zusätzlich angeboten, nie die anderer Kandidaten.
PROFIL_VISUM_OPTIONEN = ["EU-Bürger", "Arbeitsvisum", "Kein Visum", "Sonstiges"]
PROFIL_VERFUEGBARKEIT_OPTIONEN = ["Sofort", "1 Monat", "3 Monate", "Kündigungslaufzeit"]
PROFIL_ABSCHLUSS_OPTIONEN = ["Bachelor", "Master", "Diplom", "PhD", "Sonstiges"]
PROFIL_SPRACHNIVEAUS = ["A1", "A2", "B1", "B2", "C1", "C2", "Muttersprache"]

# Whitelist der beschreibbaren Spalten (Spaltennamen werden nie aus Nutzereingaben gebaut).
_PROFIL_SPALTEN = (
    "standort", "nationalitaet", "visum_status", "verfuegbarkeit", "aktuelle_position",
    "berufserfahrung_jahre", "hard_skills", "soft_skills", "abschluss", "deutsch",
    "englisch", "franzoesisch", "gehaltsvorstellung",
)
_PROFIL_ZAHLEN = ("berufserfahrung_jahre", "gehaltsvorstellung")

# Profil-Vollständigkeit (Dashboard-Kachel). Design-Entscheidung 01.10.2026,
# keine externe Quelle. Basis = dieselbe Feldliste wie _PROFIL_SPALTEN (eine Quelle,
# kein Duplikat) + telefon + lebenslauf_datei; franzoesisch fällt automatisch raus,
# wenn die Spalte fehlt (PRAGMA-Abgleich).
_VOLLSTAENDIG_FELDER = (*_PROFIL_SPALTEN, "telefon", "lebenslauf_datei")

# Zeitfenster für die Dashboard-Kachel "Neu veroeffentlichte Stellen":
# gezählt werden nur aktive Stellen, die in den letzten _NEU_TAGE Tagen
# ERSTELLT wurden (jobs.erstellt_am). Design-Entscheidung 02.10.2026,
# keine externe Quelle.
_NEU_TAGE = 7


def _profil_vollstaendigkeit(conn, cand_id: int) -> int:
    """Anteil gefüllter Profilfelder in Prozent (0-100), gerundet."""
    vorhanden = {r[1] for r in conn.execute("PRAGMA table_info(candidates)").fetchall()}
    felder = [f for f in _VOLLSTAENDIG_FELDER if f in vorhanden]
    if not felder:
        return 0
    row = conn.execute(
        f"SELECT {', '.join(felder)} FROM candidates WHERE id = ?", (cand_id,)
    ).fetchone()
    if not row:
        return 0
    gefuellt = sum(1 for v in row if v is not None and str(v).strip() != "")
    return round(gefuellt / len(felder) * 100)


def profil_optionen(basis: list, aktuell) -> list:
    """Feste Optionsliste + der aktuelle Wert des Nutzers (falls nicht enthalten).

    Ohne den aktuellen Wert wirft ui.select ein ValueError bzw. der Wert ginge beim
    Speichern verloren (z. B. Freitext-Abschluss aus der CV-Extraktion).
    """
    optionen = list(basis)
    if aktuell not in (None, "") and aktuell not in optionen:
        optionen.append(aktuell)
    return optionen


def _profil_wert(spalte: str, wert):
    """Normalisiert einen Formularwert: leer/ungesetzt -> None (=NULL), Zahlen -> int."""
    if spalte in _PROFIL_ZAHLEN:
        if wert is None or (isinstance(wert, str) and not wert.strip()):
            return None
        return int(wert)
    if wert is None:
        return None
    if isinstance(wert, str):
        wert = wert.strip()
        return wert or None
    return wert


def save_profile_fields(conn, cand_id: int, werte: dict) -> None:
    """Schreibt die Profilfelder; committet NICHT (Aufrufer entscheidet).

    Nur Spalten aus der Whitelist UND aus dem tatsächlichen Schema (PRAGMA table_info,
    z. B. `franzoesisch` nur falls vorhanden). Kein Wert wird erfunden: leer -> NULL.
    Statusübergang wie bisher (CV vorhanden: registriert/profil_vollstaendig ->
    lebenslauf_hochgeladen; ohne CV: profil_vollstaendig).
    """
    vorhanden = {r[1] for r in conn.execute("PRAGMA table_info(candidates)").fetchall()}
    spalten = [c for c in _PROFIL_SPALTEN if c in werte and c in vorhanden]
    setz = ", ".join(f"{c}=?" for c in spalten)
    conn.execute(
        f"""UPDATE candidates SET {setz},
            status = CASE
                WHEN COALESCE(TRIM(lebenslauf_datei),'') = ''
                     AND COALESCE(TRIM(lebenslauf_text),'') = ''
                THEN 'profil_vollstaendig'
                WHEN status IN ('registriert','profil_vollstaendig')
                THEN 'lebenslauf_hochgeladen'
                ELSE status END,
            aktualisiert_am=CURRENT_TIMESTAMP
            WHERE id=?""",
        [_profil_wert(c, werte[c]) for c in spalten] + [cand_id],
    )


def _tab_profil(s: dict) -> None:
    section_header(title=_('Mein Profil'), icon="person")

    # A3c (30.09.2026): eine Abfrage; Spaltennamen aus cursor.description statt
    # doppeltem PRAGMA table_info (+ ungenutztem `cols`).
    conn = db.get_conn()
    cur = conn.execute("SELECT * FROM candidates WHERE id = ?", (s["user_cand_id"],))
    row = cur.fetchone()
    spalten = [d[0] for d in cur.description]
    conn.close()

    if not row:
        empty_state(icon="person_off", title=_('Profil nicht gefunden'))
        return

    profile = dict(zip(spalten, row))

    # 02.10.2026 (Nutzerentscheidung): Profil-Karten sind klappbar (ui.expansion,
    # Muster wie "Lebenslauf hochladen"). Standard OFFEN (value=True), damit die
    # Inhalte (Skills/Sprachen) weiter im sichtbaren Text stehen (e2e_profile_readview).
    with ui.expansion(_('Persoenliche Daten'), icon="person", value=True).classes("w-full mt-4"):
        # Personal info (12 Speicher-Felder, P1: knowledge/portal/candidate-portal-fields.md
        # "Read-View Anzeige" — Quelle Speicher app.py:2798-2806)
        info_row(_('Name'), profile.get("name", "—"), icon="person")
        info_row(_('E-Mail'), profile.get("email", "—"), icon="email")
        info_row(_('Status'), status_label(profile.get("status")) if profile.get("status") else "—", icon="info")
        info_row(_('Standort'), profile.get("standort") or "—", icon="location_on")
        info_row(_('Nationalitaet'), profile.get("nationalitaet") or "—", icon="flag")
        info_row(_('Visum-Status'), _(profile.get("visum_status") or "—"), icon="badge")
        info_row(_('Verfuegbarkeit'), _(profile.get("verfuegbarkeit") or "—"), icon="schedule")
        info_row(_('Aktuelle Position'), profile.get("aktuelle_position") or "—", icon="work")

    # Skills
    with ui.expansion(_('Fachkompetenzen'), icon="psychology", value=True).classes("w-full mt-4"):
        skills = profile.get("hard_skills") or "—"
        if skills and skills != "—":
            for skill in skills.split(",") if isinstance(skills, str) else skills:
                skill_chip(skill.strip())
        else:
            ui.label(_('Noch keine Skills erfasst')).classes(C.MUTED)
        soft = profile.get("soft_skills")
        if soft:
            info_row(_('Soft Skills'), soft, icon="groups")

    # Experience (+ Abschluss, P1)
    with ui.expansion(_('Berufserfahrung'), icon="work", value=True).classes("w-full mt-4"):
        years = profile.get("berufserfahrung_jahre")
        if years:
            stat_card(label=_('Jahre Erfahrung'), value=_('{0} Jahre').format(years), icon="work", color=PRIMARY)
        else:
            ui.label(_('Noch nicht erfasst')).classes(C.MUTED)
        if profile.get("abschluss"):
            info_row(_('Abschluss'), _(profile["abschluss"]), icon="school")

    # Languages
    with ui.expansion(_('Sprachen'), icon="translate", value=True).classes("w-full mt-4"):
        lang_items = []
        if profile.get("deutsch"):
            lang_items.append(("Deutsch", profile["deutsch"]))
        if profile.get("englisch"):
            lang_items.append(("Englisch", profile["englisch"]))
        if profile.get("franzoesisch"):
            lang_items.append(("Französisch", profile["franzoesisch"]))
        if lang_items:
            for lang, level in lang_items:
                info_row(_(lang), level, icon="translate")
        else:
            ui.label(_('Noch nicht erfasst')).classes(C.MUTED)

    # Gehaltsvorstellung (Feld #12 der 12er-Liste — jetzt klappbar wie die anderen)
    with ui.expansion(_('Gehaltsvorstellung'), icon="payments", value=True).classes("w-full mt-4"):
        gehalt = profile.get("gehaltsvorstellung")
        if gehalt:
            stat_card(label=_('Gehaltsvorstellung'), value=f"{gehalt:,.0f} EUR".replace(",", "."),
                      icon="payments", color=PRIMARY)
        else:
            ui.label(_('Noch nicht erfasst')).classes(C.MUTED)

    # ── Profil bearbeiten (12 Felder, Port app.py:2777-2806) ──
    # Quellen: app.py:2781-2793 (Streamlit-Original). A3b (30.09.2026): FESTE Listen
    # (Modulkonstanten PROFIL_*_OPTIONEN) statt SELECT DISTINCT über ALLE Kandidaten
    # (Datenleck: fremde Freitext-Werte wie Abschluss/Schule anderer Nutzer wurden
    # angeboten). Der aktuelle Wert des Nutzers wird per profil_optionen() ergänzt.
    visum_options = profil_optionen(PROFIL_VISUM_OPTIONEN, profile.get("visum_status"))
    abschluss_options = profil_optionen(PROFIL_ABSCHLUSS_OPTIONEN, profile.get("abschluss"))
    verf_options = profil_optionen(PROFIL_VERFUEGBARKEIT_OPTIONEN, profile.get("verfuegbarkeit"))
    de_options = profil_optionen(PROFIL_SPRACHNIVEAUS, profile.get("deutsch"))
    en_options = profil_optionen(PROFIL_SPRACHNIVEAUS, profile.get("englisch"))
    fr_options = profil_optionen(PROFIL_SPRACHNIVEAUS, profile.get("franzoesisch"))
    hat_franz = "franzoesisch" in spalten  # A3d: nur editierbar, wenn die Spalte existiert

    with ui.expansion(_('Profil bearbeiten'), icon="edit").classes("w-full mt-4"):
        with ui.grid(columns=2).classes("w-full gap-4"):
            inp_standort = ui.input(label=_('Standort'), value=profile.get("standort") or "").classes("w-full")
            inp_nationalitaet = ui.input(label=_('Nationalitaet'), value=profile.get("nationalitaet") or "").classes("w-full")
            # A3a (30.09.2026): KEINE erfundenen Defaults ("Sofort", "B1", 0) — ungesetzte
            # Felder bleiben leer (=NULL beim Speichern), select ist löschbar (clearable).
            sel_visum = ui.select(label=_('Visum-Status'),
                      options={v: _(v) for v in visum_options},
                      value=profile.get("visum_status") or None).props("clearable").classes("w-full")
            sel_verfuegbarkeit = ui.select(label=_('Verfuegbarkeit'),
                      options={v: _(v) for v in verf_options},
                      value=profile.get("verfuegbarkeit") or None).props("clearable").classes("w-full")
            inp_position = ui.input(label=_('Aktuelle Position'), value=profile.get("aktuelle_position") or "").classes("w-full")
            num_erfahrung = ui.number(label=_('Jahre Erfahrung'), min=0, max=50,
                      value=profile.get("berufserfahrung_jahre")).classes("w-full")
            inp_hard = ui.input(label=_('Hard Skills (kommasepariert)'),
                     value=profile.get("hard_skills") or "").classes("w-full")
            inp_soft = ui.input(label=_('Soft Skills (kommasepariert)'),
                     value=profile.get("soft_skills") or "").classes("w-full")

        with ui.grid(columns=2).classes("w-full gap-4 mt-2"):
            sel_abschluss = ui.select(label=_('Abschluss'),
                      options={v: _(v) for v in abschluss_options},
                      value=profile.get("abschluss") or None).props("clearable").classes("w-full")
            sel_deutsch = ui.select(label=_('Deutsch'),
                      options={v: _(v) for v in de_options},
                      value=profile.get("deutsch") or None).props("clearable").classes("w-full")
            sel_englisch = ui.select(label=_('Englisch'),
                      options={v: _(v) for v in en_options},
                      value=profile.get("englisch") or None).props("clearable").classes("w-full")
            sel_franz = None
            if hat_franz:
                sel_franz = ui.select(label=_('Französisch'),
                          options={v: _(v) for v in fr_options},
                          value=profile.get("franzoesisch") or None).props("clearable").classes("w-full")
            num_gehalt = ui.number(label=_('Gehaltsvorstellung (EUR)'), min=0, max=200000,
                      value=profile.get("gehaltsvorstellung")).classes("w-full")

        async def save_profile():
            werte = {
                "standort": inp_standort.value, "nationalitaet": inp_nationalitaet.value,
                "visum_status": sel_visum.value, "verfuegbarkeit": sel_verfuegbarkeit.value,
                "aktuelle_position": inp_position.value,
                "berufserfahrung_jahre": num_erfahrung.value,
                "hard_skills": inp_hard.value, "soft_skills": inp_soft.value,
                "abschluss": sel_abschluss.value, "deutsch": sel_deutsch.value,
                "englisch": sel_englisch.value, "gehaltsvorstellung": num_gehalt.value,
            }
            if sel_franz is not None:
                werte["franzoesisch"] = sel_franz.value
            conn = db.get_conn()
            save_profile_fields(conn, s["user_cand_id"], werte)
            conn.commit()
            conn.close()
            ui.notify(_('Profil gespeichert!'), type="positive")
            # Toast-vor-Navigation-Regel (06.10.2026,
            # knowledge/ui-design-system.md): navigate_to()
            # loest window.open(url,"_self") aus und wuerde
            # den Toast sofort zerstoeren.
            await asyncio.sleep(1.5)
            navigate_to("candidate", "profil")

        ui.button(_('Profil speichern'), icon="save", on_click=save_profile).classes(C.BTN_PRIMARY + " mt-3")

    # Status-Historie (aus app.py:3047-3054)
    with ui.card().classes(C.CARD + " w-full mt-4"):
        ui.label(_('Mein Status')).classes(C.CARD_TITLE + " mb-3")
        info_row(_('Aktueller Status'), status_label(profile.get("status")) if profile.get("status") else "—", icon="info")
        if profile.get("registriert_am"):
            info_row(_('Registriert'), str(profile["registriert_am"])[:10], icon="event")
        if profile.get("aktualisiert_am"):
            info_row(_('Aktualisiert'), str(profile["aktualisiert_am"])[:10], icon="update")

        # Status-Verlauf
        conn2 = db.get_conn()
        history = conn2.execute(
            "SELECT status, changed_at, notizen FROM candidate_status_history WHERE candidate_id = ? ORDER BY changed_at DESC",
            (s["user_cand_id"],),
        ).fetchall()
        conn2.close()

        if history:
            ui.label(_('Verlauf')).classes("font-medium mt-4 mb-2")
            items = []
            for h_status, h_date, h_notiz in history:
                items.append({
                    "title": status_label(h_status),
                    "status": "done" if h_status in ("eingestellt", "abgelehnt", "zurückgezogen") else "active",
                    "date": h_date[:16] if h_date else "",
                })
            timeline(items)

    with ui.expansion(_('Lebenslauf hochladen'), icon="cloud_upload").classes("w-full mt-4"):
        _upload_section(s)

    with ui.expansion(_('Dokumente'), icon="folder").classes("w-full mt-4"):
        _dokumente_section(s)

    # ── Passwort ändern (N5, Design-Entscheidung: knowledge/portal/candidate-portal-fields.md) ──
    with ui.expansion(_('Passwort aendern'), icon="lock").classes("w-full mt-4"):
        pw_alt = ui.input(label=_('Aktuelles Passwort'), password=True).classes("w-full")
        pw_neu = ui.input(label=_('Neues Passwort'), password=True).classes("w-full")
        pw_wdh = ui.input(label=_('Neues Passwort wiederholen'), password=True).classes("w-full")

        async def do_change_pw():
            # P2 (Spec: knowledge/system/event-loop-blockieren.md): change_password
            # enthält bis zu 3 argon2-Ops (0,4–1,2 s je Op) → via run.io_bound vom
            # Event-Loop entkoppeln. Die DB-Verbindung wird IM Worker-Thread erzeugt:
            # eine SQLite-Verbindung darf die Thread-Grenze nicht überschreiten
            # (sqlite3 check_same_thread, Default True) — Design-Entscheidung,
            # übernommen aus Vorbild cdabbed.
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
                        conn_pw, "candidates", s["user_cand_id"],
                        pw_alt.value, pw_neu.value)
                finally:
                    conn_pw.close()

            ok, msg = await run.io_bound(_work)
            # S5 (12.10.2026): logic.change_password liefert deutsche msgids
            # -> am Call-Site übersetzen (Spec: knowledge/system/i18n.md).
            ui.notify(_(msg), type="positive" if ok else "negative")

        ui.button(_('Passwort aendern'), on_click=do_change_pw).classes(C.BTN_PRIMARY + " mt-2")


# ─── Tab 3: Stellenangebote ──────────────────────────────────────────

def _tab_stellen(s: dict) -> None:
    section_header(title=_('Stellenangebote'), subtitle=_('Offene Positionen durchsuchen'), icon="work")

    conn = db.get_conn()
    jobs = conn.execute(
        "SELECT j.id, j.titel, j.beschreibung, j.standort, j.stellentyp, "
        "j.hard_skills, j.soft_skills, j.berufserfahrung_jahre, j.deutsch_level, "
        "j.englisch_level, j.gehaltsrahmen_min, j.gehaltsrahmen_max, "
        "e.firma, e.branche, e.groesse "
        "FROM jobs j JOIN employers e ON j.employer_id = e.id "
        "WHERE j.status = 'aktiv' ORDER BY j.id DESC"
    ).fetchall()
    cand = conn.execute(
        "SELECT hard_skills, soft_skills, berufserfahrung_jahre, abschluss, "
        "deutsch, englisch, standort, lebenslauf_text, status "
        "FROM candidates WHERE id = ?",
        (s["user_cand_id"],),
    ).fetchone()
    conn.close()
    # B2-3 (cv-pflicht.md (c)2): Status-Liste = Parität app.py:3278
    cv_ok = bool(cand) and (cand[8] or "") in (
        "lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet", "eingeladen")

    if not jobs:
        empty_state(icon="work_off", title=_('Keine offenen Stellen'), description=_('Schau spaeter nochmal vorbei.'))
        return

    if not cv_ok:
        ui.label(
            _('⚠️ CV-Pflicht: Bewerben ist erst nach Lebenslauf-Upload möglich (👤 Mein Profil → Lebenslauf). Stellen ansehen ist erlaubt.')
        ).classes(C.BODY + " text-amber-600")

    def _format_gehalt(gmin, gmax):
        if gmin and gmax:
            return f"{gmin:,}–{gmax:,} EUR".replace(",", ".")
        elif gmin:
            return f"ab {gmin:,} EUR".replace(",", ".")
        elif gmax:
            return f"bis {gmax:,} EUR".replace(",", ".")
        return "–"

    # Feature G (ii) (Spec: knowledge/lifecycle/matching-criteria.md §2-§4, GO 24.09.2026):
    # Live-Score je aktivem Job (§4: live solange N ≤ ~20), Option A: score DESC,
    # Tie-Break id DESC. CV-Gate (§6, Design-Entscheidung): ohne lebenslauf_text
    # keine Scores/Badges, Reihenfolge bleibt id DESC (Upload setzt Status
    # lebenslauf_hochgeladen, candidate.py:64). Kein DB-Write, keine hardcodierten
    # Schwellen (Kategorien/Farben aus get_current_weights() + hr-benchmark-MCP).
    show_scores = bool(cand and (cand[7] or "").strip())
    scored = []
    for job in jobs:
        score = None
        result = None
        if show_scores:
            k_data = {"hard_skills": cand[0], "soft_skills": cand[1],
                      "berufserfahrung_jahre": cand[2], "abschluss": cand[3],
                      "deutsch": cand[4], "englisch": cand[5],
                      "standort": cand[6], "lebenslauf_text": cand[7] or ""}
            j_data = {"hard_skills": job[5], "soft_skills": job[6],
                      "berufserfahrung_jahre": job[7], "deutsch_level": job[8],
                      "englisch_level": job[9], "standort": job[3],
                      "stellentyp": job[4], "branche": job[13]}
            try:
                result = logic.berechne_match_score(k_data, j_data)
                score = result["total"]
            except Exception as ex:
                # Degradation: ein Job ohne Badge statt Tab-Crash — aber
                # geloggt (R5-1), nicht stumm.
                _log.warning("Match-Score fuer Job %s fehlgeschlagen: %s", job[0], ex)
                score = None
        scored.append((job, score, result))
    if show_scores:
        scored.sort(key=lambda t: (-(t[1] if t[1] is not None else -1), -t[0][0]))

    for job, score, result in scored:
        (j_id, j_titel, j_beschr, j_ort, j_typ, j_hard, j_soft,
         j_erf, j_de, j_en, j_gmin, j_gmax, e_firma, e_branche, e_groesse) = job
        gehalt_txt = _format_gehalt(j_gmin, j_gmax)

        with ui.card().classes(C.CARD_HOVER + " w-full mb-3"):
            # Titel-Zeile: #ID Titel – Firma (Ort, Typ)
            with ui.row().classes("items-center justify-between w-full"):
                ui.label(_('#{0} {1} – {2} ({3}, {4})').format(j_id, j_titel, e_firma, j_ort, j_typ)).classes(C.CARD_TITLE)
                if score is not None:
                    ui.badge(_('{0} % passend').format(score), color=None).classes(score_badge_class(score))
                # Check if already applied. P1-1 (30.09.2026, Nutzerentscheid
                # „Reaktivieren“): eine ZURÜCKGEZOGENE Bewerbung belegt ebenfalls die
                # UNIQUE-Zeile, blockiert aber nicht mehr — sie kann erneut gesendet
                # werden und wird in derselben Zeile reaktiviert (db.apply_to_job).
                conn = db.get_conn()
                applied = conn.execute(
                    "SELECT id, status FROM applications WHERE candidate_id = ? AND job_id = ?",
                    (s["user_cand_id"], j_id),
                ).fetchone()
                conn.close()
                zurueckgezogen = bool(applied) and applied[1] == "zurückgezogen"

                if applied and not zurueckgezogen:
                    ui.badge(_('Beworben'), color=None).classes(C.BADGE_GREEN)
                else:
                    # A2 (P0-4, 30.09.2026): j_id/j_titel/e_firma sind Schleifenvariablen
                    # und würden im Closure spät gebunden (Dialog zeigte die LETZTE
                    # Stelle der Liste). Bindung per Default-Argument zum Definitionszeitpunkt;
                    # NiceGUI zählt Parameter mit Default nicht als Event-Argument.
                    def _open_apply_dialog(jid=j_id, titel=j_titel, firma=e_firma):
                        with ui.dialog() as dialog, ui.card().classes("w-[520px]"):
                            ui.label(_('Bewerbung: {0}').format(titel)).classes(C.CARD_TITLE)
                            ui.label(firma or _('Unbekannt')).classes(C.SMALL + " text-gray-500")
                            if zurueckgezogen:
                                # P1-1: ehrliche Ansage, was beim erneuten Senden passiert
                                ui.label(
                                    _('ℹ️ Sie hatten diese Bewerbung zurückgezogen. Beim erneuten Absenden beginnt sie neu (Status: Eingegangen).')
                                ).classes(C.SMALL + " text-amber-600")
                            bew_text = ui.textarea(_('Motivationstext (optional, max. 2000 Zeichen):')) \
                                .props("maxlength=2000").classes("w-full")
                            with ui.row().classes("justify-end gap-2 mt-2 w-full"):
                                ui.button(_('Abbrechen'), on_click=dialog.close).props("flat")
                                async def _submit():
                                    try:
                                        # R3-5 (N-D1): Rueckgabe wird ausgewertet —
                                        # notifications-Zeile fuer den Arbeitgeber
                                        # entsteht NUR bei Erfolg (App-Id gesetzt).
                                        # Ausloeser auch bei Reaktivierung (gleiche
                                        # app_id) = neues Ereignis, s. _notify_neue_bewerbung.
                                        app_id = _bewerbung_senden(
                                            s["user_cand_id"], jid, bew_text.value or None,
                                            s.get("user_name") or "",
                                        )
                                        ui.notify(_('Bewerbung gesendet! Der Agent prueft Ihren Lebenslauf.'), type="positive")
                                        dialog.close()
                                        # Toast-vor-Navigation-Regel (06.10.2026,
                                        # knowledge/ui-design-system.md): navigate_to()
                                        # loest window.open(url,"_self") aus und wuerde
                                        # den Toast sofort zerstoeren.
                                        await asyncio.sleep(1.5)
                                        navigate_to("candidate", "stellen")
                                    except sqlite3.IntegrityError:
                                        ui.notify(_('Sie haben sich bereits auf diese Stelle beworben.'), type="negative")
                                        dialog.close()
                                    except Exception as ex:
                                        ui.notify(_('Fehler: {0}').format(ex), type="negative")
                                ui.button(_('Erneut bewerben') if zurueckgezogen else _('Jetzt bewerben'),
                                          icon="send", on_click=_submit).classes(C.BTN_PRIMARY)
                        dialog.open()

                    if cv_ok:
                        ui.button(_('Bewerben'), icon="send", on_click=_open_apply_dialog).classes(C.BTN_PRIMARY)
                    else:
                        with ui.button(_('🔒 Lebenslauf nötig'), icon="lock").props("disable").classes(C.BTN_PRIMARY):
                            ui.tooltip(_('Bitte zuerst Lebenslauf hochladen (Mein Profil → Lebenslauf)'))

            # Details: klappbar (Option B: Card + ui.expansion)
            with ui.expansion(text=_('Details anzeigen'), icon="expand_more").classes("w-full"):
                if score is not None:
                    score_bar(score)
                # Feature G (iii) (Spec matching-criteria.md §5, GO 24.09.2026):
                # „Warum passt das?" = 7 erklaerung-Einträge (Pattern employer.py:829-832)
                # + Disclaimer (Startgewichte/Feedback-Loop) + explain-match-Hinweis.
                if score is not None and result and result.get("erklaerung"):
                    with ui.expansion(_('Warum passt das?'), icon="help_outline").classes("w-full mt-1"):
                        for _key, _text in result["erklaerung"].items():
                            ui.label(_('- {0}: {1}').format(_key, _text)).classes("text-xs text-gray-600")
                        ui.label(
                            _('Score aus Startgewichten (Design-Entscheidung, keine externe Quelle) — Gewichte werden per Feedback-Loop nach echten Einstellungsentscheidungen kalibriert (siehe matching-criteria.md).')
                        ).classes("text-xs text-gray-500 mt-2")
                        ui.label(
                            _('Detailbegründung: agent-generierte Erklärung nach Ihrer Bewerbung (Skill explain-match).')
                        ).classes("text-xs text-gray-500")
                # 3-Spalten-Layout (wie Streamlit app.py:3310-3323)
                with ui.grid(columns=3).classes("w-full gap-4 mt-3"):
                    with ui.column():
                        info_row(_('Firma'), e_firma, icon="business")
                        info_row(_('Branche'), e_branche or "–", icon="category")
                        info_row(_('Groesse'), e_groesse or "–", icon="group")
                    with ui.column():
                        info_row(_('Standort'), j_ort, icon="location_on")
                        info_row(_('Stellentyp'), j_typ, icon="work")
                    with ui.column():
                        info_row(_('Gehalt'), gehalt_txt, icon="euro")
                        info_row(_('Erfahrung'), _('min. {0} Jahre').format(j_erf or 0), icon="schedule")
                        info_row(_('Deutsch'), j_de, icon="translate")

                # Beschreibung + Skills
                ui.separator().classes("my-2")
                info_row(_('Beschreibung'), j_beschr, icon="description")
                if j_hard:
                    with ui.row().classes("items-center gap-1 mt-2"):
                        ui.label(_('Must-Have-Skills:')).classes("font-medium")
                        for skill in (j_hard or "").split(","):
                            skill_chip(skill.strip())
                if j_soft:
                    with ui.row().classes("items-center gap-1 mt-2"):
                        ui.label(_('Soft Skills:')).classes("font-medium")
                        for skill in (j_soft or "").split(","):
                            skill_chip(skill.strip(), color="teal")


# ─── Tab 4: Meine Bewerbungen ────────────────────────────────────────

def _tab_bewerbungen(s: dict) -> None:
    section_header(title=_('Meine Bewerbungen'), subtitle=_('Status verfolgen'), icon="send")

    @ui.refreshable
    def bewerbungen_list():
        try:
            conn = db.get_conn()
            bewerbungen = conn.execute(
                """SELECT a.id, a.job_id, j.titel, e.firma, a.status,
                          a.erstellungsdatum, a.aktualisiert_am, a.bewerbungstext
                   FROM applications a
                   JOIN jobs j ON a.job_id = j.id
                   JOIN employers e ON j.employer_id = e.id
                   WHERE a.candidate_id = ? ORDER BY a.erstellungsdatum DESC""",
                (s["user_cand_id"],),
            ).fetchall()
            conn.close()

            if not bewerbungen:
                empty_state(
                    icon="send",
                    title=_('Keine Bewerbungen vorhanden'),
                    description=_("Bewerbe dich im Tab 'Stellenangebote'."),
                    action_label=_('Stellen durchsuchen'),
                    on_action=lambda: navigate_to("candidate", "stellen"),
                )
                return

            for b_id, b_job_id, b_titel, b_firma, b_status, b_erstellt, b_akt, b_text in bewerbungen:
                icon = STATUS_ICONS.get(b_status, "📨")
                with ui.card().classes(C.CARD_HOVER + " w-full mb-3"):
                    with ui.row().classes("items-center justify-between w-full"):
                        with ui.row().classes("items-center gap-3"):
                            ui.label(icon).classes("text-lg")
                            with ui.column().classes("gap-0"):
                                ui.label(_('{0} – {1}').format(b_titel, b_firma)).classes(C.CARD_TITLE)
                                with ui.row().classes("items-center gap-2"):
                                    status_badge(b_status)
                                    ui.label(_('#{0}').format(b_id)).classes(C.MUTED)

                    # R6-4 (30.09.2026): Nur AKTIVE Status duerfen den
                    # Zurückziehen-Button zeigen (vorher Blacklist liess auch
                    # 'abgelehnt' zu). Finale Status: abgelehnt/eingestellt/
                    # zurückgezogen — dort gibt es nichts mehr zu ziehen.
                    if b_status in ("eingegangen", "angesehen", "eingeladen"):
                        def _withdraw(a_id=b_id):
                            conn_w = db.get_conn()
                            conn_w.execute(
                                "UPDATE applications SET status='zurückgezogen', "
                                "aktualisiert_am=CURRENT_TIMESTAMP WHERE id=? AND candidate_id=?",
                                (a_id, s["user_cand_id"]),
                            )
                            conn_w.execute(
                                "INSERT INTO application_status_history "
                                "(application_id, status, changed_by) VALUES (?, 'zurückgezogen', 'kandidat')",
                                (a_id,),
                            )
                            conn_w.commit()
                            conn_w.close()
                            ui.notify(
                                _('Bewerbung zurückgezogen. Sie können sich später erneut bewerben.'), type="info",
                            )
                            bewerbungen_list.refresh()

                        def _ask_withdraw(a_id=b_id):
                            from webui.components import confirm_dialog
                            confirm_dialog(
                                _("Bewerbung zurückziehen?"),
                                _('Der Status wird auf „Zurückgezogen" gesetzt. Diese Aktion kann nicht rückgängig gemacht werden.'),
                                on_confirm=lambda: _withdraw(a_id=a_id),
                            )

                        ui.button(_('↩️ Zurückziehen'), on_click=_ask_withdraw).classes(C.BTN_SECONDARY + " text-xs")

                    with ui.column().classes("mt-3 gap-2"):
                        with ui.row().classes("items-center gap-4"):
                            if b_erstellt:
                                info_row(_('Beworben am'), b_erstellt[:10], icon="calendar_today")
                            if b_akt:
                                info_row(_('Letzte Änderung'), b_akt[:10], icon="update")

                        if b_text:
                            ui.label(_('Motivation:')).classes(C.SMALL + " font-medium mt-2")
                            ui.label(b_text).classes(C.BODY + " italic")

                        if b_status == "eingeladen":
                            artifacts = db.get_invitation_artifacts(b_id)
                            if artifacts:
                                with ui.card().classes("bg-blue-50 border border-blue-200 p-4 mt-2"):
                                    ui.label(_('📅 Einladung')).classes("font-medium text-blue-800")
                                    # P0 (28.09.2026): Termin sichtbar. Das Task-ERGEBNIS
                                    # fuehrt den Termin als "termin" (Text) bzw. als
                                    # "termin_datum"+"termin_uhrzeit" (Payload) — vorher
                                    # wurde nur nach den Payload-Schluesseln gesucht,
                                    # deshalb blieb die Karte ohne Datum
                                    # (Beleg: messung-vorher.json, employer/candidate
                                    # ohne Flag 'termin-mit-zeit-sichtbar').
                                    _termin = artifacts.get("termin")
                                    if not _termin:
                                        _d = artifacts.get("termin_datum")
                                        _z = artifacts.get("termin_uhrzeit", "")
                                        if _d:
                                            _termin = f"{_d} {_z}".strip()
                                    if _termin:
                                        ui.label(_('Termin: {0}').format(_termin)).classes(
                                            "text-base font-bold text-blue-900 mt-1")
                                    else:
                                        ui.label(_('Termin wird noch vereinbart.')).classes(
                                            "text-sm text-amber-800 mt-1")
                                    # Meeting-Link (VDO.Ninja seit 27.09.2026); `jitsi_url` ist
                                    # der Legacy-Schlüssel fuer bereits erzeugte Einladungen.
                                    _meet = (artifacts.get("vdo_ninja_gast_url")   # Gate 8 (seit 28.09.2026)
                                             or artifacts.get("vdo_ninja_url")
                                             or artifacts.get("jitsi_url"))
                                    if _meet:
                                        with ui.row().classes("items-center gap-2 mt-1 items-start"):
                                            ui.icon("videocam", size="sm").classes("text-blue-600 mt-3")
                                            # Klartext statt Rohlink (UI-Regel 28.09.2026).
                                            # readonly ist KEIN ui.input-Parameter (erzeugte
                                            # TypeError und riss den Rest der Karte ab —
                                            # Link und ICS-Button fehlten) → .props().
                                            ui.input(label=_('Meeting-Link'), value=_meet).classes(
                                                "w-full text-sm").props("readonly outlined dense")
                                    # N1-Port (app.py:502-520): ICS-Download für den Kandidaten-Kalender
                                    _ics = artifacts.get("ics_path")
                                    if _ics and Path(str(_ics)).exists():
                                        def _dl_ics(_p=str(_ics), _n=Path(str(_ics)).name):
                                            ui.download(_p, _n, "text/calendar")
                                        ui.button(_('📅 Termin in Kalender speichern (.ics)'),
                                                  icon="event", on_click=_dl_ics).classes("bg-blue-50 text-blue-700 mt-1")
                            else:
                                ui.label(_('⏳ Einladung wird vorbereitet...')).classes(C.MUTED + " mt-2")

                        # Status-Historie
                        conn_h = db.get_conn()
                        historie = conn_h.execute(
                            "SELECT status, changed_at FROM application_status_history "
                            "WHERE application_id = ? ORDER BY changed_at",
                            (b_id,),
                        ).fetchall()
                        conn_h.close()

                        if historie:
                            items = []
                            for h_status, h_date in historie:
                                h_icon = STATUS_ICONS.get(h_status, "📄")
                                items.append({
                                    "title": f"{h_icon} {status_label(h_status)}",
                                    "status": "done" if h_status in ("eingestellt", "abgelehnt", "zurückgezogen") else "active",
                                    "date": h_date[:10] if h_date else "",
                                })
                            with ui.expansion(_('📋 Status-Historie')):
                                timeline(items)
        except Exception as ex:
            # R5-1 (30.09.2026): nie wieder stumm — dieser Block hat den
            # STATUS_ICONS-NameError verschwiegen (Tab wirkte leer).
            _log.exception("bewerbungen_list fehlgeschlagen: %s", ex)
            ui.label(_('⚠️ Bewerbungen konnten nicht geladen werden. Fehler: {0}').format(ex)).classes("text-red-600")
            ui.button(_('Erneut versuchen'), on_click=bewerbungen_list.refresh)

    bewerbungen_list()
    ui.timer(interval=15.0, callback=bewerbungen_list.refresh)


# ─── Tab 4: Dokumente ──────────────────────────────────────────────

def _dokumente_section(s: dict) -> None:
    cand_id = s["user_cand_id"]
    _doc_typen = ["Zeugnis", "Zertifikat", "Sprachzeugnis", "Pass", "Visum/Aufenthaltstitel", "Sonstiges"]
    doc_typ = ui.select(options={v: _(v) for v in _doc_typen}, value=_doc_typen[0], label=_('Dokumenttyp')).classes("w-full mb-4")

    async def on_multi_upload(e):
        _typ_slug = re.sub(r"[^A-Za-z]+", "-", doc_typ.value).strip("-")
        # P1-11 (30.09.2026): `insert_document` liefert False bei Fehler; das wurde
        # ignoriert und es wurde pauschal "gespeichert" gemeldet — auch wenn KEIN
        # Dokument in der DB landete. Jetzt je Datei zaehlen und ehrlich melden.
        ok_liste, fehler_liste = [], []
        try:
            for file in e.files:
                _clean = logic.safe_upload_name(file.name)
                # R5-2/S3c: serverseitige Endungsprüfung + accept-Filter
                if not _clean.lower().endswith((".pdf", ".txt", ".webm", ".mp4")):
                    fehler_liste.append(_('{0} (nur .pdf/.txt/.webm/.mp4)').format(file.name))
                    continue
                _path = db.BASE_DIR / "testdaten" / f"kandidat-{cand_id}-{_typ_slug}-{_clean}"
                _path.write_bytes(await file.read())
                if db.insert_document(cand_id, str(_path), doc_typ.value):
                    ok_liste.append(file.name)
                else:
                    fehler_liste.append(file.name)
        except Exception as ex:
            ui.notify(_('Fehler beim Hochladen: {0}').format(ex), type="negative")
            refresh_docs()
            return

        if ok_liste:
            ui.notify(
                _("{0} Dokument(e) gespeichert als Typ '{1}'.").format(len(ok_liste), _(doc_typ.value)),
                type="positive",
            )
        if fehler_liste:
            ui.notify(
                _('❌ {0} Dokument(e) konnten NICHT gespeichert werden: {1}{2} — bitte erneut versuchen oder Administrator kontaktieren.').format(
                    len(fehler_liste), ', '.join(fehler_liste[:3]),
                    " …" if len(fehler_liste) > 3 else ""),
                type="negative",
            )
        refresh_docs()

    ui.upload(label=_('Dokumente (PDF/TXT/Video, mehrere moeglich):'), on_multi_upload=on_multi_upload,
              multiple=True, auto_upload=True, max_file_size=150_000_000).props('accept=".pdf,.txt,.webm,.mp4"').classes("w-full mb-4")
    docs_container = ui.column().classes("w-full")

    def refresh_docs():
        docs_container.clear()
        with docs_container:
            docs = db.get_documents(cand_id)
            if not docs:
                empty_state(icon="folder_off", title=_('Noch keine Dokumente hochgeladen'))
                return
            ui.label(_('Meine Dokumente ({0})').format(len(docs))).classes(C.CARD_TITLE + " mb-3")
            for d_id, d_typ, d_pfad, d_dat in docs:
                with ui.card().classes(C.CARD_HOVER + " w-full mb-2 py-2"):
                    with ui.row().classes("items-center justify-between w-full px-4"):
                        with ui.row().classes("items-center gap-3"):
                            ui.icon("description").classes("text-blue-500")
                            with ui.column():
                                ui.label(_(d_typ)).classes("font-medium")
                                ui.label(d_pfad.split("/")[-1] if "/" in d_pfad else d_pfad).classes(C.MUTED)
                        with ui.row().classes("items-center gap-2"):
                            if d_dat:
                                ui.label(str(d_dat)[:10]).classes(C.MUTED)

                            def delete_doc(_did=d_id, _dpfad=d_pfad):
                                from pathlib import Path as _P
                                try:
                                    _P(_dpfad).unlink(missing_ok=True)
                                except Exception as ex:
                                    # R5-1: Datei-Fehler loggen, DB-Delete läuft
                                    # weiter (Datensatz soll trotzdem weg)
                                    _log.warning("unlink fehlgeschlagen (%s): %s", _dpfad, ex)
                                db.delete_document(_did, cand_id)
                                ui.notify(_('Dokument geloescht.'), type="warning")
                                refresh_docs()

                            def _ask_delete(_did=d_id, _dpfad=d_pfad):
                                from webui.components import confirm_dialog
                                confirm_dialog(
                                    _("Dokument löschen?"),
                                    _("Diese Datei wird vom Server entfernt. Dies kann nicht rückgängig gemacht werden."),
                                    on_confirm=lambda: delete_doc(_did=_did, _dpfad=_dpfad),
                                )

                            # P0 (28.09.2026): color=red = #F44336 auf weiss →
                            # 3.68:1. negative (#B91C1C) liefert 6.47:1.
                            ui.button(icon="delete", on_click=_ask_delete).props("flat color=negative dense")

    refresh_docs()


# ─── Selbstpräsentation-Datei: Video-Abschnitt (A4, 30.09.2026) ──────
# Beide Tabs schreiben dieselbe Datei ergebnisse/self-presentation-kandidat-{id}-{datum}.md:
# Pre-Screen (Meeting-Raum + Leitfragen) und Sprachtest-Tab (Abschnitt "## Video-Vorstellung").
# Befund: start_prescreen schrieb die Tagesdatei komplett neu und löschte dabei den
# Video-Abschnitt (bzw. legte an einem neuen Tag eine Datei OHNE Abschnitt an, sodass
# der Link-Lookup über die neueste Datei ihn nicht mehr fand). Fix: Abschnitt beim
# Schreiben mergen. Reine Funktionen (Verzeichnis als Parameter) → testbar ohne UI.

VIDEO_HEADING = "## Video-Vorstellung"


def video_section_md(video_url: str) -> str:
    return (
        f"{VIDEO_HEADING}\n\n"
        + _("- **Link:** [{0}]({1})").format(video_url, video_url) + "\n"
        + _("- **Sichtbarkeit:** HR sieht den Link im Recruiting-Modus ohne Status-Gate (zur Bewertung vor der Übernahme).") + "\n\n"
    )


def self_presentation_files(ergebnisse: Path, cand_id) -> list:
    """Alle Selbstpräsentations-Dateien des Kandidaten, älteste zuerst (Datum im Namen)."""
    return sorted(Path(ergebnisse).glob(f"self-presentation-kandidat-{cand_id}-*.md"))


def extract_video_section(text: str) -> str:
    """Liefert den Abschnitt '## Video-Vorstellung' (bis zur nächsten '## '-Überschrift/EOF), sonst ''."""
    i = (text or "").find(VIDEO_HEADING)
    if i < 0:
        return ""
    ende = text.find("\n## ", i + len(VIDEO_HEADING))
    abschnitt = text[i:] if ende < 0 else text[i:ende]
    return abschnitt.rstrip() + "\n\n"


def find_video_section(ergebnisse: Path, cand_id) -> str:
    """Neuester vorhandener Video-Abschnitt über alle Dateien des Kandidaten ('' = keiner)."""
    for p in reversed(self_presentation_files(ergebnisse, cand_id)):
        abschnitt = extract_video_section(p.read_text(encoding="utf-8", errors="replace"))
        if abschnitt:
            return abschnitt
    return ""


def load_video_link(ergebnisse: Path, cand_id):
    import re
    abschnitt = find_video_section(ergebnisse, cand_id)
    m = re.search(r"https://vdo\.ninja/\?[^\s)\]]+", abschnitt) if abschnitt else None
    return m.group(0) if m else None


def write_prescreen_md(ergebnisse: Path, cand_id, filename: str, md: str) -> str:
    """Schreibt die Pre-Screen-Datei und übernimmt einen vorhandenen Video-Abschnitt.

    Rückgabe: der tatsächlich geschriebene Text (inkl. gemergtem Abschnitt).
    """
    if VIDEO_HEADING not in md:
        vorhanden = find_video_section(ergebnisse, cand_id)
        if vorhanden:
            md = md.rstrip() + "\n\n" + vorhanden
    (Path(ergebnisse) / filename).write_text(md, encoding="utf-8")
    return md


def persist_video_link(ergebnisse: Path, cand_id, video_url: str, now=None) -> Path:
    """Schreibt/ersetzt den Video-Abschnitt in der neuesten Selbstpräsentations-Datei."""
    from datetime import datetime
    now = now or datetime.now()
    dateien = self_presentation_files(ergebnisse, cand_id)
    if dateien:
        p = dateien[-1]
        head = p.read_text(encoding="utf-8", errors="replace") \
            .split(VIDEO_HEADING)[0].rstrip() + "\n\n"
    else:
        p = Path(ergebnisse) / f"self-presentation-kandidat-{cand_id}-{now.strftime('%Y-%m-%d')}.md"
        head = (
            _("# Selbstpräsentation: Kandidat #{0}").format(cand_id) + "\n\n"
            + _("**Datum:** {0}").format(now.strftime('%d.%m.%Y')) + "\n\n"
            + _("## Ihr Meeting-Raum") + "\n\n"
            + _("- Noch kein Raum generiert (Tab 📹 Pre-Screen).") + "\n\n"
        )
    p.write_text(head + video_section_md(video_url), encoding="utf-8")
    return p


# ─── Tab 5: Pre-Screen (Selbstpräsentation) ─────────────────────────

def _tab_prescreen(s: dict) -> None:
    section_header(title=_('Pre-Screen'), subtitle=_('Selbstpräsentation'), icon="videocam")
    cand_id = s["user_cand_id"]

    conn = db.get_conn()
    profil = conn.execute(
        "SELECT name, hard_skills, soft_skills, berufserfahrung_jahre, status FROM candidates WHERE id = ?",
        (cand_id,),
    ).fetchone()
    conn.close()

    if not profil:
        empty_state(icon="person_off", title=_('Profil nicht gefunden'))
        return

    name, skills, soft, jahre, status = profil

    # Check non-application related status (CV upload, profil geprueft, match berechnet)
    non_app_allowed = status in ("lebenslauf_hochgeladen", "profil_geprueft", "match_berechnet")
    # Check application related status: any application with eingeladen or eingestellt
    conn = db.get_conn()
    app_allowed = conn.execute(
        "SELECT 1 FROM applications WHERE candidate_id = ? AND status IN ('eingeladen', 'eingestellt') LIMIT 1",
        (s["user_cand_id"],),
    ).fetchone() is not None
    conn.close()

    if not (non_app_allowed or app_allowed):
        # C7 (22.09.2026): ui.warning existiert NICHT in NiceGUI 3.17.1
        # (Verifikation) und ui.notify wäre nur Toast → persistente Zeile
        # (Parität zu st.warning app.py:2204, sichtbar bis Tab-Wechsel).
        # P1-2 (29.09.2026, Nutzer-GO): klickbarer Weg zum Upload statt Sackgasse
        # (Plan ui-mvp-plan-v2 §6 P1-2; Spec: knowledge/portal/cv-pflicht.md).
        with ui.column().classes("gap-2 items-start"):
            ui.label(
                _('⚠️ CV-Pflicht: Laden Sie zuerst Ihren Lebenslauf hoch (Status: {0})').format(status_label(status))
            ).classes(C.BODY + " text-amber-600")
            ui.button(_('→ Zum Lebenslauf-Upload'), icon="cloud_upload",
                      on_click=lambda: navigate_to("candidate", "profil"))
        return

    ui.label(_('Profil: {0} · Skills: {1}').format(name, skills or '–')).classes(C.BODY + " mb-4")

    # A4 (30.09.2026): Video-Link liegt im Tab Sprachtest (dort generiert) — Hinweis + Sprung,
    # damit Kandidaten die optionale Video-Vorstellung im Pre-Screen finden.
    with ui.row().classes("items-center gap-3 mb-4"):
        if load_video_link(db.BASE_DIR / "ergebnisse", cand_id):
            ui.label(_('✅ Video-Vorstellung bereits hinterlegt.')).classes(C.SMALL)
        else:
            ui.label(_('🎬 Optional: Sie können eine Video-Vorstellung (2–3 Minuten) hinterlegen.')).classes(C.SMALL)
        ui.button(_('→ Zur Video-Vorstellung'), icon="movie",
                  on_click=lambda: navigate_to("candidate", "sprachtest")).props("flat")

    prescreen_container = ui.column().classes("w-full")

    def start_prescreen():
        import random, string
        room_code = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
        room_name = f"self-presentation-{room_code}"
        # VDO.Ninja statt Jitsi (27.09.2026, Spec: knowledge/system/vdo-ninja-migration.md).
        # Fix 03.10.2026 (Spec §2.3): Selbstpräsentation = SOLO-SENDER -> `?push=` (NICHT
        # `?director=`; der Regieraum sendet kein eigenes Bild). Offizielle Doku:
        # docs.vdo.ninja (Solo-Selbstpräsentation = `&push`).
        # Kein Aufnahme-Parameter (`&record`) – erst nach dokumentierter Einwilligung
        # (knowledge/legal/recording-consent.md (i) Punkt 8).
        meet_url = f"https://vdo.ninja/?push={room_name}&record=6000"

        eigene_fragen = []
        if skills:
            for sk in [x.strip() for x in skills.split(",") if x.strip()][:4]:
                eigene_fragen.append(("Technisch", _("Beschreiben Sie ein konkretes Projekt mit {0}. Welche Ergebnisse wurden erzielt?").format(sk)))
        if soft:
            for sk in [x.strip() for x in soft.split(",") if x.strip()][:2]:
                eigene_fragen.append(("Soft Skills", _("Geben Sie ein Beispiel, das Ihre Stärke in '{0}' zeigt.").format(sk)))
        eigene_fragen.append(("Motivation", _("Welche Rolle suchen Sie und warum?")))
        eigene_fragen.append(("Praktisch", _("Wann könnten Sie starten? Wie ist Ihre Gehaltsvorstellung?")))

        from datetime import datetime
        md = _("# Selbstpräsentation: Kandidat #{0}").format(cand_id) + "\n\n"
        md += _("**Modus:** Selbstpräsentation (CANDIDATE-Session)") + "\n"
        md += _("**Datum:** {0}").format(datetime.now().strftime('%d.%m.%Y')) + "\n\n"
        md += _("## Ihr Meeting-Raum") + "\n\n"
        md += _("- **Link:** [{0}]({1})").format(meet_url, meet_url) + "\n"
        md += _("- **Empfehlung:** 3–5 Minuten, Start mit Kurzvorstellung, dann die Fragen unten beantworten.") + "\n\n"
        md += _("## Ihre Leitfragen") + "\n\n"
        for i, (kat, frage) in enumerate(eigene_fragen, 1):
            md += f"{i}. **[{_(kat)}]** {frage}\n"
        md += "\n" + _("*Erstellt am {0} vom KM-HR-Agenten.*").format(datetime.now().strftime('%d.%m.%Y %H:%M')) + "\n"

        filename = f"self-presentation-kandidat-{cand_id}-{datetime.now().strftime('%Y-%m-%d')}.md"
        # A4 (30.09.2026): vorhandenen "## Video-Vorstellung"-Abschnitt beim Schreiben
        # übernehmen (früher: Datei komplett neu → Link weg). Rückgabe = geschriebener Text.
        md = write_prescreen_md(db.BASE_DIR / "ergebnisse", cand_id, filename, md)

        prescreen_container.clear()
        with prescreen_container:
            with ui.card().classes(C.CARD + " w-full"):
                ui.label(_('Ihr Raum ist bereit!')).classes(C.CARD_TITLE)
                ui.markdown(_('**Link:** [{0}]({1})').format(meet_url, meet_url)).classes(C.BODY)
                ui.markdown(md).classes(C.BODY + " mt-4")
                ui.button(_('📥 Herunterladen'),
                          on_click=lambda: ui.download(md.encode("utf-8"), filename, "text/markdown")).classes(C.BTN_PRIMARY + " mt-4")

    ui.button(_('📹 Selbstpräsentation starten'), on_click=start_prescreen).classes(C.BTN_PRIMARY + " mt-4")


# ─── Tab: Sprachtest ─────────────────────────────────────────────────

def score_answers(fragen: list, antworten: dict) -> tuple:
    """Bewertet einen Sprachtest (reine Funktion, ohne UI/DB).

    fragen:    Liste von Frage-Dicts des MCP-Servers language-test
               ({"antworten": [Text, ...], "loesung": "a".."d", "id": ...}).
    antworten: {Frage-Index: Auswahl}; Auswahl ist der Index der gewählten
               Option (int, so liefert die UI) ODER der Optionstext (str).
               Fehlt ein Index, gilt die Frage als NICHT beantwortet.

    Rückgabe: (punkte, details) — punkte = Anzahl richtiger Antworten,
    details = Liste {"frage_id", "antwort", "korrekt"}.

    Regeln (Design-Entscheidung, keine externe Quelle):
    - Vergleich Buchstabe der gewählten Option ("abcd"[Index]) == loesung.
    - Nicht beantwortet oder Frage ohne Lösung → nie korrekt (verhindert
      "" == "" als Treffer).
    """
    punkte = 0
    details = []
    for i, frage in enumerate(fragen):
        optionen = frage.get("antworten") or []
        auswahl = antworten.get(i)
        opt_idx = None
        if isinstance(auswahl, int) and not isinstance(auswahl, bool):
            if 0 <= auswahl < len(optionen):
                opt_idx = auswahl
        elif isinstance(auswahl, str) and auswahl in optionen:
            opt_idx = optionen.index(auswahl)
        buchstabe = "abcd"[opt_idx] if opt_idx is not None and opt_idx < 4 else ""
        loesung = str(frage.get("loesung") or "").strip().lower()
        korrekt = bool(buchstabe) and bool(loesung) and buchstabe == loesung
        if korrekt:
            punkte += 1
        details.append({
            "frage_id": frage.get("id"),
            "antwort": optionen[opt_idx] if opt_idx is not None else "",
            "korrekt": korrekt,
        })
    return punkte, details


def filter_valid_questions(fragen: list) -> list:
    """Filtert unbrauchbare Fragen aus der Server-Antwort (reine Funktion).

    Anlass (30.09.2026, Beweis tests/test_language_scoring.py): Der MCP-Server
    liefert für Französisch A1 gelegentlich eine LLM-Platzhalterfrage
    ({"id": "ID", "frage": "Frage", "loesung": "lösung", ...}) — sie wäre nie
    korrekt beantwortbar und würde den Score verfälschen.

    Gültig = Fragetext nicht leer/kein Vorlagen-Echo, >= 2 nichtleere Optionen,
    Lösung a–d und auf eine vorhandene Option zeigend.
    Design-Entscheidung (keine externe Quelle).
    """
    gueltig = []
    for q in fragen or []:
        if not isinstance(q, dict):
            continue
        text = str(q.get("frage") or "").strip()
        optionen = q.get("antworten") or []
        loesung = str(q.get("loesung") or "").strip().lower()
        if not text or text == "Frage" or q.get("id") == "ID":
            continue
        if sum(1 for o in optionen if str(o).strip()) < 2:
            continue
        if loesung not in ("a", "b", "c", "d") or "abcd".index(loesung) >= len(optionen):
            continue
        gueltig.append(q)
    return gueltig


def _tab_sprachtest(s: dict) -> None:
    section_header(title=_('Sprachtest'), subtitle=_('CEFR-Niveautests'), icon="translate")
    # C4 (22.09.2026): Session-Caption 1:1 aus Streamlit (app.py:2925-2926)
    ui.label(_('🔒 Session-gebunden: Testen Sie Ihr Sprachniveau (DE/EN/FR). Ergebnis landet in Ihrem Profil (CEFR-Level).')).classes(C.MUTED)

    # A1.3 (30.09.2026): Liste ist @ui.refreshable und wird nach erfolgreichem
    # Speichern eines Tests aktualisiert (vorher: einmalig beim Tab-Aufbau).
    @ui.refreshable
    def ergebnisse_liste():
        conn = db.get_conn()
        # C4: LIMIT 5 + test_datum DESC wie Streamlit (app.py:2945)
        tests = conn.execute(
            "SELECT sprache, niveau, punkte, cefr_level, test_datum FROM language_tests WHERE candidate_id = ? ORDER BY test_datum DESC, id DESC LIMIT 5",
            (s["user_cand_id"],),
        ).fetchall()
        conn.close()

        if not tests:
            return
        ui.label(_('Deine Ergebnisse')).classes(C.CARD_TITLE + " mb-3")
        with ui.grid(columns=3).classes("w-full gap-3 mb-6"):
            for sprache, niveau, punkte, cefr_level, datum in tests:
                with ui.card().classes(C.CARD + " py-3"):
                    ui.label(_('{0} {1}').format(_(sprache), niveau)).classes("font-medium")
                    # C4: Prozent wie Streamlit (app.py:2950 {t[2]*100:.0f}%)
                    ui.label(_('Score: {0:.0f}%').format((punkte or 0) * 100)).classes(C.BODY)
                    ui.label(_('CEFR: {0}').format(cefr_level)).classes(C.SMALL)
                    if datum:
                        ui.label(str(datum)[:10] if len(str(datum)) > 10 else datum).classes(C.MUTED)

    ergebnisse_liste()

    # Start new test
    ui.label(_('Neuen Test starten')).classes(C.CARD_TITLE + " mt-4 mb-3")

    # Test state
    test_state = {
        "active": False,
        "sprache": "Deutsch",
        "niveau": "A1",
        "anzahl": 10,
        "fragen": [],
        "antworten": {},
        "idx": 0,
        "fertig": False,
    }

    test_container = ui.column().classes("w-full")

    def _show_error(text: str) -> None:
        """Sichtbare Fehlerkarte im test_container inkl. Retry (A1.1/A1.2)."""
        test_state.update(active=False, fragen=[], antworten={}, idx=0, fertig=False)
        test_container.clear()
        with test_container:
            with ui.card().classes(C.CARD + " w-full"):
                ui.label(_('⚠️ {0}').format(text)).classes(C.BODY + " text-red-600")
                ui.button(_('Erneut versuchen'), icon="refresh",
                          on_click=start_test).classes(C.BTN_PRIMARY + " mt-4")

    def start_test():
        test_container.clear()
        with test_container:
            with ui.card().classes(C.CARD + " w-full"):
                ui.label(_('Test wird geladen...')).classes(C.BODY)
                ui.spinner(size="lg")

                async def load_questions():
                    try:
                        import importlib.util as _ilu
                        from fastmcp import Client as _MCPClient
                        _spec = _ilu.spec_from_file_location(
                            "language_test_server",
                            str(db.BASE_DIR / "scripts" / "language-test-server.py"),
                        )
                        _mod = _ilu.module_from_spec(_spec)
                        # P2 (Spec: knowledge/system/event-loop-blockieren.md):
                        # Modul-Laden (importlib, inkl. fastmcp-Import) vom
                        # Event-Loop entkoppeln (NiceGUI-FAQ run.io_bound).
                        await run.io_bound(_spec.loader.exec_module, _mod)

                        async with _MCPClient(_mod.mcp) as _cli:
                            _res = await _cli.call_tool(
                                "generate_test",
                                {
                                    "sprache": test_state["sprache"],
                                    "niv": test_state["niveau"],
                                    "anzahl": test_state["anzahl"],
                                },
                            )
                            import json as _j
                            data = _j.loads(_res.data)
                            fragen_geladen = filter_valid_questions(data.get("fragen") or [])
                            if not fragen_geladen:
                                # A1.1: 0 Fragen → nichts speichern, sichtbare Fehlerkarte
                                _show_error(
                                    _('Für {0} {1} konnten keine Fragen geladen werden.').format(test_state['sprache'], test_state['niveau']))
                                return
                            test_state["fragen"] = fragen_geladen
                            test_state["active"] = True
                            test_state["idx"] = 0
                            test_state["antworten"] = {}
                            test_state["fertig"] = False
                            render_question()
                    except Exception as e:
                        # A1.1: ui.notify allein reicht nicht (Container wäre leer)
                        _show_error(_('Fehler beim Laden der Fragen: {0}').format(e))

                # A1 (30.09.2026): background_tasks.create hält eine STARKE Referenz auf den
                # Task. asyncio.ensure_future() ohne Referenz kann mitten im await vom GC
                # eingesammelt werden (Python-Doku zu create_task) → "Test wird geladen…"
                # blieb intermittierend für immer stehen (E2E: ~1 von 4 Läufen).
                background_tasks.create(load_questions(), name="sprachtest-load-questions")

    def render_question():
        test_container.clear()
        with test_container:
            if test_state["fertig"]:
                show_results()
                return

            idx = test_state["idx"]
            fragen = test_state["fragen"]

            if idx >= len(fragen):
                show_results()
                return

            frage = fragen[idx]
            with ui.card().classes(C.CARD + " w-full"):
                ui.label(_('{0} {1}').format(test_state['sprache'], test_state['niveau'])).classes(C.CARD_TITLE)
                ui.label(_('Frage {0}/{1}').format(idx + 1, len(fragen))).classes(C.MUTED)
                ui.label(frage.get("frage", "?")).classes(C.BODY + " mt-4")

                antworten = frage.get("antworten", [])
                selected = {"value": None}

                # next_button wird erst unten zugewiesen (Closure); on_select feuert
                # nur bei Nutzerauswahl (Radio startet ohne Vorauswahl), also nach der
                # Zuweisung — kein NameError (A1.4, im E2E belegt).
                def on_select(e, sel=selected):
                    sel["value"] = e.value
                    next_button.enable()

                # Optionen als {Index: Text}: Wert = Index → auch bei doppelten
                # Optionstexten eindeutig; Buchstabe ergibt sich aus dem Index.
                ui.radio({i: t for i, t in enumerate(antworten)},
                         on_change=on_select).classes("mt-4")

                def next_question():
                    if selected["value"] is None:
                        ui.notify(_('Bitte wähle eine Antwort'), type="warning")
                        return
                    test_state["antworten"][idx] = selected["value"]
                    test_state["idx"] = idx + 1
                    if test_state["idx"] >= len(fragen):
                        test_state["fertig"] = True
                    render_question()

                next_button = ui.button(_('Weiter →'), on_click=next_question).classes(C.BTN_PRIMARY + " mt-4")
                next_button.disable()

    def show_results():
        test_container.clear()
        with test_container:
            fragen = test_state["fragen"]
            antworten = test_state["antworten"]

            # A1.1: nie einen Test ohne Fragen bewerten/speichern
            if not fragen:
                _show_error(_('Der Test enthält keine Fragen und wurde nicht gespeichert.'))
                return

            # Scoring: reine Funktion score_answers() (Modulebene, getestet)
            gesamtpunkte, details = score_answers(fragen, antworten)

            # CEFR-Level via MCP-Server (eine Quelle der Wahrheit, Refactor 20.09.2026)
            avg = gesamtpunkte / len(fragen)
            _cefr = logic.cefr_from_avg(avg)
            cefr = _cefr["level"]

            # DB speichern (A1.2: Rückgabe None = Speichern fehlgeschlagen)
            import json as _json
            row_id = db.insert_language_test(
                candidate_id=s["user_cand_id"],
                sprache=test_state["sprache"],
                niveau=test_state["niveau"],
                fragen_anzahl=len(fragen),
                punkte=avg,
                cefr_level=cefr,
                details=_json.dumps(details, ensure_ascii=False),
            )
            if row_id is None:
                with ui.card().classes(C.CARD + " w-full"):
                    ui.label(_('⚠️ Ergebnis konnte nicht gespeichert werden.')).classes(
                        C.BODY + " text-red-600")
                    ui.label(_('Ihr Ergebnis: {0}/{1} richtig ({2:.0f}%, CEFR {3}) — nicht in Ihrem Profil hinterlegt.').format(gesamtpunkte, len(fragen), avg * 100, cefr)).classes(C.SMALL + " mt-2")
                    with ui.row().classes("gap-2 mt-4"):
                        ui.button(_('Erneut speichern'), icon="save",
                                  on_click=show_results).classes(C.BTN_PRIMARY)
                        ui.button(_('Neuen Test starten'), on_click=lambda: (
                            test_state.update(active=False, fragen=[], antworten={}, idx=0, fertig=False),
                            test_container.clear(),
                        )).props("flat")
                return
            ergebnisse_liste.refresh()

            # Ergebnis anzeigen
            with ui.card().classes(C.CARD + " w-full"):
                ui.label(_('✅ Test beendet!')).classes(C.CARD_TITLE)
                with ui.grid(columns=2).classes("w-full gap-4 mt-4"):
                    stat_card(_('Richtige Antworten'), _('{0}/{1}').format(gesamtpunkte, len(fragen)), "check_circle", color=PRIMARY)
                    stat_card(_('CEFR-Level'), cefr, "emoji_events", color=ACCENT)
                # C4: Prozent-Format wie Streamlit st.metric (app.py:3044 avg*100:.0f)
                ui.label(_('Score: {0:.0f}%').format(avg * 100)).classes(C.BODY + " mt-4")
                if _cefr["beschreibung"]:
                    ui.label(_('📖 {0} — {1}').format(_cefr['beschreibung'], _cefr['empfehlung'])).classes(C.SMALL + " mt-2")

                ui.button(_('Neuen Test starten'), on_click=lambda: (
                    test_state.update(active=False, fragen=[], antworten={}, idx=0, fertig=False),
                    test_container.clear(),
                )).classes(C.BTN_PRIMARY + " mt-4")

    # Selection UI
    with ui.card().classes(C.CARD + " w-full"):
        with ui.grid(columns=3).classes("w-full gap-4"):
            ui.select(
                options={v: _(v) for v in ["Deutsch", "Englisch", "Französisch"]},
                value="Deutsch",
                label=_('Sprache'),
                on_change=lambda e: test_state.update(sprache=e.value),
            ).classes("w-full")
            ui.select(
                options=["A1", "A2", "B1", "B2", "C1"],
                value="A1",
                label=_('Niveau'),
                on_change=lambda e: test_state.update(niveau=e.value),
            ).classes("w-full")
            ui.select(
                options=[5, 10, 15, 20],
                value=10,
                label=_('Anzahl Fragen'),
                on_change=lambda e: test_state.update(anzahl=e.value),
            ).classes("w-full")

        ui.button(_('Test starten'), on_click=start_test).classes(C.BTN_PRIMARY + " mt-4")

    # ── Video-Vorstellung (Parität app.py:3055-3067; Jitsi → VDO.Ninja 27.09.2026) ──
    # Fix 28.09.2026: Link wird FEST gespeichert statt nur session_state (Altstand-Bug),
    # Persistenz: Abschnitt "## Video-Vorstellung" in self-presentation-kandidat-*.md →
    # HR-Sicht components.py:561 (Recruiting-Modus, ohne Status-Gate zur Bewertung
    # vor der Übernahme – Nutzer-Entscheidung 28.09.2026).
    # Kein Aufnahmeparameter in der URL (knowledge/legal/recording-consent.md).
    ui.separator()
    ui.label(_('🎬 Video-Vorstellung (optional)')).classes(C.CARD_TITLE + " mt-4")
    ui.label(
        _('Nehmen Sie ein kurzes Video auf (2-3 Minuten). Der Link wird mit Ihrer Bewerbung gesendet.')
    ).classes(C.SMALL + " mb-2")
    video_box = ui.column().classes("w-full")

    # A4 (30.09.2026): Logik in Modulfunktionen (load_video_link / persist_video_link,
    # getestet in tests/test_video_section.py); hier nur dünne Wrapper.
    def _load_video_link():
        return load_video_link(db.BASE_DIR / "ergebnisse", s["user_cand_id"])

    def _persist_video_link(video_url: str) -> None:
        persist_video_link(db.BASE_DIR / "ergebnisse", s["user_cand_id"], video_url)

    def _show_video(video_url: str) -> None:
        video_box.clear()
        with video_box:
            ui.markdown(_('✅ **Video-Link:** [{0}]({1})').format(video_url, video_url)).classes(C.BODY)
            ui.label(_('📌 Merken Sie sich diesen Link für Ihr Bewerbungsgespräch.')).classes(C.SMALL)

    _vorhanden = _load_video_link()
    if _vorhanden:
        _show_video(_vorhanden)

    def _gen_video_link() -> None:
        import uuid
        video_code = f"vorstellung-{s['user_cand_id']}-{str(uuid.uuid4())[:8]}"
        # Fix 03.10.2026 (Spec §2.3): Solo-Selbstpräsentation = `?push=` (Sender), nicht
        # `?director=` (Regieraum ohne eigenes Bild). Ohne Aufnahme-Parameter (rechtlich).
        video_url = f"https://vdo.ninja/?push={video_code}&record=6000"
        _persist_video_link(video_url)
        _show_video(video_url)
        ui.notify(_('Video-Link generiert und mit Ihrer Bewerbung gespeichert.'), type="positive")

    ui.button(_('🎥 Video-Link generieren'), on_click=_gen_video_link).classes(C.BTN_PRIMARY + " mt-2")

    ui.add_body_html("<script>document.body.style.overflow = 'auto';</script>")


# ─── Tab 5: Onboarding ──────────────────────────────────────────────

def _tab_onboarding(s: dict) -> None:
    section_header(title=_('Onboarding'), icon="assignment")

    conn = db.get_conn()
    # C7 (22.09.2026): alle eingestellten Bewerbungen (Streamlit-Query
    # app.py:2376-2379), nicht nur die letzte
    rows = conn.execute("""
        SELECT a.id, j.titel, e.firma, a.status
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        JOIN employers e ON j.employer_id = e.id
        WHERE a.candidate_id = ? AND a.status = 'eingestellt'
        ORDER BY a.aktualisiert_am DESC
    """, (s["user_cand_id"],)).fetchall()
    conn.close()

    if not rows:
        # P1-3 (29.09.2026, Nutzer-GO): Leerzustand mit klickbarem Weg statt
        # Sackgasse (Spec: skills/pre-screen/SKILL.md, Sackgassen-Regel P1-3)
        empty_state(
            icon="pending_actions",
            title=_('Noch kein Onboarding aktiv'),
            description=_('Onboarding wird nach erfolgreicher Einstellung freigeschaltet.'),
            action_label=_('→ Stellen ansehen'),
            on_action=lambda: navigate_to("candidate", "stellen"),
        )
        return

    # R5-4 (30.09.2026): die feste timeline_items-Liste (Bewerbung →
    # Pre-Screening → … → Onboarding, immer 'done') war toter Code — die
    # Expansionen bauen ihre Timeline unten aus der ECHTEN
    # application_status_history (db.get_application_status_history).

    # D29 (b): Runner schreibt onboarding-freigabe-bewerbung-{app_id}.md
    # (agent-runner.py:1240), NICHT Streamit-Namensmuster onboarding-kandidat-*
    # (app.py:2386 — globbt nie, weil nie geschrieben → Streamlit-Gap, Schritt 2).
    ergebnisse = db.BASE_DIR / "ergebnisse"

    for b_id, b_titel, b_firma, _b_status in rows:
        with ui.expansion(text=_('🎉 {0} – {1}').format(b_titel, b_firma)).classes("w-full mb-4"):
            with ui.card().classes(C.CARD_HOVER + " w-full mb-3"):
                _history = db.get_application_status_history(b_id)
                if _history:
                    _items = []
                    for _h_status, _h_date, _h_by in _history:
                        _h_icon = STATUS_ICONS.get(_h_status, "📄")
                        _items.append({
                            "title": f"{_h_icon} {status_label(_h_status)}",
                            "status": "done" if _h_status in ("eingestellt", "abgelehnt", "zurückgezogen") else "active",
                            "date": _h_date[:10] if _h_date else "",
                        })
                    timeline(_items)
                else:
                    ui.label(_('Keine Statushistorie')).classes(C.MUTED)
                # Mentoring (Phase D P10, User-GO 24.09.2026): Anzeige im
                # bestehenden Onboarding-Tab (kein neuer Tab, Spec §7)
                _mentor = db.get_active_mentor(s["user_cand_id"])
                if _mentor:
                    ui.label(_('🤝 Ihr Ansprechpartner (Mentor): {0}').format(_mentor)).classes(
                        "text-sm font-medium text-emerald-700 mt-2"
                    )

            matches = sorted(ergebnisse.glob(f"onboarding-freigabe-bewerbung-{b_id}*.md"))
            if matches:
                onb_path = matches[-1]
                onb_text = onb_path.read_text(encoding="utf-8", errors="replace")
                ui.markdown(onb_text)
                ui.button(
                    _('Herunterladen'), icon="download",
                    on_click=lambda _c=onb_text, _n=onb_path.name: ui.download(
                        _c.encode("utf-8"), _n, "text/markdown"
                    ),
                ).classes(C.BTN_PRIMARY + " mt-3")
            else:
                ui.label(
                    _('Der Arbeitgeber hat Sie eingestellt – die Checkliste wird gerade vorbereitet.')
                ).classes(C.MUTED)


def _tab_dashboard(s: dict) -> None:
    section_header(title=_('Dashboard'), subtitle=_('Kandidaten-Uebersicht'), icon="dashboard")

    cand_id = s.get("user_cand_id")
    laufend = None
    bew_count = None

    @ui.refreshable
    def dashboard_stats():
        nonlocal laufend, bew_count
        try:
            conn = db.get_conn()
            try:
                vollstaendig = _profil_vollstaendigkeit(conn, cand_id)
                laufend = conn.execute(
                    "SELECT COUNT(*) FROM applications WHERE candidate_id = ? AND status IN (?,?,?)",
                    (cand_id, *logic.APPLICANT_ACTIVE),
                ).fetchone()[0]
                bew_count = conn.execute(
                    "SELECT COUNT(*) FROM applications WHERE candidate_id = ?",
                    (cand_id,),
                ).fetchone()[0]
                neu = conn.execute(
                    "SELECT COUNT(*) FROM jobs j WHERE j.status='aktiv' "
                    "AND j.erstellt_am >= datetime('now', ?) "
                    "AND NOT EXISTS (SELECT 1 FROM applications a "
                    "WHERE a.job_id=j.id AND a.candidate_id=?)",
                    (f"-{_NEU_TAGE} days", cand_id),
                ).fetchone()[0]
                lt = conn.execute(
                    "SELECT punkte, cefr_level, sprache FROM language_tests "
                    "WHERE candidate_id = ? ORDER BY id DESC LIMIT 1",
                    (cand_id,),
                ).fetchone()
            finally:
                conn.close()

            cefr = "—"
            if lt and lt[0] is not None:
                cefr = logic.cefr_from_avg(float(lt[0]))["level"]

            with ui.grid(columns=4).classes(C.GRID_4 + " mb-6"):
                stat_card(_('Profil-Vollständigkeit'), _('{0} %').format(vollstaendig), "person",
                          color=PRIMARY,
                          on_click=lambda: ui.navigate.to("/candidate/profil"))
                stat_card(_('Laufende Bewerbungen'), laufend, "send", color=ACCENT,
                          on_click=lambda: ui.navigate.to("/candidate/bewerbungen"))
                stat_card(_('Neu veroeffentlichte Stellen'), neu, "work", color=SECONDARY,
                          on_click=lambda: ui.navigate.to("/candidate/stellen"))
                stat_card(_('Sprachtest'), cefr, "translate", color="#7C3AED",
                          on_click=lambda: ui.navigate.to("/candidate/sprachtest"))

            # Direkt unter den Kacheln (nicht unter dem Chart) und INNERHALB des
            # refreshable-Blocks, damit der 10-s-Timer ihn mit aktualisiert.
            # Nur wenn es überhaupt keine Bewerbung gibt (bew_count == 0) —
            # sonst widerspricht der Hinweis dem Chart, und ein bereits
            # eingestellter Kandidat bekäme fälschlich „bewirb dich".
            if bew_count == 0:
                empty_state(
                    icon="work_off",
                    title=_('Noch keine Bewerbungen'),
                    description=_('Entdecke passende Stellen und bewirb dich mit einem Klick.'),
                    action_label=_('Stellen entdecken'),
                    on_action=lambda: ui.navigate.to("/candidate/stellen"),
                )
        except Exception as ex:
            _log.exception("candidate_dashboard fehlgeschlagen: %s", ex)
            ui.label(_('⚠️ Dashboard-Zahlen konnten nicht geladen werden: {0}').format(ex)).classes(
                "text-red-600")
            ui.button(_('Neu laden'), on_click=dashboard_stats.refresh)

    dashboard_stats()
    ui.timer(interval=10.0, callback=dashboard_stats.refresh)

    try:
        conn = db.get_conn()
        status_rows = conn.execute(
            "SELECT status, COUNT(*) FROM applications WHERE candidate_id = ? GROUP BY status",
            (cand_id,),
        ).fetchall()
        conn.close()

        if status_rows:
            status_data = [{"value": r[1], "name": r[0] or "unbekannt"} for r in status_rows]
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
                            "itemStyle": {"shadowBlur": 10, "shadowOffsetX": 0,
                                          "shadowColor": "rgba(0, 0, 0, 0.5)"}
                        }
                    }]
                }).classes("w-full h-64")
    except Exception as ex:
        _log.exception("candidate_dashboard chart fehlgeschlagen: %s", ex)
        ui.label(_('⚠️ Status-Verteilung konnte nicht geladen werden: {0}').format(ex)).classes(
            "text-red-600")


# Tab-Map auf Modulebene (fuer Sub-Route-Registrierung)
_TAB_MAP = {
    "dashboard": ("Dashboard", "dashboard", _tab_dashboard),
    "profil": ("Mein Profil", "person", _tab_profil),
    "stellen": ("Stellen", "work", _tab_stellen),
    "bewerbungen": ("Bewerbungen", "send", _tab_bewerbungen),
    "sprachtest": ("Sprachtest", "translate", _tab_sprachtest),
    "prescreen": ("Pre-Screen", "videocam", _tab_prescreen),
    "onboarding": ("Onboarding", "assignment", _tab_onboarding),
}

def _menu_items() -> list[dict]:
    """Sidebar-Einträge — Labels erst beim Rendern übersetzt
    (Importzeit = keine Session/Sprache, i18n-Regel knowledge/system/i18n.md)."""
    return [
        {"key": key, "label": _(vals[0]), "icon": vals[1]}
        for key, vals in _TAB_MAP.items()
    ]


def create() -> None:
    """Register the /candidate page with all tabs + Sub-Routes."""
    from nicegui import app

    def _build_candidate_page(initial_tab: str = ""):
        """Shared page builder fuer /candidate und /candidate/{tab}."""
        s = app.storage.user
        role = logic.current_role(s)
        if role != "candidate" and role != "admin":
            ui.navigate.to("/login")
            return

        def render_page(page_key: str):
            fn = _TAB_MAP.get(page_key, ("", "", _tab_dashboard))[2]
            fn(s)

        from webui.components import shell
        shell(
            role="candidate",
            user_id=s.get("user_cand_id", 0),
            user_name=s.get("user_name", _("Profil")),
            menu_items=_menu_items(),
            logout_fn=lambda: logic.logout_user(s),
            content_fn=render_page,
            s=s,
            initial_tab=initial_tab,
        )

    @ui.page("/candidate")
    def candidate_page():
        _build_candidate_page()

    # Sub-Routes auf Modulebene registrieren (direkte URL-Zugriffe)
    for _tab_key in _TAB_MAP:
        def _register(k=_tab_key):
            @ui.page(f"/candidate/{k}")
            def _sub_page(_k=k):
                _build_candidate_page(initial_tab=_k)
        _register()
