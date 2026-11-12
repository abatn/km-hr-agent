"""Bind-Guard (12.11.2026): WebUI nur auf Loopback ohne ausdrückliches Opt-in.

Hintergrund: Die lokale Dev-Instanz lauschte über ein systemd-Drop-in auf
``0.0.0.0:8080`` und war öffentlich erreichbar (Live-Admin trägt noch das
alte Seed-Passwort, ``knowledge/system/configuration-secrets.md`` §(f)).
``resolve_host`` ist fail-closed; der echte Startpfad wird zusätzlich als
Sub-Prozess geprüft (Abbruch vor ``app_bootstrap()``).
"""
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from bind_guard import (  # noqa: E402
    ENV_HOST,
    ENV_OPT_IN,
    BindConfigError,
    is_loopback_host,
    resolve_host,
)

PROBE_DIR = Path("/tmp/opencode/bind-guard")


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.1.1", "::1", "[::1]",
                                  "localhost", "LOCALHOST"])
def test_loopback_ist_erlaubt(host):
    assert is_loopback_host(host)
    assert resolve_host({ENV_HOST: host}) == host


def test_default_ist_loopback():
    assert resolve_host({}) == "127.0.0.1"
    assert resolve_host({ENV_HOST: "  "}) == "127.0.0.1"


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.10", "example.org"])
def test_nicht_loopback_ohne_opt_in_bricht_ab(host):
    with pytest.raises(BindConfigError) as ex:
        resolve_host({ENV_HOST: host})
    assert ENV_OPT_IN in str(ex.value)
    assert "configuration-secrets.md" in str(ex.value)


@pytest.mark.parametrize("wert", ["1", "true", "YES"])
def test_opt_in_erlaubt_oeffentliche_bindung(wert):
    assert resolve_host({ENV_HOST: "0.0.0.0", ENV_OPT_IN: wert}) == "0.0.0.0"


def test_opt_in_ist_nicht_default():
    src = (ROOT / "scripts" / "bind_guard.py").read_text(encoding="utf-8")
    assert 'ENV_OPT_IN = "KMHR_ALLOW_PUBLIC_BIND"' in src
    # Ohne gesetzte Variable fällt der Code auf Loopback zurück, nicht auf 0.0.0.0
    assert 'DEFAULT_HOST = "127.0.0.1"' in src


def test_guard_liegt_vor_app_bootstrap_und_ui_run():
    src = (ROOT / "webui" / "main.py").read_text(encoding="utf-8")
    pos_guard = src.index("HOST = resolve_host()")
    assert pos_guard < src.index("logic.app_bootstrap()")
    assert pos_guard < src.index("\nui.run(title=")
    assert "host=HOST" in src


def test_echter_start_bricht_vor_db_anlage_ab():
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    db_pfad = Path(tempfile.mkdtemp(prefix="b-bind-", dir=PROBE_DIR)) / "probe.db"
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = dict(os.environ, KMHR_DEV="1", KMHR_HOST="0.0.0.0",
               KMHR_DB_PATH=str(db_pfad), KMHR_PORT=str(port),
               KMHR_RUNNER_AUTOSTART="0")
    env.pop(ENV_OPT_IN, None)
    r = subprocess.run(
        [sys.executable, "-c",
         "import runpy; runpy.run_path('webui/main.py', run_name='__main__')"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 1, r.stderr[-400:]
    assert "ABBRUCH" in r.stderr and ENV_OPT_IN in r.stderr
    assert not db_pfad.exists(), "Guard muss vor app_bootstrap() liegen"
