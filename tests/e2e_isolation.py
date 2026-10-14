"""E2E-Isolation (Punkt 1 der offenen Punkte, 27.09.2026).

Vorbild: tests/conftest.py (Unit-Tests gegen Spiegel-DB). Zwei Bausteine:

  A) Regel „vorher Snapshot, danach Abgleich":
     1. VOR dem Lauf  : Snapshot der Live-DB (nur via `sqlite3 ".backup"`, nie `cp`)
     2. NACH dem Lauf : Diff Live-Dump gegen den Snapshot -> Sollwert rc=0
  B) Echte DB-Umschaltung:
     - eigener NiceGUI-Prozess auf eigenem Port (KMHR_PORT, Default 8081)
     - eigene Spiegel-DB (KMHR_DB_PATH), KMHR_RUNNER_AUTOSTART=0 (kein 2. Runner)
     - alle tests/e2e_*.py bekommen KMHR_E2E_BASE + KMHR_DB_PATH in die Env
       => weder Skript-Zugriffe (BASE/DB aus e2e_harness) noch App-Zugriffe
       (webui/db.py DB_PATH) berühren data/feedback.db

Aufruf (aus dem Repo-Root):
  .venv-streamlit/bin/python3 tests/e2e_isolation.py                 # alle 22 Skripte
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --only e2e_housing,e2e_vorgemerkt
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8090 --no-run   # nur Server+Snapshot

Logs/Artefakte (kein rm, bleiben liegen):
  /tmp/opencode/e2e-iso-<ts>/
    server.log          Log des isolierten App-Prozesses
    <script>.log        Ausgabe je Skript
    live_vorher.db      Snapshot der Live-DB (.backup)
    live_vorher.sql     Dump vor dem Lauf
    live_nachher.sql    Dump nach dem Lauf
    mirror.db           Spiegel-DB für die isolierte Instanz
    summary.txt         Ergebnistabelle inkl. Live-Diff-rc

Nicht enthalten (bewusst): Restore der Live-DB — Daten-/Tabelleninhalte
werden in dieser Runde nicht angefasst; bei Diff-rc != 0 wird nur gemeldet.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Lokale Verifikation des CI-Modus (Option A): mit KMHR_E2E_LIVE_DB auf
# tests/fixtures/seed.db zeigen und KMHR_E2E_SEED=1 setzen. Default = Live-DB.
LIVE_DB = Path(os.environ.get("KMHR_E2E_LIVE_DB") or (ROOT / "data" / "feedback.db"))
DEFAULT_PORT = 8081
# Prozesse, die NICHT angefasst werden duerfen (laufende Live-App/-Runner).
FORBIDDEN_PIDS = {82162, 81303}
# Skripte, die selbst kein E2E-Skript sind (Harness = Bibliothek, dieser Wrapper).
SKIP = {"e2e_harness.py", "e2e_isolation.py"}


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, **kw)


def sqlite_dump(db: Path, out: Path) -> int:
    """Dump der DB nach out; rc des sqlite3-Aufrufs."""
    with out.open("w") as fh:
        p = subprocess.run(["sqlite3", str(db), ".dump"], stdout=fh,
                           stderr=subprocess.PIPE, text=True)
    return p.returncode


def wait_http(url: str, timeout: float = 90.0) -> int:
    """Wartet bis HTTP 200; liefert den letzten gemeldeten Status (0 = kein Fehler)."""
    import urllib.error
    import urllib.request

    deadline = time.time() + timeout
    code = 0
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                return resp.status
        except urllib.error.HTTPError as e:
            code = e.code
        except Exception:
            code = 0
        time.sleep(1.0)
    return code


def main() -> int:
    ap = argparse.ArgumentParser(description="E2E-Isolation (Snapshot + Spiegel-Instanz)")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--only", default="", help="kommagetrennte Skriptnamen ohne .py")
    ap.add_argument("--no-run", action="store_true", help="nur Server + Snapshot, keine Skripte")
    ap.add_argument("--startup-timeout", type=float, default=90.0)
    args = ap.parse_args()

    ts = time.strftime("%Y%m%d-%H%M%S")
    logdir = Path("/tmp/opencode") / f"e2e-iso-{ts}"
    logdir.mkdir(parents=True, exist_ok=True)

    base = f"http://localhost:{args.port}"
    if not LIVE_DB.exists():
        print(f"LIVE-DB fehlt: {LIVE_DB}")
        return 3

    # ── 1) Snapshot VOR dem Lauf (nur .backup, nie cp) ─────────────────
    snap_db = logdir / "live_vorher.db"
    snap_sql = logdir / "live_vorher.sql"
    p = _run(["sqlite3", str(LIVE_DB), f".backup {snap_db}"])
    if p.returncode != 0 or not snap_db.exists() or snap_db.stat().st_size == 0:
        print(f"SNAPSHOT FEHLGESCHLAGEN rc={p.returncode} {p.stderr.strip()}")
        return 3
    sqlite_dump(LIVE_DB, snap_sql)
    # Byte-Referenz der Live-Datei (sha256 statt `cmp` gegen den .backup-Spiegel:
    # .backup normalisiert Header-Bausteine, liefert also auch bei identischem
    # Inhalt andere Bytes — nachgewiesen: 5 Header-Bytes Delta bei Dump-rc=0).
    sha_before = hashlib.sha256(LIVE_DB.read_bytes()).hexdigest()

    # ── 2) Spiegel-DB fuer die isolierte Instanz ───────────────────────
    mirror = logdir / "mirror.db"
    p = _run(["sqlite3", str(LIVE_DB), f".backup {mirror}"])
    if p.returncode != 0 or not mirror.exists():
        print(f"SPIEGEL FEHLGESCHLAGEN rc={p.returncode} {p.stderr.strip()}")
        return 3

    # ── 3) isolierter App-Prozess (eigener Port, eigene DB, kein Runner) ─
    import os
    env = dict(os.environ)
    env.update({
        "KMHR_DB_PATH": str(mirror),
        "KMHR_PORT": str(args.port),
        "KMHR_RUNNER_AUTOSTART": "0",
        "KMHR_E2E_BASE": base,
        # R3-4 (30.09.2026): Fail-closed-Gate in webui/main.py — der isolierte
        # Server UND alle Skripte starten mit diesem env, also KMHR_DEV=1.
        "KMHR_DEV": "1",
    })
    server_log = (logdir / "server.log").open("w")
    print(f"[iso] Log-Verzeichnis : {logdir}")
    print(f"[iso] Spiegel-DB      : {mirror} ({mirror.stat().st_size} B)")
    print(f"[iso] Snapshot        : {snap_db} ({snap_db.stat().st_size} B)")
    print(f"[iso] isolierter Port : {base} (KMHR_DB_PATH, KMHR_RUNNER_AUTOSTART=0)")
    server = subprocess.Popen([sys.executable, "-m", "webui.main"], cwd=ROOT, env=env,
                              stdout=server_log, stderr=subprocess.STDOUT)
    if server.pid in FORBIDDEN_PIDS:
        print("ABBRUCH: kind-prozess wuerde einen verbotenen PID treffen")
        server.terminate()
        return 3
    code = wait_http(f"{base}/login", timeout=args.startup_timeout)
    print(f"[iso] Server-Check    : HTTP {code} (PID {server.pid})")
    if code != 200:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:
            server.kill()
        print("ABBRUCH: isolierter Server nicht erreichbar — Live-DB wurde nur gelesen")
        return 3

    # ── 4) Skripte gegen die isolierte Instanz ─────────────────────────
    skip_env: set[str] = set()  # Klasse b: initialisiert für Summary-Zugriff
    if args.only:
        scripts = [ROOT / "tests" / f"{n.strip()}.py" for n in args.only.split(",") if n.strip()]
        missing = [str(s) for s in scripts if not s.exists()]
        if missing:
            print(f"ABBRUCH: Skripte fehlen: {missing}")
            server.terminate()
            return 3
    else:
        skip_env = {s.strip() for s in os.environ.get("KMHR_E2E_SKIP", "").split(",") if s.strip()}
        # Klasse b (14.10.2026): Skip-Namen validieren (Tippfehler = stilles Ausführen)
        all_scripts = {p.stem for p in (ROOT / "tests").glob("e2e_*.py")}
        unknown_skips = skip_env - all_scripts
        if unknown_skips:
            print(f"[iso] WARNUNG: Unbekannte KMHR_E2E_SKIP-Namen: {', '.join(sorted(unknown_skips))}")
        scripts = sorted(p for p in (ROOT / "tests").glob("e2e_*.py")
                         if p.name not in SKIP and p.stem not in skip_env)
        if skip_env:
            print(f"[iso] CI-Skip (KMHR_E2E_SKIP): {', '.join(sorted(skip_env))}")

    results: list[tuple[str, int, float]] = []
    t_suite = time.time()
    if not args.no_run:
        for script in scripts:
            log = logdir / f"{script.stem}.log"
            t0 = time.time()
            with log.open("w") as fh:
                rc = subprocess.run([sys.executable, str(script)], cwd=ROOT, env=env,
                                    stdout=fh, stderr=subprocess.STDOUT).returncode
            dur = time.time() - t0
            results.append((script.name, rc, dur))
            print(f"[iso] {script.name:34s} rc={rc} {dur:6.1f}s")
    suite_dur = time.time() - t_suite

    # ── 5) isolierten eigenen Server stoppen (nur dieses Kind) ─────────
    server.terminate()
    try:
        server.wait(timeout=20)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=10)
    server_log.close()

    # ── 6) Live-DB-Abgleich: Snapshot vorher vs. Live nachher ──────────
    after_sql = logdir / "live_nachher.sql"
    sqlite_dump(LIVE_DB, after_sql)
    diff_rc = subprocess.run(["diff", str(snap_sql), str(after_sql)]).returncode
    sha_after = hashlib.sha256(LIVE_DB.read_bytes()).hexdigest()
    sha_rc = 0 if sha_before == sha_after else 1
    sqlite_rc = _run(["sqlite3", str(LIVE_DB),
                      "SELECT (SELECT seq FROM sqlite_sequence WHERE name='application_status_history'),"
                      "(SELECT count(*) FROM application_status_history),"
                      "(SELECT count(*) FROM sqlite_master WHERE type='table');"]).stdout.strip()

    lines = []
    lines.append(f"E2E-Isolation-Lauf {ts}")
    lines.append(f"Log-Verzeichnis : {logdir}")
    lines.append(f"Isolierte Instanz: {base} (PID {server.pid}, Spiegel {mirror.name})")
    lines.append(f"Skripte          : {len(results)} (Gesamtdauer {suite_dur:.1f}s)")
    # Klasse b (14.10.2026): Skip-Liste ins Summary (vorher unsichtbar)
    if skip_env:
        lines.append(f"CI-Skip          : {', '.join(sorted(skip_env))}")
    for name, rc, dur in results:
        lines.append(f"  {name:34s} rc={rc} {dur:6.1f}s")
    lines.append(f"Live-Diff (dump) : rc={diff_rc}  <- Sollwert 0")
    lines.append(f"Live-Bytes sha256: vorher={sha_before[:16]}... nachher={sha_after[:16]}... "
                 f"gleich={sha_before == sha_after} (rc={sha_rc}, Sollwert 0)")
    lines.append(f"Live nachher     : seq/hist/tabellen = {sqlite_rc}")
    summary = "\n".join(lines) + "\n"
    (logdir / "summary.txt").write_text(summary)
    print(summary)
    print(f"[iso] Summary: {logdir / 'summary.txt'}")

    if args.no_run:
        # Klasse b (14.10.2026): Live-Diff trotzdem auswerten (vorher still rc=0)
        print("[iso] --no-run: keine Skripte ausgeführt, aber Live-Diff wird ausgewertet")
        fehler_no_run = []  # Keine Kind-Skripte → keine Fehler
    else:
        # Fehlerweitergabe (CI-Fix 04.10.2026): Ein fehlgeschlagenes E2E-Skript MUSS den
        # Gesamtlauf fehlschlagen lassen — vorher wurde nur DB-Diff/-Hash ausgewertet.
        fehler_no_run = [n for n, rc, _ in results if rc != 0]
        if fehler_no_run:
            print(f"[iso] FEHLGESCHLAGENE Skripte ({len(fehler_no_run)}): {', '.join(fehler_no_run)}")
    return 0 if (diff_rc == 0 and sha_rc == 0 and not fehler_no_run) else 1


if __name__ == "__main__":
    sys.exit(main())
