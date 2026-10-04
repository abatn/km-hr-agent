"""A3 (30.09.2026): Profil speichern (webui/pages/candidate.py::save_profile_fields, profil_optionen).

Keine UI, KEIN Schreiben in die Live-DB: das echte Schema von `candidates` wird über die
(per tests/conftest.py auf den Spiegel umgeleitete) DB nur GELESEN und in einer
In-Memory-DB nachgebaut; alle Schreibzugriffe laufen dort.
"""
import re
import sqlite3
from pathlib import Path

import pytest

from webui import db
from webui.pages import candidate as cand

SRC = (Path(__file__).resolve().parent.parent / "webui" / "pages" / "candidate.py").read_text(encoding="utf-8")

ALLE = ("standort", "nationalitaet", "visum_status", "verfuegbarkeit", "aktuelle_position",
        "berufserfahrung_jahre", "hard_skills", "soft_skills", "abschluss", "deutsch",
        "englisch", "gehaltsvorstellung")


def _schema_sql() -> str:
    src = db.get_conn()  # per conftest -> Spiegel (nur Lesen)
    try:
        return src.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='candidates'").fetchone()[0]
    finally:
        src.close()


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.execute(_schema_sql())
    c.execute("INSERT INTO candidates (id, email, password_hash, name, status) "
              "VALUES (1, 't@example.org', 'x', 'Test', 'registriert')")
    # Schema-Defaults ('EU-Bürger','Sofort','B1') sind NICHT Teil dieses Tests: NULLen,
    # damit "NULL bleibt NULL" eindeutig prüfbar ist.
    c.execute("UPDATE candidates SET visum_status=NULL, verfuegbarkeit=NULL, deutsch=NULL, englisch=NULL")
    yield c
    c.close()


def _row(c, cols=ALLE) -> dict:
    r = c.execute(f"SELECT {', '.join(cols)} FROM candidates WHERE id=1").fetchone()
    return dict(zip(cols, r))


def _form_aus_db(c) -> dict:
    """Simuliert das Formular: Startwerte = Bestand (NULL -> None), wie in _tab_profil."""
    return _row(c)


# ── (a) keine erfundenen Defaults ──────────────────────────────────────

def test_null_bleibt_null(conn):
    assert all(v is None for v in _row(conn).values())
    cand.save_profile_fields(conn, 1, _form_aus_db(conn))
    assert all(v is None for v in _row(conn).values()), _row(conn)


def test_leere_eingaben_werden_null_nicht_leerstring_oder_default(conn):
    werte = {c: None for c in ALLE}
    werte.update(standort="  ", aktuelle_position="", hard_skills="", soft_skills=" ",
                 berufserfahrung_jahre="", gehaltsvorstellung=None)
    cand.save_profile_fields(conn, 1, werte)
    assert all(v is None for v in _row(conn).values()), _row(conn)


def test_deutsch_c1_bleibt_beim_speichern_anderer_felder(conn):
    conn.execute("UPDATE candidates SET deutsch='C1', englisch='B2', verfuegbarkeit='3 Monate', "
                 "berufserfahrung_jahre=5, gehaltsvorstellung=1500 WHERE id=1")
    werte = _form_aus_db(conn)
    werte["standort"] = "Berlin"  # nur ein anderes Feld ändern
    cand.save_profile_fields(conn, 1, werte)
    r = _row(conn)
    assert r["deutsch"] == "C1" and r["englisch"] == "B2"
    assert r["verfuegbarkeit"] == "3 Monate"
    assert r["berufserfahrung_jahre"] == 5 and r["gehaltsvorstellung"] == 1500
    assert r["standort"] == "Berlin"


def test_bewusste_null_zahl_bleibt_null_bewusste_0_bleibt_0(conn):
    w = _form_aus_db(conn)
    w["berufserfahrung_jahre"] = 0  # Nutzer gibt explizit 0 ein
    cand.save_profile_fields(conn, 1, w)
    r = _row(conn)
    assert r["berufserfahrung_jahre"] == 0 and r["gehaltsvorstellung"] is None


def test_quelltext_keine_erfundenen_defaults_im_formular():
    profil = SRC[SRC.index("def _tab_profil"):SRC.index("def _tab_stellen")]
    assert 'or "Sofort"' not in profil and 'or "B1"' not in profil
    assert "or 0)" not in profil.split("def save_profile")[1].split("navigate_to")[0]


# ── (b) kein Datenleck / aktueller Wert immer in Optionen ──────────────

def test_keine_select_distinct_ueber_alle_kandidaten():
    profil = SRC[SRC.index("def _tab_profil"):SRC.index("def _tab_stellen")]
    profil = "\n".join(z for z in profil.splitlines() if not z.strip().startswith("#"))  # Kommentare ausnehmen
    assert "SELECT DISTINCT" not in profil.upper()
    assert "FROM candidates" in profil  # die eigene Zeile (WHERE id = ?)
    # jede Abfrage auf candidates in _tab_profil ist auf die eigene ID beschränkt
    assert not re.search(r"FROM candidates(?! WHERE id)", profil), \
        "Abfrage über ALLE Kandidaten in _tab_profil"


def test_optionen_fest_und_aktueller_wert_ergaenzt():
    assert cand.profil_optionen(cand.PROFIL_ABSCHLUSS_OPTIONEN, None) == cand.PROFIL_ABSCHLUSS_OPTIONEN
    assert cand.profil_optionen(cand.PROFIL_ABSCHLUSS_OPTIONEN, "") == cand.PROFIL_ABSCHLUSS_OPTIONEN
    # Freitext aus der CV-Extraktion bleibt wählbar (sonst ValueError in ui.select / Wertverlust)
    frei = "Master of Research in Embedded Systems"
    opts = cand.profil_optionen(cand.PROFIL_ABSCHLUSS_OPTIONEN, frei)
    assert frei in opts and set(cand.PROFIL_ABSCHLUSS_OPTIONEN) <= set(opts)
    # Wert bereits enthalten -> keine Dopplung
    assert cand.profil_optionen(cand.PROFIL_SPRACHNIVEAUS, "C1").count("C1") == 1
    # Basisliste wird nicht mutiert
    assert frei not in cand.PROFIL_ABSCHLUSS_OPTIONEN


def test_optionen_enthalten_keine_fremden_kandidatenwerte(conn):
    # zweiter Kandidat mit Freitext -> darf NICHT in den Optionen des ersten auftauchen
    conn.execute("INSERT INTO candidates (id, email, password_hash, name, abschluss, visum_status) "
                 "VALUES (2, 'f@example.org', 'x', 'Fremd', 'Geheime Schule XY', 'Sonderstatus')")
    eigener = conn.execute("SELECT abschluss, visum_status FROM candidates WHERE id=1").fetchone()
    assert "Geheime Schule XY" not in cand.profil_optionen(cand.PROFIL_ABSCHLUSS_OPTIONEN, eigener[0])
    assert "Sonderstatus" not in cand.profil_optionen(cand.PROFIL_VISUM_OPTIONEN, eigener[1])


def test_bestehender_freitext_bleibt_beim_speichern(conn):
    conn.execute("UPDATE candidates SET abschluss='M.Sc. Informatik – TU München', "
                 "visum_status='Visum erforderlich' WHERE id=1")
    cand.save_profile_fields(conn, 1, _form_aus_db(conn))
    r = _row(conn)
    assert r["abschluss"] == "M.Sc. Informatik – TU München"
    assert r["visum_status"] == "Visum erforderlich"


# ── (d) Französisch nur wenn Spalte existiert ──────────────────────────

def test_franzoesisch_ohne_spalte_wird_ignoriert(conn):
    assert "franzoesisch" not in {r[1] for r in conn.execute("PRAGMA table_info(candidates)")}
    w = _form_aus_db(conn)
    w["franzoesisch"] = "B1"
    cand.save_profile_fields(conn, 1, w)  # darf nicht werfen (no such column)
    assert "franzoesisch" not in _row(conn)


def test_franzoesisch_mit_spalte_wird_gespeichert_und_null_bleibt_null(conn):
    conn.execute("ALTER TABLE candidates ADD COLUMN franzoesisch TEXT")
    w = _form_aus_db(conn)
    w["franzoesisch"] = None
    cand.save_profile_fields(conn, 1, w)
    assert _row(conn, ("franzoesisch",))["franzoesisch"] is None
    w["franzoesisch"] = "B2"
    cand.save_profile_fields(conn, 1, w)
    assert _row(conn, ("franzoesisch",))["franzoesisch"] == "B2"


# ── Status-Verhalten unverändert ───────────────────────────────────────

def test_status_ohne_cv_profil_vollstaendig(conn):
    cand.save_profile_fields(conn, 1, _form_aus_db(conn))
    assert conn.execute("SELECT status FROM candidates WHERE id=1").fetchone()[0] == "profil_vollstaendig"


def test_status_mit_cv_lebenslauf_hochgeladen_und_spaeterer_status_bleibt(conn):
    conn.execute("UPDATE candidates SET lebenslauf_text='CV' WHERE id=1")
    cand.save_profile_fields(conn, 1, _form_aus_db(conn))
    assert conn.execute("SELECT status FROM candidates WHERE id=1").fetchone()[0] == "lebenslauf_hochgeladen"
    conn.execute("UPDATE candidates SET status='eingeladen' WHERE id=1")
    cand.save_profile_fields(conn, 1, _form_aus_db(conn))
    assert conn.execute("SELECT status FROM candidates WHERE id=1").fetchone()[0] == "eingeladen"
