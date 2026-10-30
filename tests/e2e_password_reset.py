"""E2E Passwort-Reset (18.10.2026). Spec: knowledge/system/configuration-secrets.md §(g).

Isoliert (tests/e2e_isolation.py) — nie gegen die Live-App :8080.

Kette (Kandidat):
  1. /login → Tab „Login" → „Passwort vergessen?" → Dialog → E-Mail → „Link senden"
     → generische Antwort + `send_password_reset`-Task in der SPIEGEL-DB.
  2. Task-Payload aus der Spiegel-DB laden und den Runner IN-PROCESS ausfuehren
     (mcp_call gestubbt, DB auf die Spiegel-DB gesetzt) → Link/Token aus dem Mail-
     Body. Der Klartext-Token steht NUR dort (nur Hash in der DB).
  3. /login?reset=<token> → Dialog „Neues Passwort (2×)" → speichern → der Hash in
     der Spiegel-DB ist neu (argon2id) und verifiziert das neue Passwort.
  4. Login mit dem NEUEN Passwort → landet auf /candidate.
  5. Restore: alter `password_hash` zurueck, Reset-Zeilen + Task entfernen (keine
     Residuen fuer Folgeskripte im gemeinsamen Spiegel).
"""
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from e2e_harness import BASE, DB, seed_email  # noqa: E402

CAND_EMAIL = seed_email("test@example.de")   # Kandidat 2
CAND_ALT_PW = "test1234"                     # bekannte Altpasswort-Quelle (e2e_smoke_all_pages)
CAND_NEU_PW = "ResetE2E-2026!"


def _conn():
    return sqlite3.connect(str(DB))


def _rows(sql, params=()):
    conn = _conn()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def _orig_hash():
    return _rows("SELECT password_hash FROM candidates WHERE email = ?", (CAND_EMAIL,))


def _load_runner():
    spec = importlib.util.spec_from_file_location(
        "ar_e2e_pwreset", ROOT / "scripts" / "agent-runner.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DB_PATH = DB                      # NIE die Live-DB: Runner fest auf den Spiegel
    return mod


def main() -> int:
    check_server()
    pre = pre_max_tasks()
    fehler = []
    orig = _orig_hash()
    assert orig, f"Kandidat {CAND_EMAIL} nicht im Spiegel"
    orig_hash = orig[0][0]
    token = None

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            try:
                # ── 1. „Passwort vergessen?" ────────────────────────────
                page.goto(f"{BASE}/login", wait_until="load")
                page.wait_for_timeout(2000)
                panel = page.locator(".q-tab-panel:visible").filter(has_text="Willkommen zurueck")
                assert panel.count() == 1, "Kandidat-Login-Panel nicht sichtbar"
                panel.get_by_role("button", name="Passwort vergessen?").click()
                dlg = page.locator(".q-dialog:visible").first
                dlg.get_by_label("E-Mail").fill(CAND_EMAIL)
                dlg.get_by_role("button", name="Link senden").click()
                page.get_by_text(
                    "Wenn ein Konto mit dieser E-Mail existiert, ist der Link unterwegs."
                ).wait_for(timeout=10000)
                print('1) generische Antwort nach "Link senden" OK')
                tasks = _rows(
                    "SELECT id, payload FROM agent_tasks WHERE task_type = 'send_password_reset' "
                    "AND json_extract(payload, '$.id') = (SELECT id FROM candidates WHERE email = ?) "
                    "ORDER BY id DESC LIMIT 1",
                    (CAND_EMAIL,))
                if not tasks:
                    fehler.append("kein send_password_reset-Task in der Spiegel-DB")
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)

                # ── 2. Runner in-process (Payload aus dem Task) ─────────
                mod = _load_runner()
                captured = {}

                def _fake_mcp(server, tool, args):
                    captured.update(args)
                    return "OK (gemockt)"

                mod.mcp_call = _fake_mcp
                payload = json.loads(tasks[0][1]) if tasks else {"email": CAND_EMAIL,
                                                                 "role": "candidate"}
                res = mod.send_password_reset(payload)
                if res.get("status") != "sent":
                    fehler.append(f"Runner-Status {res.get('status')} != sent")
                body = captured.get("body", "")
                if "/login?reset=" not in body:
                    fehler.append("kein Reset-Link im Mail-Body")
                    token = None
                else:
                    token = body.split("/login?reset=")[1].split()[0].strip()
                # Token nur im Body — nicht in Subject/Rückgabe/DB-Klartext
                if token:
                    if token in captured.get("subject", ""):
                        fehler.append("Token im Subject")
                    if token in str(res):
                        fehler.append("Token in der Runner-Rückgabe")
                    stored = _rows("SELECT token_hash FROM password_resets WHERE email = ?",
                                   (CAND_EMAIL,))
                    if not stored:
                        fehler.append("keine password_resets-Zeile")
                    elif token in [s[0] for s in stored]:
                        fehler.append("Token im Klartext gespeichert")
                print(f"2) Runner: status={res.get('status')} token_len={len(token) if token else 0}")

                # ── 3. Reset-Dialog über ?reset=<token> ────────────────
                if token:
                    page.goto(f"{BASE}/login?reset={token}", wait_until="load")
                    page.wait_for_timeout(2500)
                    rdlg = page.locator(".q-dialog:visible").first
                    rdlg.get_by_label("Neues Passwort", exact=True).fill(CAND_NEU_PW)
                    rdlg.get_by_label("Neues Passwort wiederholen").fill(CAND_NEU_PW)
                    rdlg.get_by_role("button", name="Passwort speichern").click()
                    page.wait_for_timeout(2000)
                    neu = _rows("SELECT password_hash FROM candidates WHERE email = ?",
                                (CAND_EMAIL,))[0][0]
                    if neu == orig_hash:
                        fehler.append("password_hash unveraendert nach Reset")
                    sys.path.insert(0, str(ROOT / "webui"))
                    from webui.logic import verify_password_argon2id
                    if not verify_password_argon2id(CAND_NEU_PW, neu):
                        fehler.append("neuer Hash verifiziert das neue Passwort nicht")
                    print("3) Reset gespeichert + argon2id-Nachweis OK")

                    # ── 4. Login mit NEUEM Passwort ────────────────────
                    page.goto(f"{BASE}/login", wait_until="load")
                    page.wait_for_timeout(2000)
                    lp = page.locator(".q-tab-panel:visible").filter(has_text="Willkommen zurueck")
                    lp.get_by_label("E-Mail").fill(CAND_EMAIL)
                    lp.get_by_label("Passwort", exact=True).fill(CAND_NEU_PW)
                    lp.get_by_role("button", name="Einloggen").click()
                    page.wait_for_url("**/candidate**", timeout=20000)
                    print("4) Login mit neuem Passwort OK")

                    # Einmal-Verwendung: derselbe Link darf nicht erneut wirken
                    ok2 = True
                    try:
                        page.goto(f"{BASE}/login?reset={token}", wait_until="load")
                        page.wait_for_timeout(2000)
                        rd2 = page.locator(".q-dialog:visible").first
                        if rd2.count() >= 1:
                            rd2.get_by_label("Neues Passwort", exact=True).fill("Nochmal-2026!")
                            rd2.get_by_label("Neues Passwort wiederholen").fill("Nochmal-2026!")
                            rd2.get_by_role("button", name="Passwort speichern").click()
                            page.wait_for_timeout(1500)
                            after = _rows("SELECT password_hash FROM candidates WHERE email = ?",
                                          (CAND_EMAIL,))[0][0]
                            from webui.logic import verify_password_argon2id as _v
                            if _v("Nochmal-2026!", after):
                                fehler.append("Token war NICHT einmalig (2. Reset wirkte)")
                    except Exception as ex:  # noqa: BLE001
                        ok2 = False
                        print(f"   (Einmal-Test: Dialog nicht wiederverwendbar: {ex!r})")
                    if ok2:
                        print("5) Einmal-Verwendung bestaetigt (2. Nutzung wirkungslos)")
            finally:
                browser.close()
    finally:
        # ── 5. Restore (keine Residuen im gemeinsamen Spiegel) ─────────
        conn = _conn()
        try:
            conn.execute("UPDATE candidates SET password_hash = ? WHERE email = ?",
                         (orig_hash, CAND_EMAIL))
            conn.execute("DELETE FROM password_resets WHERE email = ?", (CAND_EMAIL,))
            conn.execute("DELETE FROM agent_tasks WHERE task_type = 'send_password_reset' "
                         "AND (json_extract(payload, '$.email') = ? "
                         "OR json_extract(payload, '$.id') = (SELECT id FROM candidates WHERE email = ?))",
                         (CAND_EMAIL, CAND_EMAIL))
            conn.commit()
        finally:
            conn.close()

    rest = _rows("SELECT password_hash FROM candidates WHERE email = ?", (CAND_EMAIL,))
    if not rest or rest[0][0] != orig_hash:
        fehler.append("Restore des alten password_hash fehlgeschlagen")

    db_residue_report(pre)
    if fehler:
        print("FAIL:")
        for f in fehler:
            print("  -", f)
        return 1
    print("PASS: Passwort-Reset E2E (generische Antwort -> Link -> Reset -> Login mit neuem PW)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
