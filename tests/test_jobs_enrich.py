"""Kontakt-Anreicherung: Domain-Ableitung, Verifikation, E-Mail-/Formular-Parsing."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location("jobs_enrich", SCRIPTS / "jobs_enrich.py")
en = importlib.util.module_from_spec(_spec)
sys.modules["jobs_enrich"] = en
_spec.loader.exec_module(en)


def test_domaenen_entfernen_rechtsform_nicht_mitten_im_wort():
    d = en.domaenen("Alloheim Senioren-Residenzen SE", "DE")
    assert any(x.startswith("alloheim") for x in d)
    assert any("senioren" in x for x in d)


def test_domaenen_nutzen_laender_tld():
    assert all(d.endswith(".ch") for d in en.domaenen("Concordia", "CH"))
    assert all(d.endswith(".fr") for d in en.domaenen("Aboutir Emploi", "FR"))


def test_verifiziert_braucht_firmennamen_im_titel():
    html = "<html><head><title>Alloheim Senioren-Residenzen - Pflege</title></head><body>Kontakt</body></html>"
    assert en.verifiziert(html, "Alloheim Senioren-Residenzen SE")
    assert not en.verifiziert(html, "Concordia")


def test_mails_filtert_platzhalter_und_bevorzugt_info():
    html = "mail@example.com logo.png info@firma.de bewerbung@firma.de"
    treffer = en.mails(html)
    assert "info@firma.de" == treffer[0]
    assert all("example" not in m for m in treffer)


def test_formular_findet_link():
    html = '<a href="/kontakt">Kontakt</a><a href="/impressum">Impressum</a>'
    assert en.formular(html, "https://firma.de") == "https://firma.de/kontakt"


def test_blocklist_enthaelt_portale():
    assert "hotel.de" in en.BLOCKLIST
    assert "manpower.de" in en.BLOCKLIST
