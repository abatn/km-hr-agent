"""P1-10 (30.09.2026, sicherheitsrelevant): Geheimnisse aus der Umgebung.

Nutzer-GO: `STORAGE_SECRET` (webui/main.py) und das Admin-Seed-Passwort
(webui/pages/login.py) standen im Klartext im Quellcode. Beide werden jetzt aus
Umgebungsvariablen gelesen; der Entwicklungs-Default bleibt, wird aber bei Nutzung
auf stderr gewarnt.

R3-4 (30.09.2026, Nutzer-GO „A: Fail-closed, KMHR_DEV=1-Override“): ab jetzt
FAIL CLOSED — ohne `KMHR_DEV` startet webui/main.py nur mit KMHR_STORAGE_SECRET
UND KMHR_ADMIN_SEED_PASSWORD, sonst SystemExit(1) vor app_bootstrap/ui.run.

Getestet wird die REINE Konfigurationslogik per Quelltext + Sub-Prozess — der
NiceGUI-Server wird dabei nicht gestartet (unter pytest erreicht ui.run den
Pfad `is_pytest()` und bricht an NICEGUI_SCREEN_TEST_PORT ab; als Sicherheitsnetz
laufen alle Sub-Prozesse gegen einen freien Port, eine frische Temp-DB und
KMHR_RUNNER_AUTOSTART=0).
"""
import os
import re
import socket
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = ROOT / "webui" / "main.py"
LOGIN_PY = ROOT / "webui" / "pages" / "login.py"
PROBE_DIR = Path("/tmp/opencode/r3")  # Regel 3 Runde 3: Probe-DBs nur hierhin

ENV_SECRET = "KMHR_STORAGE_SECRET"
ENV_SEED_PW = "KMHR_ADMIN_SEED_PASSWORD"
ENV_SEED_MAIL = "KMHR_ADMIN_SEED_EMAIL"
ENV_DEV = "KMHR_DEV"
WARN_MERKMAL = f"WARNUNG: {ENV_SECRET}"  # Signatur der P1-10-Default-Warnung


# ─── Sub-Prozess-Helfer (echter Start von webui/main.py) ───────────────────

def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _start_main(extra_env: dict):
    """Startet webui/main.py via runpy in einem Sub-Prozess.

    Isolation: eigene frische DB unter /tmp/opencode/r3 (Regle 3 der Runde 3,
    Live-DB data/feedback.db wird nie angefasst), freier Port, kein Runner.
    Alle R3-4-Variablen werden erst entfernt und dann gezielt gesetzt.
    Rueckgabe: (returncode | None bei Timeout, stderr, db_pfad).
    """
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    db_pfad = Path(tempfile.mkdtemp(prefix="b-secrets-", dir=PROBE_DIR)) / "probe.db"
    env = dict(os.environ)
    for key in (ENV_SECRET, ENV_SEED_PW, ENV_SEED_MAIL, ENV_DEV):
        env.pop(key, None)
    env["KMHR_RUNNER_AUTOSTART"] = "0"
    env["KMHR_DB_PATH"] = str(db_pfad)
    env["KMHR_PORT"] = str(_free_port())
    env.update(extra_env)
    try:
        r = subprocess.run(
            [sys.executable, "-c",
             "import runpy,sys; sys.argv=['main'];"
             "runpy.run_path('webui/main.py', run_name='__main__')"],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        return r.returncode, r.stderr, db_pfad
    except subprocess.TimeoutExpired as ex:
        err = ex.stderr or ""
        if isinstance(err, bytes):
            err = err.decode(errors="replace")
        return None, err, db_pfad


# ─── main.py: STORAGE_SECRET ───────────────────────────────────────────────

def test_storage_secret_kommt_aus_der_umgebung():
    src = MAIN_PY.read_text(encoding="utf-8")
    assert f'os.environ.get("{ENV_SECRET}"' in src, \
        "STORAGE_SECRET muss aus der Umgebung gelesen werden"
    # nicht mehr: nackte Zuweisung eines Klartext-Geheimnisses an STORAGE_SECRET
    assert not re.search(r'^STORAGE_SECRET = "', src, re.M), \
        "STORAGE_SECRET darf nicht mehr fest im Code stehen"


def test_default_ist_dokumentiert_als_konstante():
    src = MAIN_PY.read_text(encoding="utf-8")
    assert "STORAGE_SECRET_DEFAULT" in src
    assert "STORAGE_SECRET = os.environ.get" in src


def test_gate_liegt_vor_app_bootstrap_und_ui_run():
    """R3-4: Reihenfolge — Gate vor DB-Zugriff (app_bootstrap) und vor ui.run."""
    src = MAIN_PY.read_text(encoding="utf-8")
    pos_dev = src.index(f'{ENV_DEV} = os.environ.get("{ENV_DEV}"')
    pos_exit = src.index("raise SystemExit(1)")
    assert pos_dev < pos_exit, "KMHR_DEV-Auswertung muss vor dem SystemExit stehen"
    assert pos_exit < src.index("logic.app_bootstrap()"), \
        "Gate muss VOR app_bootstrap() (DB-Zugriff) liegen"
    # echter Modul-Level-Aufruf (Zeilenanfang), nicht der Kommentar im Gate
    assert pos_exit < src.index("\nui.run(title="), "Gate muss VOR ui.run() liegen"
    # Pruefung beider Pflicht-Variablen im _missing-Block (Zeile mit Zitaten)
    assert src.index(f'"{ENV_SEED_PW}"') < pos_exit, \
        "Gate muss auch das Admin-Seed-Passwort pruefen"


@pytest.mark.parametrize("env_set,warn_erwartet", [(False, True), (True, False)])
def test_warnung_nur_ohne_env(env_set, warn_erwartet):
    """Sub-Prozess: startet main.py und prüft die stderr-Warnung.

    Die Warnung entsteht beim Import, vor dem Serve-Bereich. R3-4: damit der
    Prozess das Fail-closed-Gate überhaupt passiert, laeuft dieser Test mit
    KMHR_DEV=1 (Default-Warnung gilt seit R3-4 nur noch dort).
    """
    extra = {ENV_DEV: "1"}
    if env_set:
        extra[ENV_SECRET] = "p1-10-probe"
    rc, err, _db = _start_main(extra)
    gefunden = ENV_SECRET in err and "WARNUNG" in err
    assert gefunden is warn_erwartet, \
        f"env_set={env_set}: stderr={err[-400:]!r}"
    assert "ABBRUCH" not in err, \
        f"KMHR_DEV=1 muss das Gate uebergehen: stderr={err[-400:]!r}"


# ─── R3-4: Fail-closed-Gate (30.09.2026, Nutzer-GO) ────────────────────────

def test_abbruch_ohne_secrets_und_ohne_dev():
    """(a) Beide Pflicht-Variablen fehlen, kein KMHR_DEV -> Abbruch, keine DB."""
    rc, err, db_pfad = _start_main({})
    assert rc == 1, f"rc={rc} erwartet 1; stderr={err[-400:]!r}"
    assert "ABBRUCH" in err, f"ABBRUCH-Meldung fehlt: {err[-400:]!r}"
    assert ENV_SECRET in err and ENV_SEED_PW in err, \
        f"fehlende Variablen muessen namentlich genannt sein: {err[-400:]!r}"
    assert "knowledge/system/configuration-secrets.md" in err, \
        "Verweis auf die Spec fehlt"
    assert not db_pfad.exists(), \
        f"Gate darf vor app_bootstrap() liegen, DB wurde aber angefasst: {db_pfad}"


def test_dev_override_startet_ohne_secrets():
    """(b) KMHR_DEV=1 ohne Secrets -> kein Abbruch, Default + Warnung."""
    rc, err, db_pfad = _start_main({ENV_DEV: "1"})
    assert "ABBRUCH" not in err, f"KMHR_DEV=1 darf nicht abbrechen: {err[-400:]!r}"
    assert WARN_MERKMAL in err, f"Default-Warnung fehlt: {err[-400:]!r}"
    assert db_pfad.exists() and db_pfad.stat().st_size > 0, \
        "app_bootstrap() muss durchgelaufen sein (frische DB angelegt)"


def test_mit_secrets_kein_abbruch_ohne_default_warnung():
    """(c) Beide Secrets gesetzt -> kein Abbruch und keine Default-Warnung."""
    rc, err, db_pfad = _start_main({ENV_SECRET: "r34-probe-secret",
                                    ENV_SEED_PW: "r34-probe-seed-pw"})
    assert "ABBRUCH" not in err, f"gesetzte Secrets duerfen nicht abbrechen: {err[-400:]!r}"
    assert WARN_MERKMAL not in err, f"keine Default-Warnung erwartet: {err[-400:]!r}"
    assert db_pfad.exists() and db_pfad.stat().st_size > 0, \
        "app_bootstrap() muss durchgelaufen sein (frische DB angelegt)"


# ─── login.py: Admin-Seed ──────────────────────────────────────────────────

def test_admin_seed_kommt_aus_der_umgebung():
    src = LOGIN_PY.read_text(encoding="utf-8")
    assert f'"{ENV_SEED_PW}"' in src
    assert f'"{ENV_SEED_MAIL}"' in src


def test_admin_seed_password_nicht_als_nackter_codewert():
    """Der alte Klartext darf nicht mehr direkt im INSERT-Argument stehen."""
    src = LOGIN_PY.read_text(encoding="utf-8")
    assert 'hash_password_argon2id("admin-agent-2026")' not in src, \
        "Passwort darf nicht mehr woertlich an hash_password_argon2id uebergeben werden"
    assert "hash_password_argon2id(_seed_pw)" in src


def test_admin_seed_warnt_ohne_env():
    src = LOGIN_PY.read_text(encoding="utf-8")
    block = src[src.index("async def do_admin_login"):]
    block = block[:block.index('ui.button(_("Admin-Login")')]
    assert ENV_SEED_PW in block, "Warnung muss die Variable nennen"
    assert "WARNUNG" in block
    assert "file=sys.stderr" in block


# ─── R6-2.2 (30.09.2026): start-webui.sh liest .env, KMHR_DEV kein Default mehr ───

START_SH = ROOT / "start-webui.sh"


def _run_starter(env_file: str, extra_env: dict, timeout: int = 12):
    """Fuehrt start-webui.sh wirklich aus (isolierte DB/Port, kein Runner).
    Rueckgabe: (returncode | None bei Timeout, stdout+stderr)."""
    PROBE_DIR.mkdir(parents=True, exist_ok=True)
    db_pfad = Path(tempfile.mkdtemp(prefix="b-starter-", dir=PROBE_DIR)) / "probe.db"
    env = dict(os.environ)
    for key in (ENV_SECRET, ENV_SEED_PW, ENV_SEED_MAIL, ENV_DEV):
        env.pop(key, None)
    env.update({"KMHR_ENV_FILE": env_file, "KMHR_PORT": str(_free_port()),
                "KMHR_DB_PATH": str(db_pfad), "KMHR_RUNNER_AUTOSTART": "0"})
    env.update(extra_env)
    try:
        p = subprocess.run(["bash", str(START_SH)], env=env, capture_output=True,
                           text=True, timeout=timeout)
        return p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as ex:
        out = (ex.stdout or b"") + (ex.stderr or b"")
        return None, out.decode("utf-8", "replace") if isinstance(out, bytes) else out


def test_starter_setzt_kmhr_dev_nicht_mehr_als_default():
    text = START_SH.read_text(encoding="utf-8")
    assert not re.search(r"KMHR_DEV:-\s*1", text), "KMHR_DEV darf kein Starter-Default sein"
    assert "KMHR_ENV_FILE" in text and ".env" in text


def test_starter_verweigert_start_ohne_env_und_ohne_dev():
    rc, out = _run_starter("/nonexistent/.env", {})
    assert rc == 1, (rc, out)
    assert "ABBRUCH" in out and ENV_SECRET in out and ENV_SEED_PW in out


def test_starter_dev_override_ist_ausdruecklich_moeglich():
    rc, out = _run_starter("/nonexistent/.env", {ENV_DEV: "1"})
    assert "[start-webui] ABBRUCH" not in out, out  # Gate des Starters passiert
    assert WARN_MERKMAL in out, "unter KMHR_DEV muss die Default-Warnung sichtbar sein"


def test_starter_liest_env_datei_und_startet_ohne_default_warnung(tmp_path):
    envf = tmp_path / "test.env"
    envf.write_text(f"{ENV_SECRET}=testgeheimnis-nur-fuer-pytest\n"
                    f"{ENV_SEED_PW}=testpasswort-nur-fuer-pytest\n", encoding="utf-8")
    rc, out = _run_starter(str(envf), {})
    assert "ABBRUCH" not in out, out
    assert WARN_MERKMAL not in out, "Default-Secret wurde trotz .env benutzt"


def test_env_datei_ist_ignoriert_und_vorlage_enthaelt_keine_werte():
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert re.search(r"^\.env\*", gi, re.M) and "!.env.example" in gi
    vorlage = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "<zufaelliges-geheimnis>" in vorlage and "<zufaelliges-passwort>" in vorlage
