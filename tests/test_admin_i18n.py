"""S3/S4b/S5 (12.10.2026): i18n der Admin-Seiten.

Leichtgewichtig (kein Browser): Quelltext- und Katalog-Pruefungen.
Spec: knowledge/system/i18n.md.
"""
from __future__ import annotations

import ast
from pathlib import Path

from webui.i18n_core import tr

BASE = Path(__file__).resolve().parent.parent
ADMIN = BASE / "webui" / "pages" / "admin.py"

# Strings, die bereits im Projekt-Katalog liegen und in EN eine echte
# Uebersetzung liefern -> Stichprobe fuer Punkt (b).
SAMPLE_UEBERSETZT = (
    "Vorschau",
    "Herunterladen",
    "Abbrechen",
    "Branche",
    "Standort",
    "Telefon",
    "Mitarbeiterzahl",
    "Daten exportieren",
    "Passwort aendern",
    "Aktuelles Passwort",
)


def _admin_source() -> str:
    return ADMIN.read_text(encoding="utf-8")


def test_admin_hat_i18n_import():
    """(a) admin.py importiert den UI-Translator wie die anderen Seiten."""
    assert "from webui.i18n import _" in _admin_source()


def test_admin_labels_uebersetzen_ueber_tr():
    """(b) Stichprobe gewrappter Admin-Strings liefert in EN != Deutsch."""
    for msgid in SAMPLE_UEBERSETZT:
        assert tr(msgid, "de") == msgid, f"DE-Identitaet verletzt: {msgid!r}"
        en = tr(msgid, "en")
        assert en.strip() and en != msgid, f"EN nicht uebersetzt: {msgid!r} -> {en!r}"


def _translation_calls() -> list[ast.Call]:
    tree = ast.parse(_admin_source())
    return [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "_" and n.args
    ]


def test_admin_keine_fstrings_in_uebersetzung():
    """Konvention (i18n.md / Ruff INT001): keine f-Strings in _()."""
    bad = [ast.unparse(c) for c in _translation_calls()
           if isinstance(c.args[0], ast.JoinedStr)]
    assert not bad, f"f-String in _(): {bad[:3]}"


def test_admin_keine_uebersetzung_auf_modulebene():
    """_() darf nicht zur Importzeit laufen (keine Session/Sprache)."""
    tree = ast.parse(_admin_source())

    def _toplevel(node):
        for child in ast.iter_child_nodes(node):
            yield child
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.ClassDef, ast.Lambda)):
                yield from _toplevel(child)

    bad = [n.func.id for n in _toplevel(tree)
           if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
           and n.func.id == "_"]
    assert not bad, f"_() auf Modulebene: {bad[:3]}"


def test_admin_sidebar_labels_bei_renderzeit():
    """PAGE_MAP-Labels werden erst beim Rendern uebersetzt."""
    from webui.pages import admin
    assert not hasattr(admin, "_MENU_ITEMS_ADMIN"), \
        "_MENU_ITEMS_ADMIN (Importzeit) muss durch _menu_items_admin() ersetzt sein"
    assert callable(admin._menu_items_admin)
    orig = admin._
    admin._ = lambda s: "X-" + s
    try:
        labels = [m["label"] for m in admin._menu_items_admin()]
        keys = {m["key"] for m in admin._menu_items_admin()}
    finally:
        admin._ = orig
    assert all(lbl.startswith("X-") for lbl in labels), labels
    assert keys == set(admin.PAGE_MAP)


def test_admin_change_password_meldung_gewrappt():
    """S5: die Rueckgabe von logic.change_password wird via _() angezeigt."""
    assert "ui.notify(_(msg)" in _admin_source()


def test_admin_result_language_helper_defensiv():
    """S4b: leerer task_type -> None (kein DB-Zugriff, kein Crash)."""
    from webui.pages import admin
    assert admin._latest_result_language("") is None
