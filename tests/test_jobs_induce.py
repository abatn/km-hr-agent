"""Automatische Induktion: Quellen-Mapping, Evidenz, Skill-Auswahl (ohne Netz)."""
from __future__ import annotations

import importlib.util
import pytest
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

for name in ("jobs_agent", "jobs_api", "jobs_ch", "jobs_eures", "jobs_jdp", "jobs_lhr"):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)

_spec_skill = importlib.util.spec_from_file_location("jobs_skill", SCRIPTS / "jobs_skill.py")
sk = importlib.util.module_from_spec(_spec_skill)
sys.modules["jobs_skill"] = sk
_spec_skill.loader.exec_module(sk)

_spec = importlib.util.spec_from_file_location("jobs_induce", SCRIPTS / "jobs_induce.py")
ind = importlib.util.module_from_spec(_spec)
sys.modules["jobs_induce"] = ind
_spec.loader.exec_module(ind)


def test_quellen_mapping():
    assert ind._quelle_aus_pfad(Path("x/2026-10-31-eures-fr/index.md")) == "eures-search"
    assert ind._quelle_aus_pfad(Path("x/2026-10-31-lhr/index.md")) == "lhr-search"
    assert ind._quelle_aus_pfad(Path("x/2026-10-31-jdp/index.md")) == "jdp-search"
    assert ind._quelle_aus_pfad(Path("x/2026-10-31-ch/index.md")) == "jobroom-search"
    assert ind._quelle_aus_pfad(Path("x/2026-10-31/index.md")) == "ba-search"


def test_evidenz_enthaelt_alle_drei_laender():
    rows = ind.evidence()
    if not rows:
        pytest.skip("keine Belege im Checkout (gitignored)")
    assert len(rows) >= 20
    laender = {r["country"] for r in rows}
    assert {"DE", "CH", "FR"} <= laender


def test_evidenz_nur_bekannte_branchen():
    for r in ind.evidence():
        assert r["industry"] in ind.BRANCHEN


def test_bester_skill_bevorzugt_bewaehrte_quelle():
    skills = {
        "france-travail-search": {"id": "france-travail-search", "country": "FR",
                                  "industries": ["Krankenpflege"], "last_success": None},
        "eures-search": {"id": "eures-search", "country": "*",
                         "industries": ["Krankenpflege"], "last_success": "2026-10-31"},
    }
    assert ind._bester_skill(skills, "FR", "Krankenpflege")["id"] == "eures-search"


def test_lattice_datei_ist_liste_und_kein_skill():
    """lattice.json darf load_skills() nicht als Skill erscheinen lassen."""
    skills = sk.load_skills()
    assert "lattice" not in skills
    assert all("id" in s for s in skills.values())


def test_jdp_feed_url():
    assert ind.QUELLEN["jdp"] == "jdp-search"
