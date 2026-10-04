"""N-M1 (Dialog-Buttons ohne Tailwind-bg-*) + N-M2 (15-s-Timer zerstört Klappen nicht).

N-M1: Befund — die Match-Dialogbestätigungen nutzten `bg-blue-700/bg-red-600/
bg-green-600 text-white` (Tailwind); die Farbwirkung war unbelegt. Soll: Quasar-
Semantik `color=positive/negative/primary`. Beweis-Ziel: kein Button mit `bg-`.

N-M2: Befund — `ui.timer(interval=15.0, callback=match_content.refresh)` rechnete
alle 15 s neu und klappte offene Details zu. Soll: Refresh nur bei Datenänderung
(Signatur aus COUNT/MAX). Ist bereits im Code (`_tick`/`_data_signature`); dieser
Test hält es fest. Verhalten: `tests/e2e_nm2_expansion_persist.py`.

Reine Quelltext-Inspektion — keine DB, keine UI.
"""
import re
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "webui" / "pages" / "employer.py"
       ).read_text(encoding="utf-8")

# ui.button(...) samt angehängter Methoden (.props/.classes/...) — eine Klammer-Ebene
_BTN = re.compile(
    r"ui\.button\((?:(?:[^()])|(?:\([^()]*\)))*\)"
    r"(?:\.(?:props|classes|style|tooltip)\([^)]*\))*", re.S)


# ─── N-M1 ────────────────────────────────────────────────────────────────

def test_nm1_kein_button_mit_tailwind_bg():
    treffer = [b.group(0) for b in _BTN.finditer(SRC) if "bg-" in b.group(0)]
    assert not treffer, f"Button(s) mit Tailwind-bg-*: {treffer}"


def test_nm1_dialogbestaetigungen_nutzen_quasar_semantik():
    assert 'ui.button(_(\'Einladen\'), on_click=do_invite).props("color=primary")' in SRC
    assert 'ui.button(_(\'Ablehnen\'), on_click=do_reject).props("color=negative")' in SRC
    assert 'ui.button(_(\'Einstellen\'), on_click=do_hire).props("color=positive")' in SRC
    # alte Tailwind-Klassen dürfen nicht zurückkehren
    for alt in ("bg-blue-700 text-white", "bg-red-600 text-white",
                "bg-green-600 text-white", 'classes("bg-gray-100")'):
        assert alt not in SRC, alt


# ─── N-M2 ────────────────────────────────────────────────────────────────

def test_nm2_timer_nutzt_signatur_statt_direktem_refresh():
    assert "ui.timer(interval=15.0, callback=_tick)" in SRC
    assert "ui.timer(interval=15.0, callback=match_content.refresh)" not in SRC


def test_nm2_tick_refresh_nur_bei_geaenderter_signatur():
    i = SRC.index("    def _tick():")
    block = SRC[i:i + 220]
    assert "_data_signature()" in block
    assert "if sig != _sig[\"v\"]:" in block
    assert "match_content.refresh()" in block


def test_nm2_signatur_liest_aenderungszeit_und_count():
    i = SRC.index("def _data_signature():")
    block = SRC[i:i + 1500]
    assert "MAX(a.aktualisiert_am)" in block
    assert "COUNT(*)" in block
    assert "applications" in block
