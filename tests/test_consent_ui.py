"""Consent-UI: Registrierungs-Einwilligung (AGB/Datenschutz) + Aufnahme-Einwilligung.

Prüft die Oberfläche in `webui/pages/login.py` und `webui/pages/candidate.py`:

* Pflicht-Checkbox bei Kandidat:innen- und Arbeitgeber-Registrierung ist
  **nicht** vorangehakt, verlinkt `/agb` und `/datenschutz` und blockiert das
  INSERT, solange sie leer ist; nach dem INSERT werden die Nachweise `terms`
  und `privacy` mit `db.record_consent` geschrieben.
* Aufnahme-Einwilligung (`recording`) ist eine **eigene**, nicht vorangehakte
  Checkbox und gated `&record=6000`; ohne Haken entsteht der Link ohne Aufnahme
  und es wird kein Nachweis geschrieben.
* Der HR-Raumfall bleibt unverändert (`&record=off`, kein `record=6000`
  außerhalb der Kandidaten-Selbstpräsentation).

Rechtsgrundlage: Art. 7 Abs. 2/4 DSGVO, Erwägungsgrund 32/42/43;
§ 26 Abs. 2 BDSG; knowledge/legal/recording-consent.md.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from webui import db
from webui.pages import candidate as candidate_page
from webui.pages import login as login_page

ROOT = Path(__file__).resolve().parents[1]
LOGIN_SRC = (ROOT / "webui" / "pages" / "login.py").read_text(encoding="utf-8")
CAND_SRC = (ROOT / "webui" / "pages" / "candidate.py").read_text(encoding="utf-8")

REGISTRIERUNG_TEXT = "Ich akzeptiere die AGB und die Datenschutzerklärung"
AUFNAHME_TEXT = "Ich willige in die Aufzeichnung meiner Video-Vorstellung ein."


def _login_tree() -> ast.Module:
    return ast.parse(LOGIN_SRC)


def _cand_tree() -> ast.Module:
    return ast.parse(CAND_SRC)


def _funktion(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"Funktion {name} nicht gefunden")


def _strings(node: ast.AST) -> list[str]:
    return [
        n.value for n in ast.walk(node)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
    ]


# ─── Registrierung: AGB + Datenschutz ───────────────────────────────

def test_registrierung_checkbox_nicht_vorangehakt():
    """Erwägungsgrund 32: vorangekreuzte Kästchen sind keine Einwilligung."""
    fn = _funktion(_login_tree(), "_consent_checkbox")
    src = ast.get_source_segment(LOGIN_SRC, fn) or ""
    assert REGISTRIERUNG_TEXT in src
    assert re.search(r"value\s*=\s*False", src), "Checkbox muss value=False setzen"
    assert not re.search(r"value\s*=\s*True", src), "Checkbox darf nie vorangehakt sein"


def test_registrierung_checkbox_verlinkt_agb_und_datenschutz():
    fn = _funktion(_login_tree(), "_consent_checkbox")
    src = ast.get_source_segment(LOGIN_SRC, fn) or ""
    assert '"/agb"' in src
    assert '"/datenschutz"' in src
    assert "ui.link" in src


def test_kandidat_registrierung_blockiert_ohne_haken():
    assert "if not r_consent.value:" in LOGIN_SRC
    guard = LOGIN_SRC.index("if not r_consent.value:")
    insert = LOGIN_SRC.index("INSERT INTO candidates")
    assert guard < insert, "Consent-Guard muss VOR dem INSERT stehen"
    zwischen = LOGIN_SRC[guard:insert]
    assert "return" in zwischen, "ohne Haken darf kein INSERT laufen"
    assert "record_consent" not in zwischen, "ohne Haken darf nichts gespeichert werden"


def test_arbeitgeber_registrierung_blockiert_ohne_haken():
    assert "if not er_consent.value:" in LOGIN_SRC
    guard = LOGIN_SRC.index("if not er_consent.value:")
    insert = LOGIN_SRC.index("INSERT INTO employers")
    assert guard < insert
    zwischen = LOGIN_SRC[guard:insert]
    assert "return" in zwischen
    assert "record_consent" not in zwischen


def test_registrierung_schreibt_terms_und_privacy_nach_insert():
    """Beide Zwecke (getrennte Einwilligungen, Art. 7 Abs. 2) je Konto-Typ."""
    assert '_record_registration_consents(\n                                        "candidate", cur.lastrowid' in LOGIN_SRC
    assert '"employer", cur.lastrowid' in LOGIN_SRC
    fn = _funktion(_login_tree(), "_record_registration_consents")
    src = ast.get_source_segment(LOGIN_SRC, fn) or ""
    assert '"terms"' in src and '"privacy"' in src
    assert "db.CONSENT_VERSION" in src
    assert "db.record_consent" in src


def test_record_registration_consents_schreibt_zwei_zeilen(monkeypatch):
    """Laufzeit: zwei Aufrufe mit subject_type/subject_id/Zweck + Sprach-Nachweis."""
    calls: list[tuple] = []

    def fake_record(subject_type, subject_id, purpose, **kwargs):
        calls.append((subject_type, subject_id, purpose, kwargs))
        return len(calls)

    monkeypatch.setattr(db, "record_consent", fake_record, raising=False)
    monkeypatch.setattr(db, "CONSENT_VERSION", "2026-10-26", raising=False)

    login_page._record_registration_consents("candidate", 42, "fr")

    assert [c[2] for c in calls] == ["terms", "privacy"]
    assert all(c[0] == "candidate" and c[1] == 42 for c in calls)
    assert all(c[3]["language"] == "fr" for c in calls)
    assert all(c[3]["text_version"] == "2026-10-26" for c in calls)


# ─── Aufnahme-Einwilligung (Selbstpräsentation / Video) ─────────────

def test_aufnahme_checkbox_nicht_vorangehakt_und_mit_datenschutz_link():
    fn = _funktion(_cand_tree(), "_recording_consent_ui")
    src = ast.get_source_segment(CAND_SRC, fn) or ""
    assert AUFNAHME_TEXT in src
    assert re.search(r"value\s*=\s*False", src)
    assert not re.search(r"value\s*=\s*True", src)
    assert "/datenschutz" in src


def test_aufnahme_text_nennt_zweck_empfaenger_speicherdauer_widerruf_freiwilligkeit():
    """Pflichtinhalt nach Art. 13 DSGVO / § 26 Abs. 2 BDSG (Spec (e1))."""
    fn = _funktion(_cand_tree(), "_recording_consent_ui")
    src = ast.get_source_segment(CAND_SRC, fn) or ""
    for begriff in ("Zweck", "Empfänger", "Speicherung", "Widerruf", "Freiwillig"):
        assert begriff in src, f"Pflichtinhalt fehlt: {begriff}"


def test_aufnahme_nicht_mit_agb_gebuendelt():
    """Art. 7 Abs. 2 / ErwG 43: Aufnahme ist eine eigene Einwilligung."""
    fn = _funktion(_cand_tree(), "_recording_consent_ui")
    checkbox = next(
        n for n in ast.walk(fn)
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "checkbox"
    )
    label = " ".join(_strings(checkbox))
    assert AUFNAHME_TEXT in label
    assert "AGB" not in label
    assert "Datenschutz" not in label  # kein gebuendelter Pflichttext im Label


def test_url_ohne_einwilligung_traegt_keinen_aufnahmeparameter():
    url = candidate_page.selbstpraesentation_url("selfpresentation1234", recording_consent=False)
    assert url == "https://vdo.ninja/?push=selfpresentation1234"
    assert "record" not in url


def test_url_mit_einwilligung_traegt_aufnahmeparameter():
    url = candidate_page.selbstpraesentation_url("selfpresentation1234", recording_consent=True)
    assert url == "https://vdo.ninja/?push=selfpresentation1234&record=6000"


def test_record_6000_nur_in_gegateter_funktion():
    """`&record=6000` existiert genau einmal im Quelltext und hängt am Haken."""
    assert CAND_SRC.count('"&record=6000"') == 1
    fn = _funktion(_cand_tree(), "selbstpraesentation_url")
    gate = None
    for node in ast.walk(fn):
        if isinstance(node, ast.If) and any(
            isinstance(n, ast.Name) and n.id == "recording_consent"
            for n in ast.walk(node.test)
        ):
            gate = node
            break
    assert gate is not None, "kein `if recording_consent:` gefunden"
    assert any("&record=6000" in s for s in _strings(gate))
    # Kehrt die Funktion irgendwo außerhalb des Gates mit Aufnahme zurück?
    aussen = [n for n in ast.walk(fn) if isinstance(n, ast.Return) and not _ist_im(gate, n)]
    assert not any("&record=6000" in s for n in aussen for s in _strings(n))


def _ist_im(wurzel: ast.AST, ziel: ast.AST) -> bool:
    return any(n is ziel for n in ast.walk(wurzel))


def test_record_consent_recording_nur_im_haken_zweig():
    """Nachweis (`recording`) nur, wenn die separate Checkbox gesetzt ist."""
    tree = _cand_tree()
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "record_consent"
    ]
    assert len(calls) == 2, "genau zwei Aufnahme-Nachweise (Pre-Screen + Video)"
    for call in calls:
        assert isinstance(call.args[2], ast.Constant)
        assert call.args[2].value == "recording"
    eltern = _eltern(tree)
    for call in calls:
        node: ast.AST = call
        gated = False
        while node in eltern:
            node = eltern[node]
            if isinstance(node, ast.If) and isinstance(node.test, ast.Attribute):
                if node.test.attr == "value" and isinstance(node.test.value, ast.Name):
                    gated = node.test.value.id in ("rec_consent", "video_rec_consent")
                    break
        assert gated, "record_consent steht nicht in einem `if <checkbox>.value:`-Zweig"


def _eltern(tree: ast.AST) -> dict:
    """Eltern-Karte für AST-Knoten (Identität, keine Gleichheit)."""
    eltern: dict = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            eltern[child] = node
    return eltern


def test_link_erzeugung_nutzt_die_gegatete_url():
    """Beide Erzeuger (Pre-Screen + Video) bauen die URL über die Gateted-Funktion."""
    assert CAND_SRC.count("selbstpraesentation_url(") == 3  # Definition + 2 Aufrufer
    assert "meet_url = selbstpraesentation_url(room_name, recording_consent=bool(rec_consent.value))" in CAND_SRC
    assert "recording_consent=bool(video_rec_consent.value))" in CAND_SRC


# ─── HR-Raumfall bleibt unverändert ─────────────────────────────────

def test_hr_raum_weiterhin_record_off():
    """HR-Raumfall unverändert: Gast-Link `&record=off`, Director-Link ohne Parameter."""
    runner = (ROOT / "scripts" / "agent-runner.py").read_text(encoding="utf-8")
    components = (ROOT / "webui" / "components.py").read_text(encoding="utf-8")
    assert 'vdo.ninja/?room=prescreening{code}&record=off' in runner
    assert 'vdo.ninja/?director=prescreening{room_code}' in components
    assert "record=6000" not in runner
    assert "record=6000" not in components


def test_kein_record_6000_ausserhalb_der_kandidaten_selbstpraesentation():
    treffer = []
    for base in ("webui", "scripts"):
        for path in (ROOT / base).rglob("*.py"):
            if "record=6000" in path.read_text(encoding="utf-8", errors="replace"):
                treffer.append(path.relative_to(ROOT).as_posix())
    assert treffer == ["webui/pages/candidate.py"]


# ─── i18n: neue UI-Strings liegen in allen vier Katalogen ───────────

@pytest.mark.parametrize("lang", ["de", "en", "fr", "ar"])
def test_consent_strings_im_katalog(lang):
    po = (ROOT / "webui" / "locales" / lang / "LC_MESSAGES" / "messages.po").read_text(encoding="utf-8")
    for msgid in (
        REGISTRIERUNG_TEXT,
        "Bitte akzeptieren Sie AGB und Datenschutzerklärung, um sich zu registrieren.",
        AUFNAHME_TEXT,
        "🎬 Aufzeichnung der Selbstpräsentation (optional)",
        "Ohne Einwilligung wird der Link ohne Aufnahme erzeugt.",
        "Details: [Datenschutzerklärung](/datenschutz).",
    ):
        assert f'msgid "{msgid}"' in po, f"{lang}: msgid fehlt: {msgid}"


def test_mo_catalog_kennt_die_neuen_strings():
    """Kompilierter Katalog (.mo) enthält die Strings (sonst faellt die UI auf DE zurueck)."""
    import gettext

    cat = gettext.GNUTranslations(
        open(ROOT / "webui" / "locales" / "en" / "LC_MESSAGES" / "messages.mo", "rb")
    )
    assert cat.gettext(REGISTRIERUNG_TEXT) != REGISTRIERUNG_TEXT
    assert cat.gettext(AUFNAHME_TEXT) != AUFNAHME_TEXT
