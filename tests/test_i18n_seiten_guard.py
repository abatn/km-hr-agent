"""i18n-Guard für 404-Seite, geteilte Komponenten und die Dokumenten-Tabelle.

Analog zu `tests/test_billing_i18n.py`: jedes `_()`-Literal dieser Dateien muss in
allen vier Katalogen (de/en/fr/ar) mit nicht-leerer Übersetzung stehen und die
benannten Platzhalter müssen erhalten bleiben. `employer.py` wird nur gezielt
geprüft, weil der Slot ein Quasar-Template als rohen String enthält (kein `_()`-Call).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KATALOGE = ["de", "en", "fr", "ar"]
PO = {l: ROOT / "webui" / "locales" / l / "LC_MESSAGES" / "messages.po" for l in KATALOGE}
SCAN = [ROOT / "webui" / "pages" / "not_found.py", ROOT / "webui" / "components.py"]


def _entpacke(s: str) -> str:
    return s.replace('\\"', '"').replace("\\\\", "\\").replace("\\n", "\n")


def _katalog(lang: str) -> dict[str, str]:
    text = PO[lang].read_text(encoding="utf-8")
    paare: dict[str, str] = {}
    aktuell = None
    for zeile in text.splitlines():
        if zeile.startswith("msgid "):
            aktuell = _entpacke(zeile[6:].strip().strip('"'))
        elif zeile.startswith("msgstr ") and aktuell is not None:
            paare[aktuell] = _entpacke(zeile[7:].strip().strip('"'))
            aktuell = None
    return paare


def _literale(pfad: Path) -> list[tuple[int, str]]:
    tree = ast.parse(pfad.read_text(encoding="utf-8"))
    out = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "_" and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            out.append((node.lineno, node.args[0].value))
    return out


def _platzhalter(s: str) -> set[str]:
    return set(re.findall(r"\{([a-zA-Z0-9_]*)\}", s))


def test_alle_literale_in_404_und_komponenten_in_allen_katalogen():
    kataloge = {l: _katalog(l) for l in KATALOGE}
    fehlend = []
    for pfad in SCAN:
        for zeile, msgid in _literale(pfad):
            for lang in KATALOGE:
                if msgid not in kataloge[lang]:
                    fehlend.append(f"{pfad.name}:{zeile} fehlt in {lang}: {msgid[:80]!r}")
                elif not kataloge[lang][msgid].strip():
                    fehlend.append(f"{pfad.name}:{zeile} leere Übersetzung in {lang}: {msgid[:80]!r}")
    assert not fehlend, "Fehlende Übersetzungen:\n" + "\n".join(fehlend)


def test_platzhalter_paritaet_404_und_komponenten():
    kataloge = {l: _katalog(l) for l in KATALOGE}
    for pfad in SCAN:
        for zeile, msgid in _literale(pfad):
            soll = _platzhalter(msgid)
            if not soll:
                continue
            for lang in KATALOGE:
                ist = _platzhalter(kataloge[lang].get(msgid, ""))
                assert ist == soll, f"{pfad.name}:{zeile} {lang}: Platzhalter {soll} != {ist}"


def test_employer_dokumente_slot_nutzt_uebersetzung():
    """`Öffnen` im Quasar-Slot wird zur Renderzeit per `_()` eingesetzt, nicht als Literal."""
    quelle = (ROOT / "webui" / "pages" / "employer.py").read_text(encoding="utf-8")
    assert 'label="Öffnen"' not in quelle
    assert """label="''' + _("Öffnen") + r'''\"""" in quelle
    for lang in KATALOGE:
        kat = _katalog(lang)
        assert "Öffnen" in kat, f"{lang}: msgid 'Öffnen' fehlt"
        assert kat["Öffnen"].strip(), f"{lang}: 'Öffnen' leer"
