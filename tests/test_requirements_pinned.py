"""P7 (08.10.2026): Guard-Test — drift-kritische Pakete müssen exakt fixiert sein.

Spec: knowledge/system/dependency-pinning.md
Hintergrund: Offene `>=`-Angaben ließen Builds neuere mcp/fastmcp-Versionen ziehen als lokal
getestet (Dependency-Drift). Dieser Test verhindert ein versehentliches Zurückfallen auf `>=`.
"""
from pathlib import Path

REQ = Path(__file__).resolve().parents[1] / "requirements.txt"

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
