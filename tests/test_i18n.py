"""Tests für die i18n-Infrastruktur (Phase 1, 02.10.2026).

Prüft die lab-relevanten Zusagen aus knowledge/system/i18n.md:
* 4 Sprachen (de/en/fr/ar) mit kompilierten Katalogen.
* Key-Gleichheit: alle Kataloge haben dieselben msgids wie DE.
* Keine leeren msgstr.
* gettext liefert je Sprache die erwartete Übersetzung.
* RTL-Erkennung für Arabisch.
"""
from __future__ import annotations

import ast
import gettext
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
LOCALES = BASE / "webui" / "locales"
LANGS = ("de", "en", "fr", "ar")


def _catalog(lang: str) -> gettext.GNUTranslations:
    return gettext.translation("messages", str(LOCALES), languages=[lang], fallback=True)


def test_vier_sprachen_mit_mo():
    for lang in LANGS:
        assert (LOCALES / lang / "LC_MESSAGES" / "messages.mo").is_file(), f"mo fehlt: {lang}"


def test_key_gleichheit_und_keine_leeren_msgstr():
    """Alle Kataloge haben dieselben Keys wie DE; kein msgstr ist leer."""
    de = _catalog("de")
    de_keys = {k for k in de._catalog if k}
    assert de_keys, "DE-Katalog leer"
    for lang in LANGS:
        cat = _catalog(lang)
        keys = {k for k in cat._catalog if k}
        assert keys == de_keys, f"{lang}: Key-Menge != DE ({keys ^ de_keys})"
        for k in de_keys:
            assert str(cat._catalog[k]).strip(), f"{lang}: leerer msgstr für {k!r}"


def test_uebersetzung_je_sprache():
    assert _catalog("de").gettext("Zum Login") == "Zum Login"
    assert _catalog("en").gettext("Zum Login") == "Log in"
    assert _catalog("fr").gettext("Zum Login") == "Connexion"
    assert _catalog("ar").gettext("Zum Login") == "تسجيل الدخول"


def test_i18n_modul_und_rtl():
    from webui import i18n
    assert i18n.SUPPORTED == LANGS
    assert i18n.DEFAULT == "de"
    assert i18n.is_rtl("ar") is True
    assert i18n.is_rtl("de") is False
    assert i18n.is_rtl("fr") is False


# ─── Phase 4 (02.10.2026): Rechts-Seiten als <name>.<lang>.md ───

LEGAL = BASE / "knowledge" / "legal"
LEGAL_PAGES = ("impressum", "datenschutz", "agb", "kontakt")


def test_rechts_seiten_vier_sprachen():
    """Alle 4 Rechts-Seiten existieren in allen 4 Sprachen (12 Dateien)."""
    missing = [
        f"{name}.{lang}.md"
        for name in LEGAL_PAGES for lang in ("en", "fr", "ar")
        if not (LEGAL / f"{name}.{lang}.md").is_file()
    ]
    assert not missing, f"fehlende Rechts-Dateien: {missing}"
    for name in LEGAL_PAGES:
        assert (LEGAL / f"{name}.md").is_file(), f"DE-Fallback fehlt: {name}.md"


def test_rechts_seiten_aufloesung_je_sprache(monkeypatch):
    """_resolve liefert je Sprache die passende Datei; DE zeigt auf <name>.md."""
    from webui.pages import legal
    for lang in LANGS:
        monkeypatch.setattr(legal, "get_language", lambda l=lang: l)
        for name in LEGAL_PAGES:
            expect = f"{name}.md" if lang == "de" else f"{name}.{lang}.md"
            assert legal._resolve(name).name == expect, f"{lang}/{name}"


def test_rechts_seiten_fallback_bei_fehlender_datei(monkeypatch):
    """Fehlt eine lokale Datei, wird auf <name>.md zurückgefallen (nie crash)."""
    from webui.pages import legal
    monkeypatch.setattr(legal, "get_language", lambda: "xx")  # unbekannte Sprache
    for name in LEGAL_PAGES:
        assert legal._resolve(name).name == f"{name}.md", name


def test_rechts_seiten_startet_nicht_crash():
    """legal.py lädt (importierbar) und registriert genau 4 Routen."""
    from webui.pages import legal
    assert set(legal.PAGES) == set(LEGAL_PAGES)


# ─── Phase 5 (03.10.2026): Candidate-Portal ───

CANDIDATE = BASE / "webui" / "pages" / "candidate.py"


def _candidate_translation_calls() -> list[ast.Call]:
    tree = ast.parse(CANDIDATE.read_text(encoding="utf-8"))
    return [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "_" and n.args
    ]


def test_candidate_portal_strings_uebersetzt():
    """Kern-UI-Strings des Candidate-Portals sind in EN/FR/AR übersetzt."""
    samples = ["Profil speichern", "Bewerben", "Lebenslauf hochladen",
               "Meine Dokumente ({0})", "🔒 Lebenslauf nötig",
               # Phase 5b: section_header/empty_state/ui.number/IfExp-Nachzügler
               "Mein Profil", "Keine offenen Stellen", "Jetzt bewerben",
               "→ Stellen ansehen", "Kandidaten-Uebersicht"]
    for s in samples:
        de = _catalog("de").gettext(s)
        assert de == s, f"DE-Referenz fehlt: {s!r}"
        for lang in ("en", "fr", "ar"):
            got = _catalog(lang).gettext(s)
            assert got.strip() and got != s, f"{lang} nicht übersetzt: {s!r}"


def test_candidate_keine_fstrings_in_uebersetzung():
    """Konvention (i18n.md / Ruff INT001): keine f-Strings in _() —
    dynamische Teile laufen über _('…{0}…').format(...)."""
    bad = [
        ast.unparse(c) for c in _candidate_translation_calls()
        if isinstance(c.args[0], ast.JoinedStr)
    ]
    assert not bad, f"f-String in _(): {bad[:3]}"


def test_candidate_keine_uebersetzung_auf_modulebene():
    """Übersetzungen dürfen nicht zur Importzeit passieren (keine Session/Sprache)."""
    tree = ast.parse(CANDIDATE.read_text(encoding="utf-8"))

    def _toplevel(node):
        for child in ast.iter_child_nodes(node):
            yield child
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.ClassDef, ast.Lambda)):
                yield from _toplevel(child)

    bad = [
        n.func.id for n in _toplevel(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "_"
    ]
    assert not bad, f"_() auf Modulebene: {bad[:3]}"


def test_candidate_sidebar_labels_bei_renderzeit():
    """Sidebar-Labels werden bei Renderzeit übersetzt, nicht als Konstante."""
    from webui.pages import candidate
    assert not hasattr(candidate, "_MENU_ITEMS"), \
        "_MENU_ITEMS (Importzeit) muss durch _menu_items() ersetzt sein"
    assert callable(candidate._menu_items)
    orig = candidate._
    candidate._ = lambda s: "X-" + s
    try:
        labels = [m["label"] for m in candidate._menu_items()]
        keys = {m["key"] for m in candidate._menu_items()}
    finally:
        candidate._ = orig
    assert all(lbl.startswith("X-") for lbl in labels), labels
    assert keys == set(candidate._TAB_MAP)


# ─── Phase 6 (03.10.2026): Employer-Portal ───

EMPLOYER = BASE / "webui" / "pages" / "employer.py"


def _employer_translation_calls() -> list[ast.Call]:
    tree = ast.parse(EMPLOYER.read_text(encoding="utf-8"))
    return [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "_" and n.args
    ]


def test_employer_portal_strings_uebersetzt():
    """Kern-UI-Strings des Arbeitgeber-Portals sind in EN/FR/AR übersetzt."""
    samples = ["Offene Stellen", "Kandidaten-Suche", "Ablehnen", "Eingeladen?",
               "Firmenprofil", "📢 Stelle ausschreiben", "Unbekannt"]
    for s in samples:
        assert _catalog("de").gettext(s) == s, f"DE-Referenz fehlt: {s!r}"
        for lang in ("en", "fr", "ar"):
            got = _catalog(lang).gettext(s)
            assert got.strip() and got != s, f"{lang} nicht übersetzt: {s!r}"


def test_employer_keine_fstrings_in_uebersetzung():
    bad = [
        ast.unparse(c) for c in _employer_translation_calls()
        if isinstance(c.args[0], ast.JoinedStr)
    ]
    assert not bad, f"f-String in _(): {bad[:3]}"


def test_employer_keine_uebersetzung_auf_modulebene():
    tree = ast.parse(EMPLOYER.read_text(encoding="utf-8"))

    def _toplevel(node):
        for child in ast.iter_child_nodes(node):
            yield child
            if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                      ast.ClassDef, ast.Lambda)):
                yield from _toplevel(child)

    bad = [
        n.func.id for n in _toplevel(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "_"
    ]
    assert not bad, f"_() auf Modulebene: {bad[:3]}"


def test_employer_sidebar_labels_bei_renderzeit():
    from webui.pages import employer
    assert not hasattr(employer, "_MENU_ITEMS_EMP"), \
        "_MENU_ITEMS_EMP (Importzeit) muss durch _menu_items_emp() ersetzt sein"
    assert callable(employer._menu_items_emp)
    orig = employer._
    employer._ = lambda s: "X-" + s
    try:
        labels = [m["label"] for m in employer._menu_items_emp()]
        keys = {m["key"] for m in employer._menu_items_emp()}
    finally:
        employer._ = orig
    assert all(lbl.startswith("X-") for lbl in labels), labels
    assert keys == set(employer.PAGE_MAP)


# ─── Phase 6b (03.10.2026): geteilte Komponenten (components.py) ───

COMPONENTS = BASE / "webui" / "components.py"


def test_components_strings_uebersetzt():
    samples = ["Benachrichtigungen", "Laden...", "Ansehen", "Bestätigen",
               "Vorschau", "Datei hier ablegen oder klicken"]
    for s in samples:
        assert _catalog("de").gettext(s) == s, f"DE-Referenz fehlt: {s!r}"
        for lang in ("en", "fr", "ar"):
            got = _catalog(lang).gettext(s)
            assert got.strip() and got != s, f"{lang} nicht übersetzt: {s!r}"


def test_components_keine_fstrings_und_keine_importzeit_uebersetzung():
    """Konvention: keine f-Strings in _(); keine _() zur Importzeit —
    auch nicht als Default-Parameter (der würde beim Import ausgewertet)."""
    tree = ast.parse(COMPONENTS.read_text(encoding="utf-8"))
    # f-Strings in _()
    bad_f = [
        ast.unparse(c) for c in ast.walk(tree)
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
        and c.func.id == "_" and c.args and isinstance(c.args[0], ast.JoinedStr)
    ]
    assert not bad_f, f"f-String in _(): {bad_f[:3]}"
    # _() als Default-Parameter (Importzeit!)
    bad_d = []
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in list(fn.args.defaults) + [k.value for k in fn.args.kw_defaults if k]:
                if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                       and n.func.id == "_" for n in ast.walk(d)):
                    bad_d.append(fn.name)
    assert not bad_d, f"_() als Default-Parameter: {bad_d}"

