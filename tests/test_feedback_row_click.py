"""M-07 (01.10.2026): Klickziel je Tabellenzeile.

Befund: `ergebnisse/ui-analyse-2026-09-29.md:84` — Zeilen ohne Klickziel
(vorher 19: 9× Kandidaten-Suche + 10× Feedback). Ursache: `components.data_table()`
setzte nie `selection`, daher blieb `on_select` wirkungslos
(`nicegui/elements/table.py:77` → `selection or 'none'`).

Regel: `knowledge/ui-design-system.md` §11.1 „Klickziel je Tabellenzeile“.
Soll:
  1. `data_table(on_row_click=…)` setzt `selection="single"`.
  2. Feedback-Zeile auflösbar → Kandidaten-ID (Sprung zur Match-Seite),
     nicht auflösbar (Altbestand) → `None` (Detail-Dialog).

Reine Funktionen (`_feedback_klarname`, `_feedback_row_cid`) + Quelltext-Inspektion;
DB-Zugriff read-only über den conftest-Spiegel (keine Writes, keine UI).
"""
import re
from pathlib import Path

from webui import db
from webui.pages import employer as emp

_ROOT = Path(__file__).resolve().parents[1]
SRC_EMP = (_ROOT / "webui" / "pages" / "employer.py").read_text(encoding="utf-8")
SRC_COMP = (_ROOT / "webui" / "components.py").read_text(encoding="utf-8")


# ─── _feedback_klarname ───────────────────────────────────────────────────

def test_klarname_leer_und_kandidat_marker():
    nbi = {2: "Sirine Ilahi"}
    assert emp._feedback_klarname("", nbi) == "--"
    assert emp._feedback_klarname(None, nbi) == "--"
    assert emp._feedback_klarname("Kandidat #2", nbi) == "Sirine Ilahi"
    # unbekannte Nummer → unverändert (keine Erfindung)
    assert emp._feedback_klarname("Kandidat #99", nbi) == "Kandidat #99"


def test_klarname_altbestand_markdown_name():
    # Altbestand: '**Name:** Anna Schuster' → 'Anna Schuster'
    assert emp._feedback_klarname("**Name:** Anna Schuster", {}) == "Anna Schuster"
    # normaler Name bleibt unverändert
    assert emp._feedback_klarname(" batnini abdelkader ", {}) == "batnini abdelkader"


# ─── _feedback_row_cid: 3 Stufen ──────────────────────────────────────────

def _maps(*pairs):
    nbi = {cid: nm for cid, nm in pairs}
    nti, ti = {}, {}
    for cid, nm in pairs:
        if not nm:
            continue
        nti.setdefault(nm.strip().casefold(), cid)
        toks = tuple(sorted(t for t in re.split(r"\s+", nm.casefold()) if t))
        ti.setdefault(toks, []).append(cid)
    return nbi, nti, ti


def test_stufe1_vorgangsnummer_gewinnt():
    nbi, nti, ti = _maps((7, "Sirine Ilahi"))
    cid = emp._feedback_row_cid("employer-job-1-cand-7-2026-09-28", "egal", nbi, nti, ti)
    assert cid == 7


def test_stufe1_faellt_durch_wenn_id_unbekannt_dann_name():
    nbi, nti, ti = _maps((7, "Sirine Ilahi"))
    # Vorgangs-ID 99 existiert nicht → Stufe 2 (exakter Name) greift
    cid = emp._feedback_row_cid("employer-job-1-cand-99-x", "Sirine Ilahi", nbi, nti, ti)
    assert cid == 7


def test_stufe2_exakter_name_case_insensitiv():
    nbi, nti, ti = _maps((5, "Anna Schuster"))
    # kein -cand- in match_id (Altbestand profil-…)
    cid = emp._feedback_row_cid("profil---anna-schuster-2026-09-28", "anna schuster", nbi, nti, ti)
    assert cid == 5


def test_stufe3_token_menge_reihenfolge_tolerant():
    # Kandidat #1 heißt "batnini abdelkader", Feedback speicherte "Abdelkader Batnini"
    nbi, nti, ti = _maps((1, "batnini abdelkader"))
    cid = emp._feedback_row_cid("", "Abdelkader Batnini", nbi, nti, ti)
    assert cid == 1


def test_stufe3_mehrdeutig_ist_none_kein_raten():
    # zwei Kandidaten mit identischer Token-Menge {max,muster} → nicht eindeutig
    nbi, nti, ti = _maps((1, "Max Muster"), (2, "Muster Max"))
    # exakter Name trifft eindeutig (#2 casefold == 'muster max')
    assert emp._feedback_row_cid("", "muster max", nbi, nti, ti) == 2
    # Doppel-Leerzeichen: kein exakter Treffer, Token-Menge aber mehrdeutig → None
    assert emp._feedback_row_cid("", "Muster  Max", nbi, nti, ti) is None


def test_altbestand_ohne_kandidat_ist_none():
    nbi, nti, ti = _maps((1, "batnini abdelkader"))
    cid = emp._feedback_row_cid(
        "profil---**name:**-anna-schuster-2026-09-28", "**Name:** Anna Schuster",
        nbi, nti, ti)
    assert cid is None


# ─── Invariante gegen den read-only DB-Spiegel ────────────────────────────

def test_resolver_ids_sind_echte_kandidaten():
    conn = db.get_conn()
    try:
        rows = conn.execute("SELECT match_id, kandidat_name FROM feedback").fetchall()
        pairs = conn.execute("SELECT id, name FROM candidates").fetchall()
    finally:
        conn.close()
    nbi, nti, ti = _maps(*pairs)
    for mid, nm in rows:
        cid = emp._feedback_row_cid(mid, nm, nbi, nti, ti)
        assert cid is None or cid in nbi, (mid, nm, cid)


def test_none_zeilen_sind_wirklich_nicht_aufloesbar():
    """Kein None-Ergebnis darf in Wahrheit auflösbar sein (kein Fall verpasst)."""
    conn = db.get_conn()
    try:
        rows = conn.execute("SELECT match_id, kandidat_name FROM feedback").fetchall()
        pairs = conn.execute("SELECT id, name FROM candidates").fetchall()
    finally:
        conn.close()
    nbi, nti, ti = _maps(*pairs)
    for mid, nm in rows:
        if emp._feedback_row_cid(mid, nm, nbi, nti, ti) is not None:
            continue
        klarname = emp._feedback_klarname(nm, nbi)
        # weder exakter Name noch eindeutige Token-Menge vorhanden
        assert nti.get(klarname.strip().casefold()) is None, (mid, nm)
        toks = tuple(sorted(t for t in re.split(r"\s+", klarname.casefold()) if t))
        assert len(ti.get(toks) or []) != 1, (mid, nm)


# ─── Quelltext-Regeln ─────────────────────────────────────────────────────

def test_data_table_aktiviert_selection_bei_row_click():
    assert 'selection="single" if on_row_click else None' in SRC_COMP, (
        "data_table muss selection setzen, sonst ist on_select wirkungslos")
    assert "on_select=on_row_click" in SRC_COMP


def test_feedback_tabelle_und_zeilen_click_verdrahtet():
    assert "on_row_click=_zeile_geklickt" in SRC_EMP
    assert "def _zeile_geklickt(e):" in SRC_EMP
    assert "_feedback_row_cid(" in SRC_EMP
    assert "/employer/match?kandidat=" in SRC_EMP


def test_feedback_zeile_hat_sichtbares_klickziel():
    # Muster wie Kandidaten-Suche: Namens-Knopf feuert die Auswahl
    assert 'add_slot("body-cell-name"' in SRC_EMP
    assert "$el.closest('tr').querySelector('.q-checkbox').click()" in SRC_EMP
    # data_table muss die Tabelle zurueckgeben, damit der Slot gesetzt werden kann
    assert "return result" in SRC_COMP
    assert "result = table" in SRC_COMP
