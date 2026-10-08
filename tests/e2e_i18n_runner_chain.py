"""E2E (07.10.2026): nutzersichtbare Agent-Kette (Runner + MCP) in DE/EN/FR/AR.

Spec (verbindlich): `knowledge/system/i18n-runner-chain.md` (Sprach-Matrix §4,
Ist-Analyse/Gap §2). Nachweis je Sprache L ∈ {de,en,fr,ar}:

  1. Login cand16 (DE) -> Sprachwechsel auf L -> `documentElement.lang == L`.
  2. Profil speichern -> Toast == msgstr(L, "Profil gespeichert!").
  3. CV-Upload -> Toast == msgstr(L, "Lebenslauf hochgeladen ({0} Zeichen).")
     + candidates.status='lebenslauf_hochgeladen' + Task extract_profile (id > pre).
  4. Bewerben -> Toast == msgstr(L, "Bewerbung gesendet! ...") + 10 Kettentasks
     (id > pre) + notifications-Zeile (role='employer') in Sprache L.
  5. Runner-Drain (DRY_RUN, offline) -> alle Kettentasks 'done', keine 'failed'.
  6. Klasse-F-Nachweis (P2/P3, 07.10.2026): Runner nutzt NUR die framework-freie
     i18n-Kernschicht `webui.i18n_core` (kein NiceGUI) UND die DRY-RUN-Mail-Betreffe
     sind je Sprache unterschiedlich (Klasse F geschlossen).
  7. Restore im finally -> cand16-Zeile, neue applications/status_history/
     candidate_documents/agent_tasks/notifications + Testdateien zurueck; F3
     Test-Reste=0.

NUR isoliert (R6-0, KMHR_RUNNER_AUTOSTART=0 im Wrapper), nie Live-DB:
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port 8095 --only e2e_i18n_runner_chain

Runner-Simulation statt Subprozess (`--once` wuerde die LIVE-DB abarbeiten):
Runner-Modul laden (Muster tests/e2e_contract_preflight.py::_load_runner),
DB_PATH auf die Spiegel-DB setzen, DRY_RUN=True, Pflicht-Offline-Patches
(_pdf_forensic_pre_scan, ansvar_search, zusaetzlich get_ansvar_token als
Netz-Haertung) — mcp_call/run_llm_task brechen im DRY_RUN vor jedem echten
Mail-/Netz-/LLM-Call ab.
"""
from __future__ import annotations

import importlib.util
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from e2e_harness import BASE, DB, check_server, db_residue_report, pre_max_tasks, seed_email

LIVE_DB = (ROOT / "data" / "feedback.db").resolve()
RUNNER = ROOT / "scripts" / "agent-runner.py"
LOCALES = ROOT / "webui" / "locales"
TESTDATEN = ROOT / "testdaten"

CAND_ID = 16
CAND_EMAIL = seed_email("e2e-beweis-phase1@example.com")
CAND_PASSWORD = "E2EMentoring2026!"
MARKER = "E2E-I18N-RUNNER-BEWEIS"
LANGS = ("de", "en", "fr", "ar")

CHAIN_TASKS = (
    "send_confirmation", "extract_profile", "match_candidate", "check_compliance",
    "assess_culture_fit", "verify_documents", "check_visa", "explain_match",
    "check_gdpr", "notify_user",
)

# Erwartete msgstr (verbindlich, Quelle: webui/locales/*/messages.po, ⓘ07.10.2026)
TOAST_PROFILE = {
    "de": "Profil gespeichert!",
    "en": "Profile saved!",
    "fr": "Profil enregistré !",
    "ar": "تم حفظ الملف الشخصي!",
}
TOAST_CV = {
    "de": "Lebenslauf hochgeladen ({0} Zeichen).",
    "en": "CV uploaded ({0} characters).",
    "fr": "CV téléchargé ({0} caractères).",
    "ar": "تم تحميل السيرة الذاتية ({0} حرفًا).",
}
TOAST_APPLY = {
    "de": "Bewerbung gesendet! Der Agent prueft Ihren Lebenslauf.",
    "en": "Application submitted! The agent is checking your CV.",
    "fr": "Candidature envoyée ! L'agent vérifie votre CV.",
    "ar": "تم إرسال الطلب! يتحقق الوكيل من سيرتك الذاتية.",
}
NOTIF_TITLE = {
    "de": "Neue Bewerbung",
    "en": "New application",
    "fr": "Nouvelle candidature",
    "ar": "طلب جديد",
}
NOTIF_MSG = {
    "de": "{0} hat sich beworben: {1}",
    "en": "{0} has applied: {1}",
    "fr": "{0} a postulé : {1}",
    "ar": "{0} قدّم طلبًا: {1}",
}


# ─── .po lesen (UI-Labels fuer Klicks; Toasts per obiger Matrix geprueft) ──

def load_po(lang: str) -> dict:
    path = LOCALES / lang / "LC_MESSAGES" / "messages.po"
    d: dict = {}
    cur = None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("msgid "):
            cur = _unescape(line[len("msgid "):])
        elif line.startswith("msgstr ") and cur is not None:
            d[cur] = _unescape(line[len("msgstr "):])
            cur = None
    return d


def _unescape(tok: str) -> str:
    tok = tok.strip()
    if tok.startswith('"') and tok.endswith('"') and len(tok) >= 2:
        tok = tok[1:-1]
    return tok.replace('\\"', '"').replace("\\\\", "\\")


def t(po: dict, msgid: str) -> str:
    return po.get(msgid) or msgid


# ─── DB-Helfer ─────────────────────────────────────────────────────────────

def _q(sql: str, args=()):
    conn = sqlite3.connect(str(DB))
    try:
        return conn.execute(sql, args).fetchall()
    finally:
        conn.close()


def _q1(sql: str, args=()):
    rows = _q(sql, args)
    return rows[0] if rows else None


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


def cand_state():
    return _q1("SELECT status, lebenslauf_datei, lebenslauf_text FROM candidates WHERE id=?",
               (CAND_ID,))


def baseline() -> dict:
    return {
        "cand": cand_state(),
        "app_max": _q1("SELECT COALESCE(MAX(id),0) FROM applications")[0],
        "app_n": _q1("SELECT COUNT(*) FROM applications")[0],
        "hist_max": _q1("SELECT COALESCE(MAX(id),0) FROM application_status_history")[0],
        "doc_max": _q1("SELECT COALESCE(MAX(id),0) FROM candidate_documents")[0],
        "notif_max": _q1("SELECT COALESCE(MAX(id),0) FROM notifications")[0],
        "notif_n": _q1("SELECT COUNT(*) FROM notifications")[0],
        "files": {p.name for p in TESTDATEN.glob(f"kandidat-{CAND_ID}-*")},
    }


def choose_target_job():
    """Erste aktive Stelle, auf die cand16 im Baseline NICHT beworben ist."""
    for jid, titel in _q("SELECT id, titel FROM jobs WHERE status='aktiv' ORDER BY id DESC"):
        n = _q1("SELECT COUNT(*) FROM applications WHERE candidate_id=? AND job_id=?",
                (CAND_ID, jid))[0]
        if n == 0:
            return jid, titel
    return None


def reset_target(jid: int) -> None:
    """Entfernt cand16-Bewerbung(en) auf der Zielstelle (frisches app_id je Sprache)."""
    ids = [r[0] for r in _q("SELECT id FROM applications WHERE candidate_id=? AND job_id=?",
                            (CAND_ID, jid))]
    conn = sqlite3.connect(str(DB))
    try:
        for aid in ids:
            conn.execute("DELETE FROM application_status_history WHERE application_id=?", (aid,))
            conn.execute("DELETE FROM applications WHERE id=?", (aid,))
        conn.commit()
    finally:
        conn.close()


def drain_runner(mod, pre: int, failures: list, lang: str) -> None:
    """Alle pending-Tasks id>pre deterministisch ausfuehren (DRY_RUN, offline)."""
    for _ in range(40):
        rows = _q("SELECT id, task_type, payload, attempts FROM agent_tasks "
                  "WHERE id>? AND status='pending' ORDER BY id", (pre,))
        if not rows:
            break
        for tid, tt, pl, att in rows:
            conn = sqlite3.connect(str(DB))
            try:
                mod.process_task(conn, tid, tt, pl, att or 0)
            finally:
                conn.close()
    else:
        failures.append(f"[{lang}] Runner-Drain: Obergrenze 40 Runden erreicht, "
                        "Queue nicht leer")
    if _q1("SELECT COUNT(*) FROM agent_tasks WHERE id>? AND status='pending'", (pre,))[0]:
        failures.append(f"[{lang}] Runner-Drain: pending-Tasks verbleiben")


def assert_chain(app_id: int, pre: int, failures: list, lang: str) -> None:
    rows = _q("SELECT task_type, status FROM agent_tasks "
              "WHERE id>? AND json_extract(payload, '$.application_id')=?", (pre, app_id))
    by_type: dict = {}
    for tt, st in rows:
        by_type.setdefault(tt, set()).add(st)
    for tt in CHAIN_TASKS:
        if tt not in by_type:
            failures.append(f"[{lang}] Kettentask {tt} fehlt (app {app_id})")
        elif "done" not in by_type[tt]:
            failures.append(f"[{lang}] Kettentask {tt} status={by_type[tt]} (app {app_id})")
    failed = _q("SELECT id, task_type, error_text FROM agent_tasks "
                "WHERE id>? AND status='failed'", (pre,))
    if failed:
        failures.append(f"[{lang}] failed Tasks: {failed}")


# ─── Runner-Modul + Offline-Patches ────────────────────────────────────────

def load_runner():
    spec = importlib.util.spec_from_file_location("agent_runner_i18n_e2e", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DB_PATH = Path(DB)
    mod.DRY_RUN = True
    # Pflicht-Offline-Patches (Spec §3): laufen VOR dem DRY_RUN-Guard.
    mod._pdf_forensic_pre_scan = lambda cand_id: "[E2E] forensik uebersprungen"
    mod.ansvar_search = lambda *a, **k: {"results": []}
    # Zusatz-Haertung (Design-Entscheidung): get_ansvar_token() macht sonst VOR
    # dem DRY_RUN-Guard einen HTTP-Test -> offline ersetzen.
    mod.get_ansvar_token = lambda: "E2E-TOKEN"
    return mod


def read_log(path: Path, offset: int) -> str:
    try:
        if not path.exists():
            return ""
        size = path.stat().st_size
        if size < offset:
            return path.read_text(encoding="utf-8", errors="replace")
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            fh.seek(offset)
            return fh.read()
    except Exception:  # noqa: BLE001
        return ""


def check_klasse_f(failures: list, log_text: str) -> None:
    """P2/P3 (07.10.2026): Klasse F geschlossen. Der Runner nutzt die framework-
    freie i18n-Kernschicht (`webui.i18n_core`, gettext, KEIN NiceGUI) — der
    Session-Layer `webui.i18n`/NiceGUI bleibt verboten (Prozess-Trennung §7.1)."""
    src = RUNNER.read_text(encoding="utf-8")
    forbidden = ("from webui import i18n", "webui.i18n import",
                 "import nicegui", "from nicegui", "gettext.translation",
                 "set_language(", "LABELS")
    hits = [n for n in forbidden if n in src]
    if hits:
        failures.append(f"Klasse-F verletzt: NiceGUI-/Session-i18n-Spur im Runner {hits}")
    elif "from webui.i18n_core import" not in src:
        failures.append("Klasse-F: Runner importiert webui.i18n_core nicht (framework-frei)")
    else:
        print("OK Klasse-F statisch: Runner nutzt nur webui.i18n_core (framework-frei)")
    # Sprachabhaengige DRY-RUN-Betreffe (Sprach-Matrix §4) — kein Gap mehr.
    betreffe = {
        "de": "Ihre Bewerbung ist eingegangen",
        "en": "Your application has been received",
        "fr": "Votre candidature a été reçue",
        "ar": "تم استلام طلبك",
    }
    fehlend = [lang for lang, s in betreffe.items() if s not in log_text]
    if fehlend:
        failures.append(f"Klasse-F: DRY-RUN-Mail-Betreff fehlt/falsch fuer {fehlend}")
    else:
        print("OK Klasse-F funktional: DRY-RUN-Mail-Betreff je Sprache unterschiedlich")


# ─── Browser-Flows ─────────────────────────────────────────────────────────

def open_box(page, title: str) -> None:
    try:
        page.get_by_text(title, exact=True).first.click(timeout=8000)
        page.wait_for_timeout(500)
    except Exception:  # noqa: BLE001 — bereits offen / kein Titel-Treffer
        pass


def safe_goto(page, url: str, timeout: int = 90000) -> None:
    for _ in range(4):
        try:
            page.goto(url, wait_until="load", timeout=timeout)
            return
        except Exception:  # noqa: BLE001
            page.wait_for_timeout(1500)
    page.goto(url, wait_until="domcontentloaded", timeout=timeout)


def set_files(page, paths: list[str]) -> None:
    loc = page.locator(".q-uploader").locator("input[type=file]").first
    try:
        loc.set_input_files(paths)
    except Exception:  # noqa: BLE001
        loc.evaluate("el => { el.style.display='block'; el.style.visibility='visible'; }")
        loc.set_input_files(paths)


def wait_toast(page, expected: str, timeout: float = 8.0) -> bool:
    return wait_for(lambda: expected in page.locator("body").inner_text(),
                    timeout=timeout, interval=0.2)


def login_de(page) -> None:
    page.goto(f"{BASE}/login", wait_until="load", timeout=90000)
    page.wait_for_timeout(2000)
    page.get_by_label("E-Mail").fill(CAND_EMAIL)
    page.get_by_label("Passwort", exact=True).fill(CAND_PASSWORD)
    page.get_by_role("button", name="Einloggen").click()
    page.wait_for_url("**/candidate**", timeout=20000)


def switch_lang(page, lang: str) -> None:
    code = {"de": "DE", "en": "EN", "fr": "FR", "ar": "AR"}[lang]
    page.get_by_role("button", name=code, exact=True).first.click()
    page.wait_for_timeout(3000)


def run_language(browser, lang: str, target: tuple, pre: int, mod, base: dict,
                 failures: list) -> bool:
    po = load_po(lang)
    jid, titel = target
    ok = True
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(60000)
    try:
        login_de(page)
        switch_lang(page, lang)
        dom_lang = page.evaluate("document.documentElement.lang")
        if dom_lang != lang:
            failures.append(f"[{lang}] documentElement.lang={dom_lang!r} (erwartet {lang!r})")
            ok = False
        else:
            print(f"[{lang}] Sprachwechsel ok (documentElement.lang={dom_lang})")

        # 2) Profil speichern
        safe_goto(page, f"{BASE}/candidate/profil")
        page.wait_for_timeout(2000)
        open_box(page, t(po, "Profil bearbeiten"))
        btn = page.get_by_role("button", name=t(po, "Profil speichern")).first
        btn.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        btn.click()
        exp_prof = TOAST_PROFILE[lang]
        if wait_toast(page, exp_prof):
            print(f"[{lang}] Toast Profil: {exp_prof!r}")
        else:
            failures.append(f"[{lang}] Toast Profil fehlt: {exp_prof!r}")
            ok = False

        # 3) CV-Upload
        safe_goto(page, f"{BASE}/candidate/profil")
        page.wait_for_timeout(2000)
        open_box(page, t(po, "Lebenslauf hochladen"))
        ts = int(time.time())
        cv = TESTDATEN / f"e2e-i18n-runner-cv-{lang}-{ts}.txt"
        content = (f"{MARKER} {lang} {ts}\nMax Mustermann, Fachinformatiker "
                   "Anwendungsentwicklung, 5 Jahre Erfahrung Python, Deutsch C1.\n")
        cv.write_text(content, encoding="utf-8")
        set_files(page, [str(cv)])
        exp_cv = TOAST_CV[lang].format(len(content))
        if wait_toast(page, exp_cv):
            print(f"[{lang}] Toast CV: {exp_cv!r}")
        else:
            failures.append(f"[{lang}] Toast CV fehlt: {exp_cv!r}")
            ok = False
        uploaded = wait_for(
            lambda: (lambda s: s and s[0] == "lebenslauf_hochgeladen" and MARKER in (s[2] or ""))
            (cand_state()))
        if not uploaded:
            st = cand_state()
            failures.append(f"[{lang}] CV nicht in DB (status={st[0] if st else None!r})")
            ok = False
        else:
            print(f"[{lang}] CV-Upload DB ok (status=lebenslauf_hochgeladen)")
        if not wait_for(lambda: _q1("SELECT COUNT(*) FROM agent_tasks WHERE id>? "
                                    "AND task_type='extract_profile'", (pre,))[0] >= 1,
                        timeout=10):
            failures.append(f"[{lang}] extract_profile-Task (CV) fehlt")
            ok = False

        # 4) Bewerben (Zielstelle vorher freiraeumen -> frisches app_id)
        reset_target(jid)
        safe_goto(page, f"{BASE}/candidate/stellen")
        page.wait_for_timeout(2500)
        card = page.locator(".q-card").filter(has_text=re.compile(rf"#{jid} ")).first
        card.wait_for(timeout=30000)
        card.get_by_role("button", name=t(po, "Bewerben")).click()
        page.locator(".q-dialog").wait_for(timeout=10000)
        page.get_by_role("button", name=t(po, "Jetzt bewerben")).click()
        exp_apply = TOAST_APPLY[lang]
        if wait_toast(page, exp_apply):
            print(f"[{lang}] Toast Bewerbung: {exp_apply!r}")
        else:
            failures.append(f"[{lang}] Toast Bewerbung fehlt: {exp_apply!r}")
            ok = False
        page.wait_for_timeout(1500)

        app_row = _q1("SELECT id FROM applications WHERE candidate_id=? AND job_id=? "
                      "ORDER BY id DESC LIMIT 1", (CAND_ID, jid))
        if not app_row:
            failures.append(f"[{lang}] keine Bewerbung auf Job #{jid} angelegt")
            ok = False
            return ok
        app_id = app_row[0]
        if not wait_for(lambda: _q1("SELECT COUNT(*) FROM agent_tasks "
                                    "WHERE id>? AND json_extract(payload,'$.application_id')=?",
                                    (pre, app_id))[0] >= len(CHAIN_TASKS), timeout=15):
            failures.append(f"[{lang}] nicht alle 10 Kettentasks gequeued (app {app_id})")
            ok = False

        # notifications-Zeile in Sprache L (neueste Zeile = dieser Apply-Vorgang)
        nrow = _q1("SELECT titel, nachricht FROM notifications WHERE id>? "
                   "AND role='employer' ORDER BY id DESC LIMIT 1", (base["notif_max"],))
        if not nrow:
            failures.append(f"[{lang}] notifications-Zeile fehlt")
            ok = False
        else:
            exp_t, msg = nrow
            pat = re.escape(NOTIF_MSG[lang]).replace(r"\{0\}", ".*").replace(r"\{1\}", re.escape(titel))
            if exp_t != NOTIF_TITLE[lang]:
                failures.append(f"[{lang}] notification titel={exp_t!r} != {NOTIF_TITLE[lang]!r}")
                ok = False
            if not re.fullmatch(pat, msg):
                failures.append(f"[{lang}] notification nachricht={msg!r} passt nicht zu {pat!r}")
                ok = False
            if ok:
                print(f"[{lang}] notifications ok: {exp_t!r} / {msg!r}")

        # 5) Runner-Drain (DRY_RUN, offline)
        drain_runner(mod, pre, failures, lang)
        assert_chain(app_id, pre, failures, lang)
        if not any(f.startswith(f"[{lang}]") for f in failures):
            print(f"[{lang}] Runner-Drain: alle Kettentasks done")
    except Exception as ex:  # noqa: BLE001
        failures.append(f"[{lang}] Exception: {ex!r}")
        ok = False
    finally:
        ctx.close()
    return ok


# ─── Restore ───────────────────────────────────────────────────────────────

def restore(base: dict, pre: int) -> None:
    conn = sqlite3.connect(str(DB))
    try:
        st = base["cand"]
        conn.execute("UPDATE candidates SET status=?, lebenslauf_datei=?, lebenslauf_text=? "
                     "WHERE id=?", (st[0], st[1], st[2], CAND_ID))
        conn.execute("DELETE FROM application_status_history WHERE id>?", (base["hist_max"],))
        conn.execute("DELETE FROM applications WHERE id>?", (base["app_max"],))
        conn.execute("DELETE FROM candidate_documents WHERE id>?", (base["doc_max"],))
        conn.execute("DELETE FROM agent_tasks WHERE id>?", (pre,))
        conn.execute("DELETE FROM notifications WHERE id>?", (base["notif_max"],))
        conn.commit()
    finally:
        conn.close()
    for p in TESTDATEN.glob("e2e-i18n-runner-*"):
        p.unlink(missing_ok=True)
    for p in TESTDATEN.glob(f"kandidat-{CAND_ID}-*"):
        if p.name not in base["files"]:
            p.unlink(missing_ok=True)


def main() -> int:
    if Path(DB).resolve() == LIVE_DB:
        print("ABBRUCH: DB-Pfad ist die Live-DB — nur via tests/e2e_isolation.py ausfuehren")
        return 2
    check_server()
    pre = pre_max_tasks()
    base = baseline()
    target = choose_target_job()
    print(f"Baseline: cand={base['cand']} app_max={base['app_max']} notif_max={base['notif_max']} "
          f"pre={pre}")
    if target is None:
        print("FAIL: keine freie aktive Stelle fuer cand16 (Spiegel-DB)")
        return 1
    print(f"Zielstelle: #{target[0]} {target[1]!r}")

    failures: list[str] = []
    mod = load_runner()
    log_offset = mod.LOG_FILE.stat().st_size if mod.LOG_FILE.exists() else 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                for lang in LANGS:
                    ok = run_language(browser, lang, target, pre, mod, base, failures)
                    print(f"[{lang}] rc={'0' if ok else '1'}")
            finally:
                browser.close()

        log_text = read_log(mod.LOG_FILE, log_offset)
        check_klasse_f(failures, log_text)
    finally:
        restore(base, pre)

    after = cand_state()
    if after != base["cand"]:
        failures.append(f"Restore verletzt: candidates {base['cand']} -> {after}")
    if _q1("SELECT COUNT(*) FROM applications")[0] != base["app_n"]:
        failures.append("Restore verletzt: applications-Anzahl")
    if _q1("SELECT COUNT(*) FROM notifications")[0] != base["notif_n"]:
        failures.append("Restore verletzt: notifications-Anzahl")
    files_now = {p.name for p in TESTDATEN.glob(f"kandidat-{CAND_ID}-*")}
    if files_now != base["files"]:
        failures.append(f"Restore verletzt: testdaten {base['files']} -> {files_now}")
    residue = db_residue_report(pre)
    if residue:
        failures.append(f"Test-Reste: {residue} agent_tasks verbleiben")

    if failures:
        print("E2E I18N RUNNER CHAIN FAIL:")
        for f in failures:
            print("  -", f)
        return 1
    print("E2E I18N RUNNER CHAIN PASS (DE/EN/FR/AR: Toast + Kette + notifications + "
          "Runner-Drain done; Klasse F geschlossen)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
