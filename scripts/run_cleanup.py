#!/usr/bin/env python3
"""DSGVO-Cleanup für den systemd-Timer `kmhr-cleanup.service`.

Ruft ausschließlich `webui.logic.run_dsgvo_cleanup_once()` auf.
Kein Import von `webui.main` (kein NiceGUI-/Server-Start).
Exit 0 = Lauf ok; Exit 1 = Cleanup meldete einen Fehler.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from webui.logic import run_dsgvo_cleanup_once


def main() -> int:
    result = run_dsgvo_cleanup_once()
    print("[run_cleanup] " + ", ".join(
        f"{key}={value}" for key, value in sorted(result.items())))
    return 1 if result.get("fehler") else 0


if __name__ == "__main__":
    sys.exit(main())
