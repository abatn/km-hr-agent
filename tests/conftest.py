"""Test-Isolation: Unit-Tests schreiben NIE in die Live-DB.

WARUM (Diagnose mit Beweisen, ergebnisse/entscheidungen.md, DIAGNOSE-AUFTRAG
27.09.2026 — Rohausgaben dort):
  * tests/test_dialog_identity.py:30-31 leitet den Pfad hart aus __file__ ab
    -> data/feedback.db (LIVE), 9x sqlite3.connect, 8 Write-Statements
    (applications + application_status_history), Restore in finally.
  * Jeder volle pytest-Lauf erhöhte sqlite_sequence um +4 (gemessen: 874->878
    volllauf, 878->878 nur die 3 anderen Dateien, 878->882 nur dialog_identity;
    3 INSERTs in Block A (:210) + 1 in Block B (:273) = 4).
  * Keine Umleitung existierte: conftest.py (Root) nur pytest_plugins,
    pytest.ini ohne env, webui/db.py ohne environ (grep = 0 Treffer).
  * Abbruch-Schadensbild in der Kopie reproduziert: 7 failed, 19 passed,
    Bewerbungen 20/23/26 blieben auf 'abgelehnt'.

WIE (Design-Entscheidung, keine externe Quelle nötig — Verhalten, kein Wert):
  * Diese Datei wird von pytest VOR dem Import jeder tests/test_*.py geladen.
  * Sie legt EINEN pro pytest-Prozess frischen Spiegel in /tmp an (Quelle wird
    read-only via .backup gespiegelt => die Live-DB wird nur GELESEN) und
    fängt danach jedes sqlite3.connect() ab: jeder Zugriff, dessen Pfad auf
    data/feedback.db zeigt, läuft stattdessen in den Spiegel.
  * Dadurch gilt das für ALLE Tests der Session — auch für
    tests/test_send_rejection_guard.py (liest Live-Status App 23 über
    scripts/agent-runner.py, das sich DB_PATH aus __file__ baut, :102).
  * KEIN Test, KEINE Baseline (PRE_HIST_COUNT=21 usw.) und KEIN Zeile Code in
    webui/, scripts/, app.py wird verändert — nur der Zielpfad des Zugriffs.

Nachweis-Kanal: der Spiegelpfad samt Vorher/Nachher-Werten wird in
/tmp/opencode/kmhr-mirror-last.txt geschrieben (extern messtbar, ohne dass
pytest-Ausgaben umgeschrieben werden muessen). Der Header nennt Laufzeitpunkt,
PID und status=start|beendet — status=start heisst: Lauf laeuft noch ODER ist
abgebrochen (Endwerte fehlen) => ein veralteter Pointer ist erkennbar.

Hygiene (Schritt 3, 27.09.2026): das eigene Spiegelverzeichnis wird beim
Prozessende ERST NACH den Endwerten entfernt; Reste abgebrochener Laeufe
werden beim naechsten Start auf die neuesten _KEEP_MIRRORS begrenzt.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

# ─── Pfade ────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
_LIVE = (_ROOT / "data" / "feedback.db").resolve()
_PTR = Path("/tmp/opencode/kmhr-mirror-last.txt")

# ─── Hygiene (Schritt 3, 27.09.2026) ─────────────────────────────────────
# Ziel A — DESIGN-ENTSCHEIDUNG (Verhalten, keine Quelle noetig):
#   (1) Beim Prozessende wird NUR das eigene Verzeichnis entfernt — und erst
#       NACHDEM die Endwerte in die Pointer-Datei geschrieben wurden
#       (pytest_sessionfinish unten). Live-DB und deren .bak-Dateien werden
#       nie beruehrt (doppelte Pfadpruefung: Name + Elternverzeichnis).
#   (2) kill -9 laesst sich nicht aueraeumen: deshalb werden beim START die
#       aeltesten Reste entfernt und die _KEEP_MIRRORS neuesten behalten —
#       die Belege der letzten Abbrueche bleiben erhalten, das Verzeichnis
#       wachst nicht mehr unbegrenzt (vorher: 20, nach dem naechsten Lauf 3).
#   OFFEN (bewusst nicht geloest): Parallelitaet — zwei pytest-Prozesse
#   gleichzeitig koennen sich gegenseitig Reste wegnehmen.
_KEEP_MIRRORS = 3
_PRUNE_LOG: list[str] = []


def _prune_old_mirrors() -> None:
    """Begrenzt eigene kmhr-mirror-* Reste auf die _KEEP neuesten."""
    try:
        dirs = [p for p in _PTR.parent.glob("kmhr-mirror-*") if p.is_dir()]
        dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for old in dirs[_KEEP_MIRRORS:]:
            # doppelte Sicherung: nur eigenes Praefix, nur im erlaubten Elternpfad
            if old.name.startswith("kmhr-mirror-") and old.parent == _PTR.parent:
                shutil.rmtree(old, ignore_errors=True)
                _PRUNE_LOG.append(old.name)
    except Exception as e:  # Hygiene darf den Testlauf nie verfaelschen
        _PRUNE_LOG.append(f"FEHLER: {e}")


# Reste begrenzen, DANN erst das eigene Verzeichnis anlegen (Reihenfolge:
# nie das eigene frische Verzeichnis mitten im Lauf entfernen)
_prune_old_mirrors()

# frischer, eindeutiger Spiegel je pytest-Prozess (kein rm der Live-DB)
_MIRROR_DIR = Path(tempfile.mkdtemp(prefix="kmhr-mirror-", dir="/tmp/opencode"))
_MIRROR = (_MIRROR_DIR / "feedback.db").resolve()

# ─── Original-Connect sichern (vor dem Patch) ─────────────────────────────
_orig_connect = sqlite3.connect


def _snapshot(path: Path) -> str:
    """Liest seq/count/max_id/status OHNE den eigenen Patch (ro, kein Schreibzugriff)."""
    conn = _orig_connect(f"file:{path}?mode=ro", uri=True)
    try:
        seq = conn.execute(
            "SELECT seq FROM sqlite_sequence WHERE name='application_status_history'"
        ).fetchone()[0]
        hist = conn.execute("SELECT COUNT(*) FROM application_status_history").fetchone()[0]
        mid = conn.execute("SELECT MAX(id) FROM application_status_history").fetchone()[0]
        st = dict(conn.execute(
            "SELECT id, status FROM applications WHERE id IN (8,20,23,25,26)"))
        return (f"seq={seq} hist_count={hist} max_id={mid} status="
                + ",".join(f"{k}:{st[k]}" for k in sorted(st)))
    finally:
        conn.close()


# ─── Spiegel anlegen: Live NUR lesend kopieren (mode=ro + .backup) ────────
_src = _orig_connect(f"file:{_LIVE}?mode=ro", uri=True)
_dst = _orig_connect(str(_MIRROR))
try:
    _src.backup(_dst)
finally:
    _dst.close()
    _src.close()

# ─── Ziel B: der Pointer weist JEDES LAUF eindeutig aus ──────────────────
# status=start  => Lauf laeuft noch ODER ist abgebrochen (veraltet erkennbar)
# status=beendet => Endwerte vollstaendig geschrieben
_RUN_ID = f"run={datetime.now().isoformat(timespec='seconds')} pid={os.getpid()}"
_START = (
    f"{_RUN_ID}\nstatus=start\nmirror={_MIRROR}\n"
    f"start_live={_snapshot(_LIVE)}\nstart_mirror={_snapshot(_MIRROR)}\n"
    + (f"pruned={','.join(_PRUNE_LOG)}\n" if _PRUNE_LOG else "pruned=-\n")
)
_PTR.write_text(_START, encoding="utf-8")


# ─── UMLEITUNG: jeder Zugriff auf die Live-DB landet im Spiegel ───────────
def _rewrite(path) -> str | None:
    try:
        p = str(path)
    except Exception:
        return None
    if p.startswith("file:"):
        p = p[5:].split("?")[0]
    #anker: exakter Live-Pfad ODER jeder Pfad, der auf data/feedback.db endet
    if p.endswith("data/feedback.db"):
        return str(_MIRROR)
    try:
        if Path(p).expanduser().resolve() == _LIVE:
            return str(_MIRROR)
    except Exception:
        pass
    return None


def _connect(path, *args, **kwargs):
    target = _rewrite(path)
    return _orig_connect(target if target else path, *args, **kwargs)


sqlite3.connect = _connect


def pytest_sessionfinish(session, exitstatus):
    """Endwerte in die Pointer-Datei — UND ERST DANACH das eigene Spiegel-
    verzeichnis entfernen. Reihenfolge ist die Sicherheitsregel: nie vor den
    Snapshots, nie die Live-DB, nie deren .bak-Dateien."""
    try:
        lines = _START + (f"end_live={_snapshot(_LIVE)}\nend_mirror={_snapshot(_MIRROR)}\n"
                          f"exitstatus={exitstatus}\nstatus=beendet\n")
        _PTR.write_text(lines, encoding="utf-8")
        print(f"\n[ISOLATION] {_PTR}")
        for line in lines.strip().splitlines():
            print(f"[ISOLATION] {line}")
    except Exception as e:  # niemals den Testlauf verfälschen
        print(f"[ISOLATION] Snapshot fehlgeschlagen: {e}")
    # Ziel A: eigenes Verzeichnis entfernen (doppelte Pfadpruefung)
    try:
        if (_MIRROR_DIR.name.startswith("kmhr-mirror-")
                and _MIRROR_DIR.parent == _PTR.parent
                and _MIRROR_DIR.is_dir()
                and _MIRROR_DIR != _LIVE.parent):
            shutil.rmtree(_MIRROR_DIR, ignore_errors=True)
            print(f"[ISOLATION] aufgeraeumt: {_MIRROR_DIR}")
        else:
            print(f"[ISOLATION] Aufraeumung uebersprungen (Pfadpruefung): {_MIRROR_DIR}")
    except Exception as e:
        print(f"[ISOLATION] Aufraeumung fehlgeschlagen: {e}")
