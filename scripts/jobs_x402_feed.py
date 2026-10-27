"""Agenten-Stellenfeed hinter x402: Agenten zahlen pro Suche, Stellen werden über die Bazaar gefunden.

Idee (siehe marketing/ADS_INNOVATION.md): Kein Werbenetzwerk, kein Konto, keine Kreditkarte.
Ein Agent des Kandidaten oder des Arbeitgebers sucht Stellen und zahlt den Preis pro Anfrage.
Die Deklaration (`bazaar`) macht den Dienst für Discovery-Indexer auffindbar.

Regeln:
- Nur öffentliche Stellendaten (aktive Stellen, ohne Test-/E2E-Stellen). Keine Personen-, Bewerbungs- oder Task-Daten.
- Jede Textzelle läuft durch den PII-Guard des Social-Agenten.
- Antworten sind als organisch gekennzeichnet (`sponsored: false`); bezahlte Platzierung gibt es nicht.
- Nur Testnetz (`eip155:84532`). Mainnet wird beim Start abgelehnt.
"""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TESTNET = "eip155:84532"
MAINNET = "eip155:8453"
ROUTE = "GET /api/agent/jobs"
MAX_RESULTS = 20

_spec = importlib.util.spec_from_file_location("social_agent_feed", ROOT / "scripts" / "social_agent.py")
social = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(social)  # type: ignore[union-attr]


class FeedError(RuntimeError):
    pass


def check_network(network: str) -> None:
    if network == MAINNET:
        raise FeedError("Mainnet ist für den Stellenfeed gesperrt; nur Testnetz")
    if network != TESTNET:
        raise FeedError(f"Netz nicht freigegeben: {network}")


def bazaar_extension() -> dict[str, Any]:
    """Discovery-Deklaration (x402 v2 Bazaar) für GET /api/agent/jobs."""
    return {
        "info": {
            "input": {"type": "http", "method": "GET",
                      "queryParams": {"q": "Stichwort im Stellentitel (optional)",
                                      "land": "Ländercode DE, FR, CH, MA, DZ, TN, EG (optional)"}},
            "output": {"type": "json", "example": {"jobs": [{"id": 1, "titel": "Beispiel"}],
                                                   "count": 1, "sponsored": False}},
        },
        "schema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "input": {"type": "object",
                          "properties": {"type": {"type": "string", "const": "http"},
                                         "method": {"type": "string", "const": "GET"}}},
            },
        },
    }


def route_config(price: str, network: str, pay_to: str) -> dict[str, Any]:
    check_network(network)
    return {
        "accepts": [{"scheme": "exact", "network": network, "payTo": pay_to,
                     "price": price, "maxTimeoutSeconds": 60}],
        "description": "Organische Stellensuche im KM-HR-Agent (öffentliche Stellendaten, keine Werbung).",
        "mimeType": "application/json",
        "serviceName": "KM-HR-Agent Stellenfeed",
        "tags": ["jobs", "recruiting", "europe", "north-africa"],
        "extensions": {"bazaar": bazaar_extension()},
    }


def search_jobs(db_path: Path, q: str = "", land: str = "", limit: int = MAX_RESULTS) -> dict[str, Any]:
    """Liest ausschließlich öffentliche Stellenfelder (read-only)."""
    limit = max(1, min(int(limit), MAX_RESULTS))
    sql = ("SELECT id, titel, standort, land, stellentyp, gehaltsrahmen_min, gehaltsrahmen_max, "
           "erstellt_am FROM jobs WHERE status='aktiv' AND titel NOT LIKE 'E2E-Beweis%' "
           "AND titel NOT LIKE '%Teststelle%'")
    params: list[Any] = []
    if q:
        sql += " AND titel LIKE ?"
        params.append(f"%{q[:80]}%")
    if land:
        sql += " AND land = ?"
        params.append(land[:4])
    sql += " ORDER BY erstellt_am DESC, id DESC LIMIT ?"
    params.append(limit)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    cols = ("id", "titel", "standort", "land", "stellentyp", "gehaltsrahmen_min",
            "gehaltsrahmen_max", "erstellt_am")
    jobs = [dict(zip(cols, r)) for r in rows]
    for job in jobs:
        for key in ("titel", "standort", "land", "stellentyp"):
            social.assert_no_pii(str(job.get(key) or ""))
    return {"jobs": jobs, "count": len(jobs), "sponsored": False,
            "hinweis": "Organische Ergebnisse. Bewerbung über den Arbeitgeber, Entscheidung beim Menschen."}


def build_app(db_path: Path, facilitator_url: str, price: str = "$0.01",
              network: str = TESTNET, pay_to: str = "0x1cE5379a485a0bd726fce57BbfDfc316b0D35Cc4"):
    from fastapi import FastAPI, Query
    from x402 import x402ResourceServer
    from x402.http import HTTPFacilitatorClient
    from x402.http.middleware.fastapi import payment_middleware
    from x402.mechanisms.evm.exact.server import ExactEvmScheme

    check_network(network)
    app = FastAPI(title="KM-HR-Agent Stellenfeed (x402)")
    facilitator = HTTPFacilitatorClient({"url": facilitator_url, "timeout": 10})
    server = x402ResourceServer(facilitator)
    server.register(network, ExactEvmScheme())
    app.middleware("http")(payment_middleware(
        {ROUTE: route_config(price, network, pay_to)}, server,
        paywall_config={"app_name": "KM-HR-Agent Stellenfeed"}, sync_facilitator_on_start=True))

    @app.get("/api/agent/jobs")
    async def jobs(q: str = Query("", max_length=80), land: str = Query("", max_length=4),
                   limit: int = Query(MAX_RESULTS, ge=1, le=MAX_RESULTS)):
        return search_jobs(db_path, q=q, land=land, limit=limit)

    return app


if __name__ == "__main__":
    print("Start über uvicorn (siehe marketing/ADS_INNOVATION.md); Modul enthält keinen Serverstart.")
    sys.exit(0)
