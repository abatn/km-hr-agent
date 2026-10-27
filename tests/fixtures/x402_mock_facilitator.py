"""Wire-kompatibler Test-Facilitator (/supported, /verify, /settle) für x402-Tests.

Übernommen aus ~/mimo-agents/flight-agent/attest/tests/mock_facilitator.py (gleiche Endpunkte,
keine Chain). Nur für Tests; der echte Facilitator ist eine andere URL in der Konfiguration.
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

NETWORK = os.environ.get("MOCK_NETWORK", "eip155:84532")
app = FastAPI(title="Mock x402 Facilitator", docs_url=None, redoc_url=None)


def _payer(body: dict[str, Any]) -> str:
    payload = body.get("paymentPayload") or {}
    inner = payload.get("payload") or {}
    authorization = inner.get("authorization") or {}
    return str(authorization.get("from") or "0x" + "11" * 20)


@app.get("/supported")
async def supported() -> JSONResponse:
    return JSONResponse({
        "kinds": [
            {"x402Version": 2, "scheme": "exact", "network": NETWORK},
            {"x402Version": 1, "scheme": "exact", "network": "base-sepolia"},
        ],
        "signers": {},
        "extensions": [],
    })


@app.post("/verify")
async def verify(request: Request) -> JSONResponse:
    body = await request.json()
    payload = body.get("paymentPayload") or {}
    inner = payload.get("payload") or {}
    signature = inner.get("signature")
    authorization = inner.get("authorization") or {}
    valid = bool(signature) and bool(authorization.get("to")) and bool(authorization.get("value"))
    return JSONResponse({
        "isValid": valid,
        "payer": _payer(body),
        "invalidReason": None if valid else "signature or authorization missing",
    })


@app.post("/settle")
async def settle(request: Request) -> JSONResponse:
    body = await request.json()
    seed = f"{time.time()}-{_payer(body)}".encode()
    tx = "0x" + hashlib.sha256(seed).hexdigest()
    return JSONResponse({
        "success": True,
        "transaction": tx,
        "network": NETWORK,
        "payer": _payer(body),
    })
