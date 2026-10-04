"""E2E: echter Datei-Upload über die NiceGUI-Handler (Fix QA-Bug 1-3, 28.09.2026).

Warum: vor dem Fix nutzten candidate.py (CV + Dokumente) und admin.py die
falsche Event-API (e.value / e.args / file.content). NiceGUI 3.17.1 liefert
nur UploadEventArguments.file (events.py:135-137) mit async read()
(upload_files.py:59-66, SmallFileUpload). QA-Multi-Agent-Runde 28.09.2026
hatte alle 3 Handler als defekt nachgewiesen — es existierte BISHER KEIN
Test, der überhaupt eine Datei hochlädt (set_input_files vorher = 0 Treffer
in tests/). Dieses Skript schließt genau diese Lücke.

Parität Altstand: app.py:2841-2861 (Portal-CV, .getvalue()) und
app.py:2883-2895 (Dokumente, accept_multiple_files + write_bytes).

NUR gegen Isolations-Instanz (KMHR_E2E_BASE MUSS gesetzt sein):
gegen Live würde die Queue den echten Runner starten (extract_profile ->
NVIDIA-API + DB-Schreibupdates), das wäre ein Seiteneffekt.
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --only e2e_cv_upload --port 8095

Ablauf:
 A QUELLTEXT   candidate.py/admin.py enthalten die korrekte API, nicht die alte
 B CV-UPLOAD   Login cand16 -> /candidate/profil -> Box "Lebenslauf hochladen"
               oeffnen -> set_input_files(TXT-Marker)
               -> status 'lebenslauf_hochgeladen' + lebenslauf_text + Toast
               + extract_profile-Task (id > Baseline)
 C DOKUMENTE   /candidate/profil -> Box "Dokumente" oeffnen -> 2 Dateien auf
               einmal (on_multi_upload)
               -> 2 candidate_documents-Zeilen + Dateien auf Disk + Toast
 D RESTORE     candidates-Zeilen, Dokument-Zeilen+Dateien, neue Tasks und
               neue testdaten/-Dateien werden in finally zurueckgesetzt;
               residue-Report + Baseline-Gleichheit muessen 0/True sein.
"""
from __future__ import annotations

import os
import sqlite3
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import BASE  # Env KMHR_E2E_BASE (Isolation 27.09.2026)
from e2e_harness import DB  # Env KMHR_DB_PATH (Isolation 27.09.2026)
from e2e_harness import check_server, db_residue_report, pre_max_tasks

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TESTDATEN = ROOT / "testdaten"
CAND_ID = 16
CAND_EMAIL = "e2e-beweis-phase1@example.com"
CAND_PASSWORD = "E2EMentoring2026!"
POS_STATUS = "lebenslauf_hochgeladen"
MARKER = "E2E-UPLOAD-BEWEIS"


def wait_for(fn, timeout: float = 20.0, interval: float = 0.4) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            if fn():
                return True
        except Exception:  # noqa: BLE001 — DB-Race waehrend Write
            pass
        time.sleep(interval)
    return False


def db_state() -> dict:
    conn = sqlite3.connect(str(DB))
    try:
        row = conn.execute(
            "SELECT status, lebenslauf_datei, lebenslauf_text FROM candidates WHERE id=?",
            (CAND_ID,),
        ).fetchone()
        docs = conn.execute(
            "SELECT COUNT(*) FROM candidate_documents WHERE candidate_id=?", (CAND_ID,)
        ).fetchone()[0]
        max_doc = conn.execute("SELECT COALESCE(MAX(id),0) FROM candidate_documents").fetchone()[0]
        return {
            "status": row[0],
            "datei": row[1],
            "text": row[2] or "",
            "docs": docs,
            "max_doc": max_doc,
        }
    finally:
        conn.close()


def daten_files() -> list[str]:
    return sorted(p.name for p in TESTDATEN.glob(f"kandidat-{CAND_ID}-*"))


def count_new_tasks(pre_id: int) -> int:
    conn = sqlite3.connect(str(DB))
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM agent_tasks WHERE id > ? AND task_type='extract_profile'",
            (pre_id,),
        ).fetchone()[0]
    finally:
        conn.close()


def login(page) -> None:
    page.goto(f"{BASE}/login", wait_until="networkidle")
    page.get_by_label("E-Mail").fill(CAND_EMAIL)
    page.get_by_label("Passwort", exact=True).fill(CAND_PASSWORD)
    page.get_by_role("button", name="Einloggen").click()
    page.wait_for_url("**/candidate**", timeout=15000)


def open_box(page, title: str) -> None:
    """Oeffnet eine geschlossene ui.expansion in 'Mein Profil' per Klick auf den Titel."""
    try:
        page.get_by_text(title, exact=True).first.click(timeout=8000)
        page.wait_for_timeout(500)
    except Exception:  # noqa: BLE001 — bereits offen / kein Titel-Treffer
        pass


def safe_goto(page, url: str, timeout: int = 90000) -> None:
    """goto mit Retry: nach dem Upload navigiert der Handler per ui.navigate.to
    auf /candidate/profil (Full-Reload). Ein sofortiges goto auf denselben Pfad
    kann an der noch laufenden Navigation mit ERR_ABORTED scheitern."""
    for _ in range(4):
        try:
            page.goto(url, wait_until="load", timeout=timeout)
            return
        except Exception:  # noqa: BLE001 — laufende Navigation abwarten
            page.wait_for_timeout(1500)
    page.goto(url, wait_until="domcontentloaded", timeout=timeout)


def set_files(page, paths: list[str], uploader_text: str | None = None) -> None:
    """Waehlt Datei(en) im versteckten q-uploader-input aus.

    uploader_text: optionaler Label-Filter (NiceGUI rendert den Inhalt einer
    geschlossenen ui.expansion nicht — daher gezielt den Uploader der geoeffneten
    Box adressieren, z. B. 'Dokumente (PDF/TXT').
    """
    root = page.locator(".q-uploader")
    if uploader_text:
        root = root.filter(has_text=uploader_text)
    loc = root.locator("input[type=file]").first
    try:
        loc.set_input_files(paths)
    except Exception:  # noqa: BLE001 — unsichtbarer Input: sichtbar machen
        loc.evaluate("el => { el.style.display = 'block'; el.style.visibility = 'visible'; }")
        loc.set_input_files(paths)


def check_a(failures) -> None:
    cand = (ROOT / "webui" / "pages" / "candidate.py").read_text(encoding="utf-8")
    adm = (ROOT / "webui" / "pages" / "admin.py").read_text(encoding="utf-8")
    for needle, src, desc in [
        ("await e.file.read()", cand, "candidate CV: await e.file.read()"),
        ("await file.read()", cand, "candidate Dokumente: await file.read()"),
        ("on_multi_upload=on_multi_upload", cand, "candidate Dokumente: on_multi_upload-Bindung"),
        ("async def on_upload", cand, "candidate CV: async-Handler"),
        ("await e.file.read()", adm, "admin: await e.file.read()"),
        ("async def _on_upload", adm, "admin: async-Handler"),
    ]:
        ok = needle in src
        print(f"A {desc}: {'OK' if ok else 'FEHLT'}")
        if not ok:
            failures.append(f"A {desc} fehlt")
    for needle, src, desc in [
        ("e.value.read(", cand, "candidate: alte e.value.read()"),
        ("e.value.name", cand, "candidate: alte e.value.name"),
        ("file.content", cand, "candidate: altes file.content"),
        ("e.args.get(", adm, "admin: altes e.args.get()"),
    ]:
        gone = needle not in src
        print(f"A alt entfernt {desc!r}: {'OK' if gone else 'NOCH DA'}")
        if not gone:
            failures.append(f"A alte API {desc!r} ist noch im Code")


def check_b(page, base: dict, pre_tasks: int, failures) -> None:
    if base["status"] == POS_STATUS:
        print("B Vorbedingung: Status bereits 'lebenslauf_hochgeladen' (wird trotzdem getestet)")
    page.goto(f"{BASE}/candidate/profil", wait_until="load", timeout=90000)
    page.wait_for_timeout(2500)
    open_box(page, "Lebenslauf hochladen")
    ts = int(time.time())
    cv = TESTDATEN / f"e2e-upload-cv-{ts}.txt"
    cv.write_text(
        f"{MARKER} {ts}\nMax Mustermann, Fachinformatiker Anwendungsentwicklung, "
        "5 Jahre Erfahrung Python, Deutsch C1.\n",
        encoding="utf-8",
    )
    try:
        set_files(page, [str(cv)])
        ok = wait_for(
            lambda: (lambda s: s[0] == POS_STATUS and MARKER in (s[1] or ""))(
                sqlite3.connect(str(DB)).execute(
                    "SELECT status, lebenslauf_text FROM candidates WHERE id=?", (CAND_ID,)
                ).fetchone()
            )
        )
        if not ok:
            st = db_state()
            failures.append(f"B CV-Upload nicht in DB: status={st['status']!r} marker_fehlt")
        else:
            print("B CV-Upload: status='lebenslauf_hochgeladen' + Marker im lebenslauf_text")
        ok_task = wait_for(lambda: count_new_tasks(pre_tasks) >= 1, timeout=10)
        if not ok_task:
            failures.append("B extract_profile-Task wurde nicht gequeued")
        else:
            print(f"B extract_profile-Task: gequeued (neu={count_new_tasks(pre_tasks)})")
        ok_toast = wait_for(
            lambda: "Lebenslauf hochgeladen" in page.locator("body").inner_text(), timeout=8
        )
        if not ok_toast:
            failures.append("B Toast 'Lebenslauf hochgeladen' fehlt")
        else:
            print("B Toast: sichtbar")
    finally:
        cv.unlink(missing_ok=True)


def check_c(page, base: dict, failures) -> None:
    safe_goto(page, f"{BASE}/candidate/profil")
    page.wait_for_timeout(2500)
    open_box(page, "Dokumente")
    ts = int(time.time())
    d1 = TESTDATEN / f"e2e-upload-doc-a-{ts}.txt"
    d2 = TESTDATEN / f"e2e-upload-doc-b-{ts}.txt"
    d1.write_text(f"{MARKER} Dokument A {ts}\n", encoding="utf-8")
    d2.write_text(f"{MARKER} Dokument B {ts}\n", encoding="utf-8")
    try:
        set_files(page, [str(d1), str(d2)], uploader_text="Dokumente (PDF/TXT")
        ok = wait_for(
            lambda: db_state()["docs"] == base["docs"] + 2
            and db_state()["max_doc"] > base["max_doc"]
        )
        if not ok:
            st = db_state()
            failures.append(
                f"C Dokumenten-Upload fehlgeschlagen: docs {base['docs']} -> {st['docs']} "
                f"(erwartet +2, Typ 'Zeugnis')"
            )
        else:
            print(f"C Dokumente: +2 Zeilen (docs={db_state()['docs']})")
            conn = sqlite3.connect(str(DB))
            rows = conn.execute(
                "SELECT datei_pfad FROM candidate_documents WHERE id > ?", (base["max_doc"],)
            ).fetchall()
            conn.close()
            missing = [r[0] for r in rows if not Path(r[0]).exists()]
            if len(rows) != 2:
                failures.append(f"C erwartet 2 neue Zeilen, gefunden {len(rows)}")
            if missing:
                failures.append(f"C Dateien fehlen auf Disk: {missing}")
            if rows and not missing:
                print(f"C Dateien auf Disk: {[Path(r[0]).name for r in rows]}")
        ok_toast = wait_for(
            lambda: "gespeichert" in page.locator("body").inner_text(), timeout=8
        )
        if not ok_toast:
            failures.append("C Toast 'Dokument(e) gespeichert' fehlt")
        else:
            print("C Toast: sichtbar")
    finally:
        d1.unlink(missing_ok=True)
        d2.unlink(missing_ok=True)


def restore(base: dict, pre_tasks: int, base_files: list[str]) -> None:
    conn = sqlite3.connect(str(DB))
    try:
        conn.execute(
            "UPDATE candidates SET status=?, lebenslauf_datei=?, lebenslauf_text=? WHERE id=?",
            (base["status"], base["datei"], base["text"], CAND_ID),
        )
        conn.execute("DELETE FROM candidate_documents WHERE id > ?", (base["max_doc"],))
        conn.execute("DELETE FROM agent_tasks WHERE id > ?", (pre_tasks,))
        conn.commit()
    finally:
        conn.close()
    for p in TESTDATEN.glob(f"kandidat-{CAND_ID}-*"):
        if p.name not in base_files:
            p.unlink(missing_ok=True)
    for p in TESTDATEN.glob("e2e-upload-*"):
        p.unlink(missing_ok=True)


def main() -> int:
    if "KMHR_E2E_BASE" not in os.environ:
        print(
            "ABBRUCH: KMHR_E2E_BASE nicht gesetzt — dieses Skript laeuft NUR "
            "gegen die Isolations-Instanz (Live-Runner wuerde extract_profile "
            "real ausfuehren). Aufruf: tests/e2e_isolation.py --only e2e_cv_upload"
        )
        return 3
    check_server()
    pre_tasks = pre_max_tasks()
    base = db_state()
    base_files = daten_files()
    print(f"DB-Baseline vor: status={base['status']!r} docs={base['docs']} "
          f"max_doc={base['max_doc']} tasks<={pre_tasks} files={len(base_files)}")
    failures: list[str] = []
    check_a(failures)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_default_timeout(60000)
        try:
            login(page)
            check_b(page, base, pre_tasks, failures)
            check_c(page, base, failures)
        except Exception as ex:  # noqa: BLE001
            failures.append(f"Exception: {ex!r}")
        finally:
            browser.close()

    restore(base, pre_tasks, base_files)
    after = db_state()
    print(f"DB-Baseline nach (Restore): status={after['status']!r} docs={after['docs']} "
          f"files={len(daten_files())}")
    if (after["status"], after["datei"], after["text"]) != (base["status"], base["datei"], base["text"]):
        failures.append("D Restore verletzt: candidates-Zeile weicht ab")
    if after["docs"] != base["docs"]:
        failures.append(f"D Restore verletzt: docs {base['docs']} -> {after['docs']}")
    if daten_files() != base_files:
        failures.append(f"D Restore verletzt: testdaten-Dateien {base_files} -> {daten_files()}")
    residue = db_residue_report(pre_tasks)
    if residue:
        failures.append(f"D Test-Reste: {residue} agent_tasks verbleiben")

    if failures:
        print("FAIL:")
        for f in failures:
            print(" -", f)
        return 1
    print("PASS: Upload-Kette CV (Tab 1) + Mehrfach-Dokumente (Tab 4) ueber echte "
          "NiceGUI-Events (e.file/e.files, async read) — DB, Queue, Toast, Restore ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
