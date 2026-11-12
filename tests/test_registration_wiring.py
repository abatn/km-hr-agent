"""Quelltext-Waechter: E-Mail-Guard und Honeypot sind verdrahtet (12.11.2026).

Ergaenzt `tests/test_registration_guard.py` (Unit) und
`tests/test_registration_ui.py` (Rendering). Hier wird die **Struktur** von
`webui/pages/login.py` geprueft — die Stellen, die ein Refactor still
auseinanderlaufen laesst:

* Keine fuenfte Kopie der Altregel `lambda v: "@" in v and "." in v`.
* Drei Login-Felder nutzen die tolerante, zwei Registrierungsfelder die
  strikte Validierung (K1 aus `ergebnisse/planung-5-7.md`).
* Beide Registrierungs-Handler pruefen Honeypot/Timing und E-Mail **vor** dem
  INSERT; das INSERT selbst bleibt im Handler (K2).
* Der generische Fehlertext liegt in allen vier Katalogen (i18n).

Spec: `knowledge/system/registration-hardening.md`.
"""
from __future__ import annotations

import ast
import gettext
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LOGIN_SRC = (ROOT / "webui" / "pages" / "login.py").read_text(encoding="utf-8")
GENERIC = "Registrierung derzeit nicht möglich. Bitte versuchen Sie es später erneut."


def _funktion(name: str) -> ast.AST:
    tree = ast.parse(LOGIN_SRC)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"Funktion {name} nicht gefunden")


# ─── Die fuenf Felder ──────────────────────────────────────────────────

def test_altregel_existiert_nicht_mehr():
    assert '"@" in v and "." in v' not in LOGIN_SRC, (
        "Altregel wieder da — bitte reg_guard.email_field_valid / "
        "reg_guard.registration_email_field_valid nutzen"
    )
    assert "lambda v: \"@\" in v" not in LOGIN_SRC


def test_drei_login_felder_tolerant_zwei_registrierungsfelder_strikt():
    """`email`, `e_email`, `a_email` tolerant; `r_email`, `er_email` strikt."""
    assert LOGIN_SRC.count("reg_guard.email_field_valid") == 3
    assert LOGIN_SRC.count("reg_guard.registration_email_field_valid") == 2


# ─── Handler-Reihenfolge (K2: INSERT bleibt im Handler) ────────────────

@pytest.mark.parametrize("funktion,insert", [
    ("do_register", "INSERT INTO candidates"),
    ("do_employer_register", "INSERT INTO employers"),
])
def test_guards_stehen_vor_dem_insert(funktion, insert):
    fn = _funktion(funktion)
    segment = ast.get_source_segment(LOGIN_SRC, fn) or ""
    assert insert in segment, f"{funktion}: INSERT nicht im Handler"
    assert "reg_guard.registration_blocked(" in segment, f"{funktion}: Honeypot/Timing fehlt"
    assert "reg_guard.registration_email_blocked(" in segment, f"{funktion}: E-Mail-Guard fehlt"
    assert segment.index("registration_email_blocked") < segment.index(insert)
    assert segment.index("registration_blocked") < segment.index(insert)


@pytest.mark.parametrize("funktion,feld,marker", [
    ("do_register", "r_hp", "hp-register-candidate"),
    ("do_employer_register", "er_hp", "hp-register-employer"),
])
def test_honeypot_und_startzeit_im_panel(funktion, feld, marker):
    fn = _funktion(funktion)
    segment = ast.get_source_segment(LOGIN_SRC, fn) or ""
    assert f"{feld}.value" in segment
    assert "_honeypot_field(" in LOGIN_SRC
    assert marker in LOGIN_SRC
    # Startzeit und Lockfeld werden beim Rendern des Panels angelegt, nicht im Handler.
    panel_start = LOGIN_SRC.index(marker)
    handler_start = LOGIN_SRC.index(f"async def {funktion}(")
    assert panel_start < handler_start, "Lockfeld muss vor dem Handler gerendert werden"
    assert "time.monotonic()" in LOGIN_SRC[:handler_start]


def test_honeypot_ist_off_screen_und_nicht_fokussierbar():
    fn = _funktion("_honeypot_field")
    segment = ast.get_source_segment(LOGIN_SRC, fn) or ""
    assert "aria-hidden=true" in segment
    assert "tabindex=-1" in segment
    assert "left:-10000px" in segment


def test_generische_meldung_ist_eine_meldung():
    """Honeypot und Timing teilen sich denselben Satz (kein Bot-Feedback)."""
    assert LOGIN_SRC.count(GENERIC) == 2


# ─── i18n ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("lang", ["de", "en", "fr", "ar"])
def test_generische_meldung_in_allen_katalogen(lang):
    po = (ROOT / "webui" / "locales" / lang / "LC_MESSAGES" / "messages.po").read_text(encoding="utf-8")
    assert f'msgid "{GENERIC}"' in po, f"{lang}: msgid fehlt"


def test_mo_katalog_uebersetzt_die_meldung():
    with open(ROOT / "webui" / "locales" / "en" / "LC_MESSAGES" / "messages.mo", "rb") as f:
        cat = gettext.GNUTranslations(f)
    assert cat.gettext(GENERIC) != GENERIC
