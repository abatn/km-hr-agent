"""Gebühren- und Rechnungs-UI (Kandidat, Arbeitgeber, Admin).

Kein Online-Zahldienst: nur Rechnung, Bankdaten aus KMHR_BANK_* und manuelle
Bestätigung des Zahlungseingangs durch das Team. Feature-Flag
KMHR_BILLING_ENABLED (Default aus) — ohne Flag rendert nichts.

Alle DB-Callbacks öffnen eine eigene Verbindung und schließen sie in
try/finally (Handler-Connection-Regel, skills/nicegui-migration/SKILL.md).
Strings erst zur Renderzeit übersetzen (knowledge/system/i18n.md), daher
keine Modul-Konstanten mit UI-Text und kein f-String in _().
"""
from __future__ import annotations

from datetime import datetime

from nicegui import ui

from webui import billing, db
from webui.components import empty_state, section_header
from webui.i18n import _
from webui.theme import C


def _fee_label(key: str) -> str:
    labels = {
        "beratung": _("Beratung / CV-Check"),
        "vertrag": _("Vermittlung (Arbeitsvertrag)"),
        "visum": _("Visumgenehmigung"),
    }
    return labels.get(key, key)


def _visum_zustand(neu) -> str:
    """Dreiwertig: None = entfällt, False = war schon da, True = neu erstellt."""
    if neu is None:
        return _("entfällt (Ausbildung)")
    return _("erstellt") if neu else _("bereits vorhanden")


def _status_label(key: str) -> str:
    labels = {
        "rechnung_gestellt": _("Rechnung gestellt"),
        "bezahlt": _("Bezahlt"),
        "storniert": _("Storniert"),
    }
    return labels.get(key, key)


def _bank_card() -> None:
    """Bankdaten für die Überweisung — ohne konfigurierte Daten keine Zahlungsaufforderung."""
    daten = billing.bank_details()
    with ui.card().classes(C.CARD + " w-full mt-4"):
        ui.label(_("Zahlung per Banküberweisung")).classes(C.CARD_TITLE + " mb-2")
        if not daten["configured"]:
            ui.label(_("Bankdaten sind noch nicht konfiguriert. "
                       "Bitte keine Rechnung ohne gültige Bankdaten versenden.")).classes(
                "text-sm text-amber-700")
            return
        zeilen = [
            (_("Kontoinhaber"), daten["holder"]),
            (_("Bank"), daten["bank"] or "—"),
            (_("IBAN"), daten["iban"]),
            (_("BIC"), daten["bic"] or "—"),
            (_("Verwendungszweck"), _("Rechnungsnummer")),
        ]
        for label, wert in zeilen:
            with ui.row().classes("w-full justify-between gap-4"):
                ui.label(label).classes("text-sm text-gray-500")
                ui.label(wert).classes("text-sm font-medium")


def _fee_table(fees: list[dict]) -> None:
    if not fees:
        empty_state(icon="receipt_long", title=_("Noch keine Rechnungen"),
                    description=_("Rechnungen erscheinen hier nach der Buchung oder nach dem Auslöser."))
        return
    zeilen = [{
        "id": f["id"],
        "rechnung": f["invoice_number"],
        "leistung": _fee_label(f["fee_type"]),
        "betrag": billing.format_eur(int(f["amount_cents"])),
        "status": _status_label(f["status"]),
        "faellig": f["due_date"],
    } for f in fees]
    ui.table(columns=[
        {"name": "rechnung", "label": _("Rechnung"), "field": "rechnung", "align": "left"},
        {"name": "leistung", "label": _("Leistung"), "field": "leistung", "align": "left"},
        {"name": "betrag", "label": _("Betrag"), "field": "betrag", "align": "right"},
        {"name": "status", "label": _("Status"), "field": "status", "align": "left"},
        {"name": "faellig", "label": _("Fällig"), "field": "faellig", "align": "left"},
    ], rows=zeilen, row_key="id", pagination=10).classes("w-full")
    ui.label(_("Zahlungseingang wird durch das Team bestätigt; die Rechnung bleibt bis dahin offen.")).classes(
        "text-xs text-gray-500 mt-2")


def _summen_karten(summ: dict) -> None:
    with ui.row().classes("w-full gap-4 mb-3"):
        with ui.card().classes(C.CARD + " flex-1"):
            ui.label(_("Offen")).classes("text-xs text-gray-500")
            ui.label(billing.format_eur(summ["offen_cents"])).classes("text-xl font-bold")
        with ui.card().classes(C.CARD + " flex-1"):
            ui.label(_("Bezahlt")).classes("text-xs text-gray-500")
            ui.label(billing.format_eur(summ["bezahlt_cents"])).classes("text-xl font-bold")


def _bewerbungs_options(conn, cand_id: int) -> dict:
    """Bewerbungen des Kandidaten als Auswahl — Beratung wird daran geknüpft."""
    rows = conn.execute(
        """SELECT a.id, j.titel, e.firma
           FROM applications a
           JOIN jobs j ON j.id = a.job_id
           JOIN employers e ON e.id = j.employer_id
           WHERE a.candidate_id = ? ORDER BY a.id DESC""", (cand_id,)).fetchall()
    return {str(r[0]): _("#{id} · {titel} · {firma}").format(id=r[0], titel=r[1], firma=r[2])
            for r in rows}


def candidate_billing_section(cand_id: int) -> None:
    """Kandidat: Beratungstermin buchen (99 €), eigene Rechnungen, Bankdaten."""
    if not billing.billing_enabled():
        return

    @ui.refreshable
    def _inhalt() -> None:
        conn = db.get_conn()
        try:
            fees = billing.list_fees("candidate", cand_id, conn)
            summ = billing.summary(conn, "candidate", cand_id)
            termine = billing.list_termine(conn, cand_id)
            options = _bewerbungs_options(conn, cand_id)
        finally:
            conn.close()

        _summen_karten(summ)

        # ── Schritt 2: Beratungstermin buchen ──────────────────────────
        with ui.card().classes(C.CARD + " w-full mb-4"):
            ui.label(_("Beratung / CV-Check buchen (99 €)")).classes(C.CARD_TITLE + " mb-2")
            if not options:
                ui.label(_("Für eine Beratung brauchst du zuerst eine Bewerbung. "
                           "Sobald du dich beworben hast, kannst du hier einen Termin buchen.")).classes(
                    "text-sm text-gray-500")
            else:
                ui.label(_("Die Beratung ist eine separate Leistung und wird nicht auf eine "
                           "spätere Vermittlungsgebühr angerechnet.")).classes(
                    "text-sm text-gray-500 mb-3")
                with ui.row().classes("items-end gap-3 w-full"):
                    app_select = ui.select(options=options, label=_("Bewerbung")).classes("flex-1")
                    slot_input = ui.input(label=_("Termin (TT.MM.JJJJ HH:MM)"),
                                          placeholder="15.11.2026 10:00").classes("w-64")

                    async def buchen() -> None:
                        if not app_select.value:
                            ui.notify(_("Bitte Bewerbung wählen."), type="negative")
                            return
                        roh = (slot_input.value or "").strip()
                        try:
                            slot = datetime.strptime(roh, "%d.%m.%Y %H:%M").isoformat()
                        except ValueError:
                            ui.notify(_("Bitte Termin im Format TT.MM.JJJJ HH:MM eingeben."),
                                      type="negative")
                            return
                        conn = db.get_conn()
                        try:
                            billing.create_termin(conn, application_id=int(app_select.value),
                                                  candidate_id=cand_id, slot_at=slot)
                        except ValueError as ex:
                            ui.notify(_("Termin konnte nicht gebucht werden: {0}").format(_(str(ex))),
                                      type="negative")
                            return
                        finally:
                            conn.close()
                        ui.notify(_("Termin gebucht. Rechnung über 99 € wurde erstellt."), type="positive")
                        _inhalt.refresh()

                    ui.button(_("Termin buchen (99 €)"), icon="event_available",
                              on_click=buchen).classes(C.BTN_PRIMARY)

        # ── Gebuchte Termine ───────────────────────────────────────────
        if termine:
            with ui.card().classes(C.CARD + " w-full mb-4"):
                ui.label(_("Gebuchte Beratungstermine")).classes(C.CARD_TITLE + " mb-2")
                for t in termine:
                    ui.label("#{} · {} · {}".format(
                        t["application_id"], t["slot_at"].replace("T", " "), t["job_titel"])).classes(
                        "text-sm text-gray-600 dark:text-gray-300")

        _fee_table(fees)
        _bank_card()

    section_header(title=_("Gebühren & Rechnungen"), subtitle=_("Rechnungen und Banküberweisung"),
                   icon="receipt_long")
    _inhalt()


def employer_billing_section(employer_id: int) -> None:
    """Arbeitgeber: eigene Rechnungen, Bankdaten. Kein Buchungs-Button."""
    if not billing.billing_enabled():
        return

    @ui.refreshable
    def _inhalt() -> None:
        conn = db.get_conn()
        try:
            fees = billing.list_fees("employer", employer_id, conn)
            summ = billing.summary(conn, "employer", employer_id)
        finally:
            conn.close()

        _summen_karten(summ)
        ui.label(_("Gebühren für Vermittlung und Visa entstehen, sobald eine Bewerbung "
                   "eingestellt bzw. das Visum genehmigt wurde.")).classes(
            "text-sm text-gray-500 mb-3")
        _fee_table(fees)
        _bank_card()

    section_header(title=_("Gebühren & Rechnungen"), subtitle=_("Rechnungen und Banküberweisung"),
                   icon="receipt_long")
    _inhalt()


def admin_billing_section() -> None:
    """Admin: alle Rechnungen, Visumgebühr erfassen (Schritt 4), Zahlung bestätigen."""
    if not billing.billing_enabled():
        with ui.card().classes(C.CARD + " w-full mt-4"):
            ui.label(_("Abrechnung ist deaktiviert.")).classes(C.CARD_TITLE)
            ui.label(_("Aktivieren mit KMHR_BILLING_ENABLED=1.")).classes("text-sm text-gray-500")
        return

    @ui.refreshable
    def _inhalt() -> None:
        conn = db.get_conn()
        try:
            fees = billing.list_all_fees(conn)
            summ = billing.summary(conn)
            eingestellt = conn.execute(
                """SELECT a.id, c.name, j.titel, e.firma, j.bruttojahresgehalt_eur
                   FROM applications a
                   JOIN candidates c ON c.id = a.candidate_id
                   JOIN jobs j ON j.id = a.job_id
                   JOIN employers e ON e.id = j.employer_id
                   WHERE a.status = 'eingestellt' ORDER BY a.id DESC LIMIT 200""").fetchall()
        finally:
            conn.close()

        _summen_karten(summ)

        # ── Schritt 4: Visumgebühr erfassen ────────────────────────────
        with ui.card().classes(C.CARD + " w-full mb-4"):
            ui.label(_("Visumgebühr erfassen (nach Visum-Genehmigung)")).classes(C.CARD_TITLE + " mb-2")
            ui.label(_("Kandidat: 1.000 € · Arbeitgeber: 20 Prozent des Bruttojahresgehalts "
                       "(gedeckelt auf 2.000 €) · Ausbildung: nur Arbeitgeber.")).classes(
                "text-sm text-gray-500 mb-3")
            if not eingestellt:
                ui.label(_("Keine eingestellten Bewerbungen vorhanden.")).classes("text-sm text-gray-500")
            else:
                optionen = {}
                vorbelegt = {}
                for r in eingestellt:
                    optionen[str(r[0])] = _("#{id} · {name} · {titel} · {firma}").format(
                        id=r[0], name=r[1], titel=r[2], firma=r[3])
                    vorbelegt[str(r[0])] = r[4]
                with ui.row().classes("items-end gap-3 w-full"):
                    app_select = ui.select(options=optionen, label=_("Eingestellte Bewerbung")).classes("flex-1")
                    salary = ui.number(label=_("Bruttojahresgehalt (EUR)"), min=1, step=1000).classes("w-56")

                    async def visum_erfassen() -> None:
                        if not app_select.value:
                            ui.notify(_("Bitte Bewerbung wählen."), type="negative")
                            return
                        brutto = int(salary.value or vorbelegt.get(app_select.value) or 0)
                        if brutto <= 0:
                            ui.notify(_("Bitte Bruttojahresgehalt eingeben."), type="negative")
                            return
                        conn = db.get_conn()
                        try:
                            ids = billing.create_visa_fees(
                                conn, application_id=int(app_select.value),
                                brutto_jahr_cents=brutto * 100)
                        except ValueError as ex:
                            ui.notify(_("Visumgebühr fehlgeschlagen: {0}").format(_(str(ex))),
                                      type="negative")
                            return
                        finally:
                            conn.close()
                        ui.notify(_("Visumgebühren: Kandidat {k}, Arbeitgeber {a}.").format(
                            k=_visum_zustand(ids["kandidat"]),
                            a=_visum_zustand(ids["arbeitgeber"])), type="positive")
                        _inhalt.refresh()

                    ui.button(_("Visumgebühren erstellen"), on_click=visum_erfassen).classes(C.BTN_PRIMARY)

        # ── Zahlungseingang bestätigen / stornieren ────────────────────
        offen = [f for f in fees if f["status"] == "rechnung_gestellt"]
        with ui.card().classes(C.CARD + " w-full mb-4"):
            ui.label(_("Zahlungseingang bestätigen / stornieren")).classes(C.CARD_TITLE + " mb-2")
            if not offen:
                ui.label(_("Keine offenen Rechnungen.")).classes("text-sm text-gray-500")
            else:
                optionen = {str(f["id"]): _("{} · {} · {}").format(
                    f["invoice_number"], _fee_label(f["fee_type"]),
                    billing.format_eur(int(f["amount_cents"]))) for f in offen}
                with ui.row().classes("items-end gap-3 w-full"):
                    fee_select = ui.select(options=optionen, label=_("Offene Rechnung")).classes("flex-1")

                    async def _status_setzen(status: str) -> None:
                        if not fee_select.value:
                            ui.notify(_("Bitte Rechnung wählen."), type="negative")
                            return
                        fee_id = int(fee_select.value)
                        conn = db.get_conn()
                        try:
                            if status == "bezahlt":
                                billing.mark_paid(conn, fee_id)
                                meldung = _("Zahlungseingang bestätigt.")
                            else:
                                billing.cancel_fee(conn, fee_id, _("Admin-Storno"))
                                meldung = _("Rechnung storniert.")
                        finally:
                            conn.close()
                        ui.notify(meldung, type="positive")
                        _inhalt.refresh()

                    ui.button(_("Bezahlt"), on_click=lambda: _status_setzen("bezahlt")).classes(C.BTN_PRIMARY)
                    ui.button(_("Stornieren"), on_click=lambda: _status_setzen("storniert")).props(
                        "flat color=negative")

        # ── Alle Rechnungen ────────────────────────────────────────────
        if not fees:
            empty_state(icon="receipt_long", title=_("Noch keine Rechnungen"))
        else:
            zeilen = []
            for f in fees:
                zahler = (f["candidate_name"] if f["payer_role"] == "candidate"
                          else f["employer_firma"]) or f["payer_role"]
                zeilen.append({
                    "id": f["id"], "rechnung": f["invoice_number"], "zahler": zahler,
                    "leistung": _fee_label(f["fee_type"]),
                    "betrag": billing.format_eur(int(f["amount_cents"])),
                    "status": _status_label(f["status"]), "faellig": f["due_date"],
                })
            ui.table(columns=[
                {"name": "rechnung", "label": _("Rechnung"), "field": "rechnung", "align": "left"},
                {"name": "zahler", "label": _("Zahler"), "field": "zahler", "align": "left"},
                {"name": "leistung", "label": _("Leistung"), "field": "leistung", "align": "left"},
                {"name": "betrag", "label": _("Betrag"), "field": "betrag", "align": "right"},
                {"name": "status", "label": _("Status"), "field": "status", "align": "left"},
                {"name": "faellig", "label": _("Fällig"), "field": "faellig", "align": "left"},
            ], rows=zeilen, row_key="id", pagination=20).classes("w-full mt-3")

    section_header(title=_("Abrechnung"), subtitle=_("Gebühren, Rechnungen und Zahlungseingang"),
                   icon="receipt_long")
    _inhalt()
