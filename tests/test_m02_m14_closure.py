"""M-02 + M-14 (01.10.2026): MD-Klärung „Fix → schließen".

Beide Befunde der Master-Liste (28.09.) galten in `ui-analyse-2026-09-29.md`
als „offen/MD-Klärung". Dieser Test friert den Ist-Stand ein, damit die
Schließungs-Entscheidung (`ergebnisse/entscheidungen.md`) reproduzierbar bleibt.

M-02 (Termin sichtbar, P0):
  1. `candidate.py` liest den Task-Schlüssel `termin` VOR dem Payload-Paar
     `termin_datum`/`termin_uhrzeit` (nur so erscheint der Termin, wenn das
     Ergebnis `termin` liefert).
  2. Der frühere stille `except` der Bewerbungsliste (Nebensatz ui-analyse:129)
     ist seit R5-1 (30.09.2026) nicht mehr stumm: `_log.exception(...)` +
     sichtbare Fehlerzeile + „Erneut versuchen"-Knopf. Kein `pass`-Rumpf,
     kein `except:` ohne Namen in der Datei.

M-14 (Feedback-Namensauflösung, P2):
  1. `_feedback_klarname` (früher `_feedback_name`) löst Altbestand
     `**Name:** …` und `Kandidat #N` über die `candidates`-Namen auf.
  2. Der Alt-Name `_feedback_name` existiert nicht mehr (MD-Fundort veraltet).
"""
import re
from pathlib import Path

from webui.pages import employer as emp

_ROOT = Path(__file__).resolve().parents[1]
SRC_CAND = (_ROOT / "webui" / "pages" / "candidate.py").read_text(encoding="utf-8")
SRC_EMP = (_ROOT / "webui" / "pages" / "employer.py").read_text(encoding="utf-8")


# ─── M-02 Teil 1: Termin-Schlüssel-Reihenfolge ────────────────────────────

def test_m02_termin_wird_vor_payload_schluesseln_gelesen():
    i_termin = SRC_CAND.index('_termin = artifacts.get("termin")')
    i_datum = SRC_CAND.index('artifacts.get("termin_datum")')
    assert i_termin < i_datum, "`termin` muss vor `termin_datum` geprüft werden"


def test_m02_fallback_termin_datum_und_uhrzeit_vorhanden():
    assert 'artifacts.get("termin_uhrzeit", "")' in SRC_CAND
    assert 'f"{_d} {_z}".strip()' in SRC_CAND


# ─── M-02 Teil 2: kein stiller except in der Bewerbungsliste (R5-1) ───────

def test_r5_bewerbungsliste_except_ist_nicht_stumm():
    assert 'bewerbungen_list fehlgeschlagen' in SRC_CAND
    assert '_log.exception(' in SRC_CAND
    assert 'Erneut versuchen' in SRC_CAND


def test_kein_bare_except_und_kein_leerer_pass_rumpf():
    # `except:` (ohne Ausnahme) oder `except Exception:` ohne `as` gibt es nicht
    assert re.search(r"except\s*:", SRC_CAND) is None
    assert re.search(r"except\s+Exception\s*:", SRC_CAND) is None
    # keine `pass`-Zeile als einziger Rumpf
    assert re.search(r"^\s*pass\s*$", SRC_CAND, re.M) is None


# ─── M-14: Klartextauflösung ──────────────────────────────────────────────

def test_m14_feedback_klarname_loest_altbestand_auf():
    nbi = {2: "Sirine Ilahi"}
    assert emp._feedback_klarname("  **Name:** Anna Schuster", nbi) == "Anna Schuster"
    assert emp._feedback_klarname("Kandidat #2", nbi) == "Sirine Ilahi"
    assert emp._feedback_klarname("", nbi) == "--"


def test_m14_alter_funktionsname_existiert_nicht_mehr():
    # MD-Fundort `_feedback_name` (ui-analyse:91) ist veraltet → umbenannt.
    assert "_feedback_name" not in SRC_EMP
    assert "def _feedback_klarname(" in SRC_EMP
