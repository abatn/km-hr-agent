"""Vertragstests fuer den Onboarding-Generator (19.10.2026, DB-Quelle).

Deckt die Umstellung ab: Arbeitgeber-Portal nutzt **DB-Bewerber mit Status
`eingestellt`**, Admin/Demo bleibt Profil-Dateien. Quelle der Regel:
`skills/generate-onboarding/SKILL.md` §1, `knowledge/portal/employer-board.md` §3(c).

Keine UI-Ausfuehrung: Source-/AST-/Katalog-Pruefungen (analog
`tests/test_board_actions.py`).
"""
from __future__ import annotations

import ast
import gettext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMP = (ROOT / "webui/pages/employer.py").read_text(encoding="utf-8")
COMP = (ROOT / "webui/components.py").read_text(encoding="utf-8")
ADMIN = (ROOT / "webui/pages/admin.py").read_text(encoding="utf-8")
SKILL = (ROOT / "skills/generate-onboarding/SKILL.md").read_text(encoding="utf-8")


def _fn_seg(src: str, name: str) -> str:
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(src, node) or ""
    raise AssertionError(f"Funktion {name} nicht gefunden")


def test_generator_signatur_optional_kwonly():
    """Employer-Parameter sind keyword-only mit Default -> Admin-Aufruf bleibt gueltig."""
    seg = _fn_seg(COMP, "onboarding_generator_section")
    assert "candidates: list[tuple] | None = None" in seg
    assert "firma: str = \"\"" in seg
    # Admin ruft ohne Argumente -> Profil-Modus bleibt erhalten.
    assert "onboarding_generator_section()" in ADMIN


def test_employer_seite_nutzt_db_quelle_und_statusfilter():
    seg = _fn_seg(EMP, "_page_onboarding")
    # Quelle = DB, Status-Filter auf applications.status (nicht candidates.status).
    assert "a.status = 'eingestellt'" in seg
    assert "c.lebenslauf_text" in seg
    assert "candidates=" in seg and "firma=_firma" in seg
    # Genau eine Zeile je Kandidat (letzte eingestellte Bewerbung).
    assert "ORDER BY a2.aktualisiert_am DESC" in seg
    # Kein Zugriff auf die Profil-Liste im Employer-Pfad.
    assert "list_profiles" not in seg


def test_generator_db_und_profil_zweig():
    seg = _fn_seg(COMP, "onboarding_generator_section")
    assert "if candidates is None:" in seg
    assert "row_by_id is not None" in seg
    assert "logic.list_profiles()" in seg
    # DB-Modus: Name aus der DB, Mentor eindeutig per candidate_id.
    assert "mentor_candidate_id = cand_id" in seg
    assert "AND candidate_id = ?" in seg
    # Dateiname im DB-Modus mit Kandidaten-ID (Kollisionsschutz).
    assert "onboarding-{kandidat_name}-{sd.strftime('%Y-%m-%d')}.md" in seg
    # Firma dynamisch, Fallback unveraendert.
    assert "**Betreff:** Willkommen bei {0}!" in seg
    assert "**Betreff:** Willkommen bei TechVision GmbH!" in seg
    # Transparenz-Hinweis (lokal, kein Mailversand).
    assert "kein automatischer Mailversand" in seg


def test_freigabe_report_wird_angezeigt():
    seg = _fn_seg(EMP, "_page_onboarding")
    assert "onboarding-freigabe-bewerbung-{app_id}.md" in seg
    assert "Freigabe-Report" in seg


def test_skill_spec_nennt_db_quelle():
    assert "applications.status = 'eingestellt'" in SKILL
    assert "list_profiles()" in SKILL
    assert "Kein Mailversand" in SKILL


def test_neue_i18n_keys_in_allen_katalogen():
    keys = [
        "**Betreff:** Willkommen bei {0}!",
        "Keine eingestellten Kandidaten gefunden.",
        "Checkliste wird lokal in ergebnisse/ gespeichert — kein automatischer Mailversand.",
        "Freigabe-Report",
    ]
    for lang in ("de", "en", "fr", "ar"):
        mo = ROOT / "webui/locales" / lang / "LC_MESSAGES" / "messages.mo"
        with mo.open("rb") as fh:
            cat = gettext.GNUTranslations(fh)
        for key in keys:
            got = cat.gettext(key)
            assert got, (lang, key)
            if lang == "de":
                assert got == key, (lang, key)
            else:
                assert got != key, (lang, key)
