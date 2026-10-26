"""Gebühren-Logik (webui/billing.py) — isolierte SQLite-Tests.

Schema und Werte stammen aus der Nutzerentscheidung 26.10.2026:
  Schritt 2 Beratung      Kandidat            9.900 ct  bei Terminbuchung
  Schritt 3 Vertrag       Kandidat           50.000 ct  nach unterschriebenem Vertrag
  Schritt 3 Vertrag       Arbeitgeber       100.000 ct  nach unterschriebenem Vertrag
  Schritt 4 Visum         Kandidat          100.000 ct  nach Visumgenehmigung
  Schritt 4 Visum         Arbeitgeber    20 % Bruttojahresgehalt, gedeckelt 200.000 ct
  Ausbildung (§ 296a SGB III): nur Arbeitgeber, Kandidat entfällt.
"""
from __future__ import annotations

import sqlite3

import pytest

from webui import billing, db


@pytest.fixture()
def billing_db(tmp_path, monkeypatch):
    """Temp-DB mit dem echten Schema aus init_billing_migrations."""
    pfad = tmp_path / "billing.db"
    monkeypatch.setattr(db, "DB_PATH", pfad)
    db.init_billing_migrations(pfad)
    conn = sqlite3.connect(str(pfad))
    conn.executescript("""
        CREATE TABLE candidates (id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE employers (id INTEGER PRIMARY KEY, firma TEXT);
        CREATE TABLE jobs (id INTEGER PRIMARY KEY, employer_id INTEGER, titel TEXT,
                           stellentyp TEXT, bruttojahresgehalt_eur INTEGER);
        CREATE TABLE applications (id INTEGER PRIMARY KEY, candidate_id INTEGER,
                                  job_id INTEGER, status TEXT);
    """)
    conn.execute("INSERT INTO candidates (id, name) VALUES (1, 'Test Kandidat')")
    conn.execute("INSERT INTO employers (id, firma) VALUES (1, 'Test Firma')")
    conn.execute("INSERT INTO jobs (id, employer_id, titel, stellentyp, bruttojahresgehalt_eur) "
                 "VALUES (1, 1, 'Fachkraft', 'Vollzeit', NULL)")
    conn.execute("INSERT INTO applications (id, candidate_id, job_id, status) "
                 "VALUES (1, 1, 1, 'eingestellt')")
    conn.commit()
    conn.close()
    return pfad


def _conn(pfad):
    c = sqlite3.connect(str(pfad))
    c.row_factory = sqlite3.Row
    return c


# ─── berechne_gebuehr: reine Logik, keine DB ──────────────────────────

def test_schritt3_regulaer():
    assert billing.berechne_gebuehr("vertrag", "candidate") == (50_000, "")
    assert billing.berechne_gebuehr("vertrag", "employer") == (100_000, "")


def test_schritt2_nur_kandidat():
    assert billing.berechne_gebuehr("beratung", "candidate") == (9_900, "")
    assert billing.berechne_gebuehr("beratung", "employer") is None


def test_schritt4_visum_fest_und_prozent():
    assert billing.berechne_gebuehr("visum", "candidate") == (100_000, "")
    assert billing.berechne_gebuehr("visum", "employer",
                                    bruttojahresgehalt_cent=300_000) == (60_000, "")
    # Ohne Gehalt keine Arbeitgeber-Gebühr (kein erfundener Betrag).
    assert billing.berechne_gebuehr("visum", "employer") is None


def test_deckel_2000_euro():
    """20 % von 5.000.000 ct wären 1.000.000 — gedeckelt auf 200.000 mit Hinweis."""
    betrag, note = billing.berechne_gebuehr("visum", "employer",
                                            bruttojahresgehalt_cent=5_000_000)
    assert betrag == 200_000
    assert "Deckel" in note
    # Grenze: exakt 20 % = 200.000 → kein Deckel-Hinweis.
    betrag2, note2 = billing.berechne_gebuehr("visum", "employer",
                                              bruttojahresgehalt_cent=1_000_000)
    assert betrag2 == 200_000 and note2 == ""


def test_ausbildung_kandidat_zahlt_nicht():
    for schritt in ("beratung", "vertrag", "visum"):
        assert billing.berechne_gebuehr(schritt, "candidate", job_is_ausbildung=True) is None
    assert billing.berechne_gebuehr("vertrag", "employer", job_is_ausbildung=True) == (100_000, "")


def test_unbekannter_schritt_fehlt():
    with pytest.raises(ValueError):
        billing.berechne_gebuehr("quatsch", "candidate")
    with pytest.raises(ValueError):
        billing.berechne_gebuehr("vertrag", "wer_auch_immers")


# ─── Schritt 3: Trigger bei Einstellung ───────────────────────────────

def test_eingestellt_ohne_flag_legt_nichts_an(billing_db, monkeypatch):
    monkeypatch.delenv("KMHR_BILLING_ENABLED", raising=False)
    conn = _conn(billing_db)
    try:
        assert billing.billing_on_eingestellt(1, db_path=billing_db) == 0
        assert conn.execute("SELECT COUNT(*) FROM billing_fees").fetchone()[0] == 0
    finally:
        conn.close()


def test_eingestellt_mit_flag(billing_db, monkeypatch):
    monkeypatch.setenv("KMHR_BILLING_ENABLED", "1")
    conn = _conn(billing_db)
    try:
        assert billing.billing_on_eingestellt(1, db_path=billing_db) == 2
        fees = conn.execute(
            "SELECT payer_role, fee_type, amount_cents FROM billing_fees ORDER BY id").fetchall()
        assert [(f["payer_role"], f["amount_cents"]) for f in fees] == [
            ("candidate", 50_000), ("employer", 100_000)]
        assert all(f["fee_type"] == "vertrag" for f in fees)
        # Idempotent: zweiter Aufruf legt nichts Neues an.
        assert billing.billing_on_eingestellt(1, db_path=billing_db) == 0
        assert conn.execute("SELECT COUNT(*) FROM billing_fees").fetchone()[0] == 2
    finally:
        conn.close()


def test_eingestellt_ausbildung_nur_arbeitgeber(billing_db, monkeypatch):
    monkeypatch.setenv("KMHR_BILLING_ENABLED", "1")
    conn = _conn(billing_db)
    try:
        conn.execute("UPDATE jobs SET stellentyp='Ausbildung' WHERE id=1")
        conn.commit()
        assert billing.billing_on_eingestellt(1, db_path=billing_db) == 1
        fees = conn.execute("SELECT payer_role, amount_cents, job_is_ausbildung "
                            "FROM billing_fees").fetchall()
        assert len(fees) == 1
        assert fees[0]["payer_role"] == "employer"
        assert fees[0]["job_is_ausbildung"] == 1
    finally:
        conn.close()


def test_eingestellt_db_fehler_bricht_nicht_ab(billing_db, monkeypatch, tmp_path):
    """DB-Fehler nach dem Status-Commit darf den Ablauf nicht abbrechen."""
    monkeypatch.setenv("KMHR_BILLING_ENABLED", "1")
    # Ein Verzeichnis als DB-Pfad → sqlite3 kann keine Verbindung öffnen.
    ordner = tmp_path / "keine-db"
    ordner.mkdir()
    assert billing.billing_on_eingestellt(1, db_path=ordner) == 0


def test_eingestellt_unbekannte_bewerbung(billing_db, monkeypatch):
    monkeypatch.setenv("KMHR_BILLING_ENABLED", "1")
    assert billing.billing_on_eingestellt(999, db_path=billing_db) == 0


# ─── Schritt 2: Terminbuchung ─────────────────────────────────────────

def test_terminbuchung_legt_beratung_an(billing_db):
    conn = _conn(billing_db)
    try:
        billing.create_termin(conn, application_id=1, candidate_id=1, slot_at="2026-11-15T10:00")
        fees = conn.execute("SELECT fee_type, amount_cents, application_id "
                            "FROM billing_fees").fetchall()
        assert len(fees) == 1
        assert fees[0]["fee_type"] == "beratung"
        assert fees[0]["amount_cents"] == 9_900
        assert fees[0]["application_id"] == 1
        termine = conn.execute("SELECT slot_at FROM termin_buchungen").fetchall()
        assert len(termine) == 1
    finally:
        conn.close()


def test_terminbuchung_fremde_bewerbung_abgelehnt(billing_db):
    conn = _conn(billing_db)
    try:
        conn.execute("INSERT INTO candidates (id, name) VALUES (2, 'Fremder')")
        conn.commit()
        with pytest.raises(ValueError):
            billing.create_termin(conn, application_id=1, candidate_id=2,
                                  slot_at="2026-11-15T10:00")
        assert conn.execute("SELECT COUNT(*) FROM billing_fees").fetchone()[0] == 0
    finally:
        conn.close()


def test_terminbuchung_doppelter_slot_abgelehnt(billing_db):
    conn = _conn(billing_db)
    try:
        billing.create_termin(conn, application_id=1, candidate_id=1, slot_at="2026-11-15T10:00")
        with pytest.raises(ValueError):
            billing.create_termin(conn, application_id=1, candidate_id=1,
                                  slot_at="2026-11-15T10:00")
        assert conn.execute("SELECT COUNT(*) FROM billing_fees").fetchone()[0] == 1
    finally:
        conn.close()


def test_terminbuchung_zweiter_slot_fuer_gleiche_bewerbung_abgelehnt(billing_db):
    """Pro Bewerbung ein Beratungstermin — sonst Termin ohne Rechnung."""
    conn = _conn(billing_db)
    try:
        billing.create_termin(conn, application_id=1, candidate_id=1, slot_at="2026-11-15T10:00")
        with pytest.raises(ValueError):
            billing.create_termin(conn, application_id=1, candidate_id=1,
                                  slot_at="2026-11-16T10:00")
        assert conn.execute("SELECT COUNT(*) FROM termin_buchungen").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM billing_fees").fetchone()[0] == 1
    finally:
        conn.close()


def test_terminbuchung_ausbildung_ohne_gebuehr(billing_db):
    """Ausbildung: Kandidat zahlt auch für die Beratung nichts."""
    conn = _conn(billing_db)
    try:
        conn.execute("UPDATE jobs SET stellentyp='Ausbildung' WHERE id=1")
        conn.commit()
        billing.create_termin(conn, application_id=1, candidate_id=1, slot_at="2026-11-15T10:00")
        assert conn.execute("SELECT COUNT(*) FROM billing_fees").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM termin_buchungen").fetchone()[0] == 1
    finally:
        conn.close()


# ─── Schritt 4: Visumgenehmigung ──────────────────────────────────────

def test_visum_regulaer(billing_db):
    conn = _conn(billing_db)
    try:
        ids = billing.create_visa_fees(conn, application_id=1, brutto_jahr_cents=400_000)
        assert ids["ist_ausbildung"] is False
        fees = conn.execute("SELECT payer_role, amount_cents, salary_basis_cents "
                            "FROM billing_fees ORDER BY id").fetchall()
        assert [(f["payer_role"], f["amount_cents"]) for f in fees] == [
            ("candidate", 100_000), ("employer", 80_000)]
        # Grundlage nur beim Arbeitgeber gespeichert.
        assert fees[0]["salary_basis_cents"] is None
        assert fees[1]["salary_basis_cents"] == 400_000
    finally:
        conn.close()


def test_visum_deckel(billing_db):
    conn = _conn(billing_db)
    try:
        billing.create_visa_fees(conn, application_id=1, brutto_jahr_cents=5_000_000)
        ag = conn.execute("SELECT amount_cents, note FROM billing_fees "
                          "WHERE payer_role='employer'").fetchone()
        assert ag["amount_cents"] == 200_000
        assert "Deckel" in ag["note"]
    finally:
        conn.close()


def test_visum_ausbildung_nur_arbeitgeber(billing_db):
    conn = _conn(billing_db)
    try:
        conn.execute("UPDATE jobs SET stellentyp='Ausbildung' WHERE id=1")
        conn.commit()
        ids = billing.create_visa_fees(conn, application_id=1, brutto_jahr_cents=300_000)
        assert ids["kandidat"] is None
        assert ids["arbeitgeber"] is not None
        assert conn.execute("SELECT COUNT(*) FROM billing_fees").fetchone()[0] == 1
    finally:
        conn.close()


def test_visum_ohne_gehalt_abgelehnt(billing_db):
    conn = _conn(billing_db)
    try:
        with pytest.raises(ValueError):
            billing.create_visa_fees(conn, application_id=1, brutto_jahr_cents=0)
        with pytest.raises(ValueError):
            billing.create_visa_fees(conn, application_id=1, brutto_jahr_cents=-5)
        assert conn.execute("SELECT COUNT(*) FROM billing_fees").fetchone()[0] == 0
    finally:
        conn.close()


def test_visum_unbekannte_bewerbung(billing_db):
    conn = _conn(billing_db)
    try:
        with pytest.raises(ValueError):
            billing.create_visa_fees(conn, application_id=999, brutto_jahr_cents=300_000)
    finally:
        conn.close()


# ─── Statuswechsel und Abfragen ───────────────────────────────────────

def test_mark_paid(billing_db):
    conn = _conn(billing_db)
    try:
        billing.create_termin(conn, application_id=1, candidate_id=1, slot_at="2026-11-15T10:00")
        fee = conn.execute("SELECT id FROM billing_fees").fetchone()
        billing.mark_paid(conn, fee["id"])
        row = conn.execute("SELECT status, paid_at FROM billing_fees WHERE id=?",
                           (fee["id"],)).fetchone()
        assert row["status"] == "bezahlt"
        assert row["paid_at"] is not None
        # Bereits bezahlt: kein zweites Mal.
        billing.mark_paid(conn, fee["id"])
        assert conn.execute("SELECT COUNT(*) FROM billing_fees WHERE status='bezahlt'").fetchone()[0] == 1
    finally:
        conn.close()


def test_cancel_fee(billing_db):
    conn = _conn(billing_db)
    try:
        billing.create_termin(conn, application_id=1, candidate_id=1, slot_at="2026-11-15T10:00")
        fee = conn.execute("SELECT id FROM billing_fees").fetchone()
        billing.cancel_fee(conn, fee["id"], "Kandidat hat storniert")
        row = conn.execute("SELECT status, note FROM billing_fees WHERE id=?",
                           (fee["id"],)).fetchone()
        assert row["status"] == "storniert"
        assert "Kandidat hat storniert" in row["note"]
    finally:
        conn.close()


def test_cancel_beratung_gibt_termin_frei(billing_db):
    """Nach Storno der Beratung ist dieselbe Bewerbung wieder buchbar."""
    conn = _conn(billing_db)
    try:
        billing.create_termin(conn, application_id=1, candidate_id=1, slot_at="2026-11-15T10:00")
        fee = conn.execute("SELECT id FROM billing_fees WHERE fee_type='beratung'").fetchone()
        billing.cancel_fee(conn, fee["id"], "Kandidat")
        assert conn.execute("SELECT status FROM termin_buchungen").fetchone()[0] == "storniert"
        billing.create_termin(conn, application_id=1, candidate_id=1, slot_at="2026-11-16T10:00")
        assert conn.execute("SELECT COUNT(*) FROM termin_buchungen").fetchone()[0] == 2
    finally:
        conn.close()


def test_cancel_nicht_bezahlbare_rechnung(billing_db):
    conn = _conn(billing_db)
    try:
        billing.create_termin(conn, application_id=1, candidate_id=1, slot_at="2026-11-15T10:00")
        fee = conn.execute("SELECT id FROM billing_fees").fetchone()
        billing.mark_paid(conn, fee["id"])
        billing.cancel_fee(conn, fee["id"], "Versuch")
        assert conn.execute("SELECT status FROM billing_fees WHERE id=?",
                            (fee["id"],)).fetchone()[0] == "bezahlt"
    finally:
        conn.close()


def test_list_fees_filter(billing_db):
    conn = _conn(billing_db)
    try:
        conn.execute("INSERT INTO employers (id, firma) VALUES (2, 'Zweite Firma')")
        conn.execute("INSERT INTO jobs (id, employer_id, titel, stellentyp) VALUES (2, 2, 'Andere', 'Vollzeit')")
        conn.execute("INSERT INTO applications (id, candidate_id, job_id, status) VALUES (2, 1, 2, 'eingestellt')")
        conn.commit()
        billing.create_termin(conn, application_id=1, candidate_id=1, slot_at="2026-11-15T10:00")
        billing.create_visa_fees(conn, application_id=2, brutto_jahr_cents=400_000)

        kand = billing.list_fees("candidate", 1, conn)
        assert len(kand) == 2  # beratung (app 1) + visum (app 2)
        ag1 = billing.list_fees("employer", 1, conn)
        assert len(ag1) == 0  # nur Visum-Gebühren über app 2, kein vertrag-Trigger
        ag2 = billing.list_fees("employer", 2, conn)
        assert len(ag2) == 1
        assert ag2[0]["fee_type"] == "visum"

        with pytest.raises(ValueError):
            billing.list_fees("quatsch", 1, conn)
    finally:
        conn.close()


def test_summary(billing_db):
    conn = _conn(billing_db)
    try:
        billing.create_termin(conn, application_id=1, candidate_id=1, slot_at="2026-11-15T10:00")
        assert billing.summary(conn)["offen_cents"] == 9_900
        fee = conn.execute("SELECT id FROM billing_fees").fetchone()
        billing.mark_paid(conn, fee["id"])
        summ = billing.summary(conn)
        assert summ["offen_cents"] == 0
        assert summ["bezahlt_cents"] == 9_900
        assert summ["offen_anzahl"] == 0
    finally:
        conn.close()


def test_list_all_fees(billing_db):
    conn = _conn(billing_db)
    try:
        billing.create_termin(conn, application_id=1, candidate_id=1, slot_at="2026-11-15T10:00")
        fees = billing.list_all_fees(conn)
        assert len(fees) == 1
        assert fees[0]["candidate_name"] == "Test Kandidat"
        assert fees[0]["employer_firma"] is None  # Beratung ohne Arbeitgeber
    finally:
        conn.close()


def test_list_termine(billing_db):
    conn = _conn(billing_db)
    try:
        billing.create_termin(conn, application_id=1, candidate_id=1, slot_at="2026-11-15T10:00")
        termine = billing.list_termine(conn, 1)
        assert len(termine) == 1
        assert termine[0]["job_titel"] == "Fachkraft"
        assert billing.list_termine(conn, 2) == []
    finally:
        conn.close()


# ─── Anzeige und Bankdaten ────────────────────────────────────────────

def test_format_eur():
    assert billing.format_eur(0) == "0,00 €"
    assert billing.format_eur(9_900) == "99,00 €"
    assert billing.format_eur(123_456) == "1.234,56 €"
    assert billing.format_eur(200_000) == "2.000,00 €"


def test_bankdaten_nur_aus_env(monkeypatch):
    for var in ("KMHR_BANK_HOLDER", "KMHR_BANK_NAME", "KMHR_BANK_IBAN", "KMHR_BANK_BIC"):
        monkeypatch.delenv(var, raising=False)
    d = billing.bank_details()
    assert d["configured"] is False
    assert d["iban"] == ""
    monkeypatch.setenv("KMHR_BANK_HOLDER", "Firma Mustermann")
    monkeypatch.setenv("KMHR_BANK_IBAN", "DE02120300000000202051")
    d2 = billing.bank_details()
    assert d2["configured"] is True
    assert d2["holder"] == "Firma Mustermann"


def test_billing_enabled_default_aus(monkeypatch):
    monkeypatch.delenv("KMHR_BILLING_ENABLED", raising=False)
    assert billing.billing_enabled() is False
    monkeypatch.setenv("KMHR_BILLING_ENABLED", "1")
    assert billing.billing_enabled() is True
    monkeypatch.setenv("KMHR_BILLING_ENABLED", "0")
    assert billing.billing_enabled() is False


# ─── Rechnungsnummern sind eindeutig ──────────────────────────────────

def test_rechnungsnummern_eindeutig(billing_db):
    conn = _conn(billing_db)
    try:
        billing.create_termin(conn, application_id=1, candidate_id=1, slot_at="2026-11-15T10:00")
        billing.create_visa_fees(conn, application_id=1, brutto_jahr_cents=400_000)
        nummern = [r[0] for r in conn.execute("SELECT invoice_number FROM billing_fees")]
        assert len(nummern) == len(set(nummern)) == 3
        assert all(n.startswith("KMHR-") for n in nummern)
    finally:
        conn.close()


def test_schema_mit_alle_migrations(billing_db):
    """Die Migration legt alle drei Teile an."""
    conn = _conn(billing_db)
    try:
        tabellen = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert "billing_fees" in tabellen
        assert "termin_buchungen" in tabellen
        spalten = {r[1] for r in conn.execute("PRAGMA table_info(jobs)")}
        assert "bruttojahresgehalt_eur" in spalten
        idx = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        assert "idx_billing_unique_app" in idx
    finally:
        conn.close()
