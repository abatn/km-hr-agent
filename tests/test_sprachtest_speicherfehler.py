"""Sprachtest-Speicherfehler — isoliert, ohne Einfluss auf die geteilte Spiegel-DB.

Ersatz für den früheren E2E-Teil D (`tests/e2e_sprachtest_flow.py`), der die
gemeinsam genutzte Spiegel-DB per `chmod 444` schreibgeschützt und dadurch
Folgeskripte mit `attempt to write a readonly database` vergiftet hat.

Zwei Ebenen, beide real:

1. `test_insert_language_test_echter_schreibfehler` — echter SQLite-Schreibfehler
   gegen eine eigene Temp-DB (Dateirechte 0444). Kein Mock: `db.insert_language_test`
   liefert laut Vertrag `None` bei Fehlern. Nach `chmod 0644` schreibt sie genau
   eine Zeile.

2. `test_speicherfehler_karte_und_retry` — echte UI (NiceGUI-`user`-Fixture,
   in-process, ohne Browser) gegen dieselbe Temp-DB. Die Rechte werden erst
   unmittelbar vor dem Speichern entzogen (Seitenaufbau/Audit bleiben intakt,
   wie im echten Betrieb), dann: Fehlerkarte, keine Zeile; Rechte zurück ->
   „Erneut speichern" -> genau eine Zeile.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from nicegui import ui

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from webui import db  # noqa: E402

CAND_ID = 1
N_FRAGEN = 10


def _kopie(tmp_path: Path) -> Path:
    """Spiegel-DB (conftest) in eine eigene Temp-DB kopieren (nie die Live-DB)."""
    ziel = tmp_path / "fault.db"
    src = sqlite3.connect(str(db.DB_PATH))
    dst = sqlite3.connect(str(ziel))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    return ziel


def _zeilen(pfad: Path) -> int:
    conn = sqlite3.connect(str(pfad))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM language_tests WHERE candidate_id=?", (CAND_ID,)
        ).fetchone()[0]
    finally:
        conn.close()


def _speichern() -> int | None:
    return db.insert_language_test(
        candidate_id=CAND_ID, sprache="Deutsch", niveau="A1",
        fragen_anzahl=N_FRAGEN, punkte=1.0, cefr_level="C1", details="{}")


def test_insert_language_test_echter_schreibfehler(tmp_path, monkeypatch):
    """Echter Schreibfehler (0444) -> None und keine Zeile; 0644 -> genau eine Zeile."""
    pfad = _kopie(tmp_path)
    monkeypatch.setattr(db, "DB_PATH", pfad)
    vorher = _zeilen(pfad)

    os.chmod(pfad, 0o444)
    try:
        assert _speichern() is None
        assert _zeilen(pfad) == vorher
    finally:
        os.chmod(pfad, 0o644)

    assert isinstance(_speichern(), int)
    assert _zeilen(pfad) == vorher + 1


def _antwort_waehlen(user, index: int = 0) -> None:
    """Erste Antwortoption wählen (Wert = Optionsindex, `candidate.py::on_select`)."""
    radios = list(user.find(kind=ui.radio).elements)
    assert radios, "kein Radio auf der Seite"
    with user.client:
        radios[0].value = index


async def test_speicherfehler_karte_und_retry(user, tmp_path, monkeypatch):
    """UI-Pfad: read-only DB -> Fehlerkarte, keine Zeile; danach Retry schreibt."""
    pfad = _kopie(tmp_path)
    monkeypatch.setattr(db, "DB_PATH", pfad)
    monkeypatch.setattr(db, "get_conn", lambda *a, **k: sqlite3.connect(str(pfad)))

    vorher = _zeilen(pfad)
    gesperrt = False
    try:
        await user.open("/sprachtest-speicherfehler")
        user.find(kind=ui.button, content="Test starten").click()
        await user.should_see(f"Frage 1/{N_FRAGEN}", retries=300)

        for k in range(1, N_FRAGEN + 1):
            _antwort_waehlen(user)
            if k == N_FRAGEN:
                # Erst unmittelbar vor dem Speichern sperren: Seitenaufbau und
                # Audit-Schreibvorgänge davor sind Teil des echten Betriebs.
                os.chmod(pfad, 0o444)
                gesperrt = True
            user.find(kind=ui.button, content="Weiter →").click()
            if k < N_FRAGEN:
                await user.should_see(f"Frage {k + 1}/{N_FRAGEN}", retries=300)

        await user.should_see("Ergebnis konnte nicht gespeichert werden", retries=300)
        await user.should_not_see("Test beendet!")
        assert _zeilen(pfad) == vorher
    finally:
        if gesperrt:
            os.chmod(pfad, 0o644)

    user.find(kind=ui.button, content="Erneut speichern").click()
    await user.should_see("Test beendet!", retries=300)
    assert _zeilen(pfad) == vorher + 1
