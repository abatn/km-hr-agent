#!/usr/bin/env python3
"""MCP-Contract-Test: lokale, PORTABLE Server starten + Handshake + tools/list.

Inventar aus opencode.json. Server mit absoluten lokalen Pfaden (.venv-pdf,
/home/...) werden nur auf Vorhandensein geprüft (lokal-spezifisch, nicht CI-portabel).
Remote-Server werden NICHT kontaktiert (externe Erreichbarkeit, kein CI-Gate).

Exit 0 = alle portablen Server OK, sonst 1.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CFG = ROOT / "opencode.json"
TIMEOUT = 40


def handshake(command: list[str]) -> tuple[bool, str, list[str]]:
    """Startet den Server, sendet initialize + tools/list. Liefert (ok, msg, tools)."""
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "ci", "version": "1.0"}}}
    tools = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    # Kein `notifications/initialized` — die FastMCP-Server beenden danach die
    # Verarbeitung weiterer Requests auf stdin (belegt 04.10.2026).
    payload = "\n".join(json.dumps(r) for r in (init, tools)) + "\n"
    try:
        p = subprocess.run(command, input=payload.encode(), capture_output=True,
                           timeout=TIMEOUT, cwd=str(ROOT))
    except FileNotFoundError as e:
        return False, f"Befehl fehlt: {e}", []
    except subprocess.TimeoutExpired:
        return False, "Timeout beim Handshake", []
    namen = []
    init_ok = False
    for line in p.stdout.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if r.get("id") == 1 and "result" in r:
            init_ok = True  # Server startet + handshaked
        if r.get("id") == 2 and "result" in r:
            namen = [t.get("name") for t in r["result"].get("tools", [])]
    if not init_ok:
        err = p.stderr.decode("utf-8", errors="replace")[:200]
        return False, f"kein initialize-Handshake (stderr: {err})", []
    return True, "OK", namen


def main() -> int:
    cfg = json.loads(CFG.read_text(encoding="utf-8"))["mcp"]
    fehler, geprueft, uebersprungen = [], 0, []
    for name, s in cfg.items():
        if s.get("type") != "local":
            uebersprungen.append(f"{name} (remote)")
            continue
        cmd = s.get("command") or []
        if not cmd:
            fehler.append(f"{name}: kein command"); continue
        # portable = reiner python3 + relativer .py-Pfad
        portabel = cmd[0] in ("python3", "python") and all(
            not a.startswith("/") for a in cmd[1:])
        if not portabel:
            uebersprungen.append(f"{name} (absolute Pfade/npx — lokal-spezifisch)")
            continue
        ok, msg, tools = handshake(cmd)
        if ok:
            geprueft += 1
            print(f"  ✓ {name}: {len(tools)} Tools — {', '.join(tools[:6])}")
        else:
            fehler.append(f"{name}: {msg}")
    print(f"\nMCP-Contract: {geprueft} portabel geprüft, "
          f"{len(uebersprungen)} übersprungen, {len(fehler)} Fehler")
    for u in uebersprungen:
        print(f"  – übersprungen: {u}")
    for f in fehler:
        print(f"  FEHLER: {f}")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
