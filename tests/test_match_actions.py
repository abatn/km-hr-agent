"""P0-3 (29.09.2026): Match-Seite — zustandsbewusste Aktionen, application_id-Dialoge.

Reine Funktionen (webui/pages/employer.py, Modulebene im Bereich _page_match):
  ALLOWED_TRANSITIONS, _legal_actions, _bar_pct, _invite_termin_error, _parse_kandidat_param
Plus Quelltext-Inspektion der Dialog-Handler (kein UI-Start, KEINE DB-Zugriffe).
"""
import re
from datetime import datetime
from pathlib import Path

import pytest

from webui.pages import employer as emp

SRC = (Path(__file__).resolve().parent.parent / "webui" / "pages" / "employer.py").read_text(encoding="utf-8")


def _slice(text: str, start: str, end_marker: str) -> str:
    i = text.index(start)
    j = text.index(end_marker, i) + len(end_marker)
    return text[i:j]


# ─── _legal_actions: exakt ALLOWED_TRANSITIONS ─────────────────────────────

def test_whitelist_unveraendert():
    assert emp.ALLOWED_TRANSITIONS == {
        "eingegangen": {"angesehen", "abgelehnt"},
        "angesehen": {"eingeladen", "abgelehnt"},
        "eingeladen": {"eingestellt", "abgelehnt"},
    }


@pytest.mark.parametrize("status,erwartet", [
    ("eingegangen", ["angesehen", "abgelehnt"]),
    ("angesehen", ["eingeladen", "abgelehnt"]),
    ("eingeladen", ["eingestellt", "abgelehnt"]),
])
def test_legal_actions_aktive_status(status, erwartet):
    assert emp._legal_actions(status) == erwartet
    assert set(emp._legal_actions(status)) == emp.ALLOWED_TRANSITIONS[status]


@pytest.mark.parametrize("status", ["eingestellt", "abgelehnt", "zurückgezogen", "", None, "quatsch"])
def test_legal_actions_final_oder_unbekannt_leer(status):
    assert emp._legal_actions(status) == []


def test_eingegangen_hat_kein_einladen_und_kein_einstellen():
    acts = emp._legal_actions("eingegangen")
    assert "eingeladen" not in acts and "eingestellt" not in acts
    assert emp._MATCH_ACTION_LABEL["angesehen"] == "Als angesehen markieren"


# ─── _bar_pct: Punkte / KATEGORIE_MAX ──────────────────────────────────────

def test_bar_pct_beispiele_aus_dem_auftrag():
    assert emp._bar_pct("kern", 30) == 100
    assert emp._bar_pct("erfahrung", 10) == 33
    assert emp._bar_pct("bildung", 15) == 100


def test_bar_pct_alle_kategorien_gegen_kategorie_max():
    for key, mx in emp.logic.KATEGORIE_MAX.items():
        assert emp._bar_pct(key, mx) == 100, key
        assert emp._bar_pct(key, 0) == 0, key
        assert emp._bar_pct(key, mx / 2) == 50, key


def test_bar_pct_kappt_und_ist_robust():
    assert emp._bar_pct("kern", 999) == 100
    assert emp._bar_pct("kern", -5) == 0
    assert emp._bar_pct("kern", None) == 0
    assert emp._bar_pct("unbekannt", 10) == 0
    # alte Fehlformel: erfahrung 10 -> min(10*10,100)=100 statt 33
    assert emp._bar_pct("erfahrung", 10) != 100


# ─── _invite_termin_error ──────────────────────────────────────────────────

JETZT = datetime(2026, 9, 29, 14, 30, 45)


def test_termin_zukunft_ok():
    assert emp._invite_termin_error("2026-09-30", "10:00", JETZT) is None
    assert emp._invite_termin_error("2026-09-29", "14:30", JETZT) is None  # gleiche Minute erlaubt
    assert emp._invite_termin_error("2026-09-29", "18:00", JETZT) is None


def test_termin_vergangenheit_abgelehnt():
    assert "Vergangenheit" in emp._invite_termin_error("2026-09-28", "10:00", JETZT)
    assert "Vergangenheit" in emp._invite_termin_error("2026-09-29", "09:00", JETZT)


@pytest.mark.parametrize("datum,zeit", [(None, "10:00"), ("", "10:00"), ("kein-datum", "10:00"),
                                         ("2026-09-30", ""), ("2026-09-30", "25:99"), ("2026-09-30", None)])
def test_termin_ungueltig_gibt_meldung(datum, zeit):
    msg = emp._invite_termin_error(datum, zeit, JETZT)
    assert isinstance(msg, str) and msg


# ─── _parse_kandidat_param ─────────────────────────────────────────────────

@pytest.mark.parametrize("raw,erwartet", [("5", 5), (" 12 ", 12), (7, 7), ("0", None), ("-3", None),
                                           ("abc", None), ("", None), (None, None), ("1.5", None)])
def test_parse_kandidat_param(raw, erwartet):
    assert emp._parse_kandidat_param(raw) == erwartet


# ─── Quelltext-Inspektion: Dialoge tragen application_id ───────────────────

def test_kein_active_app_ids_mehr_zur_zielauswahl():
    assert "_active_app_ids" not in SRC
    for alt in ("_invite_cid", "_reject_cid", "_hire_cid"):
        assert alt not in SRC


def test_dialog_kontexte_tragen_app_id():
    for name in ("_invite_ctx", "_reject_ctx", "_hire_ctx"):
        assert f'{name} = {{"app_id": 0}}' in SRC, name


def test_do_handler_nutzen_app_info_und_legal_pro_app_id():
    for def_name, close in (("def do_invite", "ui.button(_('Einladen'), on_click=do_invite)"),
                            ("def do_reject", "ui.button(_('Ablehnen'), on_click=do_reject)"),
                            ("def do_hire", "ui.button(_('Einstellen'), on_click=do_hire)")):
        sl = _slice(SRC, def_name, close)
        assert "app_id = _" in sl and '["app_id"]' in sl, def_name
        assert "_app_info(app_id)" in sl, def_name
        assert sl.count("_legal(") == 1, def_name
        # Guard steht VOR dem UPDATE
        assert sl.index("_legal(") < sl.index("UPDATE applications"), def_name
        assert "WHERE id=?" in sl


def test_reject_wirkt_nur_auf_gewaehlte_bewerbung():
    sl = _slice(SRC, "def do_reject", "ui.button(_('Ablehnen'), on_click=do_reject)")
    assert "executemany" not in sl
    assert sl.count('queue_agent_task("send_rejection"') == 1
    assert '"application_id": app_id' in sl
    # interne Notiz landet in application_status_history.notizen (Schema-Feld existiert)
    assert "notizen" in sl and "reject_reason.value" in sl


def test_keine_toten_eingaben():
    assert "invite_message" not in SRC
    # reject_reason wird ausgewertet
    assert SRC.count("reject_reason") >= 3


def test_lambda_defaults_binden_loop_variablen():
    block = _slice(SRC, "for _ns in _legal_actions(app_status):", "color=negative flat no-caps\")")
    for m in re.finditer(r"on_click=lambda ([^:]*):", block):
        params = m.group(1)
        assert "=" in params, f"Lambda ohne Default-Bindung: {params}"
    assert "lambda _a=app_id" in block
    assert "_t=titel" in block and "_n=cand_name" in block


def test_karte_hat_keine_globalen_drei_buttons_mehr():
    # jede Aktion nur einmal im Aktionszeilen-Loop, nicht mehr mit candidate_id
    assert "reject_dialog.open()" in _slice(SRC, "def _open_reject", "reject_dialog.open()")
    assert "on_click=lambda n=cand_name, cid=c_id" not in SRC


def test_timer_ruft_tick_nicht_direkt_refresh():
    assert "ui.timer(interval=15.0, callback=_tick)" in SRC
    assert "ui.timer(interval=15.0, callback=match_content.refresh)" not in SRC
    tick = _slice(SRC, "    def _tick():", "match_content.refresh()")
    assert "_data_signature()" in tick and "!=" in tick


def test_balken_nutzt_bar_pct_nicht_die_alte_formel():
    assert "kat_score * 10" not in SRC and "kat_score * 2" not in SRC
    assert "_bar_pct(kat_key, kat_score)" in SRC


# ─── M-13 (01.10.2026): kein Doppel-Score im Match-Klappenkopf ─────────────

def test_m13_score_bar_ohne_eigenes_label_und_eine_kategorie_zeile():
    """M-13-Fix: `score_bar(total, show_label=False)` + genau ein Kategorie-Label.

    Defekt war „53/100" (score_bar-Eigenlabel) ZUSÄTZLICH zu „53/100 (Schwach)".
    Echter Nachweis: `tests/e2e_m13_score_once.py` (14 Klappen, je 1 Treffer).
    """
    block = _slice(SRC, 'with _job_exp.add_slot("header"):',
                   "ui.label(_('{0}/100 ({1})').format(total, _(kategorie)))")
    assert "score_bar(total, show_label=False)" in block
    assert block.count("/100") == 1, "Kopf darf genau EIN Score-Label enthalten"
    assert "ui.label(_('{0}/100 ({1})').format(total, _(kategorie)))" in block


# ─── M-18 (01.10.2026): Skills nicht mehr still auf 4 kürzen ──────────────

def test_m18_skills_kuerzung_markiert():
    # Prompt 2 (13.10.2026): Top 3 + klappbarer Marker "Alle {n} anzeigen" statt Tooltip-Chip.
    assert 'str(h_skills).split(",")[:4]' not in SRC
    assert 'split(",") if s.strip()]' in SRC
    assert "_top, _rest = _skills[:3], _skills[3:]" in SRC
    assert "_('Alle {0} anzeigen').format(len(_rest))" in SRC
    assert "_rest_row.set_visibility(False)" in SRC
    assert "_('Passung')" in SRC
    assert "_('Live-Score aus DB')" not in SRC
