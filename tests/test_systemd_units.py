"""Systemd-Units: ExecStart-Ziele und der DSGVO-Cleanup-Wrapper.

Prüft, dass jede in `deploy/systemd/*.service` referenzierte Zieldatei im Repo
existiert (absolute Pfade `/opt/km-hr-agent/...` werden auf das Repo gemappt),
und führt `scripts/run_cleanup.py` gegen eine Kopie der Seed-DB aus.
"""
from __future__ import annotations

import ast
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
UNITS = BASE / "deploy" / "systemd"


def _exec_start_targets(unit_path: Path) -> list[str]:
    targets: list[str] = []
    for line in unit_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("ExecStart="):
            continue
        for token in line.split("=", 1)[1].split():
            if not token.startswith("/opt/km-hr-agent/"):
                continue
            # Interpreter/Venv ist nicht repo-versioniert; geprüft wird das Ziel.
            if "/.venv-" in token:
                continue
            targets.append(token)
    return targets


def test_cleanup_units_existieren() -> None:
    assert (UNITS / "kmhr-cleanup.service").is_file()
    assert (UNITS / "kmhr-cleanup.timer").is_file()


def test_jede_execstart_zieldatei_existiert() -> None:
    units = sorted(UNITS.glob("*.service"))
    assert units, "keine Service-Units in deploy/systemd/"
    fehlend: list[str] = []
    for unit in units:
        for target in _exec_start_targets(unit):
            rel = target.removeprefix("/opt/km-hr-agent/")
            if not (BASE / rel).is_file():
                fehlend.append(f"{unit.name}: {target}")
    assert not fehlend, "Fehlende ExecStart-Ziele: " + ", ".join(fehlend)


def test_run_cleanup_importiert_kein_webui_main() -> None:
    src = (BASE / "scripts" / "run_cleanup.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    module = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            module.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module.append(node.module or "")
    assert "webui.logic" in module
    assert not any(name == "webui.main" or name.startswith("webui.main.")
                   for name in module)


def test_run_cleanup_gegen_db_kopie(tmp_path: Path) -> None:
    quelle = BASE / "tests" / "fixtures" / "seed.db"
    ziel = tmp_path / "feedback.db"
    with sqlite3.connect(quelle) as src, sqlite3.connect(ziel) as dst:
        src.backup(dst)
    env = os.environ.copy()
    env["KMHR_DB_PATH"] = str(ziel)
    lauf = subprocess.run(
        [sys.executable, str(BASE / "scripts" / "run_cleanup.py")],
        cwd=str(BASE), env=env, capture_output=True, text=True, timeout=120,
    )
    assert lauf.returncode == 0, lauf.stderr
    assert "geloeschte_bewerbungen" in lauf.stdout
