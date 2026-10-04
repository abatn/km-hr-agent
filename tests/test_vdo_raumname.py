"""Raumname alphanumerisch — `prescreening{code}` statt `pre-screening-{code}` (Lab Schritt 3, 04.10.2026).

Quelle (Lab Schritt 1): docs.vdo.ninja/advanced-settings/setup-parameters/room —
„&room — 1 to 49-characters long: aLphaNumEric-characters; case sensitive."
Live-Befund 04.10.2026: bei `pre-screening-{code}` ersetzte VDO die Bindestriche
(`pre_screening_{code}`) und zeigte die Warnung „Only AlphaNumeric characters …".
Spec: knowledge/system/vdo-ninja-migration.md §2.5.

Geprüft werden die echten f-Strings aus dem Code (geparst, nicht nachgebaut).
"""
import random
import re
import string
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "agent-runner.py"
COMPONENTS = ROOT / "webui" / "components.py"


def _fstring(src: str, var: str) -> str:
    m = re.search(rf"{var}\s*=\s*(f\"[^\"]*\")", src)
    assert m, f"f-String für {var} nicht gefunden"
    return m.group(1)


def _room(url: str) -> str:
    m = re.search(r"(?:director|room)=([^&]+)", url)
    assert m, f"kein Raumparameter in {url}"
    return m.group(1)


def test_runner_director_und_gast_ohne_bindestrich():
    src = RUNNER.read_text(encoding="utf-8")
    code = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    director = eval(_fstring(src, "vdo_ninja_url"), {"code": code})  # noqa: S307
    gast = eval(_fstring(src, "vdo_ninja_gast_url"), {"code": code})  # noqa: S307
    assert director == f"https://vdo.ninja/?director=prescreening{code}"
    assert gast == f"https://vdo.ninja/?room=prescreening{code}&record=off"
    for url in (director, gast):
        room = _room(url)
        assert room.isalnum(), f"Raumname nicht alphanumerisch: {room}"
        assert len(room) <= 49, f"Raumname laenger als 49 Zeichen: {room}"


def test_prescreen_werkzeug_ohne_bindestrich():
    src = COMPONENTS.read_text(encoding="utf-8")
    room_code = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    meet = eval(_fstring(src, "meet_url"), {"room_code": room_code})  # noqa: S307
    assert meet == f"https://vdo.ninja/?director=prescreening{room_code}"
    room = _room(meet)
    assert room.isalnum() and len(room) <= 49, f"Raumname nicht alphanumerisch: {room}"


def test_kein_altes_muster_in_den_geaenderten_dateien():
    for path in (RUNNER, COMPONENTS):
        src = path.read_text(encoding="utf-8")
        assert "?director=pre-screening-" not in src, f"altes Director-Muster in {path.name}"
        assert "?room=pre-screening-" not in src, f"altes Gast-Muster in {path.name}"
