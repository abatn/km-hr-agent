"""Tests für die Sperr-Schlüssel aus Firma und Stellenanzeige."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

_spec = importlib.util.spec_from_file_location("jobs_keys", SCRIPTS / "jobs_keys.py")
keys = importlib.util.module_from_spec(_spec)
sys.modules["jobs_keys"] = keys
_spec.loader.exec_module(keys)

BA_URL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-1003940671-S"
EURES_URL = "https://europa.eu/eures/portal/jv-se/jv-details/MTAwMDEtMTAwMzk1MTEwNC1T IDE?lang=de"


def test_firma_key_ohne_rechtsform_und_umlaute():
    assert keys.firma_key("Permacon GmbH") == "permacon"
    assert keys.firma_key("PERMACON") == "permacon"
    assert keys.firma_key("  Permacon   ") == "permacon"
    assert keys.firma_key("Müller & Söhne") == "muller-sohne"
    assert keys.firma_key("Bäckerei Kröger") == "backerei-kroger"


def test_firma_key_entfernt_ev_und_gmbh_co_kg():
    assert keys.firma_key("AWO Regionalverband Mitte-West Thüringen e.V.") == (
        "awo-regionalverband-mitte-west-thuringen"
    )
    assert keys.firma_key("Beispiel GmbH & Co. KG") == "beispiel"
    assert keys.firma_key("Beispiel GmbH & Co KG") == "beispiel"
    assert keys.firma_key("Beispiel GmbH & Co. KG.") == "beispiel"


def test_firma_key_leer():
    assert keys.firma_key("") == ""
    assert keys.firma_key(None) == ""


def test_anzeige_keys_ba_url_hat_id_zuerst():
    result = keys.anzeige_keys(BA_URL, "Permacon GmbH", "Pflegefachkraft (m/w/d)")
    assert result[0] == "id:10001-1003940671-S"
    assert result[1].startswith("hash:")
    assert len(result) == 2


def test_anzeige_keys_eures_url_hat_id_zuerst():
    result = keys.anzeige_keys(EURES_URL, "Hotel Beispiel", "Rezeptionist")
    assert result[0] == "id:MTAwMDEtMTAwMzk1MTEwNC1T"


def test_anzeige_keys_ohne_id_nur_hash():
    result = keys.anzeige_keys("https://example.org/karriere/stelle-42", "Firma AG", "Koch")
    assert len(result) == 1
    assert result[0].startswith("hash:")


def test_hash_stabil_und_abhaengig():
    a = keys.anzeige_keys("", "Permacon GmbH", "Pflegefachkraft")
    b = keys.anzeige_keys("https://example.org/x", "permacon", "  Pflegefachkraft ")
    assert a == b
    c = keys.anzeige_keys("", "Permacon GmbH", "Altenpfleger")
    assert a != c
    d = keys.anzeige_keys("", "Andere Firma GmbH", "Pflegefachkraft")
    assert a != d


def test_ist_gesperrt():
    k = keys.anzeige_keys(BA_URL, "Permacon GmbH", "Pflegefachkraft")
    assert keys.ist_gesperrt(k, {k[0]})
    assert keys.ist_gesperrt(k, {k[1]})
    assert keys.ist_gesperrt(k, [k[0]])
    assert not keys.ist_gesperrt(k, {"id:999", "hash:0000"})
    assert not keys.ist_gesperrt([], {k[0]})
