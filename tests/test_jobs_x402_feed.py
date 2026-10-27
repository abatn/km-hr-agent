"""Stellenfeed hinter x402: 402 mit Bazaar-Deklaration, bezahlte Suche, PII- und Netz-Sperre.

Läuft mit `.venv-ads` (requirements-ads.txt); im Projekt-venv übersprungen.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("x402")
pytest.importorskip("uvicorn")
eth_account = pytest.importorskip("eth_account")
import httpx  # noqa: E402
import uvicorn  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
SEED = FIX / "seed.db"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


facilitator_mod = _load("x402_mock_facilitator_feed", FIX / "x402_mock_facilitator.py")
feed = _load("jobs_x402_feed", ROOT / "scripts" / "jobs_x402_feed.py")


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _Server:
    def __init__(self, app, port: int) -> None:
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)

    def start(self) -> None:
        self.thread.start()
        for _ in range(200):
            if self.server.started:
                return
            time.sleep(0.05)
        raise RuntimeError("Testserver startet nicht")

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(5)


@pytest.fixture(scope="module")
def base():
    fport = _free_port()
    fac = _Server(facilitator_mod.app, fport)
    fac.start()
    eport = _free_port()
    app = feed.build_app(SEED, f"http://127.0.0.1:{fport}")
    ex = _Server(app, eport)
    ex.start()
    yield f"http://127.0.0.1:{eport}"
    ex.stop()
    fac.stop()


def _paid_client(key: str):
    from x402 import x402Client
    from x402.http.clients.httpx import x402AsyncTransport
    from x402.mechanisms.evm.exact.client import ExactEvmScheme
    from x402.mechanisms.evm.signers import EthAccountSigner
    from eth_account import Account

    client = x402Client()
    client.register("eip155:84532", ExactEvmScheme(EthAccountSigner(Account.from_key(key))))
    return x402AsyncTransport(client)


def test_unbezahlt_gibt_402_mit_bazaar_deklaration(base):
    r = httpx.get(f"{base}/api/agent/jobs", timeout=20)
    assert r.status_code == 402
    raw = r.headers["payment-required"]
    data = json.loads(base64.b64decode(raw))
    accepts = data["accepts"][0]
    assert accepts["network"] == "eip155:84532"
    assert accepts["scheme"] == "exact"
    assert "bazaar" in data["extensions"]
    assert data["extensions"]["bazaar"]["info"]["input"]["method"] == "GET"
    assert data["resource"]["url"].endswith("/api/agent/jobs")


def test_bezahlte_suche_liefert_organische_stellen(base):
    import asyncio

    key = eth_account.Account.create().key.hex()

    async def run():
        transport = _paid_client(key)
        async with httpx.AsyncClient(transport=transport, timeout=60) as http:
            return await http.get(f"{base}/api/agent/jobs", params={"limit": 5})

    r = asyncio.run(run())
    assert r.status_code == 200
    body = r.json()
    assert body["sponsored"] is False
    assert 1 <= body["count"] <= 5
    assert all("titel" in j and "id" in j for j in body["jobs"])
    assert "candidate" not in json.dumps(body).lower()


def test_stichwortfilter(base):
    jobs = feed.search_jobs(SEED, q="Zzz-kein-Treffer-Zzz")
    assert jobs["count"] == 0
    everything = feed.search_jobs(SEED, limit=20)
    assert everything["count"] >= 1


def test_limit_wird_begrenzt():
    assert feed.search_jobs(SEED, limit=500)["count"] <= feed.MAX_RESULTS


def test_mainnet_ist_gesperrt():
    with pytest.raises(feed.FeedError, match="Mainnet"):
        feed.check_network("eip155:8453")
    with pytest.raises(feed.FeedError):
        feed.route_config("$0.01", "eip155:8453", "0x" + "1" * 40)


def test_pii_in_titel_wird_blockiert(tmp_path):
    db = tmp_path / "t.db"
    import sqlite3
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE jobs (id INTEGER, titel TEXT, standort TEXT, land TEXT, stellentyp TEXT, "
                 "gehaltsrahmen_min INT, gehaltsrahmen_max INT, erstellt_am TEXT, status TEXT)")
    conn.execute("INSERT INTO jobs VALUES (1, 'Kontakt: hr@example.com', 'Berlin', 'DE', 'Vollzeit', 1, 2, '2026', 'aktiv')")
    conn.commit()
    conn.close()
    with pytest.raises(Exception, match="DSGVO"):
        feed.search_jobs(db)


def test_sqlite_nur_lesend(tmp_path):
    import sqlite3
    with pytest.raises(sqlite3.OperationalError):
        conn = sqlite3.connect(f"file:{SEED}?mode=ro", uri=True)
        try:
            conn.execute("DELETE FROM jobs")
        finally:
            conn.close()
