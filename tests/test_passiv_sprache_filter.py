"""Passiv-Filter „Sprache" (Extraktion 18.10.2026): `webui/pages/employer.py::sprache_passt`.

Die pure Funktion ersetzt die frühere Kette dreier `continue`-Zeilen in `_pf_berechne`
(Suchmarke `if _pf_sprache == "fr"`) mit 1:1 gleicher Semantik:
  "de"/"en"/"fr" → Level-Wert an der jeweils passenden Position (trim) darf nicht leer sein,
  "alle"/unbekannte Werte → ohne Bedingung (True).
Spec: knowledge/portal/employer-board.md.

Nur In-Memory-Aufrufe der reinen Funktion — kein DB-Zugriff, keine UI, keine Fixtures.
"""
import pytest

from webui.pages import employer as emp


@pytest.mark.parametrize("sprache,de,en,fr,erwartet", [
    # de (Position 6)
    ("de", "B1", None, None, True),
    ("de", "", None, None, False),
    ("de", "   ", None, None, False),   # Whitespace-Zeile wie "" (trim)
    ("de", None, None, None, False),
    # en (Position 7)
    ("en", None, "C1", None, True),
    ("en", None, None, None, False),
    # fr (Position 10)
    ("fr", None, None, "B2", True),
    ("fr", None, None, " ", False),
    ("fr", None, None, None, False),
    # unbekannte Werte = keine Bedingung (1:1 zur alten Kette)
    ("alle", None, None, None, True),
    ("", None, None, None, True),
    ("xx", None, None, None, True),
    # Unabhängigkeit: fr prüft NUR Position fr, ignoriert de/en-Werte
    ("fr", "", "", "B1", True),
])
def test_sprache_passt(sprache, de, en, fr, erwartet):
    assert emp.sprache_passt(sprache, de, en, fr) is erwartet, (sprache, de, en, fr)
