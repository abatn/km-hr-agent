"""Consent-Nachweise (26.10.2026): Schema, Upsert, Widerruf, Historie.

Vertrag mit der UI: `CONSENT_VERSION`, `init_consents_table`, `record_consent`,
`withdraw_consent`, `get_consents` (webui/db.py). Kein Live-Zugriff: die Tests
arbeiten auf einer temporären DB (`db_path`) bzw. auf dem conftest-Spiegel
(Default-Pfad) — nie auf `data/feedback.db`.
"""
import json
import sqlite3

import pytest

from webui import db


def _tmp(tmp_path) -> str:
    """Frische DB mit consents-Tabelle (isoliert je Test)."""
    p = tmp_path / "consents.db"
    db.init_consents_table(p)
    return str(p)


# ─── Schema ──────────────────────────────────────────────────────────────

def test_init_ist_idempotent(tmp_path):
    p = tmp_path / "consents.db"
    db.init_consents_table(p)
    db.init_consents_table(p)  # zweiter Aufruf darf nicht scheitern
    conn = sqlite3.connect(str(p))
    try:
        spalten = {r[1] for r in conn.execute("PRAGMA table_info(consents)")}
        indizes = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='consents'")}
    finally:
        conn.close()
    assert spalten == {"id", "subject_type", "subject_id", "purpose", "text_version",
                       "granted_at", "form", "language", "channel", "withdrawn_at",
                       "evidence_json"}
    assert "idx_consents_subject" in indizes


def test_init_heilt_altbestand_ohne_neue_spalten(tmp_path):
    p = tmp_path / "alt.db"
    conn = sqlite3.connect(str(p))
    try:
        conn.execute("""CREATE TABLE consents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_type TEXT NOT NULL,
            subject_id INTEGER NOT NULL,
            purpose TEXT NOT NULL,
            text_version TEXT NOT NULL,
            granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(subject_type, subject_id, purpose, text_version))""")
        conn.execute("INSERT INTO consents (subject_type, subject_id, purpose, text_version) "
                     "VALUES ('candidate', 1, 'terms', '2026-01-01')")
        conn.commit()
    finally:
        conn.close()

    db.init_consents_table(p)
    db.init_consents_table(p)

    conn = sqlite3.connect(str(p))
    try:
        spalten = {r[1] for r in conn.execute("PRAGMA table_info(consents)")}
        anzahl = conn.execute("SELECT COUNT(*) FROM consents").fetchone()[0]
    finally:
        conn.close()
    assert {"form", "language", "channel", "withdrawn_at", "evidence_json"} <= spalten
    assert anzahl == 1  # Bestandsdaten bleiben erhalten

def test_schema_enthaelt_keine_pii_spalten(tmp_path):
    p = _tmp(tmp_path)
    conn = sqlite3.connect(p)
    try:
        spalten = {r[1].lower() for r in conn.execute("PRAGMA table_info(consents)")}
    finally:
        conn.close()
    # Datenminimierung: nur IDs/Zweck/Metadaten, keine Personendaten.
    for verboten in ("name", "vorname", "nachname", "email", "e_mail", "telefon",
                     "adresse", "geburtsdatum", "cv", "lebenslauf"):
        assert verboten not in spalten


# ─── record + get ────────────────────────────────────────────────────────

def test_record_und_get(tmp_path):
    p = _tmp(tmp_path)
    cid = db.record_consent("candidate", 7, "privacy", language="en",
                            channel="ui", evidence={"checkbox": "privacy-v3"}, db_path=p)
    assert isinstance(cid, int) and cid > 0

    zeilen = db.get_consents("candidate", 7, db_path=p)
    assert len(zeilen) == 1
    z = zeilen[0]
    assert z["id"] == cid
    assert z["subject_type"] == "candidate"
    assert z["subject_id"] == 7
    assert z["purpose"] == "privacy"
    assert z["text_version"] == db.CONSENT_VERSION == "2026-10-26"
    assert z["form"] == "electronic"
    assert z["language"] == "en"
    assert z["channel"] == "ui"
    assert z["granted_at"]
    assert z["withdrawn_at"] is None
    assert z["active"] is True
    assert json.loads(z["evidence_json"]) == {"checkbox": "privacy-v3"}


def test_get_ist_leer_fuer_unbekanntes_subjekt(tmp_path):
    p = _tmp(tmp_path)
    assert db.get_consents("employer", 999, db_path=p) == []


def test_employer_und_candidate_getrennt(tmp_path):
    p = _tmp(tmp_path)
    db.record_consent("candidate", 3, "terms", db_path=p)
    db.record_consent("employer", 3, "terms", db_path=p)
    assert len(db.get_consents("candidate", 3, db_path=p)) == 1
    assert len(db.get_consents("employer", 3, db_path=p)) == 1


# ─── Upsert (gleiche Textversion) ────────────────────────────────────────

def test_duplikat_ist_upsert_und_hebt_widerruf_auf(tmp_path):
    p = _tmp(tmp_path)
    cid = db.record_consent("candidate", 11, "talent_pool", db_path=p)
    assert db.withdraw_consent("candidate", 11, "talent_pool", db_path=p) is True

    cid2 = db.record_consent("candidate", 11, "talent_pool", language="fr",
                             channel="email", evidence={"mail": "opt-in"}, db_path=p)
    zeilen = db.get_consents("candidate", 11, db_path=p)
    assert cid2 == cid                # gleiche Zeile, kein Duplikat
    assert len(zeilen) == 1
    assert zeilen[0]["withdrawn_at"] is None
    assert zeilen[0]["active"] is True
    assert zeilen[0]["language"] == "fr"
    assert zeilen[0]["channel"] == "email"
    assert json.loads(zeilen[0]["evidence_json"]) == {"mail": "opt-in"}


def test_upsert_behaelt_beleg_ohne_neuen_beleg(tmp_path):
    p = _tmp(tmp_path)
    db.record_consent("candidate", 12, "privacy", evidence={"a": 1}, db_path=p)
    db.record_consent("candidate", 12, "privacy", db_path=p)  # evidence=None
    z = db.get_consents("candidate", 12, db_path=p)[0]
    assert json.loads(z["evidence_json"]) == {"a": 1}


def test_neue_textversion_erzeugt_neue_zeile(tmp_path):
    p = _tmp(tmp_path)
    db.record_consent("candidate", 13, "terms", text_version="2026-01-01", db_path=p)
    db.record_consent("candidate", 13, "terms", text_version="2026-10-26", db_path=p)
    zeilen = db.get_consents("candidate", 13, db_path=p)
    assert [z["text_version"] for z in zeilen] == ["2026-01-01", "2026-10-26"]
    assert all(z["active"] for z in zeilen)


# ─── Widerruf ────────────────────────────────────────────────────────────

def test_withdraw_setzt_nur_withdrawn_at(tmp_path):
    p = _tmp(tmp_path)
    db.record_consent("candidate", 21, "special_category", db_path=p)
    assert db.withdraw_consent("candidate", 21, "special_category", db_path=p) is True

    zeilen = db.get_consents("candidate", 21, db_path=p)
    assert len(zeilen) == 1                  # Nachweis bleibt erhalten
    assert zeilen[0]["withdrawn_at"]
    assert zeilen[0]["active"] is False
    assert zeilen[0]["granted_at"]           # Erteilung bleibt dokumentiert
    # zweiter Widerruf ändert nichts mehr
    assert db.withdraw_consent("candidate", 21, "special_category", db_path=p) is False


def test_withdraw_ohne_eintrag_ist_false(tmp_path):
    p = _tmp(tmp_path)
    assert db.withdraw_consent("employer", 5, "marketing", db_path=p) is False


def test_withdraw_trifft_nur_den_zweck(tmp_path):
    p = _tmp(tmp_path)
    db.record_consent("candidate", 22, "terms", db_path=p)
    db.record_consent("candidate", 22, "marketing", db_path=p)
    assert db.withdraw_consent("candidate", 22, "marketing", db_path=p) is True
    offen = {z["purpose"] for z in db.get_consents("candidate", 22, db_path=p) if z["active"]}
    assert offen == {"terms"}


# ─── Vertragsprüfung ─────────────────────────────────────────────────────

@pytest.mark.parametrize("subject_type,purpose", [
    ("admin", "terms"),
    ("candidate", "newsletter"),
])
def test_unbekannte_werte_werden_abgelehnt(tmp_path, subject_type, purpose):
    p = _tmp(tmp_path)
    with pytest.raises(ValueError):
        db.record_consent(subject_type, 1, purpose, db_path=p)


def test_subject_id_muss_positiv_sein(tmp_path):
    p = _tmp(tmp_path)
    with pytest.raises(ValueError):
        db.record_consent("candidate", 0, "terms", db_path=p)


def test_language_muss_unterstuetzt_sein(tmp_path):
    p = _tmp(tmp_path)
    with pytest.raises(ValueError):
        db.record_consent("candidate", 1, "terms", language="xx", db_path=p)


# ─── Integration: conftest-Spiegel (Default-Pfad) ────────────────────────

def test_default_pfad_nutzt_spiegel_mit_tabelle():
    # init_consents_table() laeuft in tests/conftest.py auf den Spiegel;
    # hier ohne db_path -> beweist die App-Start-Paritat.
    db.init_consents_table()
    cid = db.record_consent("candidate", 424242, "language_test")
    zeilen = db.get_consents("candidate", 424242)
    assert [z["id"] for z in zeilen] == [cid]
    assert db.withdraw_consent("candidate", 424242, "language_test") is True
