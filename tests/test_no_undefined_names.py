"""R5-1.4 (30.09.2026): Statische Wächterprüfung — keine undefinierten Namen.

Hintergrund: STATUS_ICONS wurde in candidate.py benutzt, war aber nicht mehr
definiert (NameError, verschwiegen durch `except Exception: pass` → leerer
Tab). Pyflakes hätte es zur Compile-Zeit gemeldet. Zwei weitere echte Funde
kammen direkt im ersten Lauf: employer.py 'refresh_table' (falscher Name,
NameError beim Render der Kandidaten-Suche) und der verlorene def-Kopf von
_contract_preflight_section (NameError bei 'eingestellt').

Diese Tests laufen pyflakes über den Produktionscode und schlagen bei
"undefined name" fehl. Andere Meldungen (unused import etc.) werden
nicht blockiert — bewusste Grenze (Design-Entscheidung), damit der Wächter
fokussiert bleibt.

Ausführen: .venv-streamlit/bin/python3 -m pytest tests/test_no_undefined_names.py -v
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [ROOT / "webui", ROOT / "scripts" / "agent-runner.py"]


def _pyflakes_output() -> list[str]:
    proc = subprocess.run(
        [sys.executable, "-m", "pyflakes", *[str(t) for t in TARGETS]],
        capture_output=True, text=True, cwd=ROOT,
    )
    return [line for line in (proc.stdout + proc.stderr).splitlines() if line.strip()]


def test_pyflakes_verfuegbar():
    """Pyflakes muss in der venv installiert sein (sonst waere der Wächter stumm)."""
    proc = subprocess.run(
        [sys.executable, "-m", "pyflakes", "--version"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        "pyflakes fehlt in .venv-streamlit — installieren mit: "
        "pip install pyflakes (nur in die venv, R5-1.4)"
    )


def test_keine_undefinierten_namen():
    """Kein 'undefined name' in webui/** und scripts/agent-runner.py."""
    lines = _pyflakes_output()
    undefined = [line for line in lines if "undefined name" in line]
    assert not undefined, (
        "Undefinierte Namen im Produktionscode (würden zur Laufzeit als "
        f"NameError crashen):\n" + "\n".join(undefined)
    )
