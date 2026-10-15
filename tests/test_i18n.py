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
import re
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
    # 15.10.2026 (employer-board.md §6): Sidebar zeigt nur 4 Punkte; alle übrigen Seiten
    # liegen unter „Mehr“. Vollständigkeit wird jetzt gegen Sidebar ∪ Mehr geprüft.
    assert keys == set(employer.SIDEBAR_KEYS)
    assert set(employer.SIDEBAR_KEYS) <= set(employer.PAGE_MAP)
    assert (keys | {k for k in employer.PAGE_TITLES if k not in employer.SIDEBAR_KEYS}) \
        == set(employer.PAGE_MAP)


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



# ─── Klasse D (P9.1, 06.10.2026): dynamische _()-Keys, die NICHT statisch    ───
# extrahierbar sind (employer.py CAND_POOL_ALL_LABEL / _MATCH_ACTION_LABEL) und
# daher hand in alle Kataloge eingetragen werden muessen (Gap-Register i18n.md).
# Regression: _() gibt sonst roh deutsch zurueck (sichtbarer Bug in EN/FR/AR).
KLASSE_D_KEYS = (
    "Alle mit Lebenslauf",        # employer.py:83 CAND_POOL_ALL_LABEL, Konsum :101 via _()
    "Als angesehen markieren",   # employer.py:987 _MATCH_ACTION_LABEL['angesehen'], Konsum :1478
)


def test_klasse_d_dynamische_keys_in_allen_katalogen():
    for key in KLASSE_D_KEYS:
        for lang in LANGS:
            cat = _catalog(lang)
            assert key in cat._catalog, f"{lang}: Key {key!r} fehlt im .mo (Klasse D)"
            assert str(cat._catalog[key]).strip(), f"{lang}: msgstr fuer {key!r} leer"
        assert _catalog("de").gettext(key) == key, "DE: msgstr != msgid (Identitaet)"


def test_klasse_d_uebersetzt_in_en_fr_ar():
    """EN/FR/AR liefern fuer beide Keys eine echte Uebersetzung (nicht den deutschen Rohtext)."""
    for key in KLASSE_D_KEYS:
        for lang in ("en", "fr", "ar"):
            got = _catalog(lang).gettext(key)
            assert got != key, f"{lang}: {key!r} bleibt deutsch (msgstr == msgid)"
            assert got.strip(), f"{lang}: leere Uebersetzung fuer {key!r}"


# ─── Klasse A Reststellen (P9.2b, 06.10.2026) ───
# 6 neue msgids, hand in alle 4 Kataloge eingetragen (dynamischer Konsum
# employer.py `_(kat_name)` / `_('{0} Jahre')` etc. — statisch nicht
# zuverlaessig extrahierbar). Uebersetzungen = Design-Entscheidung.
P9_2B_NEUE_KEYS = ("Kern", "Bildung", "Soft", "Profil", "Alle", "{0} Jahre")


def test_p9_2b_neue_msgids_in_allen_katalogen():
    """Alle 6 neuen Keys liegen in jeder Sprache im .mo, nicht leer; DE = Identitaet."""
    for key in P9_2B_NEUE_KEYS:
        for lang in LANGS:
            cat = _catalog(lang)
            assert key in cat._catalog, f"{lang}: Key {key!r} fehlt im .mo"
            assert str(cat._catalog[key]).strip(), f"{lang}: msgstr fuer {key!r} leer"
        assert _catalog("de").gettext(key) == key, f"DE: msgstr != msgid fuer {key!r}"


def test_p9_2b_uebersetzt_in_en_fr_ar():
    """EN/FR/AR liefern fuer die 6 Keys die Design-Entscheidung-Erstfassung.

    Hinweis: 'Soft' bleibt in EN und FR bewusst 'Soft' (Lehnwort) — daher
    wird hier auf die konkreten Werte geprueft, nicht auf '!= msgid'."""
    erwartet = {
        "Kern": ("Core", "Noyau", "النواة"),
        "Bildung": ("Education", "Formation", "التعليم"),
        "Soft": ("Soft", "Soft", "السلوكية"),
        "Profil": ("Profile", "Profil", "الملف الشخصي"),
        "Alle": ("All", "Tous", "الكل"),
        "{0} Jahre": ("{0} years", "{0} ans", "{0} سنة"),
    }
    for key, (en, fr, ar) in erwartet.items():
        got = {"en": _catalog("en").gettext(key),
               "fr": _catalog("fr").gettext(key),
               "ar": _catalog("ar").gettext(key)}
        assert got == {"en": en, "fr": fr, "ar": ar}, f"{key!r}: {got}"
        for lang in ("en", "fr", "ar"):
            assert got[lang].strip(), f"{lang}: leere Uebersetzung fuer {key!r}"


# Quelltext-Regression: die in P9.2b gewickelten ANZEIGE-Muster duerfen nicht
# roh zurueckkehren. Bewusst NICHT geprueft werden die absichtlich deutschen
# Persistenz-/Parser-Stellen (Klasse B / Persistenz) — ein globaler Scan wuerde
# sie faelschlich als Fehler werten:
#   * employer.py: `f"Kandidat #{c_id}"`        -> feedback.kandidat_name (INSERT)
#   * employer.py: `else "Unbekannt"`            -> feedback.stellenprofil (INSERT)
#   * employer.py: `s.startswith("Kandidat #")`  -> Parser _feedback_klarname
# Diese bleiben deutsch (Pseudonym-Format hat Parser-Abhaengigkeit); die Anzeige
# wird uebersetzt. Gegenprobe test_p9_2b_persistenz_stellen_bleiben_deutsch.
_P9_2B_VERBOTEN_EMP = (
    'r[2] or f"Kandidat #{r[1]}"',
    'r[1] or f"Kandidat #{r[0]}"',
    "_fname or 'Kandidat #' + str(",
    '(c[1] or f"Kandidat #{c[0]}")',
    "c[1] or f'Kandidat #{c[0]}'",
    'cand_name = name or "Unbekannt"',
    "_pname or 'Unbekannt'",
    '"alle": "Alle"',
    's.get("employer_firma", "Profil")',
)
_P9_2B_VERBOTEN_CAND = (
    'value=f"{years} Jahre"',
    '("Franzoesisch",',
    "info_row(lang, level,",
    'firma or "Unbekannt"',
    's.get("user_name", "Profil")',
)


def test_p9_2b_anzeige_roh_muster_gewrappt():
    """Gezielter Quelltext-Test je Anzeige-Stelle (nicht global): die rohen
    deutschen ANZEIGE-Muster sind verschwunden und laufen ueber _()."""
    emp = EMPLOYER.read_text(encoding="utf-8")
    cand = CANDIDATE.read_text(encoding="utf-8")
    for s in _P9_2B_VERBOTEN_EMP:
        assert s not in emp, f"ROH-Muster (Anzeige) in employer.py: {s!r}"
    for s in _P9_2B_VERBOTEN_CAND:
        assert s not in cand, f"ROH-Muster (Anzeige) in candidate.py: {s!r}"


def test_p9_2b_persistenz_stellen_bleiben_deutsch():
    """Gegenprobe: die bewusst deutschen Persistenz-/Parser-Stellen sind
    unangetastet (deutsches Pseudonym-Format in feedback.kandidat_name)."""
    emp = EMPLOYER.read_text(encoding="utf-8")
    assert 'f"Kandidat #{c_id}"' in emp, "Persistenz-Pseudonym fehlt/aendert sich"
    assert 'else "Unbekannt"' in emp, "Persistenz-Fallback stellenprofil fehlt"
    assert 's.startswith("Kandidat #")' in emp, "Parser _feedback_klarname fehlt"


# ─── Klasse B + C (P9.3, 06.10.2026): Select-Options + Status/Kategorie ───
# 73 neue msgids, hand in alle 4 Kataloge eingetragen (Select-Options haben
# persistierte deutsche Werte, die Anzeige laeuft ueber _(); STATUS_LABELS /
# _cat_map / gehalt_check ebenso). Uebersetzungen = Design-Entscheidung.
P9_3_NEUE_KEYS = (
    # C1 STATUS_LABELS
    "Eingegangen", "Angesehen", "Eingestellt", "Abgelehnt", "Zurückgezogen",
    "Lebenslauf hochgeladen", "Zugeordnet", "Aktiv", "Erledigt",
    "Fehlgeschlagen", "Läuft", "In Warteschlange", "Offen", "Pausiert",
    "Besetzt", "Abgelaufen", "Profil vollständig", "Profil geprüft",
    "Match berechnet",
    # C3 _cat_map (vereinheitlicht: Weak→Schwach)
    "Hervorragend", "Bedingt", "Schwach", "Gut",
    # C4 gehalt_check
    "❓ unbekannt", "✅ offen", "✅ passt (offen)", "✅ passt", "⚠️ außerhalb Rahmen",
    # B employer.py
    "IT", "Consulting", "Industrie", "Handel", "Gesundheit", "Finanzen",
    "Sonstiges",
    "1-10", "11-50", "51-200", "201-1000", "1000+",
    "Vollzeit", "Teilzeit", "Freelance", "Hybrid", "Remote",
    "Keine Anforderung", "A1", "A2", "B1", "B2", "C1", "C2", "Muttersprache",
    "Egal", "Bachelor", "Master", "PhD",
    "Zeugnis", "Zertifikat", "Sprachzeugnis", "Pass", "Visum/Aufenthaltstitel",
    "Ja", "Nein", "Vorgemerkt",
    # B candidate.py
    "EU-Bürger", "Arbeitsvisum", "Kein Visum",
    "Sofort", "1 Monat", "3 Monate", "Kündigungslaufzeit",
    "Diplom",
)


def test_p9_3_neue_msgids_in_allen_katalogen():
    """Alle 73 neuen P9.3-Keys liegen je Sprache im .mo, nicht leer; DE = Identitaet."""
    assert len(P9_3_NEUE_KEYS) == len(set(P9_3_NEUE_KEYS)) == 73, \
        "P9.3-Keyliste muss 73 eindeutige Keys haben"
    for key in P9_3_NEUE_KEYS:
        for lang in LANGS:
            cat = _catalog(lang)
            assert key in cat._catalog, f"{lang}: Key {key!r} fehlt im .mo (P9.3)"
            assert str(cat._catalog[key]).strip(), f"{lang}: msgstr fuer {key!r} leer"
        assert _catalog("de").gettext(key) == key, f"DE: msgstr != msgid fuer {key!r}"


def test_p9_3_uebersetzt_in_en_fr_ar():
    """Stichproben der P9.3-Uebersetzungen (Design-Entscheidung-Erstfassung)."""
    erwartet = {
        "Eingegangen": ("Received", "Reçu", "واردة"),
        "Abgelehnt": ("Rejected", "Refusé", "مرفوض"),
        "Lebenslauf hochgeladen": ("CV uploaded", "CV téléchargé", "تم رفع السيرة الذاتية"),
        "Schwach": ("Weak", "Faible", "ضعيف"),
        "Hervorragend": ("Excellent", "Excellent", "ممتاز"),
        "⚠️ außerhalb Rahmen": ("⚠️ outside range", "⚠️ hors fourchette", "⚠️ خارج النطاق"),
        "Vollzeit": ("Full-time", "Temps plein", "دوام كامل"),
        "Vorgemerkt": ("Shortlisted", "Pré-sélectionné", "مرشح مبدئياً"),
        "EU-Bürger": ("EU citizen", "Citoyen de l'UE", "مواطن في الاتحاد الأوروبي"),
        "Kündigungslaufzeit": ("Notice period", "Préavis", "مدة الإشعار"),
        "Zeugnis": ("Reference", "Référence", "خطاب توصية"),
        "Muttersprache": ("Native", "Langue maternelle", "اللغة الأم"),
    }
    for key, (en, fr, ar) in erwartet.items():
        got = {"en": _catalog("en").gettext(key),
               "fr": _catalog("fr").gettext(key),
               "ar": _catalog("ar").gettext(key)}
        assert got == {"en": en, "fr": fr, "ar": ar}, f"{key!r}: {got}"


def test_p9_3_select_options_gewrappt():
    """Quelltext-Regression: die genannten Select-Options laufen ueber _()
    (Wert = deutscher Key unveraendert, Label uebersetzt)."""
    emp = EMPLOYER.read_text(encoding="utf-8")
    cand = CANDIDATE.read_text(encoding="utf-8")
    comp = COMPONENTS.read_text(encoding="utf-8")
    for s in (
        "options={v: _(v) for v in branchen}",
        "options={v: _(v) for v in grossen}",
        'options={v: _(v) for v in ["Vollzeit", "Teilzeit", "Freelance", "Hybrid", "Remote"]}',
        'options={v: status_label(v) for v in ["aktiv", "pausiert", "besetzt", "abgelaufen"]}',
        'options={v: _(v) for v in ["Ja", "Nein", "Vorgemerkt"]}',
        '(_("Alle") if v == "alle" else _(v)) for v in DOC_TYP_OPTIONS',
    ):
        assert s in emp, f"employer.py: Select-Option nicht gewrappt: {s!r}"
    for s in (
        "options={v: _(v) for v in visum_options}",
        "options={v: _(v) for v in verf_options}",
        "options={v: _(v) for v in abschluss_options}",
        "options={v: _(v) for v in de_options}",
        "options={v: _(v) for v in en_options}",
        "options={v: _(v) for v in fr_options}",
        'options={v: _(v) for v in ["Deutsch", "Englisch", "Französisch"]}',
        "options={v: _(v) for v in _doc_typen}",
    ):
        assert s in cand, f"candidate.py: Select-Option nicht gewrappt: {s!r}"
    assert 'options={v: _(v) for v in ["Ja", "Nein"]}' in comp, \
        "components.py: Feedback-Select (Ja/Nein) nicht gewrappt"


def test_p9_3_status_label_und_cat_map_vereinheitlicht():
    """status_label laeuft durch _(); _cat_map in components.py und employer.py
    sind identisch (Employer-/app.py-Paritaet: Weak→'Schwach')."""
    comp = COMPONENTS.read_text(encoding="utf-8")
    emp = EMPLOYER.read_text(encoding="utf-8")
    assert 'return _(STATUS_LABELS.get(status,' in comp, "status_label nicht gewrappt"
    assert '_cat_map = {"Strong": "Hervorragend", "Consider": "Bedingt",\n                        "Weak": "Schwach"}' in comp, \
        "components.py _cat_map nicht vereinheitlicht"
    assert '_cat_map = {"Strong": "Hervorragend", "Consider": "Bedingt", "Weak": "Schwach"}' in emp, \
        "employer.py _cat_map fehlt"
    for src in (comp, emp):
        assert '"Weak": "Nicht passend"' not in src, "alte widerspruechliche Map noch vorhanden"


def test_p9_3_gehalt_check_gewrappt():
    """gehalt_check-Rueckgaben laufen durch _() (Anzeige-Layer)."""
    logic = (BASE / "webui" / "logic.py").read_text(encoding="utf-8")
    for s in ('return _("❓ unbekannt")', 'else _("✅ offen")',
              'return _("✅ passt (offen)")', 'return _("✅ passt")',
              'else _("⚠️ außerhalb Rahmen")'):
        assert s in logic, f"logic.gehalt_check nicht gewrappt: {s!r}"


def test_p9_3_persistenz_werte_unveraendert():
    """Gegenprobe: die in die DB geschriebenen Werte sind unveraendert deutsch
    (nur die Anzeige wird uebersetzt)."""
    emp = EMPLOYER.read_text(encoding="utf-8")
    cand = CANDIDATE.read_text(encoding="utf-8")
    comp = COMPONENTS.read_text(encoding="utf-8")
    # Select-Werte unveraendert (deutsche Keys)
    for s in ("stellentyp=typ_select.value", "abschluss=abschluss_select.value",
              "branche=branche_select.value"):
        assert s in emp, f"Persistenz-Wert geaendert: {s!r}"
    assert "eingeladen = eingeladen_select.value or \"Nein\"" in emp
    # Feedback-Kategorie wird weiter roh (deutsch) gespeichert
    assert "(match_id, name, stell, score_val, kategorie," in comp
    # Dokumenttyp wird roh gespeichert
    assert "db.insert_document(cand_id, str(_path), doc_typ.value)" in cand


# ─── Klasse E (P9.4, 06.10.2026): Daten-Layer (erzeugte MD/Dateien/Fragen) ───
# 115 neue msgids, in alle 4 Kataloge eingetragen. Erzeugte Texte (Pre-Screen,
# Onboarding, Willkommens-Mail, Feedback, Meeting/Video, CSV) laufen bei der
# ERZEUGUNG durch _() -> Sprache des ausloesenden Nutzers (Design-Entscheidung;
# Persistenz-Records bleiben deutsch). Uebersetzungen = eigene Erstfassung.
P9_4_NEUE_KEYS = (
    '# Feedback: {0}',
    '# Onboarding-Checkliste: {0}',
    '# Pre-Screening: {0}',
    '# Selbstpräsentation: Kandidat #{0}',
    '## 1. Willkommens-E-Mail',
    '## 2. IT-Ausstattung',
    '## 3. Systemzugänge',
    '## 4. Erstgespräche',
    '## 5. Einarbeitungsplan',
    '## 6. Arbeitsvertrag',
    '## Bewertung',
    '## Gewichtungsanpassung',
    '## Ihr Meeting-Raum',
    '## Ihre Leitfragen',
    '## 📊 Zusammenfassung',
    '## 📋 Screening-Fragen',
    '## 📹 Meeting-Details',
    '### Letzte Änderungen',
    '**Anmerkungen:** {0}',
    '**Betreff:** Willkommen bei TechVision GmbH!',
    '**Datum:** {0}',
    '**Eingeladen:** {0}',
    '**Empfänger:** {0}',
    '**Erstellt:** {0}',
    '**Match-ID:** `{0}`',
    '**Match-Score:** {0}/100',
    '**Modus:** Selbstpräsentation (CANDIDATE-Session)',
    '**Score:** {0}/100 ({1})',
    '**Startdatum:** {0}',
    '**Stelle:** {0}',
    '*Erstellt am {0} vom KM-HR-Agenten.*',
    '- **Datum:** {0}',
    '- **Dauer:** 45 Minuten',
    '- **Empfehlung:** 3–5 Minuten, Start mit Kurzvorstellung, dann die Fragen unten beantworten.',
    '- **Fragen gesamt:** {0}',
    '- **Link:** [{0}]({1})',
    '- **Lücken-Fragen:** {0}',
    '- **Motivations-Fragen:** {0}',
    '- **Sichtbarkeit:** HR sieht den Link im Recruiting-Modus ohne Status-Gate (zur Bewertung vor der Übernahme).',
    '- **Sprach-Check:** {0}',
    '- **Technische Fragen:** {0}',
    '- **Uhrzeit:** 10:00–10:45 Uhr',
    '- Noch kein Raum generiert (Tab 📹 Pre-Screen).',
    'Beschreiben Sie Ihren Führungsstil.',
    'Beschreiben Sie ein konkretes Projekt mit {0}. Welche Ergebnisse wurden erzielt?',
    'Beschreiben Sie eine AWS-Migration, die Sie geleitet haben.',
    'Dein Ansprechpartner: {0}',
    'Erfahrung (Jahre)',
    "Geben Sie ein Beispiel, das Ihre Stärke in '{0}' zeigt.",
    'Haben Sie Erfahrung mit Infrastructure-as-Code (z.B. Terraform)?',
    'Ihre Gehaltsvorstellung?',
    'Mit freundlichen Grüßen,\nHR Team',
    'Sehr geehrte(r) {0},',
    'Wann könnten Sie starten?',
    'Wann könnten Sie starten? Wie ist Ihre Gehaltsvorstellung?',
    'Was ist Ihr bevorzugter Arbeitsstil (Remote/Hybrid/Onsite)?',
    'Was reizt Sie an dieser Position?',
    'Welche Cloud-Plattformen haben Sie eingesetzt?',
    'Welche Rolle suchen Sie und warum?',
    'Wie gehen Sie vor bei einem Kubernetes-Cluster-Ausfall?',
    'Wie implementieren Sie CI/CD-Pipelines?',
    'Wie ist Ihr Deutsch-Level (B1/B2/C1)?',
    'Wo sehen Sie sich in 3–5 Jahren?',
    'als **{0}** in unserem Team begrüßen zu dürfen.',
    'wir freuen uns sehr, Sie ab dem **{0}** ',
    '| **Durchschnitt** | **{0}/5** |',
    '| 1 | Orientierung | Umgebung kennenlernen, Zugänge testen |',
    '| 1 | Teamleitung | Willkommen + Rahmenbedingungen | Tag 1 |',
    '| 2 | Code-Basis | Repository durchlesen, erstes Ticket |',
    '| 2 | HR | Vertragsunterlagen + Benefits | Tag 1 |',
    '| 3 | IT-Onboarding | Systemzugänge + Geräte | Tag 1 |',
    '| 3 | Infrastruktur | AWS Cluster, Monitoring, Deployments |',
    '| 4 | Scrum Master | Agile Prozesse | Tag 2 |',
    '| 4 | erstes Feature | Kleine Änderung, PR, Review |',
    '| 5 | DevOps-Team | Technische Architektur | Tag 3 |',
    '| 5 | Independence | Eigenständiges Ticket, Daily Standup |',
    '| 6 | K8s-Audit | Cluster-Review, Optimierungsvorschläge |',
    '| 6 | Product Owner | Produktübersicht | Tag 5 |',
    '| 7 | CTO | Technische Vision | Woche 2 |',
    '| 8 | Kollegen | Team-Lunch | Woche 1 |',
    '| AWS Console | ☐ Angelegt | Tag 3 |',
    '| Allowlist (Versicherung) | ☐ Ausgefüllt | Woche 1 |',
    '| Arbeitsvertrag | ☐ Zugestellt | Vor Start |',
    '| Betriebsvereinbarung | ☐ Gelesen | Woche 1 |',
    '| Confluence | ☐ Angelegt | Tag 1 |',
    '| DSGVO-Einwilligung | ☐ Unterschrieben | Tag 1 |',
    '| Datenschutzrichtlinie | ☐ Gelesen | Tag 1 |',
    '| Dokument | Status | Frist |',
    '| E-Mail (Google Workspace) | ☐ Angelegt | Tag 1 |',
    '| Empfehlung hilfreich | {0}/5 |',
    '| Fachlich korrekt | {0}/5 |',
    '| Gerät | Status | Zuständig |',
    '| GitHub | ☐ Angelegt | Tag 1 |',
    '| Headset | ☐ Bestellt | IT-Abteilung |',
    '| IT-Sicherheitsrichtlinie | ☐ Gelesen + unterschrieben | Tag 1 |',
    '| Jira | ☐ Angelegt | Tag 1 |',
    '| Kategorie | Alt | Neu | Grund |',
    '| Kriterium | Punkte |',
    '| Kubernetes Cluster | ☐ Angelegt | Tag 5 |',
    '| Laptop-Tasche | ☐ Bestellt | IT-Abteilung |',
    '| Linux-Workstation | ☐ Bestellt | IT-Abteilung |',
    '| MacBook Pro / ThinkPad | ☐ Bestellt | IT-Abteilung |',
    '| Monitor (27 Zoll) | ☐ Bestellt | IT-Abteilung |',
    '| NDA | ☐ Unterschrieben | Tag 1 |',
    '| Skills richtig | {0}/5 |',
    '| Slack | ☐ Angelegt | Tag 1 |',
    '| Standort zutreffend | {0}/5 |',
    '| System | Zugang | Frist |',
    '| Tastatur + Maus | ☐ Bestellt | IT-Abteilung |',
    '| Termin | Person | Thema | Datum |',
    '| VPN-Zugang | ☐ Angelegt | Tag 1 |',
    '| Woche | Thema | Ziel |',
    '| {0} | {1}% | {2}% | {3} |',
    'ℹ️ Cap erreicht ({0} = {1}) – keine Anpassung.',
    '✅ {0}: {1} → {2} (Rohgewicht, normalisiert auf 100)',
)


def test_p9_4_neue_msgids_in_allen_katalogen():
    """Alle 115 neuen P9.4-Keys liegen je Sprache im .mo, nicht leer; DE = Identitaet."""
    assert len(P9_4_NEUE_KEYS) == len(set(P9_4_NEUE_KEYS)) == 115, \
        "P9.4-Keyliste muss 115 eindeutige Keys haben"
    for key in P9_4_NEUE_KEYS:
        for lang in LANGS:
            cat = _catalog(lang)
            assert key in cat._catalog, f"{lang}: Key {key!r} fehlt im .mo (P9.4)"
            assert str(cat._catalog[key]).strip(), f"{lang}: msgstr fuer {key!r} leer"
        assert _catalog("de").gettext(key) == key, f"DE: msgstr != msgid fuer {key!r}"


def test_p9_4_uebersetzt_in_en_fr_ar():
    """Stichproben der P9.4-Uebersetzungen (Design-Entscheidung-Erstfassung)."""
    erwartet = {
        "## 📹 Meeting-Details": ("## 📹 Meeting details", "## 📹 Détails de la réunion", "## 📹 تفاصيل الاجتماع"),
        "Erfahrung (Jahre)": ("Experience (years)", "Expérience (années)", "الخبرة (سنوات)"),
        "Sehr geehrte(r) {0},": ("Dear {0},", "Madame, Monsieur {0},", "عزيزي(ة) {0}،"),
        "Welche Cloud-Plattformen haben Sie eingesetzt?": ("Which cloud platforms have you used?", "Quelles plateformes cloud avez-vous utilisées ?", "ما هي المنصات السحابية التي استخدمتها؟"),
        "Dein Ansprechpartner: {0}": ("Your contact person: {0}", "Votre interlocuteur : {0}", "جهة الاتصال الخاصة بك: {0}"),
        "| Gerät | Status | Zuständig |": ("| Device | Status | Responsible |", "| Appareil | Statut | Responsable |", "| الجهاز | الحالة | المسؤول |"),
        "✅ {0}: {1} → {2} (Rohgewicht, normalisiert auf 100)": ("✅ {0}: {1} → {2} (raw weight, normalized to 100)", "✅ {0} : {1} → {2} (poids brut, normalisé sur 100)", "✅ {0}: {1} → {2} (الوزن الخام، مُطبيع إلى 100)"),
    }
    for key, (en, fr, ar) in erwartet.items():
        got = {"en": _catalog("en").gettext(key),
               "fr": _catalog("fr").gettext(key),
               "ar": _catalog("ar").gettext(key)}
        assert got == {"en": en, "fr": fr, "ar": ar}, f"{key!r}: {got}"


def test_p9_4_templates_gewrappt():
    """Quelltext-Regression: die Klasse-E-Templates laufen beim Erzeugen durch _().
    Bewusst NICHT geprueft: VIDEO_HEADING/_badge_icon/Keyword-Matching (Erkennung)."""
    comp = COMPONENTS.read_text(encoding="utf-8")
    cand = CANDIDATE.read_text(encoding="utf-8")
    emp = EMPLOYER.read_text(encoding="utf-8")
    logic = (BASE / "webui" / "logic.py").read_text(encoding="utf-8")
    for s in (
        '_("Welche Cloud-Plattformen haben Sie eingesetzt?")',
        '_("## 📹 Meeting-Details")',
        '_("# Pre-Screening: {0}").format(name)',
        '_("# Onboarding-Checkliste: {0}").format(name)',
        '_("Sehr geehrte(r) {0},").format(name)',
        '_("# Feedback: {0}").format(name)',
        '_("## Gewichtungsanpassung")',
        '_("| Gerät | Status | Zuständig |")',
    ):
        assert s in comp, f"components.py: Klasse-E-Template nicht gewrappt: {s!r}"
    for s in (
        '_("# Selbstpräsentation: Kandidat #{0}").format(cand_id)',
        '_("## Ihre Leitfragen")',
        '_("Wann könnten Sie starten? Wie ist Ihre Gehaltsvorstellung?")',
    ):
        assert s in cand, f"candidate.py: Klasse-E-Template nicht gewrappt: {s!r}"
    for s in (
        '_(_label.split(" ", 1)[1])',
        '("📋 Profil extrahieren",',
        '("🛂 Visum pruefen",',
        '_("Erfahrung (Jahre)")',
    ):
        assert s in emp, f"employer.py: Klasse-E-Anzeige nicht gewrappt: {s!r}"
    for s in (
        '_("ℹ️ Cap erreicht ({0} = {1}) – keine Anpassung.")',
        '_("✅ {0}: {1} → {2} (Rohgewicht, normalisiert auf 100)")',
    ):
        assert s in logic, f"logic.py: Feedback-Rueckgabe nicht gewrappt: {s!r}"


def test_p9_4_agent_tasks_labels_deutsch_und_gewrappt():
    """_agent_tasks ist ein Anzeige-Dict: deutsche msgids, Uebersetzung beim Konsum
    (Renderzeit, keine Importzeit). Die alten englischen Labels sind weg."""
    emp = EMPLOYER.read_text(encoding="utf-8")
    for alt in ('"📋 Extract Profile"', '"🎯 Match Candidate"',
                '"🛂 Check Visa"', '"🔒 Check GDPR"', '"💡 Explain Match"'):
        assert alt not in emp, f"altes englisches Task-Label noch vorhanden: {alt}"
    assert '"📋 Profil extrahieren"' in emp
    assert '_(_label)' in emp          # Konsum im Expander/Fehlt-Zweig


# ─── P9.5 (07.10.2026): Agent-Details-Titel + Status-Timeline ───
# Guard-Tests gegen die Testlücke von test_p9_4_agent_tasks_labels_deutsch_und_gewrappt:
# jener Test prüfte nur, dass der CODE die deutschen Labels enthält — nicht, ob die
# Laufzeit-Keys (_agent_tasks-Liste + Badge-Variante ohne Emoji) in den Katalogen
# existieren. Ebenso dürfen die Status-Timelines keine Roh-Slugs mehr zeigen.


def test_p9_5_agent_tasks_keys_in_allen_katalogen():
    """P9.5: Alle 9 `_agent_tasks`-Labels liegen in beiden Varianten (Expander-Key
    MIT Emoji, Badge-Key via `label.split(" ", 1)[1]` OHNE Emoji) in allen 4
    Katalogen — jeweils mit nicht-leerem msgstr.

    Liest die Laufzeit-Liste `_agent_tasks = [ … ]` aus employer.py als Text und
    extrahiert die String-Paare per Regex (derselbe Ansatz wie der P9.4-Test — nur
    dass hier die KATALOG-Seite geprüft wird, nicht die Code-Seite)."""
    emp = EMPLOYER.read_text(encoding="utf-8")
    m = re.search(r"_agent_tasks\s*=\s*\[(.*?)\]", emp, re.S)
    assert m, "_agent_tasks-Liste in employer.py nicht gefunden"
    pairs = re.findall(r'\("([^"]+)",\s*"([^"]+)"\)', m.group(1))
    labels = [label for label, _glob in pairs]
    assert len(labels) == 9, f"9 Labels erwartet, gefunden: {labels!r}"

    for label in labels:
        for key in (label, label.split(" ", 1)[1]):      # Expander-Key + Badge-Key
            for lang in LANGS:
                cat = _catalog(lang)
                assert key in cat._catalog, f"{lang}: fehlender Katalog-Key {key!r}"
                assert str(cat._catalog[key]).strip(), f"{lang}: leerer msgstr für {key!r}"

    # Extra-Assert: der eine fehlende Badge-Key (ohne Emoji) aus dieser Runde.
    for lang in LANGS:
        assert "Match erklaeren" in _catalog(lang)._catalog, \
            f"{lang}: Badge-Key 'Match erklaeren' fehlt im Katalog"


def test_p9_5_status_timeline_klartext():
    """P9.5: Die Status-Timelines in candidate.py laufen über `status_label()`
    (Klartext aus `STATUS_LABELS`) statt über die Roh-Slugs.

    Bewusst NICHT geprüft (beabsichtigt): die Komponenten-Zustandsfelder
    `"status": "done" if …` bleiben Rohwert — das ist der Zustands-Enum der
    Timeline-Komponente, keine Anzeige für den Nutzer."""
    cand = CANDIDATE.read_text(encoding="utf-8")
    # Vorhandensein: je mind. 1 Treffer (Codemarken _tab_profil/_tab_bewerbungen
    # bzw. _tab_onboarding).
    assert "status_label(h_status)" in cand, \
        "status_label(h_status) fehlt — Timeline zeigt Roh-Slug"
    assert "status_label(_h_status)" in cand, \
        "status_label(_h_status) fehlt — Timeline zeigt Roh-Slug"
    # Abwesenheit der 3 rohen Muster.
    for roh in ('f"{h_status}"', 'f"{h_icon} {h_status}"', 'f"{_h_icon} {_h_status}"'):
        assert roh not in cand, f"roher Status-Slug in Timeline: {roh!r}"


# ─── Rollout 12.10.2026: neue Admin-/MCP-/Logic-msgids ──────────────────────
# Regression-Guard zur Katalog-Pflege: Jedes literal genutzte Erstargument von
# _()/tr()/_gettext() aus admin.py + den beiden MCP-Servern muss in ALLEN vier
# Katalogen liegen (nicht-leer; DE = Identitaet). Dazu die dynamischen Keys, die
# per Wert durch den Katalog laufen: die 7 Wochentage (mcp-meeting-server.py
# `tr(day_name_de[start.weekday()], language)`) und die 5 `logic.change_password`-
# Meldungen (Konsum via `_(msg)` in admin/candidate/employer).
# Extraktion = AST (nur Literale, keine f-Strings) — wie in der Rollout-Vorlage.
_ROLLOUT_QUELLEN = (
    BASE / "webui" / "pages" / "admin.py",
    BASE / "mcp-email-server.py",
    BASE / "mcp-meeting-server.py",
)
_ROLLOUT_DYNAMISCH = (
    "Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag",
    "Benutzer nicht gefunden.",
    "Altes Passwort ist nicht korrekt.",
    "Neues Passwort muss mindestens 8 Zeichen lang sein.",
    "Neues Passwort darf nicht dem alten Passwort entsprechen.",
    "Passwort geändert.",
)


def _rollout_genutzte_msgids() -> set[str]:
    keys: set[str] = set()
    for path in _ROLLOUT_QUELLEN:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            name = f.id if isinstance(f, ast.Name) else (
                f.attr if isinstance(f, ast.Attribute) else None)
            if name not in {"_", "tr", "_gettext"} or not n.args:
                continue
            a0 = n.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                keys.add(a0.value)
    return keys | set(_ROLLOUT_DYNAMISCH)


def test_rollout_1210_genutzte_msgids_in_allen_katalogen():
    """Jeder genutzte Rollout-msgid liegt nicht-leer in allen 4 Katalogen, DE = Identitaet."""
    keys = _rollout_genutzte_msgids()
    assert len(keys) >= 240, f"Extraktion zu klein: {len(keys)}"
    for key in keys:
        for lang in LANGS:
            cat = _catalog(lang)
            assert key in cat._catalog, f"{lang}: Rollout-Key {key!r} fehlt im .mo"
            assert str(cat._catalog[key]).strip(), f"{lang}: leerer msgstr für {key!r}"
        assert _catalog("de").gettext(key) == key, f"DE: msgstr != msgid für {key!r}"
