"""Test-Gebotsbörse mit x402-Schranke (nur Tests, Testnetz-Mock).

POST /x402/bid verlangt eine x402-Zahlung (HTTP 402 -> PAYMENT-SIGNATURE -> 200).
Bezahlte Gebote werden in `app.state.paid_bids` gezählt.
"""
from __future__ import annotations

from fastapi import FastAPI
from x402 import x402ResourceServer
from x402.http import HTTPFacilitatorClient
from x402.http.middleware.fastapi import payment_middleware
from x402.mechanisms.evm.exact.server import ExactEvmScheme

NETWORK = "eip155:84532"  # Base Sepolia (Testnet)
PAY_TO = "0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4"


def build_app(facilitator_url: str, price: str = "$0.01") -> FastAPI:
    app = FastAPI()
    app.state.paid_bids = []
    facilitator = HTTPFacilitatorClient({"url": facilitator_url, "timeout": 10})
    server = x402ResourceServer(facilitator)
    server.register(NETWORK, ExactEvmScheme())
    accepts = {"scheme": "exact", "network": NETWORK, "payTo": PAY_TO,
               "price": price, "maxTimeoutSeconds": 60}
    routes = {"POST /x402/bid": {"accepts": [dict(accepts)],
                                 "description": "Testgebot", "mimeType": "application/json"}}
    app.middleware("http")(payment_middleware(
        routes, server, paywall_config={"app_name": "Test-Börse"}, sync_facilitator_on_start=True))

    @app.post("/x402/bid")
    async def bid(payload: dict | None = None):
        app.state.paid_bids.append(payload or {})
        return {"accepted": True, "count": len(app.state.paid_bids)}

    return app
