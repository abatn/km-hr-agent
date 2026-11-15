"""P7 (08.10.2026): Guard-Test — drift-kritische Pakete müssen exakt fixiert sein.

Spec: knowledge/system/dependency-pinning.md
Hintergrund: Offene `>=`-Angaben ließen Builds neuere mcp/fastmcp-Versionen ziehen als lokal
getestet (Dependency-Drift). Dieser Test verhindert ein versehentliches Zurückfallen auf `>=`.
"""
from pathlib import Path

REQ = Path(__file__).resolve().parents[1] / "requirements.txt"
REQ_DEV = Path(__file__).resolve().parents[1] / "requirements-dev.txt"

EXPECTED_PINS = {
    "nicegui": "nicegui==3.17.1",
    "fastmcp": "fastmcp==4.0.11",
    "mcp": "mcp==2.3.0",
}


def test_drift_kritische_pakete_sind_exakt_fixiert():
    text = REQ.read_text(encoding="utf-8")
    for name, pin in EXPECTED_PINS.items():
        assert pin in text, f"{name} muss exakt als '{pin}' fixiert sein (Spec: dependency-pinning.md)"


def test_keine_offene_untergrenze_fuer_mcp_fastmcp_nicegui():
    text = REQ.read_text(encoding="utf-8")
    for name in ("nicegui", "fastmcp", "mcp"):
        assert f"{name}>=" not in text, f"{name} darf keine offene '>='-Grenze mehr haben"


def test_playwright_dev_exakt_fixiert():
    """P7-Ergaenzung (15.11.2026): Dev-Dependency-Drift.

    requirements-dev.txt hatte nur playwright>=1.63.0 (Untergrenze) — der E2E-CI
    installierte bei jedem Lauf die neueste Version (1.64.1 -> 1.65.2); die roten
    Laeufe 14./15.11.2026 liefen unter 1.65.2. Spec: dependency-pinning.md.
    """
    text = REQ_DEV.read_text(encoding="utf-8")
    assert "playwright==1.65.2" in text, (
        "playwright muss exakt als 'playwright==1.65.2' fixiert sein "
        "(Spec: dependency-pinning.md)")
    assert "playwright>=" not in text, (
        "playwright darf keine offene '>='-Grenze haben (Dependency-Drift im E2E-CI)")
