#!/usr/bin/env python3
"""Prueft alle MCP-Server aus `opencode.json` mit echtem initialize + tools/list.

Read-only: startet die Server, fragt die Tool-Liste ab und beendet sie wieder.
Remote-Server werden per HTTP-initialize geprueft (kein OAuth-Flow).

Aufruf:
    python3 deploy/verify_mcp.py            # alle Server
    python3 deploy/verify_mcp.py --only email-sender,pdf-reader

Exit 0 = alle geprueften Server antworten, sonst 1.
"""
from __future__ import annotations

import argparse
import json
import os
import select
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(os.environ.get("MCP_REPO_ROOT") or Path(__file__).resolve().parents[1])
CFG = ROOT / "opencode.json"
TIMEOUT_INIT = 120
TIMEOUT_TOOLS = 60


def _handshake_local(cmd: list[str]) -> tuple[bool, list[str], str]:
    try:
        p = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, cwd=str(ROOT), text=True, bufsize=1,
        )
    except FileNotFoundError as e:
        return False, [], f"Befehl fehlt: {e}"

    def send(obj: dict) -> None:
        assert p.stdin is not None
        p.stdin.write(json.dumps(obj) + "\n")
        p.stdin.flush()

    def read(timeout: float) -> dict | None:
        assert p.stdout is not None
        end = time.time() + timeout
        while time.time() < end:
            r, _, _ = select.select([p.stdout], [], [], 0.5)
            if not r:
                continue
            line = p.stdout.readline()
            if not line:
                return None
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
        return None

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                         "clientInfo": {"name": "verify-mcp", "version": "1.0"}}})
        if not read(TIMEOUT_INIT):
            return False, [], "kein initialize"
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        res = read(TIMEOUT_TOOLS)
        tools = [t.get("name", "") for t in (res or {}).get("result", {}).get("tools", [])]
        return True, tools, ""
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()


def _handshake_remote(url: str, headers: dict) -> tuple[bool, list[str], str]:
    def post(payload: dict) -> dict:
        body = json.dumps(payload).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8", "replace"))

    try:
        init = post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                     "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                "clientInfo": {"name": "verify-mcp", "version": "1.0"}}})
        if "result" not in init:
            return False, [], "kein initialize"
        try:
            res = post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
            tools = [t.get("name", "") for t in res.get("result", {}).get("tools", [])]
        except Exception:  # noqa: BLE001 — tools/list ist optional (Session-Pflicht)
            tools = []
        return True, tools, ""
    except Exception as e:  # noqa: BLE001 — Netzfehler sind das Ergebnis
        return False, [], f"{type(e).__name__}: {e}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MCP-Server verifizieren")
    ap.add_argument("--only", default="", help="kommagetrennte Servernamen")
    args = ap.parse_args(argv)
    nur = {s.strip() for s in args.only.split(",") if s.strip()}
    cfg = json.loads(CFG.read_text(encoding="utf-8")).get("mcp", {})

    fehler = 0
    geprueft = 0
    for name, s in cfg.items():
        if nur and name not in nur:
            continue
        if not s.get("enabled", True):
            print(f"{name:20} SKIP   (deaktiviert)")
            continue
        typ = s.get("type", "local")
        if typ == "remote":
            ok, tools, err = _handshake_remote(s.get("url", ""), s.get("headers", {}))
        else:
            cmd = s.get("command") or []
            ok, tools, err = _handshake_local(cmd) if cmd else (False, [], "kein command")
        geprueft += 1
        if ok:
            print(f"{name:20} OK     {len(tools):2d} Tools: {','.join(tools)[:70]}")
        else:
            fehler += 1
            print(f"{name:20} FEHLER {err[:90]}")
    print(f"[verify-mcp] geprueft: {geprueft}, fehler: {fehler}")
    return 0 if fehler == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
