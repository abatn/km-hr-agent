"""P1-11 (30.09.2026): stille Fehler.

BEFUND im Altstand:
  * `db.insert_document` hatte `except Exception: return False` — die Ausnahme
    wurde vollstaendig verworfen, weder Log noch Meldung.
  * `db.insert_job` hatte `except Exception: return None` — dito.
  * Der Aufrufer `candidate.py::on_multi_upload` hat den Rueckgabewert von
    `insert_document` IGNORIERT und pauschal „N Dokument(e) gespeichert"
    gemeldet — auch wenn kein einziges Dokument in der DB landete.
  * `db.get_documents` protokollierte bereits (`print(f"[db] ...")`) — die
    Konvention, der die beiden Inserts jetzt folgen.

Alle Tests laufen ueber tests/conftest.py gegen den /tmp-Spiegel; die
Live-DB wird nie beschrieben. Fuer die Fehlerwege wird sqlite3.connect im
Modul webui.db kurzzeitig ersetzt — deterministisch, ohne die DB zu beruehren.
"""
import sqlite3
from pathlib import Path

import pytest

from webui import db

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def boom(monkeypatch, capsys):
    """Lass jeden DB-Zugriff in webui.db scheitern."""
    def _explode(*a, **k):
        raise sqlite3.OperationalError("P1-11 Testfehler")
    monkeypatch.setattr(db.sqlite3, "connect", _explode)
    return capsys


# ─── insert_document ───────────────────────────────────────────────────────

def test_insert_document_meldet_erfolg_im_normalfall():
    assert db.insert_document(13, str(ROOT / "testdaten" / "x.pdf"), "Zeugnis") is True


def test_insert_document_protokolliert_den_fehler(boom):
    assert db.insert_document(13, "/tmp/x.pdf", "Zeugnis") is False
    cap = boom.readouterr()   # einmal lesen: der Puffer wird geleert
    err = cap.err + cap.out
    assert "insert_document" in err, err
    assert "P1-11 Testfehler" in err, err


def test_kein_stilles_schlucken_mehr_in_db_py():
    """Kein `except Exception:` OHNE Verarbeitung der Ausnahme (nur Docstrings
    duerfen das noch erwaehnen — die werden hier ausgezaehlt)."""
    import re
    src = (ROOT / "webui" / "db.py").read_text(encoding="utf-8")
    # echte Handler = Zeile mit except Exception: gefolgt von Einrueckung
    echt = re.findall(r"^\s+except Exception:\s*$", src, re.M)
    assert not echt, f"{len(echt)} stille Exception-Handler: {echt}"
    assert len(re.findall(r"^\s+except Exception as ex:\s*$", src, re.M)) >= 8


# ─── insert_job ────────────────────────────────────────────────────────────

def test_insert_job_protokolliert_den_fehler(boom):
    r = db.insert_job(1, "T", "B" * 60, "Berlin", "DE", "Vollzeit",
                      "Python", "", 3, "B1", "B1", "Bachelor", 1, 2)
    assert r is None
    cap = boom.readouterr()
    err = cap.err + cap.out
    assert "insert_job" in err, err
    assert "P1-11 Testfehler" in err, err


def test_insert_job_meldet_id_im_normalfall():
    r = db.insert_job(1, "P1-11 Job", "B" * 60, "Berlin", "DE", "Vollzeit",
                      "Python", "", 3, "B1", "B1", "Bachelor", 1, 2)
    assert isinstance(r, int) and r > 0


# ─── Aufrufer: keine Erfolgsmeldung ohne tatsächlichen Erfolg ──────────────

def test_upload_meldet_erfolg_nur_wenn_gespeichert():
    src = (ROOT / "webui" / "pages" / "candidate.py").read_text(encoding="utf-8")
    block = src[src.index("async def on_multi_upload"):]
    block = block[:block.index("ui.upload(")]
    assert "if db.insert_document(" in block, "Rueckgabewert wird nicht geprueft"
    assert "ok_liste" in block and "fehler_liste" in block
    # die pauschale Meldung ohne Pruefung darf nicht mehr vorkommen
    assert "ui.notify(f\"{len(e.files)} Dokument(e) gespeichert" not in block
    # und ein Fehlerfall wird sichtbar gemeldet
    assert 'type="negative"' in block
    assert "konnten NICHT gespeichert werden" in block
