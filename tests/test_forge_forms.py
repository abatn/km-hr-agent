"""FORGE-Formtransfer: Genom, Zero-Shot-Matching, ehrliche Lücken (ohne Browser)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("forge_forms", ROOT / "scripts" / "forge_forms.py")
forge = importlib.util.module_from_spec(_spec)
sys.modules["forge_forms"] = forge
_spec.loader.exec_module(forge)

FIX = ROOT / "tests" / "fixtures" / "forge"


def _html(name: str) -> str:
    return (FIX / f"{name}.html").read_text(encoding="utf-8")


def test_parse_findet_alle_felder():
    felder = forge.parse(_html("payapi"))
    assert len(felder) == 13
    assert {f.expect for f in felder} >= {"first_name", "email", "card_number", "consent"}


def test_genom_enthaelt_kernsemantiken():
    g = forge.learn(_html("payapi"))
    assert len(g["semantics"]) >= 12
    for sem in ("first_name", "last_name", "email", "phone", "street", "zip", "city",
                "country", "card_number", "card_expiry", "card_cvc", "notes", "consent"):
        assert sem in g["semantics"], sem


def test_transfer_auf_bewerbung_ohne_luecken():
    g = forge.learn(_html("payapi"))
    mapping = forge.match(g, _html("apply"))
    erwartet = [e for e in mapping if e["feld"].expect]
    assert len(erwartet) == 10
    falsch = [(e["feld"].expect, e["semantic"]) for e in erwartet
              if e["semantic"] != e["feld"].expect]
    assert not falsch, falsch


def test_transfer_auf_behoerde_dokumentiert_luecken():
    g = forge.learn(_html("payapi"))
    mapping = forge.match(g, _html("behoerde"))
    offen = {e["feld"].expect for e in mapping
             if e["feld"].expect and e["semantic"] is None}
    assert offen == {"birthdate", "nationality", "passport", "purpose"}


def test_synonyme_variante_bleibt_übertragbar():
    g = forge.learn(_html("payapi"))
    import random
    v = forge.varianten(_html("apply"), random.Random(1))["synonyme"]
    erwartet = [e for e in forge.match(g, v) if e["feld"].expect]
    assert all(e["semantic"] == e["feld"].expect for e in erwartet)


def test_unbekanntes_feld_bleibt_leer():
    g = forge.learn(_html("payapi"))
    html = _html("apply").replace("</form>", '<label for="x">Firmenname</label><input id="x" name="firma"></form>')
    treffer = [e for e in forge.match(g, html) if e["feld"].ident == "x"]
    assert treffer and treffer[0]["semantic"] is None
