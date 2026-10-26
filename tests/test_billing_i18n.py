"""i18n-Guard für die Billing-UI.

Hintergrund (26.10.2026): Fünf mehrzeilige `_()`-Strings (implizite
String-Konkatenation) fehlten in **allen vier** Katalogen. `checks.py i18n`
vergleicht nur die Kataloge untereinander und `tests/test_i18n.py` prüfte
`billing_ui.py` nicht — der Fehler blieb dadurch unsichtbar (EN/FR/AR zeigten
Deutsch). Dieser Test scannt den Quelltext per AST und vergleicht gegen die
`.po`-Dateien.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KATALOGE = ["de", "en", "fr", "ar"]
PO = {l: ROOT / "webui" / "locales" / l / "LC_MESSAGES" / "messages.po" for l in KATALOGE}


def _entpacke(s: str) -> str:
    return s.replace('\\"', '"').replace("\\\\", "\\").replace("\\n", "\n")


def _katalog(lang: str) -> dict[str, str]:
    """msgid -> msgstr aus der .po-Datei (ohne gettext-Abhängigkeit)."""
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
    """Alle `_("...")`-Literale (AST faltet mehrzeilige Konkatenation)."""
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


def test_alle_billing_ui_strings_in_allen_katalogen():
    """Jeder `_()`-String der Billing-UI existiert in de/en/fr/ar."""
    kataloge = {l: _katalog(l) for l in KATALOGE}
    fehlend = []
    for zeile, msgid in _literale(ROOT / "webui" / "pages" / "billing_ui.py"):
        for lang in KATALOGE:
            if msgid not in kataloge[lang]:
                fehlend.append(f"billing_ui.py:{zeile} fehlt in {lang}: {msgid[:80]!r}")
            elif not kataloge[lang][msgid].strip():
                fehlend.append(f"billing_ui.py:{zeile} leere Übersetzung in {lang}: {msgid[:80]!r}")
    assert not fehlend, "Fehlende Billing-UI-Übersetzungen:\n" + "\n".join(fehlend)


def test_billing_backend_meldungen_uebersetzt():
    """ValueError-Texte aus billing.py, die im UI erscheinen, sind msgids."""
    meldungen = [
        "Bewerbung nicht gefunden",
        "Bewerbung gehört nicht zu diesem Kandidaten",
        "Für diese Bewerbung ist bereits ein Beratungstermin gebucht.",
        "Termin bereits gebucht",
        "Bruttojahresgehalt muss positiv sein",
    ]
    for lang in KATALOGE:
        kat = _katalog(lang)
        for m in meldungen:
            assert m in kat, f"{lang}: Backend-Meldung fehlt im Katalog: {m!r}"


def test_platzhalter_paritaet_im_billing():
    """Benannte Platzhalter ({id}, {k}, {a}, ...) bleiben in allen Sprachen erhalten."""
    kataloge = {l: _katalog(l) for l in KATALOGE}
    for zeile, msgid in _literale(ROOT / "webui" / "pages" / "billing_ui.py"):
        soll = _platzhalter(msgid)
        if not soll:
            continue
        for lang in KATALOGE:
            ist = _platzhalter(kataloge[lang].get(msgid, ""))
            assert ist == soll, f"{lang}: Platzhalter {soll} != {ist} bei {msgid[:60]!r}"


def test_billing_ui_ohne_hartes_deutsch_in_en():
    """Stichprobe: zentrale Billing-Texte sind in EN nicht mehr deutsch."""
    en = _katalog("en")
    for msgid in (
        "Bankdaten sind noch nicht konfiguriert. Bitte keine Rechnung ohne gültige Bankdaten versenden.",
        "Für eine Beratung brauchst du zuerst eine Bewerbung. Sobald du dich beworben hast, kannst du hier einen Termin buchen.",
        "Die Beratung ist eine separate Leistung und wird nicht auf eine spätere Vermittlungsgebühr angerechnet.",
        "Gebühren für Vermittlung und Visa entstehen, sobald eine Bewerbung eingestellt bzw. das Visum genehmigt wurde.",
    ):
        assert msgid in en, f"fehlt in EN: {msgid[:60]!r}"
        assert en[msgid] != msgid, f"EN unübersetzt: {msgid[:60]!r}"
