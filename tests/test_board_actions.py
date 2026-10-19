"""Source-/MD-Vertrag fuer die 3 Board-Aktionen (MVP Arbeitgeber-UI, 19.10.2026).

Keine UI-/DB-Ausfuehrung: prueft Marker, Whitelist-Guard, Schreibsequenz,
DSGVO-Gate und die Ein-Guard-Regel des Visum-Triggers.
Spec: knowledge/portal/employer-board.md §3/§4.
"""
from __future__ import annotations

import ast
import gettext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EMP = (ROOT / "webui/pages/employer.py").read_text(encoding="utf-8")
COMP = (ROOT / "webui/components.py").read_text(encoding="utf-8")
ADMIN = (ROOT / "webui/pages/admin.py").read_text(encoding="utf-8")


def _fn_seg(src: str, name: str) -> str:
    """Quelltext-Segment einer (auch verschachtelten) Funktion per AST."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.get_source_segment(src, node) or ""
    raise AssertionError(f"Funktion {name} nicht gefunden")


def test_board_drawer_marker_und_technik():
    for marker in ("_board_drawer", "_bd_ctx", "_open_board_drawer",
                   "_bd_hire", "_bd_open_hire", "_bd_body"):
        assert marker in EMP, marker
    # NiceGUI-Layoutgrenze: rechts verankertes Dialog statt ui.right_drawer.
    assert 'ui.dialog().props("position=right")' in EMP
    assert "ui.right_drawer(" not in _fn_seg(EMP, "_page_board")


def test_board_rows_liefert_job_id():
    seg = _fn_seg(EMP, "_board_rows")
    assert "a.job_id" in seg
    assert '"job_id": r[1]' in seg


def test_board_hire_sequenz_und_live_guard():
    seg = _fn_seg(EMP, "_bd_hire")
    assert "_legal_actions(old_status)" in seg
    assert '"eingestellt" not in' in seg
    assert "UPDATE applications SET status='eingestellt'" in seg
    assert "INSERT INTO application_status_history" in seg
    assert "changed_by" in seg and "'arbeitgeber'" in seg
    # Reihenfolge: UPDATE -> History -> commit -> notify -> Queue-Hook.
    assert seg.index("UPDATE applications") < seg.index(".commit()")
    assert seg.index(".commit()") < seg.index("_notify_statuswechsel")
    assert seg.index("_notify_statuswechsel") < seg.index('queue_agent_task("onboarding_release"')
    assert '"trigger": "hr_klick_portal"' in seg


def test_visum_trigger_nur_ein_guard():
    # Genau EINE UI-Kopie des Guards liegt im geteilten Helper.
    assert COMP.count("json_extract(payload, '$.application_id') = ?") == 1
    assert "def visa_info_section" in COMP
    assert EMP.count("json_extract(payload, '$.application_id') = ?") == 0
    assert ADMIN.count("json_extract(payload, '$.application_id') = ?") == 0
    assert "def send_visa" not in EMP
    assert "def send_visa" not in ADMIN
    # Beide Arbeitgeber-Stellen + Admin rufen den Helper.
    assert EMP.count("visa_info_section(") >= 3  # Import + Stellen + Match + Board
    assert ADMIN.count("visa_info_section(") >= 1  # Aufruf (Import ohne Klammer)


def test_onboarding_ist_nur_navigation():
    seg = _fn_seg(EMP, "_bd_body")
    assert 'ui.navigate.to("/employer/onboarding")' in seg
    # Kein zweiter onboarding_release-Trigger aus dem Drawer.
    assert 'queue_agent_task("onboarding_release"' not in seg


def test_board_dsgvo_gate_und_passiv_unberuehrt():
    seg = _fn_seg(EMP, "_bd_body")
    assert "DOC_RELEASE_STATUS" in seg
    assert "Dokumente werden erst ab dem Status 'Eingeladen' sichtbar (DSGVO)." in seg
    # Klarname nur ueber die Gate-Funktion (nie r["name"] direkt).
    assert 'anzeige_name(r["name"], r["cid"], status)' in seg
    assert 'ui.label(r["name"])' not in seg
    # Passiv-Tab: keine Drawer-/Einstellen-Aktion (DSGVO, Spec §5).
    passiv = _fn_seg(EMP, "_pf_view")
    assert "_open_board_drawer" not in passiv
    assert "ui.button(_('Einstellen')" not in passiv
    assert "visa_info_section(" not in passiv


def test_match_button_bleibt_ausserhalb_des_kartenklicks():
    # Der Klickbereich (Textblock) endet vor dem Match-Button -> kein Doppel-Event.
    seg = _fn_seg(EMP, "_page_board")
    click = seg.index("cursor-pointer")
    button = seg.index("ui.button(_('Im Match öffnen')", click)
    assert click < button


def test_neue_i18n_keys_in_allen_katalogen():
    keys = [
        "Visum-Info/Schritte",
        "Dokumente werden erst ab dem Status 'Eingeladen' sichtbar (DSGVO).",
        "Bewerbungsdetails",
        "Erlaubte Folgeschritte: {0}",
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
