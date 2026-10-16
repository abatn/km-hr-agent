"""A4-Regression (16.10.2026): leerer Kandidaten-Pfad crash-t nicht.

Befund (Red-Team + Nachmessung 16.10.2026): Der Sprachtests-Block in
_page_match (Codemark `db.get_language_tests(c_id)`) liegt AUSSERHALB der
Kandidaten-Schleife; `c_id` wird nur im Loop gebunden (Codemark
`c_id, name, h_skills`). Bei leerer Liste — z. B. /employer/match?kandidat=
<Nicht-Bewerber>; der P3-Leer-Zweig ohne Return, Codemark "P3: kein Return
mehr", ueberspringt die Schleife — fuehrte das zu UnboundLocalError.
Fix: `c_id = None` vor dem Loop + Guard am Block. Q2: Verhalten
"letzter Kandidat" bleibt bewusst unveraendert (kein Verhaltensfix).

Nachweis-Mechanismus: die nicegui user-Fixture wertet jeden ERROR-Log im
Teardown als Fehler — der Crash vor dem Fix faerbte den Render-Test rot,
der Guard nach dem Fix haelt ihn gruen. Route /a4-match-focus liegt in
tests/nicegui_main.py (R5-1).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

_EMP = Path(__file__).resolve().parent.parent / "webui" / "pages" / "employer.py"


async def test_a4_fokus_pfad_ohne_crash(user):
    """Echte _page_match auf leerem Fokus-Pfad: rendert ohne ERROR-Log."""
    await user.open("/a4-match-focus?kandidat=999999")
    await user.should_see("Match-Ergebnis")


def test_a4_guard_im_quelltext():
    """Statischer Nachweis: c_id-Initialisierung vor der c_id-Lesestelle."""
    src = _EMP.read_text(encoding="utf-8")
    assert "c_id = None" in src, "c_id-Initialisierung fehlt"
    assert "if c_id is not None else []" in src, "Guard am Sprachtests-Block fehlt"
    assert src.index("c_id = None") < src.index("db.get_language_tests(c_id)"), \
        "Initialisierung muss vor der Lesestelle stehen"
