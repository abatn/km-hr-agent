"""
KM-HR-Agent – billing.py (Entgelt-Berechnung und Gebühren-Erfassung)
=====================================================================
Schema (Nutzerentscheidung 26.10.2026, Betreiber):
  Schritt 2 Beratung/CV-Check   Kandidat   9.900 ct (99 €)   bei Terminbuchung
  Schritt 3 Arbeitsvertrag      Kandidat   50.000 ct (500 €) / Arbeitgeber 100.000 ct (1.000 €)
  Schritt 4 Visum genehmigt     Kandidat  100.000 ct (1.000 €) / Arbeitgeber 20 % des Bruttojahresgehalts
Deckel: Arbeitgeber-Vergütung max. 200.000 ct (2.000 € inkl. USt, § 296 Abs. 3 SGB III),
Kappung wird in `note` markiert.
Ausbildung (§ 296a SGB III): nur Arbeitgeber-Gebühren, Kandidaten-Gebühren entfallen.

Feature-Flag KMHR_BILLING_ENABLED (Default 0). Zahlung nur per Banküberweisung;
Bankdaten nur aus KMHR_BANK_* (kein Default, kein Test-IBAN).
Framework-frei: keine NiceGUI-Imports.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

CENT_BERATUNG = 9_900
CENT_KANDIDAT_VERTRAG = 50_000
CENT_KANDIDAT_VISUM = 100_000
CENT_ARBEITGEBER_VERTRAG = 100_000
ARBEITGEBER_VISUM_PROZENT = 20
CENT_DECKEL_ARBEITGEBER = 200_000

SCHRITTE = ("beratung", "vertrag", "visum")
AUSBILDUNG_TYP = "Ausbildung"


def billing_enabled() -> bool:
    """Feature-Flag KMHR_BILLING_ENABLED (Default aus)."""
    return os.environ.get("KMHR_BILLING_ENABLED", "0") == "1"


def berechne_gebuehr(schritt: str, payer_role: str, job_is_ausbildung: bool = False,
                     bruttojahresgehalt_cent: int | None = None) -> tuple[int, str] | None:
    """Liefert (betrag_cent, note) oder None, wenn keine Gebühr anfällt.

    Ausbildung: nur Arbeitgeber zahlt (§ 296a SGB III), Kandidat = None.
    Visum-Arbeitgeber: 20 % des Bruttojahresgehalts, gedeckelt auf 2.000 €.
    """
    if schritt not in SCHRITTE:
        raise ValueError(f"billing: unbekannter Schritt {schritt!r}")
    if payer_role not in ("candidate", "employer"):
        raise ValueError(f"billing: unbekannte payer_role {payer_role!r}")
    if job_is_ausbildung and payer_role == "candidate":
        return None

    if payer_role == "candidate":
        if schritt == "beratung":
            return CENT_BERATUNG, ""
        if schritt == "vertrag":
            return CENT_KANDIDAT_VERTRAG, ""
        return CENT_KANDIDAT_VISUM, ""

    if schritt == "beratung":
        return None
    if schritt == "vertrag":
        return CENT_ARBEITGEBER_VERTRAG, ""
    if not bruttojahresgehalt_cent or bruttojahresgehalt_cent <= 0:
        return None
    betrag = bruttojahresgehalt_cent * ARBEITGEBER_VISUM_PROZENT // 100
    if betrag > CENT_DECKEL_ARBEITGEBER:
        return CENT_DECKEL_ARBEITGEBER, "Deckel 2.000 € inkl. USt (§ 296 Abs. 3 SGB III) angewendet"
    return betrag, ""


def _application_context(conn, application_id: int) -> dict:
    """Liefert Kandidat, Arbeitgeber und Stellentyp einer Bewerbung."""
    row = conn.execute(
        """SELECT a.candidate_id, j.employer_id, j.stellentyp, j.titel, c.name, e.firma
           FROM applications a
           JOIN jobs j ON j.id = a.job_id
           JOIN candidates c ON c.id = a.candidate_id
           JOIN employers e ON e.id = j.employer_id
           WHERE a.id = ?""", (application_id,)).fetchone()
    if not row:
        raise ValueError(f"billing: Bewerbung {application_id} nicht gefunden")
    return {"candidate_id": row[0], "employer_id": row[1], "stellentyp": row[2] or "",
            "job_titel": row[3] or "", "candidate_name": row[4] or "",
            "employer_firma": row[5] or "", "ist_ausbildung": (row[2] == AUSBILDUNG_TYP)}


def billing_on_eingestellt(application_id: int, db_path=None) -> int:
    """Erfasst die Gebühren Schritt 3 (Arbeitsvertrag) für Kandidat und Arbeitgeber.

    Ohne Flag oder bei Ausbildung nur Arbeitgeber (Guard in berechne_gebuehr).
    Gibt die Anzahl neu angelegter Gebühren zurück. Idempotent über erfasse_gebuehr.

    Robustheit: Der Aufruf erfolgt an den Trigger-Stellen **nach** dem Commit des
    Statuswechsels. Ein reiner Datenbankfehler (z. B. gesperrte DB) darf deshalb
    den weiteren Ablauf (Onboarding-Task) nicht abbrechen — er wird protokolliert
    und mit 0 quittiert. Logikfehler (ValueError) werden weiterhin geworfen.
    """
    if not billing_enabled():
        return 0
    import sqlite3
    from webui import db as _db
    try:
        conn = sqlite3.connect(str(db_path or _db.DB_PATH))
    except sqlite3.Error as ex:
        print(f"[billing] Verbindung fehlgeschlagen (Bewerbung {application_id}): {ex!r}")
        return 0
    try:
        row = conn.execute(
            "SELECT a.candidate_id, j.employer_id, j.stellentyp, j.bruttojahresgehalt_eur "
            "FROM applications a JOIN jobs j ON j.id = a.job_id WHERE a.id = ?",
            (application_id,)).fetchone()
        if not row:
            return 0
        cid, eid, typ, brutto = row
        ausb = (typ == AUSBILDUNG_TYP)
        neu = 0
        for role in ("candidate", "employer"):
            fee = berechne_gebuehr("vertrag", role, job_is_ausbildung=ausb)
            if fee is None:
                continue
            betrag, note = fee
            if erfasse_gebuehr(conn, application_id=application_id, candidate_id=cid,
                               employer_id=eid, payer_role=role, fee_type="vertrag",
                               betrag_cent=betrag, note=note, job_is_ausbildung=ausb):
                neu += 1
        conn.commit()
        return neu
    except sqlite3.Error as ex:
        print(f"[billing] Gebuehren-Erfassung fehlgeschlagen (Bewerbung {application_id}): {ex!r}")
        return 0
    finally:
        conn.close()


def erfasse_gebuehr(conn, *, application_id: int, candidate_id: int, employer_id: int | None,
                    payer_role: str, fee_type: str, betrag_cent: int, note: str = "",
                    salary_basis_cent: int | None = None, job_is_ausbildung: bool = False) -> bool:
    """Legt eine Gebühr an. Idempotent: eine Gebühr je Bewerbung, Zahlerrolle und Schritt.

    Gibt True zurück, wenn neu angelegt, False bei Duplikat.
    Nutzt den partiellen Unique-Index `idx_billing_unique_app` (ohne stornierte Zeilen).
    """
    heute = date.today()
    rechnungsnr = f"KMHR-{heute:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"
    cur = conn.execute(
        "INSERT OR IGNORE INTO billing_fees (application_id, candidate_id, employer_id, payer_role, "
        "fee_type, amount_cents, currency, status, invoice_number, invoice_date, due_date, "
        "salary_basis_cents, job_is_ausbildung, note) "
        "VALUES (?, ?, ?, ?, ?, ?, 'EUR', 'rechnung_gestellt', ?, ?, ?, ?, ?, ?)",
        (application_id, candidate_id, employer_id, payer_role, fee_type, betrag_cent,
         rechnungsnr, heute.isoformat(), (heute + timedelta(days=14)).isoformat(),
         salary_basis_cent, 1 if job_is_ausbildung else 0, note or None),
    )
    return cur.rowcount == 1


# ─── Schritt 2: Beratung/CV-Check bei Terminbuchung ────────────────────
# Design-Entscheidung 26.10.2026 (Betreiber): Die 99-€-Beratung wird immer an
# eine Bewerbung des Kandidaten geknüpft. `termin_buchungen.application_id`
# ist NOT NULL — das Schema ist damit bewusst bruchfrei und der bestehende
# Unique-Index `idx_billing_unique_app` schützt vor Doppelbuchungen pro
# Bewerbung. Ein Kandidat ohne Bewerbung kann noch nicht buchen.

def create_termin(conn, *, application_id: int, candidate_id: int, slot_at: str) -> int:
    """Bucht einen Beratungstermin und legt die 99-€-Gebühr (Schritt 2) an.

    Idempotent über UNIQUE(application_id, slot_at) plus dem Billing-Index.
    Pro Bewerbung ist **ein** Beratungstermin vorgesehen (die Gebühr ist je
    Bewerbung ebenfalls nur einmal fällig) — ein zweiter Termin wird abgelehnt,
    damit Termin und Rechnung nicht auseinanderlaufen.
    Gibt die termin_id zurück.
    """
    ctx = _application_context(conn, application_id)
    if ctx["candidate_id"] != candidate_id:
        raise ValueError("Bewerbung gehört nicht zu diesem Kandidaten")
    vorhanden = conn.execute(
        "SELECT 1 FROM termin_buchungen WHERE application_id = ? AND status != 'storniert' LIMIT 1",
        (application_id,)).fetchone()
    if vorhanden:
        raise ValueError("Für diese Bewerbung ist bereits ein Beratungstermin gebucht.")
    cur = conn.execute(
        "INSERT OR IGNORE INTO termin_buchungen (application_id, candidate_id, slot_at) "
        "VALUES (?, ?, ?)", (application_id, candidate_id, slot_at))
    if cur.rowcount != 1:
        raise ValueError("Termin bereits gebucht")
    termin_id = int(cur.lastrowid)
    ausb = ctx["ist_ausbildung"]
    fee = berechne_gebuehr("beratung", "candidate", job_is_ausbildung=ausb)
    if fee is not None:
        betrag, note = fee
        erfasse_gebuehr(conn, application_id=application_id, candidate_id=candidate_id,
                        employer_id=None, payer_role="candidate", fee_type="beratung",
                        betrag_cent=betrag, note=note or "Beratung/CV-Check (separate Leistung)",
                        job_is_ausbildung=ausb)
    conn.commit()
    return termin_id


# ─── Schritt 4: Visumgenehmigung (nur Admin) ───────────────────────────

def create_visa_fees(conn, *, application_id: int, brutto_jahr_cents: int) -> dict:
    """Legt die Schritt-4-Gebühren an: Kandidat 1.000 €, Arbeitgeber 20 %
    des Bruttojahresgehalts (gedeckelt 2.000 €, Kappung in `note`).

    Ausbildung: nur Arbeitgeber-Gebühr, Kandidat entfällt.
    """
    if brutto_jahr_cents <= 0:
        raise ValueError("Bruttojahresgehalt muss positiv sein")
    ctx = _application_context(conn, application_id)
    ausb = ctx["ist_ausbildung"]
    ids: dict = {"kandidat": None, "arbeitgeber": None, "ist_ausbildung": ausb}
    for role in ("candidate", "employer"):
        fee = berechne_gebuehr("visum", role, job_is_ausbildung=ausb,
                               bruttojahresgehalt_cent=brutto_jahr_cents)
        if fee is None:
            continue
        betrag, note = fee
        neu = erfasse_gebuehr(conn, application_id=application_id,
                              candidate_id=ctx["candidate_id"],
                              employer_id=ctx["employer_id"], payer_role=role,
                              fee_type="visum", betrag_cent=betrag,
                              note=note or f"Visumgenehmigung: {ctx['job_titel']}",
                              salary_basis_cent=brutto_jahr_cents if role == "employer" else None,
                              job_is_ausbildung=ausb)
        ids["kandidat" if role == "candidate" else "arbeitgeber"] = neu
    conn.commit()
    return ids


# ─── Abfragen und Statuswechsel ────────────────────────────────────────

def _row_dict(row) -> dict:
    keys = ("id", "invoice_number", "fee_type", "amount_cents", "currency",
            "status", "invoice_date", "due_date", "paid_at", "application_id",
            "note", "salary_basis_cents", "job_is_ausbildung")
    return dict(zip(keys, row))


_FEES_SPALTEN = ("id", "invoice_number", "fee_type", "amount_cents", "currency",
                 "status", "invoice_date", "due_date", "paid_at", "application_id",
                 "note", "salary_basis_cents", "job_is_ausbildung")


def list_fees(payer_role: str, payer_id: int, conn) -> list[dict]:
    """Eigene Rechnungen eines Zahlers (candidate: candidate_id, employer: employer_id)."""
    if payer_role == "candidate":
        where, param = "payer_role = 'candidate' AND candidate_id = ?", payer_id
    elif payer_role == "employer":
        where, param = "payer_role = 'employer' AND employer_id = ?", payer_id
    else:
        raise ValueError(f"billing: unbekannte payer_role {payer_role!r}")
    rows = conn.execute(
        f"SELECT {', '.join(_FEES_SPALTEN)} FROM billing_fees WHERE {where} ORDER BY id DESC",
        (param,)).fetchall()
    return [_row_dict(r) for r in rows]


def list_all_fees(conn, limit: int = 200) -> list[dict]:
    """Alle Rechnungen für die Admin-Abrechnung, mit Namen der Zahler."""
    rows = conn.execute(
        """SELECT bf.id, bf.invoice_number, bf.fee_type, bf.amount_cents, bf.currency,
                  bf.status, bf.invoice_date, bf.due_date, bf.paid_at, bf.application_id,
                  bf.note, bf.salary_basis_cents, bf.job_is_ausbildung,
                  bf.payer_role, c.name AS candidate_name, e.firma AS employer_firma
           FROM billing_fees bf
           LEFT JOIN candidates c ON c.id = bf.candidate_id
           LEFT JOIN employers e ON e.id = bf.employer_id
           ORDER BY bf.id DESC LIMIT ?""", (int(limit),)).fetchall()
    keys = _FEES_SPALTEN + ("payer_role", "candidate_name", "employer_firma")
    return [dict(zip(keys, r)) for r in rows]


def summary(conn, payer_role: str | None = None, payer_id: int | None = None) -> dict:
    """Offene und bezahlte Summen, optional gefiltert auf einen Zahler."""
    where, params = "", []
    if payer_role == "candidate":
        where, params = " AND payer_role = 'candidate' AND candidate_id = ?", [payer_id]
    elif payer_role == "employer":
        where, params = " AND payer_role = 'employer' AND employer_id = ?", [payer_id]
    row = conn.execute(
        """SELECT COALESCE(SUM(CASE WHEN status='rechnung_gestellt' THEN amount_cents END), 0),
                  COALESCE(SUM(CASE WHEN status='bezahlt' THEN amount_cents END), 0),
                  COUNT(CASE WHEN status='rechnung_gestellt' THEN 1 END)
           FROM billing_fees WHERE 1=1""" + where, tuple(params)).fetchone()
    return {"offen_cents": int(row[0]), "bezahlt_cents": int(row[1]),
            "offen_anzahl": int(row[2])}


def mark_paid(conn, fee_id: int) -> None:
    """Bestätigt den Zahlungseingang (manuell, keine automatische Zahlungserkennung)."""
    conn.execute(
        "UPDATE billing_fees SET status='bezahlt', paid_at=CURRENT_TIMESTAMP, "
        "updated_at=CURRENT_TIMESTAMP WHERE id=? AND status='rechnung_gestellt'", (fee_id,))
    conn.commit()


def cancel_fee(conn, fee_id: int, grund: str = "") -> None:
    """Storniert eine noch nicht bezahlte Rechnung.

    Bei einer Beratung wird der zugehörige Termin mit storniert, damit dieselbe
    Bewerbung wieder buchbar ist (Termin und Rechnung bleiben gekoppelt).
    """
    row = conn.execute("SELECT fee_type, application_id FROM billing_fees WHERE id = ?",
                       (fee_id,)).fetchone()
    cur = conn.execute(
        "UPDATE billing_fees SET status='storniert', "
        "note = COALESCE(note,'') || ?, updated_at=CURRENT_TIMESTAMP "
        "WHERE id=? AND status='rechnung_gestellt'",
        (f" | Storno: {grund}" if grund else " | Storno", fee_id))
    if cur.rowcount == 1 and row and row[0] == "beratung" and row[1] is not None:
        conn.execute("UPDATE termin_buchungen SET status='storniert' "
                     "WHERE application_id = ? AND status = 'gebucht'", (row[1],))
    conn.commit()


def list_termine(conn, candidate_id: int) -> list[dict]:
    """Gebuchte Beratungstermine eines Kandidaten."""
    rows = conn.execute(
        """SELECT t.id, t.slot_at, t.status, a.id AS application_id, j.titel
           FROM termin_buchungen t
           JOIN applications a ON a.id = t.application_id
           JOIN jobs j ON j.id = a.job_id
           WHERE t.candidate_id = ? ORDER BY t.slot_at DESC""", (candidate_id,)).fetchall()
    keys = ("id", "slot_at", "status", "application_id", "job_titel")
    return [dict(zip(keys, r)) for r in rows]


# ─── Anzeige und Bankdaten ─────────────────────────────────────────────

def format_eur(cents: int) -> str:
    """Deutsche Anzeige: 123456 -> '1.234,56 €'."""
    return (f"{cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            + " €")


def bank_details() -> dict:
    """Bankdaten ausschließlich aus ENV — keine erfundene IBAN, kein Karten-Payment."""
    env_keys = {"holder": "KMHR_BANK_HOLDER", "bank": "KMHR_BANK_NAME",
                "iban": "KMHR_BANK_IBAN", "bic": "KMHR_BANK_BIC"}
    werte = {k: (os.environ.get(v, "") or "").strip() for k, v in env_keys.items()}
    werte["configured"] = bool(werte["holder"] and werte["iban"])
    return werte
