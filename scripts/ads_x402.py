"""x402-Zahlungsschicht für Werbe-Gebote (Käufer-Seite). Nur Testnetz.

Ablauf (wie flight-agent/attest/client.py):
  1. Probe: POST ohne Zahlung -> HTTP 402 + Header `payment-required` (Base64-JSON).
  2. Preisdeckel prüfen, BEVOR gezahlt wird (Betrag in Atomic-Units, USDC = 6 Dezimalstellen).
  3. Zahlung mit dem Schlüssel aus `KMHR_ADS_X402_PRIVATE_KEY` (x402Client + EVM-Signer).
  4. Quittung `payment-response` zurückgeben.

Harte Regeln:
  - Nur Testnetz (`eip155:84532`). Mainnet (`eip155:8453`) wird abgelehnt.
  - Ohne Schlüssel oder ohne URL findet keine Zahlung statt.
  - Der Schlüssel wird nie ausgegeben oder protokolliert.
Das SDK `x402[evm]` wird nur importiert, wenn die Schicht benutzt wird (requirements-ads.txt).
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
from dataclasses import dataclass
from typing import Any

TESTNET_NETWORKS = {"eip155:84532"}
MAINNET_NETWORKS = {"eip155:8453"}
USDC_DECIMALS = 6


class X402Error(RuntimeError):
    pass


@dataclass
class BidReceipt:
    status: int
    price_usdc: float
    network: str
    payment_response: str | None
    body: Any


def usdc_from_atomic(atomic: str | int) -> float:
    return int(atomic) / 10 ** USDC_DECIMALS


def check_network(network: str) -> None:
    if network in MAINNET_NETWORKS:
        raise X402Error("Mainnet-Gebote sind gesperrt; nur Testnetz (eip155:84532)")
    if network not in TESTNET_NETWORKS:
        raise X402Error(f"Netz nicht freigegeben: {network}")


def parse_challenge(header_value: str) -> dict[str, Any]:
    """`payment-required` ist Base64-JSON mit `accepts` (x402 v2)."""
    data = json.loads(base64.b64decode(header_value).decode("utf-8"))
    accepts = data.get("accepts") or []
    if not accepts:
        raise X402Error("402-Antwort ohne accepts")
    return accepts[0]


def enforce_cap(challenge: dict[str, Any], max_price_usdc: float) -> float:
    price = usdc_from_atomic(challenge.get("amount") or challenge.get("maxAmountRequired") or 0)
    if price <= 0:
        raise X402Error("402-Antwort ohne gültigen Betrag")
    if price > max_price_usdc:
        raise X402Error(f"Preis {price} USDC über dem Deckel {max_price_usdc} USDC")
    return price


async def _pay_async(url: str, body: dict[str, Any], private_key: str,
                     max_price_usdc: float) -> BidReceipt:
    import httpx
    from eth_account import Account
    from x402 import x402Client
    from x402.http.clients.httpx import x402AsyncTransport
    from x402.mechanisms.evm.exact.client import ExactEvmScheme
    from x402.mechanisms.evm.signers import EthAccountSigner

    async with httpx.AsyncClient(timeout=30) as probe_http:
        probe = await probe_http.post(url, json=body)
    if probe.status_code != 402:
        raise X402Error(f"Erwartet 402 beim Probe, erhalten {probe.status_code}")
    challenge = parse_challenge(probe.headers["payment-required"])
    check_network(challenge.get("network", ""))
    price = enforce_cap(challenge, max_price_usdc)

    client = x402Client()
    client.register(challenge["network"], ExactEvmScheme(EthAccountSigner(Account.from_key(private_key))))
    transport = x402AsyncTransport(client)
    async with httpx.AsyncClient(transport=transport, timeout=60) as http:
        resp = await http.post(url, json=body)
    try:
        payload = resp.json()
    except ValueError:
        payload = resp.text
    return BidReceipt(status=resp.status_code, price_usdc=price, network=challenge["network"],
                      payment_response=resp.headers.get("payment-response"), body=payload)


def pay_bid(url: str, body: dict[str, Any], private_key: str, max_price_usdc: float) -> BidReceipt:
    """Synchroner Einstieg für den Werbe-Agenten."""
    return asyncio.run(_pay_async(url, body, private_key, max_price_usdc))


def config_from_env() -> dict[str, str] | None:
    """Liefert die Konfiguration, oder None, wenn die x402-Schicht nicht eingerichtet ist."""
    url = os.environ.get("KMHR_ADS_X402_URL", "").strip()
    key = os.environ.get("KMHR_ADS_X402_PRIVATE_KEY", "").strip()
    if not url or not key:
        return None
    return {"url": url, "private_key": key}
