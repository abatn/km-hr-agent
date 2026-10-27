"""x402-Käufer-Pfad für Werbe-Gebote: echte Zahlung gegen Mock-Facilitator und Test-Börse.

Läuft nur mit dem Test-venv `.venv-ads` (requirements-ads.txt); sonst übersprungen.
Keine Chain, kein Geld: Facilitator und Börse sind lokale Testserver im Testnetz-Format.
"""
from __future__ import annotations

import importlib.util
import json
import socket
import sys
import threading
import time
from datetime import date
from pathlib import Path

import pytest

pytest.importorskip("x402")
pytest.importorskip("uvicorn")
eth_account = pytest.importorskip("eth_account")
import uvicorn  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures"
SEED = ROOT / "tests" / "fixtures" / "seed.db"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


facilitator_mod = _load("x402_mock_facilitator", FIX / "x402_mock_facilitator.py")
exchange_mod = _load("x402_mock_exchange", FIX / "x402_mock_exchange.py")
ads_x402 = _load("ads_x402", ROOT / "scripts" / "ads_x402.py")
ads_agent = _load("ads_agent_x402", ROOT / "scripts" / "ads_agent.py")


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
def chain():
    fport = _free_port()
    fac = _Server(facilitator_mod.app, fport)
    fac.start()
    eport = _free_port()
    app = exchange_mod.build_app(f"http://127.0.0.1:{fport}", price="$0.01")
    ex = _Server(app, eport)
    ex.start()
    yield {"url": f"http://127.0.0.1:{eport}/x402/bid", "app": app}
    ex.stop()
    fac.stop()


@pytest.fixture
def key() -> str:
    return eth_account.Account.create().key.hex()


def test_zahlung_mit_quittung(chain, key):
    before = len(chain["app"].state.paid_bids)
    r = ads_x402.pay_bid(chain["url"], {"campaign": "employers_eu", "bid_cpm_eur": 13.2},
                         key, max_price_usdc=0.05)
    assert r.status == 200
    assert r.price_usdc == pytest.approx(0.01)
    assert r.network == "eip155:84532"
    assert r.payment_response
    assert len(chain["app"].state.paid_bids) == before + 1


def test_preisdeckel_vor_zahlung(chain, key):
    before = len(chain["app"].state.paid_bids)
    with pytest.raises(ads_x402.X402Error, match="Deckel"):
        ads_x402.pay_bid(chain["url"], {"campaign": "x"}, key, max_price_usdc=0.001)
    assert len(chain["app"].state.paid_bids) == before, "es wurde trotz Deckel gezahlt"


def test_mainnet_ist_gesperrt():
    with pytest.raises(ads_x402.X402Error, match="Mainnet"):
        ads_x402.check_network("eip155:8453")
    with pytest.raises(ads_x402.X402Error):
        ads_x402.check_network("eip155:1")


def test_ohne_konfiguration_keine_zahlung(monkeypatch):
    monkeypatch.delenv("KMHR_ADS_X402_URL", raising=False)
    monkeypatch.delenv("KMHR_ADS_X402_PRIVATE_KEY", raising=False)
    assert ads_x402.config_from_env() is None


def test_agent_zahlt_nur_freigegebene_kampagnen(chain, key, tmp_path, monkeypatch):
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({"campaigns": {"employers_eu": 3.0}}))
    monkeypatch.setenv("KMHR_ADS_DAILY_CAP_EUR", "3")
    monkeypatch.setenv("KMHR_ADS_APPROVAL_FILE", str(approval))
    before = len(chain["app"].state.paid_bids)
    result = ads_agent.run_once(date(2026, 10, 28), SEED, out_dir=tmp_path,
                                dmp_path=tmp_path / "dmp.jsonl",
                                x402_cfg={"url": chain["url"], "private_key": key})
    by_key = {c["campaign_key"]: c for c in result["campaigns"]}
    assert by_key["employers_eu"]["x402"]["status"] == "paid"
    assert by_key["employers_eu"]["x402"]["network"] == "eip155:84532"
    assert "x402" not in by_key["candidates_north_africa"], "nicht freigegeben, aber gezahlt"
    assert len(chain["app"].state.paid_bids) == before + 1


def test_schluessel_steht_nicht_im_protokoll(chain, key, tmp_path, monkeypatch):
    approval = tmp_path / "approval.json"
    approval.write_text(json.dumps({"campaigns": {"employers_eu": 3.0}}))
    monkeypatch.setenv("KMHR_ADS_DAILY_CAP_EUR", "3")
    monkeypatch.setenv("KMHR_ADS_APPROVAL_FILE", str(approval))
    ads_agent.run_once(date(2026, 10, 28), SEED, out_dir=tmp_path,
                       dmp_path=tmp_path / "dmp.jsonl",
                       x402_cfg={"url": chain["url"], "private_key": key})
    text = (tmp_path / "2026-10-28" / "run.json").read_text(encoding="utf-8")
    assert key not in text and key[2:] not in text
