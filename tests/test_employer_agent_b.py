"""P0-2.4: DSGVO-Gate der HR-Dokumenten-Ansicht per pytest pruefen.

Deckt den offengebliebenen Teil von P0-2 ab: die Gate-Abfrage wurde nach
`_visible_documents(conn, employer_id, typ)` / `_blocked_candidates(conn, employer_id, typ)`
(webui/pages/employer.py:71 / :107) extrahiert, war aber bis hierher NICHT per
pytest abgesichert — employer.py:44 verwies auf diese Datei, sie existierte nicht.

Getestet werden die REINEN Funktionen mit explizitem `conn`, read-only gegen
data/feedback.db. tests/conftest.py leitet jeden data/feedback.db-Zugriff in
einen /tmp-Spiegel um; diese Tests schreiben ohnehin nie.

SCHEMA-FAKT: `applications` hat KEINE Spalte `employer_id`. Arbeitgeber-Bezug
ausschliesslich ueber `JOIN jobs j ON j.id = a.job_id ... j.employer_id = ?`.
Datenlage (read-only geprueft 30.09.2026): genau EIN Arbeitgeber (id=1),
candidate_documents: Kandidat 13 -> 3 (Zeugnis/Zertifikat/Pass), Kandidat 22 -> 1 (Zeugnis).
"""
import sqlite3
from pathlib import Path

import pytest

from webui.pages.employer import (
    DOC_RELEASE_STATUS,
    _blocked_candidates,
    _visible_documents,
)

ROOT = Path(__file__).resolve().parents[1]
LIVE_DB = ROOT / "data" / "feedback.db"

# Im Spiegel existiert nur Arbeitgeber 1; 999 ist ein bewusst "fremder"
# Arbeitgeber, fuer den es keine Bewerbung und damit keine Freigabe gibt.
FREMDER_ARBEITGEBER = 999


def _dokument_halter(conn) -> set:
    """Alle Kandidaten mit mindestens einem Dokument (unabhaengig von Gate)."""
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT candidate_id FROM candidate_documents")}


def _freigegeben(conn, employer_id: int) -> set:
    """NAIVE Referenz nach Spec-Regel (dsgvo-gate.md): Bewerbung mit
    eingeladen/eingestellt bei DIESEM Arbeitgeber — ohne Typ-Filter und ohne
    Klarname-Logik der Gate-Implementierung (also keine zirkulaere Erwartung).

    R6-0 (30.09.2026): vorher {13, 22}; Kandidat 22 verlor am 30.09. die
    freigebende Bewerbung #29 (abgelehnt, Live-Vorfall, Daten bleiben).
    """
    ph = ",".join("?" * len(DOC_RELEASE_STATUS))
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT a.candidate_id FROM applications a "
        "JOIN jobs j ON j.id = a.job_id "
        f"WHERE j.employer_id = ? AND a.status IN ({ph})",
        (employer_id, *DOC_RELEASE_STATUS))}


@pytest.fixture(scope="module")
def ro_conn():
    c = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    try:
        yield c
    finally:
        c.close()


# ─── Datenlage-Guard: sonst waeren die Erwartungen unten stillschweigend falsch ──

def test_datenlage_entspricht_der_annahme(ro_conn):
    doc_holder = {r[0] for r in ro_conn.execute(
        "SELECT DISTINCT candidate_id FROM candidate_documents")}
    # 04.10.2026: Kandidat 20 (Lena Marie Hoffmann) hat Dokumente erhalten → {13, 20, 22}.
    assert doc_holder == {13, 20, 22}, f"andere Dokument-Halter: {doc_holder}"
    assert set(DOC_RELEASE_STATUS) == {"eingeladen", "eingestellt"}


# ─── _visible_documents: Freigabe-Gate ──────────────────────────────────────

def test_freigabefall_arbeitgeber_1_sieht_dokumente_der_freigegebenen(ro_conn):
    docs = _visible_documents(ro_conn, 1)
    nach_kandidat = {}
    for d in docs:
        nach_kandidat.setdefault(d["candidate_id"], []).append(d)
    erwartet = _freigegeben(ro_conn, 1) & _dokument_halter(ro_conn)
    assert set(nach_kandidat) == erwartet, nach_kandidat.keys()
    assert 13 in erwartet and len(nach_kandidat[13]) == 3
    # R6-0: 29 am 30.09. abgelehnt -> Dokumente NICHT mehr sichtbar
    assert 22 not in erwartet, "22 hat keine freigebende Bewerbung mehr"


def test_fremder_arbeitgeber_sieht_nichts(ro_conn):
    assert _visible_documents(ro_conn, FREMDER_ARBEITGEBER) == []


def test_nur_freigegebene_bewerbungen_schenken_sichtbarkeit(ro_conn):
    """Jeder gelieferte Kandidat hat mindestens eine Bewerbung mit
    eingeladen/eingestellt BEI DIESEM Arbeitgeber — Nachweis unabhaengig von der
    Gate-Implementierung (erlaubt keine Kandidaten mit z.B. nur 'abgelehnt')."""
    ph = ",".join("?" * len(DOC_RELEASE_STATUS))
    erlaubt = {r[0] for r in ro_conn.execute(
        "SELECT DISTINCT a.candidate_id FROM applications a "
        "JOIN jobs j ON j.id = a.job_id "
        f"WHERE j.employer_id = ? AND a.status IN ({ph})", (1, *DOC_RELEASE_STATUS))}
    geliefert = {d["candidate_id"] for d in _visible_documents(ro_conn, 1)}
    assert geliefert <= erlaubt, f"nicht freigegeben, aber sichtbar: {geliefert - erlaubt}"
    # Robust statt Hardcode {13, 22}: sichtbar = freigegeben ∩ Dokument-Halter.
    assert geliefert == erlaubt & _dokument_halter(ro_conn)


def test_nicht_freigegebene_bewerber_sickern_nicht_durch(ro_conn):
    """Gegenprobe: Kandidaten 11/12 haben Bewerbungen bei Arbeitgeber 1, aber
    keine freigebende (`eingegangen`/`abgelehnt`) -> duerfen nicht sichtbar sein.
    Kandidat 17 hat zwar eine freigebende Bewerbung (app 25), aber KEINE
    Dokumente -> ebenfalls nicht sichtbar (Schnittmenge ist leer).
    (Datenlage read-only geprueft 30.09.2026; erste Fassung dieses Tests
    behauptete faelschlich, 17 habe keine freigebende Bewerbung.)"""
    ohne_freigabe = {r[0] for r in ro_conn.execute(
        "SELECT a.candidate_id FROM applications a JOIN jobs j ON j.id = a.job_id "
        "WHERE j.employer_id = 1 AND a.candidate_id IN (11,12,17) "
        "GROUP BY a.candidate_id "
        "HAVING SUM(CASE WHEN a.status IN ('eingeladen','eingestellt') THEN 1 ELSE 0 END) = 0")}
    assert ohne_freigabe == {11, 12}, ohne_freigabe
    sichtbar = {d["candidate_id"] for d in _visible_documents(ro_conn, 1)}
    assert not (sichtbar & ohne_freigabe)


def test_app_status_ist_die_hoechste_freigebende_bewerbung(ro_conn):
    """Kandidat 13: hoechste freigebende Bewerbung traegt den Doc-Satz.

    R6-5 (01.10.2026): 20/26 stehen seit 30.09. auf 'eingestellt'
    (HR-Klicks 11:59/12:08), 23 ist abgelehnt (nicht freigebend) ->
    app_status = 'eingestellt' (vorher 'eingeladen'). Kandidat 1 waere auch
    'eingestellt', hat aber keine Dokumente im Satz."""
    for d in _visible_documents(ro_conn, 1):
        assert d["app_status"] in DOC_RELEASE_STATUS
    assert {d["app_status"] for d in _visible_documents(ro_conn, 1)} == {"eingestellt"}


def test_keine_doppelten_zeilen_bei_mehreren_bewerbungen(ro_conn):
    """Kandidat 13 hat 3 Bewerbungen (23/20/26) -> 3 Dokumente, nicht 3x3."""
    docs = _visible_documents(ro_conn, 1)
    ids = [d["id"] for d in docs]
    assert len(ids) == len(set(ids)), f"Doppelte Dokument-IDs: {ids}"


def test_typenfilter_case_insensitive(ro_conn):
    erwartet_zeugnis = _freigegeben(ro_conn, 1) & {r[0] for r in ro_conn.execute(
        "SELECT DISTINCT candidate_id FROM candidate_documents "
        "WHERE dokumententyp LIKE 'Zeugnis%'")}
    zeugnis = _visible_documents(ro_conn, 1, "Zeugnis")
    assert {d["candidate_id"] for d in zeugnis} == erwartet_zeugnis
    klein = _visible_documents(ro_conn, 1, "zeugnis")
    assert klein == zeugnis, "Filter muss case-insensitive sein"
    nur_pass = _visible_documents(ro_conn, 1, "Pass")
    # 13 (Pass, freigegeben) sichtbar; 22 hat keinen Pass
    assert 13 in {d["candidate_id"] for d in nur_pass}
    assert _visible_documents(ro_conn, 1, "Sonstiges") == []


def test_alle_ist_kein_filter(ro_conn):
    assert _visible_documents(ro_conn, 1, "alle") == _visible_documents(ro_conn, 1)


def test_klarname_mit_fallback(ro_conn):
    for d in _visible_documents(ro_conn, 1):
        assert d["kandidat"] and d["kandidat"] != f"Kandidat #{d['candidate_id']}", \
            "erwartet Klarname (Live-DB hat Namen); Fallback nur fuer anonym"


# ─── _blocked_candidates: KEIN Datenleck ────────────────────────────────────

def test_blocked_nennt_nur_kandidaten_mit_bewerbung_bei_diesem_arbeitgeber(ro_conn):
    blockiert = _blocked_candidates(ro_conn, 1)
    mit_bewerbung = {r[0] for r in ro_conn.execute(
        "SELECT DISTINCT a.candidate_id FROM applications a "
        "JOIN jobs j ON j.id = a.job_id WHERE j.employer_id = 1")}
    for b in blockiert:
        assert b["candidate_id"] in mit_bewerbung, \
            f"Datenleck: {b['kandidat']} hat keine Bewerbung bei Arbeitgeber 1"


def test_blocked_deckt_genau_nicht_freigegebene_halter(ro_conn):
    """blocked == Dokument-Halter OHNE freigebende Bewerbung (Differenz).
    R6-0 (30.09.2026): vorher [] (13 UND 22 freigegeben); jetzt {22}, weil
    #29 abgelehnt wurde — der Gate reagiert korrekt auf die Datenlage."""
    erwartet = _dokument_halter(ro_conn) - _freigegeben(ro_conn, 1)
    blockiert = _blocked_candidates(ro_conn, 1)
    assert {b["candidate_id"] for b in blockiert} == erwartet
    assert erwartet == {22}, f"R6-0-Datenlage: erwartet {{22}}, ist {erwartet}"
    for b in blockiert:
        assert b["app_status"] not in DOC_RELEASE_STATUS


def test_blocked_bei_fremdem_arbeitgeber_leer_kein_leck(ro_conn):
    assert _blocked_candidates(ro_conn, FREMDER_ARBEITGEBER) == []


def test_blocked_nennt_typen_gefiltert(ro_conn):
    """Zeugnis-Blocked == Zeugnis-Halter ohne Freigabe (aktuell {22})."""
    erwartet = {r[0] for r in ro_conn.execute(
        "SELECT DISTINCT candidate_id FROM candidate_documents "
        "WHERE dokumententyp LIKE 'Zeugnis%'")} - _freigegeben(ro_conn, 1)
    blockiert = _blocked_candidates(ro_conn, 1, "Zeugnis")
    assert {b["candidate_id"] for b in blockiert} == erwartet
