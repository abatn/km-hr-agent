"""N-K1 (01.10.2026): Kandidaten-Suche — Filterwerte in Klartext, nur reale Status.

Befund: `ergebnisse/ui-analyse-2026-09-29.md:65` — „Kandidaten-Suche … Dropdown zeigt
DB-Slug `lebenslauf_hochgeladen` (`:522`) weiter (N-K1)“.

Soll (Nutzer-Befund N-K1, 01.10.2026):
  1. Beschriftung = Klartext über `status_label()` (EINE Quelle: `components.STATUS_LABELS`),
  2. Optionswerte = **nur** Status, die real in der DB vorkommen (keine toten Filteroptionen),
  3. kein DB-Slug in der Anzeige.
Regel: `knowledge/ui-design-system.md` §11 „Dropdown-/Filter-Optionen“.

Reine Funktionen (`_cand_status_options`, `_list_candidates`) + Quelltext-Inspektion;
DB-Zugriff read-only über den conftest-Spiegel (keine Writes, keine UI).
"""
from pathlib import Path

from webui import db
from webui.components import status_label
from webui.pages import employer as emp

SRC = (Path(__file__).resolve().parents[1] / "webui" / "pages" / "employer.py"
       ).read_text(encoding="utf-8")


def _pool_counts(conn) -> dict:
    ph = ",".join("?" * len(emp.CAND_CV_STATUS))
    return dict(conn.execute(
        f"SELECT status, COUNT(*) FROM candidates WHERE status IN ({ph}) "
        "GROUP BY status", list(emp.CAND_CV_STATUS)).fetchall())


def _opts() -> dict:
    conn = db.get_conn()
    try:
        return emp._cand_status_options(conn)
    finally:
        conn.close()


def test_sammelwert_ist_erste_option():
    opts = _opts()
    assert list(opts)[0] == "alle"
    assert opts["alle"] == emp.CAND_POOL_ALL_LABEL == "Alle mit Lebenslauf"


def test_nur_real_vorkommende_pool_status():
    conn = db.get_conn()
    try:
        counts = _pool_counts(conn)
    finally:
        conn.close()
    opts = _opts()
    werte = [k for k in opts if k != "alle"]
    assert werte, "kein einziger realer Pool-Status angeboten"
    for st in werte:
        assert st in emp.CAND_CV_STATUS, st
        assert counts.get(st, 0) > 0, f"tote Option: {st} kommt real nicht vor"
    # Gegenrichtung: kein realer Pool-Status fehlt
    assert set(werte) == {s for s, n in counts.items() if n}


def test_labels_sind_klartext_und_nie_der_slug():
    for value, label in _opts().items():
        assert label, value
        assert "_" not in label, f"Slug in der Anzeige: {label!r}"
        if value != "alle":
            assert label == status_label(value), (value, label)


def test_jede_option_liefert_treffer():
    """Keine Option ohne Ergebnis: jeder angebotene Status hat Kandidaten im Pool."""
    conn = db.get_conn()
    try:
        for st in [k for k in emp._cand_status_options(conn) if k != "alle"]:
            assert emp._list_candidates(conn, 1, st), f"Option {st} liefert 0 Zeilen"
    finally:
        conn.close()


def test_quelltext_keine_zweite_label_kopie_und_kein_slug_options():
    assert "CAND_STATUS_LABELS" not in SRC, "zweite Klartext-Kopie darf nicht zurückkehren"
    assert "options=_status_options," in SRC
    assert "opts[st] = status_label(st)" in SRC
    # die Kandidaten-Suche darf keine Slug-Liste als Optionen rendern
    assert 'options=["alle", "lebenslauf_hochgeladen"' not in SRC
    assert 'options=["alle", "zugeordnet"' not in SRC
