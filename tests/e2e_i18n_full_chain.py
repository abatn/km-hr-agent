"""E2E (07.10.2026): KOMPLETTE Bewerbungskette je Sprache (DE/EN/FR/AR).

Spec (verbindlich): `knowledge/system/i18n-runner-chain.md` §5 (voller Gesamtlauf
je Sprache, Nutzer-Auftrag 07.10.2026) + §4 Sprach-Matrix + §7 Variante B
(Session-Sprache des Ausloesers -> `language` im Task-Payload).

Datensatz (Spiegel-DB, verifiziert 07.10.2026): Kandidat #13 `taoufik`
(Tunesien, batninitaoufik@gmail.com), Zielstelle #7 „Ausbildung zur
Pflegefachkraft (m/w/d)" (aktiv, employer_id 1, fuer #13 unbelegt),
Arbeitgeber #1 TechVision GmbH (hr@techvision.de). Alle Bestands-Bewerbungen
von #13 (job 1/5/6) sind final (abgelehnt/eingestellt) — fuer Stelle #7 gibt
es auf /employer/match genau eine legale Aktion.

Nachweis je Sprache L:
  1. Kandidaten-Login (frischer Kontext = DE) -> Umschalter -> lang == L
     (bei ar zusaetzlich dir == rtl).
  2. CV-Upload -> Toast msgstr(L, „Lebenslauf hochgeladen ({0} Zeichen).") +
     DB (status + MARKER im lebenslauf_text) + extract_profile-Task id > pre.
  3. Bewerben auf Stelle #7 -> Toast msgstr(L, „Bewerbung gesendet! ...") +
     frische application (reset_target) + 10 Kettentasks (id > pre,
     payload.language == L) + notifications-Zeile role='employer' in Sprache L.
  4. Runner-Drain (DRY_RUN, offline) -> alle Kettentasks done, keine failed.
  5. Arbeitgeber-Phase in EIGENER Playwright-Session (frischer Node-Driver) und
     eigenem Kontext -> Employer-Login (DE-Labels) -> Sprachwechsel auf L
     (locator-basierte Assertion lang/dir) -> /employer/match?kandidat=13 ->
     „Als angesehen markieren" (Karte per Aktions-Button + Titel, count==1)
     -> Toast + DB 'angesehen'.
  6. Einladen ueber den MATCH-Seiten-Dialog („Kandidat einladen"; derselbe
     Handler wie /employer/stellen, KEINE Navigation dorthin — die liess den
     Playwright-Driver in WSL verhungern, s. Spec §5): Termin-Defaults AUS DEM
     DIALOG gelesen -> „Einladen" -> DB 'eingeladen' + Payload
     termin_datum/-uhrzeit/-dauer_min (Default 30, KEIN Runner-Fallback 20),
     trigger 'hr_klick_portal', language == L (Polling auf die Task-Zeile).
  7. Runner-Drain (create_invitation) -> result_json done: termin msgstr(L),
     recording False, Gast-Link &record=off, Director-Link ohne record,
     ics_path NICHT geschrieben (DRY_RUN), mail 'DRY-RUN'.
  8. Einladungs-Mail-Betreff in-process gegen mcp-email-server.py (Muster
     `tests/test_runner_i18n.py::test_p2b_send_pre_screen_invitation_sprachabhaengig`).
  9. FRISCHER zweiter Browser-Kontext (im ersten waere die Rolle `employer`):
     Kandidaten-Login -> Sprache L -> /candidate/bewerbungen -> Einladungs-
     karte #<app_id>: Kopf msgstr(L), „Termin: <msgstr(L, {0} Uhr ...)>",
     Meeting-Link-Input mit vdo.ninja + record=off, kein <a>-Link,
     ICS-Button ABWESEND (= DRY_RUN-Nachweis).

DRY_RUN-Begruendung: Der Lauf darf weder Mail noch LLM noch Netz anstossen —
Runner-Simulation wie `tests/e2e_i18n_runner_chain.py` (Modul laden,
DB_PATH = Spiegel-DB, DRY_RUN=True, Pflicht-Offline-Patches
_pdf_forensic_pre_scan / ansvar_search / get_ansvar_token). `mcp_call`
liefert „DRY-RUN", `run_llm_task` schreibt keine Berichtsdatei (frueh-Return),
ICS wird nicht geschrieben — die HR-Klicks erzeugen DB-Zeilen + einen
create_invitation-Task. EIN Schreibrest bleibt trotz DRY_RUN: `process_task`
legt den Einladungs-Bericht `ergebnisse/einladung-bewerbung-<app_id>.md`
unbedingt an (Agent-Runner, Speicher-Nachweispflicht Spec §9) — dieser Lauf
loescht ihn im finally wieder (Baseline-Menge `rep_before`, Rest = Fehler).

Restgrenzen (bewusst, ehrlich):
  * Das Einladen laeuft ueber den Match-Dialog, NICHT ueber die Stellen-Seite:
    `goto /employer/stellen` direkt nach dem „angesehen"-Klick liess den
    Playwright-Node-Driver in dieser WSL-Umgebung wiederholt verhungern
    (EPIPE/blockierender count(); 6 Fehllaeufe, Diagnose per faulthandler).
    Die Stellen-Seite bleibt durch das gruene tests/e2e_invitation_termin.py
    (DE) abgedeckt; das dortige Inline-Label „Einladungs-Termin (…)" wird hier
    daher NICHT geprueft.
  * ICS-Download-Button des Kandidaten fehlt in DRY_RUN -> nicht klickbar;
    geprueft wird das NICHT-Vorhandensein (DRY_RUN-Nachweis, kein Produktbefund).
  * Profil-Speichern (Toast) der Alt-Vorlage ist hier NICHT enthalten — die
    befohlene Pflicht-Reihenfolge nennt ihn nicht.
  * Statischer Klasse-F-Quelltextscan bleibt `e2e_i18n_runner_chain`
    vorbehalten; hier nur die Betreff-Matrix aus dem Runner-Log (§7.2).
  * Toast nach „-> eingeladen" wird NICHT geprueft (ui.notify gefolgt von
    ui.navigate.reload = zu kleines Zeitfenster) — harter Nachweis ist die DB.

Isolation (R6-0): NUR via tests/e2e_isolation.py, nie gegen die Live-DB:
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --port <frei> --only e2e_i18n_full_chain

Exit-Codes: 0 = PASS, 1 = FAIL (Liste am Ende), 2 = Live-DB-Pfad (Guard).
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import sqlite3
import sys
import time
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from e2e_harness import BASE, DB, check_server, db_residue_report, pre_max_tasks

LIVE_DB = (ROOT / "data" / "feedback.db").resolve()
RUNNER = ROOT / "scripts" / "agent-runner.py"
EMAIL_SERVER_PY = ROOT / "mcp-email-server.py"
LOCALES = ROOT / "webui" / "locales"
TESTDATEN = ROOT / "testdaten"
ERGEBNISSE = ROOT / "ergebnisse"

CAND_ID = 13
CAND_EMAIL = "batninitaoufik@gmail.com"
CAND_PASSWORD = "Abd15121978!"
EMP_EMAIL = "hr@techvision.de"
EMP_PW = "sicher123"
EMPLOYER_ID = 1
JOB_ID = 7
MARKER = "E2E-I18N-FULL-CHAIN"
# Sprachliste per Umgebungsvariable begrenzbar (z.B. KMHR_FULLCHAIN_LANGS=de).
# Grund (07.10.2026): der Gesamtlauf braucht 4 Browserphasen; unter Speicherdruck
# (Agent-Prozess belegt ~3,5 GB) stuerzte der Playwright-Driver sporadisch ab
# (EPIPE). Einzelsprach-Laeufe senken den Peak und lassen Fortschritt stehen.
LANGS = tuple(x.strip() for x in
              os.environ.get("KMHR_FULLCHAIN_LANGS", "de,en,fr,ar").split(",")
              if x.strip())

CHAIN_TASKS = (
    "send_confirmation", "extract_profile", "match_candidate", "check_compliance",
    "assess_culture_fit", "verify_documents", "check_visa", "explain_match",
    "check_gdpr", "notify_user",
)

# Erwartete msgstr (verbindlich, Quelle: webui/locales/*/messages.po + .mo, ⓘ07.10.2026)
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
# send_confirmation-Betreff je Sprache (Runner baut ihn ueber tr(); Log-Nachweis §7.2)
BETREFFE = {
    "de": "Ihre Bewerbung ist eingegangen",
    "en": "Your application has been received",
    "fr": "Votre candidature a été reçue",
    "ar": "تم استلام طلبك",
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


def app_state(app_id: int) -> str:
    row = _q1("SELECT status FROM applications WHERE id=?", (app_id,))
    return row[0] if row else ""


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
        "apps13": _q("SELECT id, job_id, status FROM applications WHERE candidate_id=? ORDER BY id",
                     (CAND_ID,)),
    }


def validate_target():
    """Stelle #7 + Datensatz-Checks. Rueckgabe (titel, kandidatenname) oder None.

    Abbruch, wenn die Zielstelle nicht freisehbar waere (falscher employer,
    nicht aktiv, Bestands-Bewerbung von #13 auf #7 oder offene Alt-Bewerbung)
    — sonst waeren die reset-/Kartenschaetze dieses Laufs ungueltig."""
    job = _q1("SELECT id, titel, status, employer_id FROM jobs WHERE id=?", (JOB_ID,))
    if not job or job[2] != "aktiv" or job[3] != EMPLOYER_ID:
        return None
    if _q1("SELECT COUNT(*) FROM applications WHERE candidate_id=? AND job_id=?",
           (CAND_ID, JOB_ID))[0]:
        return None
    offen = _q("SELECT id, status FROM applications WHERE candidate_id=? "
               "AND status NOT IN ('abgelehnt','eingestellt','zurückgezogen')", (CAND_ID,))
    if offen:
        return None
    cand = _q1("SELECT name, email FROM candidates WHERE id=?", (CAND_ID,))
    if not cand or cand[1] != CAND_EMAIL or not cand[0]:
        return None
    return job[1], cand[0]


def reset_target(jid: int) -> None:
    """Entfernt die Bewerbung(en) von #13 auf der Zielstelle (frisches app_id je Sprache)."""
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
    # Variante B (Spec §7.1): jede Task der KETTE traegt die Ausloeser-Sprache.
    # Nur CHAIN_TASKS zaehlen — Nicht-Chain-Tasks mit application_id (z.B. der
    # Auto-Refresh match_candidate aus scripts/agent-runner.py, ohne language;
    # Fund 07.10.2026) sind INFO-Zeile, kein Assertion-Fehler.
    ph = ",".join("?" * len(CHAIN_TASKS))
    langen = {r[0] for r in _q(
        f"SELECT DISTINCT json_extract(payload, '$.language') FROM agent_tasks "
        f"WHERE id>? AND json_extract(payload, '$.application_id')=? "
        f"AND task_type IN ({ph})", (pre, app_id, *CHAIN_TASKS))}
    if langen != {lang}:
        pairs = _q(f"SELECT task_type, json_extract(payload, '$.language') FROM agent_tasks "
                   f"WHERE id>? AND json_extract(payload, '$.application_id')=? "
                   f"AND task_type IN ({ph})", (pre, app_id, *CHAIN_TASKS))
        failures.append(f"[{lang}] payload.language der Kettentasks = {langen!r} "
                        f"(erwartet {{{lang!r}}}) — Paare (task, language): {pairs!r}")
    rest = _q(f"SELECT DISTINCT task_type, json_extract(payload, '$.language') FROM agent_tasks "
              f"WHERE id>? AND json_extract(payload, '$.application_id')=? "
              f"AND task_type NOT IN ({ph})", (pre, app_id, *CHAIN_TASKS))
    if rest:
        print(f"[{lang}] INFO Nicht-Chain-Tasks mit app_id (task, language): {rest}")


# ─── Runner-Modul + Offline-Patches ────────────────────────────────────────

def load_runner():
    spec = importlib.util.spec_from_file_location("agent_runner_full_chain_e2e", RUNNER)
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


def check_betreffe(failures: list, log_text: str) -> None:
    """Spec §7.2: DRY-RUN-Betreff der Bestaetigungsmail je Sprache verschieden.
    Nur die konfigurierte Sprachliste (KMHR_FULLCHAIN_LANGS) wird geprueft."""
    fehlend = [lang for lang in LANGS if BETREFFE.get(lang) not in log_text]
    if fehlend:
        failures.append(f"Betreff-Matrix: send_confirmation-Betreff fehlt/falsch fuer {fehlend}")
    else:
        print(f"OK Betreff-Matrix: send_confirmation-Betreff je Sprache verschieden "
              f"({len(LANGS)}/{len(LANGS)})")


_MCP_CACHE: dict = {}


def load_email_mcp():
    """mcp-email-server.py in-process laden (Dateiname mit Bindestrich -> importlib)."""
    if "email" not in _MCP_CACHE:
        spec = importlib.util.spec_from_file_location("mcp_email_full_chain", EMAIL_SERVER_PY)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MCP_CACHE["email"] = mod
    return _MCP_CACHE["email"]


def check_einladungsbetreff(lang: str, po: dict, position: str, failures: list) -> None:
    """P2b-Ebene im E2E-Kontext: send_pre_screen_invitation baut Betreff ueber tr().
    DRY_RUN fuehrt den MCP-Server NICHT aus (mcp_call bricht ab) — deshalb der
    Direktaufruf mit gestopftem send_email (KEIN Versand, Muster
    tests/test_runner_i18n.py::test_p2b_send_pre_screen_invitation_sprachabhaengig)."""
    mod = load_email_mcp()
    captured: dict = {}

    def _fake_send(to, subject, body, **kw):
        captured["subject"] = subject
        return "OK|fake"

    orig = mod.send_email
    mod.send_email = _fake_send
    try:
        mod.send_pre_screen_invitation(
            "e2e@example.org", f"Kandidat #{CAND_ID}", position,
            "https://vdo.ninja/?room=prescreeningtest&record=off",
            "2026-10-10", "10:00", "Themen", language=lang)
    finally:
        mod.send_email = orig
    erwartet = t(po, "Pre-Screening: {position}").format(position=position)
    if captured.get("subject") != erwartet:
        failures.append(f"[{lang}] Einladungs-Mail-Betreff {captured.get('subject')!r} "
                        f"!= {erwartet!r}")
    else:
        print(f"[{lang}] Einladungs-Mail-Betreff ok: {erwartet!r}")


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


def assert_lang(page, lang: str, failures: list) -> bool:
    # Locator-basiert statt page.evaluate: evaluate hat KEINEN Timeout (Hängen-Risiko,
    # Lauf 3 07.10.2026: 900-s-Abbruch) — Attribute respektieren set_default_timeout.
    dom = page.locator("html").first.get_attribute("lang")
    if dom != lang:
        failures.append(f"[{lang}] documentElement.lang={dom!r} (erwartet {lang!r})")
        return False
    if lang == "ar":
        richtung = page.locator("html").first.get_attribute("dir")
        if richtung != "rtl":
            failures.append(f"[{lang}] documentElement.dir={richtung!r} (erwartet 'rtl')")
            return False
    return True


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


def login_employer(page, po: dict) -> None:
    """Employer-Login in Sprache L (Session-Sprache ueberlebt den Seitenwechsel —
    Muster tests/e2e_invitation_termin.py::login_employer, Labels uebersetzt)."""
    safe_goto(page, f"{BASE}/login")
    page.wait_for_timeout(2000)
    page.get_by_role("tab", name=t(po, "Arbeitgeber"), exact=True).click()
    page.wait_for_timeout(700)
    # Panel am Login-Button festmachen (waehrend der Tab-Animation 2 E-Mail-Felder)
    panel = page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=t(po, "Arbeitgeber-Login"))).first
    panel.get_by_label(t(po, "E-Mail")).fill(EMP_EMAIL)
    panel.get_by_label(t(po, "Passwort"), exact=True).fill(EMP_PW)
    panel.get_by_role("button", name=t(po, "Arbeitgeber-Login")).click()
    page.wait_for_url("**/employer**", timeout=20000)


def stellen_karte(page, app_id: int, titel: str):
    """Karte der Bewerbung #app_id auf /employer/stellen (count==1) oder None."""
    cards = (page.locator(".q-card")
             .filter(has_text=re.compile(rf"#{app_id}\b"))
             .filter(has_text=titel))
    if cards.count() != 1:
        return None
    return cards.first


def candidate_phase(browser, lang: str, pre: int, mod, base: dict, job: tuple,
                    failures: list) -> int | None:
    """Schritte 1-4: Kandidaten-Login, Sprachwechsel, CV-Upload, Bewerben, Drain.
    Bekommt eine EIGENE Playwright-Session (der Aufrufer schliesst sie); die
    Employer-Phase laeuft danach in einer FRISCHEN Session (Driver-Isolation)."""
    po = load_po(lang)
    titel, cand_name = job
    ok = True
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(20000)
    app_id = None
    try:
        # 1) Kandidaten-Login (frischer Kontext = DE) -> Sprachwechsel auf L
        login_de(page)
        switch_lang(page, lang)
        if assert_lang(page, lang, failures):
            print(f"[{lang}] Sprachwechsel ok (lang + dir)" + (" — RTL" if lang == "ar" else ""))
        else:
            ok = False
        notif_before = _q1("SELECT COALESCE(MAX(id),0) FROM notifications")[0]

        # 2) CV-Upload
        safe_goto(page, f"{BASE}/candidate/profil")
        page.wait_for_timeout(2000)
        open_box(page, t(po, "Lebenslauf hochladen"))
        ts = int(time.time())
        cv = TESTDATEN / f"e2e-i18n-full-cv-{lang}-{ts}.txt"
        content = (f"{MARKER} {lang} {ts}\nTaoufik, Krankenpfleger in Tunesien, "
                   "6 Jahre Berufserfahrung, Deutsch B1, Franzoesisch.\n")
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

        # 3) Bewerben auf Stelle #7 (Zielstelle vorher freiraeumen -> frisches app_id)
        reset_target(JOB_ID)
        safe_goto(page, f"{BASE}/candidate/stellen")
        page.wait_for_timeout(2500)
        job_cards = page.locator(".q-card").filter(
            has_text=re.compile(rf"#{JOB_ID} {re.escape(titel)}"))
        n_cards = job_cards.count()
        if n_cards != 1:
            failures.append(f"[{lang}] Stellenkarte #{JOB_ID} nicht eindeutig ({n_cards})")
            return None
        job_cards.first.get_by_role("button", name=t(po, "Bewerben"), exact=True).click()
        page.locator(".q-dialog").wait_for(timeout=10000)
        page.get_by_role("button", name=t(po, "Jetzt bewerben"), exact=True).click()
        exp_apply = TOAST_APPLY[lang]
        if wait_toast(page, exp_apply):
            print(f"[{lang}] Toast Bewerbung: {exp_apply!r}")
        else:
            failures.append(f"[{lang}] Toast Bewerbung fehlt: {exp_apply!r}")
            ok = False
        page.wait_for_timeout(1500)

        app_row = _q1("SELECT id FROM applications WHERE candidate_id=? AND job_id=? "
                      "ORDER BY id DESC LIMIT 1", (CAND_ID, JOB_ID))
        if not app_row:
            failures.append(f"[{lang}] keine Bewerbung auf Job #{JOB_ID} angelegt")
            return None
        app_id = app_row[0]
        if not wait_for(lambda: _q1("SELECT COUNT(*) FROM agent_tasks "
                                    "WHERE id>? AND json_extract(payload,'$.application_id')=?",
                                    (pre, app_id))[0] >= len(CHAIN_TASKS), timeout=15):
            failures.append(f"[{lang}] nicht alle 10 Kettentasks gequeued (app {app_id})")
            ok = False

        # notifications-Zeile in Sprache L (neueste employer-Zeile nach notif_before)
        nrow = _q1("SELECT titel, nachricht FROM notifications WHERE id>? "
                   "AND role='employer' ORDER BY id DESC LIMIT 1", (notif_before,))
        if not nrow:
            failures.append(f"[{lang}] notifications-Zeile fehlt")
            ok = False
        else:
            exp_t, msg = nrow
            pat = (re.escape(NOTIF_MSG[lang]).replace(r"\{0\}", ".*")
                   .replace(r"\{1\}", re.escape(titel)))
            n0 = len(failures)
            if exp_t != NOTIF_TITLE[lang]:
                failures.append(f"[{lang}] notification titel={exp_t!r} != {NOTIF_TITLE[lang]!r}")
                ok = False
            if not re.fullmatch(pat, msg):
                failures.append(f"[{lang}] notification nachricht={msg!r} passt nicht zu {pat!r}")
                ok = False
            if len(failures) == n0:
                print(f"[{lang}] notifications ok: {exp_t!r} / {msg!r}")

        # 4) Runner-Drain der Bewerberkette (DRY_RUN, offline)
        n0 = len(failures)
        drain_runner(mod, pre, failures, lang)
        assert_chain(app_id, pre, failures, lang)
        if len(failures) == n0:
            print(f"[{lang}] Runner-Drain: alle Kettentasks done (incl. payload.language)")
    except Exception as ex:  # noqa: BLE001
        failures.append(f"[{lang}] Exception (Kandidat): {ex!r}")
        ok = False
    finally:
        ctx.close()
    if not ok:
        print(f"[{lang}] Hinweis: Kandidaten-Phase mit Teilfehlern (siehe failures)")
    return app_id


def employer_phase(browser, lang: str, pre: int, mod, app_id: int, job: tuple,
                   failures: list) -> bool:
    """Schritte 5-10: HR-Login, angesehen, einladen, Artefakte, Kandidaten-Karte.

    EIGENE Playwright-Session: der Aufrufer uebergibt einen frisch gestarteten
    Browser. Grund (Diagnose 07.10.2026): nach der Kandidaten-Phase (v.a. dem
    Datei-Upload) verhungerte der Playwright-Node-Driver in dieser WSL-Umgebung
    bei der ersten Employer-Navigation (EPIPE bzw. blockierender `count()`),
    obwohl dieselbe Sequenz OHNE Kandidaten-Phase stabil lief. Ein frischer
    Driver pro Phase behebt das (Nachweis: ergebnisse/entscheidungen.md)."""
    po = load_po(lang)
    titel, cand_name = job
    ok = True
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(20000)
    try:
        login_employer(page, load_po("de"))
        switch_lang(page, lang)
        if assert_lang(page, lang, failures):
            print(f"[{lang}] HR-Session in Sprache L (documentElement.lang)")
        else:
            ok = False
        safe_goto(page, f"{BASE}/employer/match?kandidat={CAND_ID}")
        page.wait_for_timeout(2500)

        # 6) „Als angesehen markieren" (Match-Seite, einziger Ort dieses Labels)
        # Selektor ueber den AKTIONS-Button (Diagnose 07.10.2026: Name+Titel allein
        # fasste im1. Lauf 2..5 Karten — massgeblich ist die Karte mit der Aktion).
        karten = (page.locator(".q-card")
                  .filter(has=page.get_by_role("button",
                                               name=t(po, "Als angesehen markieren")))
                  .filter(has_text=titel))
        n_k = karten.count()
        if n_k != 1:
            debug = []
            for i in range(page.locator(".q-card").count()):
                c_i = page.locator(".q-card").nth(i)
                txt = c_i.inner_text()[:100].replace("\n", " | ")
                if titel in txt or cand_name in txt:
                    debug.append((txt, c_i.get_by_role("button").all_inner_texts()[:4]))
            failures.append(f"[{lang}] Match-Seite: {n_k} Karten mit "
                            f"'Als angesehen markieren'+Titel — erwartet 1; "
                            f"Kandidaten-Karten-Debug={debug!r}")
            ok = False
        else:
            btn_seen = karten.first.get_by_role("button",
                                                name=t(po, "Als angesehen markieren"))
            n_b = btn_seen.count()
            if n_b != 1:
                failures.append(f"[{lang}] 'Als angesehen markieren' {n_b}x in der Karte — "
                                "erwartet 1 (kein Klick)")
                ok = False
            else:
                btn_seen.first.click()
                exp_seen = t(po, "Bewerbung als angesehen markiert.")
                if wait_toast(page, exp_seen):
                    print(f"[{lang}] Toast angesehen: {exp_seen!r}")
                else:
                    failures.append(f"[{lang}] Toast angesehen fehlt: {exp_seen!r}")
                    ok = False
                if wait_for(lambda: app_state(app_id) == "angesehen", timeout=10):
                    print(f"[{lang}] DB-Status nach Klick: angesehen")
                else:
                    failures.append(f"[{lang}] DB-Status ist {app_state(app_id)!r} "
                                    "statt 'angesehen'")
                    ok = False

        # 7) Einladen ueber den MATCH-Seiten-Dialog statt Navigation zu
        # /employer/stellen. Grund (Diagnose 07.10.2026, WSL): die Navigation
        # unmittelbar nach dem „angesehen"-Klick liess den Playwright-Client
        # wiederholt verhungern (Node-Driver-EPIPE bzw. blockierender count()),
        # obwohl dieselbe Seite in isolierten Laeufen stabil war; ein frischer
        # Driver half nicht. Der Dialog nutzt DENSELBEN Handler wie die Stellen-
        # Seite: queue_agent_task("create_invitation", ... trigger="hr_klick_portal").
        # Die Stellen-Seite selbst bleibt durch tests/e2e_invitation_termin.py
        # (DE, gruen) abgedeckt (Nachweis: ergebnisse/entscheidungen.md).
        print(f"[{lang}] Schritt 7: Einladen (Match-Dialog)", flush=True)
        ziel_karte = (page.locator(".q-card").filter(has_text=titel)
                      .filter(has=page.get_by_role("button", name=t(po, "Einladen"))))
        wait_for(lambda: ziel_karte.count() >= 1, timeout=20000)
        n_z = ziel_karte.count()
        if n_z < 1:
            page.set_default_timeout(5000)
            try:
                debug = [x[:90].replace("\n", " | ")
                         for x in page.locator(".q-card").all_inner_texts(timeout=5000)]
            except Exception:  # noqa: BLE001
                debug = ["<Debug-Zeitueberschreitung>"]
            finally:
                page.set_default_timeout(20000)
            failures.append(f"[{lang}] Match-Karte mit 'Einladen'-Button nicht gefunden; "
                            "Karten=" + repr(debug))
            ok = False
            payload: dict = {}
            datum = zeit = ""
            dauer = 30
        else:
            ziel_karte.first.get_by_role("button", name=t(po, "Einladen")).click()
            dlg = page.locator(".q-dialog").filter(
                has_text=t(po, "Kandidat einladen")).first
            dlg.wait_for(state="visible", timeout=15000)
            if t(po, "Kandidat einladen") in dlg.inner_text():
                print(f"[{lang}] Einladen-Dialog in Zielsprache ok")
            else:
                failures.append(f"[{lang}] Dialog-Titel {t(po, 'Kandidat einladen')!r} fehlt")
                ok = False
            # Termin-Defaults aus dem Dialog lesen (Quelle der Wahrheit = Formular)
            werte = dlg.locator("input").evaluate_all("els => els.map(e => e.value || '')")
            datum = next((v for v in werte if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v)), "")
            zeit = next((v for v in werte if re.search(r"\d{1,2}:\d{2}", v)), "")
            if not datum:
                datum = (date.today() + timedelta(days=1)).isoformat()
                print(f"[{lang}] HINWEIS: Datum-Feld nicht lesbar, Fallback {datum}")
            if not zeit:
                zeit = "10:00"
                print(f"[{lang}] HINWEIS: Zeit-Feld nicht lesbar, Fallback 10:00")
            dlg.get_by_role("button", name=t(po, "Einladen")).click()
            if wait_for(lambda: app_state(app_id) == "eingeladen", timeout=15):
                print(f"[{lang}] DB-Status nach Dialog: eingeladen")
            else:
                failures.append(f"[{lang}] DB-Status ist {app_state(app_id)!r} "
                                "statt 'eingeladen'")
                ok = False
            # RACE-Fix 07.10.2026: den create_invitation-Task schreibt der Klick-Handler
            # erst NACH dem Status-UPDATE (eigene DB-Verbindung) — ohne dieses Polling
            # las de den Task zu frueh ("fehlt"), er lief dann in die naechste Sprache
            # und scheiterte dort an der bereits geloeschten Bewerbung.
            wait_for(lambda: _q1("SELECT COUNT(*) FROM agent_tasks "
                                 "WHERE task_type='create_invitation' "
                                 "AND json_extract(payload,'$.application_id')=?",
                                 (app_id,))[0] >= 1, timeout=10)
            prow = _q1("SELECT payload FROM agent_tasks WHERE task_type='create_invitation' "
                       "AND json_extract(payload,'$.application_id')=? "
                       "ORDER BY id DESC LIMIT 1", (app_id,))
            if not prow:
                failures.append(f"[{lang}] create_invitation-Task fehlt (app {app_id})")
                payload = {}
                dauer = 30
            else:
                payload = json.loads(prow[0])
                dauer = int(payload.get("termin_dauer_min") or 30)
                # Payload-Werte sind ab hier die Referenz (ui.time liefert HH:MM:SS)
                datum = str(payload.get("termin_datum") or datum)
                zeit = str(payload.get("termin_uhrzeit") or zeit)
                n0 = len(failures)
                if payload.get("trigger") != "hr_klick_portal":
                    failures.append(f"[{lang}] trigger={payload.get('trigger')!r}")
                    ok = False
                if payload.get("language") != lang:
                    failures.append(f"[{lang}] payload.language={payload.get('language')!r} "
                                    f"(erwartet {lang!r})")
                    ok = False
                if dauer != 30:
                    failures.append(f"[{lang}] termin_dauer_min={dauer!r} != 30")
                    ok = False
                if not re.search(r"\d{1,2}:\d{2}", str(payload.get("termin_uhrzeit") or "")):
                    failures.append(f"[{lang}] termin_uhrzeit fehlt/ungueltig: "
                                    f"{payload.get('termin_uhrzeit')!r}")
                    ok = False
                if len(failures) == n0:
                    print(f"[{lang}] create_invitation-Payload ok "
                          f"({datum} {zeit} {dauer} Min., trigger/language)")

        # 8) Einladung drainen + Artefakt-Assertions (Spec §7 Variante B)
        drain_runner(mod, pre, failures, lang)
        rrow = _q1("SELECT status, result_json FROM agent_tasks "
                   "WHERE task_type='create_invitation' "
                   "AND json_extract(payload,'$.application_id')=? ORDER BY id DESC LIMIT 1",
                   (app_id,))
        if not rrow or rrow[0] != "done":
            failures.append(f"[{lang}] create_invitation nicht done: {rrow!r}")
            ok = False
        else:
            res = json.loads(rrow[1] or "{}")
            n0 = len(failures)
            soll_termin = t(po, "{0} Uhr ({1} Min.)").format(f"{datum} {zeit}", dauer)
            if res.get("termin") != soll_termin:
                failures.append(f"[{lang}] result.termin={res.get('termin')!r} != {soll_termin!r}")
                ok = False
            if res.get("recording") is not False:
                failures.append(f"[{lang}] result.recording={res.get('recording')!r} != False "
                                "(Gate 10)")
                ok = False
            if "record=off" not in (res.get("vdo_ninja_gast_url") or ""):
                failures.append(f"[{lang}] Gast-Link ohne record=off: "
                                f"{res.get('vdo_ninja_gast_url')!r}")
                ok = False
            if "record" in (res.get("vdo_ninja_url") or ""):
                failures.append(f"[{lang}] Director-Link traegt record-Parameter: "
                                f"{res.get('vdo_ninja_url')!r}")
                ok = False
            ics_pfad = Path(str(res.get("ics_path") or ""))
            if ics_pfad.name and ics_pfad.exists():
                failures.append(f"[{lang}] ICS-Datei geschrieben, obwohl DRY_RUN: {ics_pfad}")
                ok = False
            if res.get("mail") != "DRY-RUN":
                failures.append(f"[{lang}] result.mail={res.get('mail')!r} != 'DRY-RUN'")
                ok = False
            n_inv = _q1("SELECT COUNT(*) FROM agent_tasks WHERE task_type='create_invitation' "
                        "AND json_extract(payload,'$.application_id')=?", (app_id,))[0]
            if n_inv != 1:
                failures.append(f"[{lang}] create_invitation {n_inv}x (erwartet 1)")
                ok = False
            if len(failures) == n0:
                print(f"[{lang}] Einladungs-Artefakte ok (termin, record=off, kein ICS, "
                      "mail=DRY-RUN)")

        # 9) Einladungs-Mail-Betreff (MCP in-process, P2b)
        check_einladungsbetreff(lang, po, titel, failures)

        # 10) Kandidaten-Einladungskarte (FRISCHER Kontext — im ersten ist die
        #     Rolle `employer` und /candidate/* wuerde auf /login umleiten)
        if not check_kandidaten_karte(browser, lang, po, app_id, datum, zeit, dauer,
                                      failures):
            ok = False
    except Exception as ex:  # noqa: BLE001
        failures.append(f"[{lang}] Exception (Arbeitgeber): {ex!r}")
        ok = False
    finally:
        ctx.close()
    return ok


def check_kandidaten_karte(browser, lang: str, po: dict, app_id: int, datum: str,
                           zeit: str, dauer: int, failures: list) -> bool:
    """Einladungskarte in /candidate/bewerbungen, Session-Sprache L (Schritt 10)."""
    ok = True
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(20000)
    try:
        login_de(page)
        switch_lang(page, lang)
        if not assert_lang(page, lang, failures):
            ok = False
        safe_goto(page, f"{BASE}/candidate/bewerbungen")
        page.wait_for_timeout(2500)
        cards = page.locator(".q-card").filter(has_text=re.compile(rf"#{app_id}\b"))
        n = cards.count()
        if n != 1:
            failures.append(f"[{lang}] Kandidaten-Karte #{app_id} nicht eindeutig ({n})")
            return False
        card = cards.first
        body = card.inner_text()
        kopf = t(po, "📅 Einladung")
        if body.count(kopf) != 1:
            failures.append(f"[{lang}] Einladungskarte: Kopf {kopf!r} {body.count(kopf)}x "
                            "(erwartet 1)")
            ok = False
        soll_termin = t(po, "Termin: {0}").format(
            t(po, "{0} Uhr ({1} Min.)").format(f"{datum} {zeit}", dauer))
        if soll_termin not in body:
            failures.append(f"[{lang}] Einladungskarte: Termin {soll_termin!r} fehlt")
            ok = False
        if t(po, "Meeting-Link") not in body:
            failures.append(f"[{lang}] Einladungskarte: Label Meeting-Link fehlt")
            ok = False
        werte = card.locator("input").evaluate_all("els => els.map(e => e.value || '')")
        vdo = [v for v in werte if "vdo.ninja" in v]
        if not vdo:
            failures.append(f"[{lang}] Einladungskarte: kein Meeting-Link-Input "
                            f"mit vdo.ninja ({werte!r})")
            ok = False
        elif "record=off" not in vdo[0]:
            failures.append(f"[{lang}] Einladungskarte: record=off fehlt: {vdo[0]!r}")
            ok = False
        hrefs = card.locator("a").evaluate_all("els => els.map(e => e.href || '')")
        if any("vdo.ninja" in h for h in hrefs):
            failures.append(f"[{lang}] Einladungskarte: vdo.ninja als <a> statt Input")
            ok = False
        ics = card.get_by_text(t(po, "📅 Termin in Kalender speichern (.ics)"))
        if ics.count():
            failures.append(f"[{lang}] ICS-Button vorhanden, obwohl DRY_RUN keine Datei "
                            "schreibt")
            ok = False
        if ok:
            print(f"[{lang}] Kandidaten-Einladungskarte ok (Kopf, Termin, Meeting-Link, "
                  "record=off, kein ICS-Button)")
    except Exception as ex:  # noqa: BLE001
        failures.append(f"[{lang}] Kandidaten-Karte Exception: {ex!r}")
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
    for p in TESTDATEN.glob("e2e-i18n-full-*"):
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
    job = validate_target()
    print(f"Baseline: cand={base['cand']} app_max={base['app_max']} "
          f"notif_max={base['notif_max']} pre={pre}")
    if job is None:
        print("FAIL: Datensatz/Spiegel-DB ungueltig (Stelle #7 aktiv+frei fuer #13, "
              "alle Alt-Bewerbungen final, cand13-Mails stimmen)")
        return 1
    print(f"Datensatz: Kandidat #{CAND_ID} / Stelle #{JOB_ID} {job[0]!r} / "
          f"Name {job[1]!r} / Employer #{EMPLOYER_ID}")

    failures: list[str] = []
    mod = load_runner()
    log_offset = mod.LOG_FILE.stat().st_size if mod.LOG_FILE.exists() else 0
    # process_task schreibt den Einladungs-Bericht AUCH im DRY_RUN (unbedingt) —
    # diese Dateien waeren sonst Test-Reste in ergebnisse/ (App-Ids nie wiederverwendet).
    rep_before = {p.name for p in ERGEBNISSE.glob("einladung-bewerbung-*.md")}

    try:
        # Je Sprache ZWEI getrennte Playwright-Sessions (Diagnose 07.10.2026):
        # der Kandidaten-Datei-Upload vergiftete den Node-Driver, sodass die erste
        # Employer-Navigation verhungerte. Frischer Driver pro Phase = stabil.
        _ARGS = ["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu",
                 "--disable-software-rasterizer"]
        for lang in LANGS:
            # A) Kandidaten-Phase
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=_ARGS)
                try:
                    app_id = candidate_phase(browser, lang, pre, mod, base, job, failures)
                finally:
                    browser.close()
            ok = True
            if app_id is None:
                failures.append(f"[{lang}] Arbeitgeber-Phase uebersprungen "
                                "(keine Bewerbung angelegt)")
                ok = False
            else:
                # B) Arbeitgeber-Phase (FRISCHE Session = frischer Node-Driver)
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True, args=_ARGS)
                    try:
                        ok = employer_phase(browser, lang, pre, mod, app_id, job,
                                            failures)
                    finally:
                        browser.close()
            print(f"[{lang}] rc={'0' if ok else '1'}")

        log_text = read_log(mod.LOG_FILE, log_offset)
        check_betreffe(failures, log_text)
    finally:
        restore(base, pre)
        # Auch bei Abbruch: frisch geschriebene Einladungs-Berichte entfernen.
        for p in ERGEBNISSE.glob("einladung-bewerbung-*.md"):
            if p.name not in rep_before:
                p.unlink(missing_ok=True)

    rep_rest = sorted(p.name for p in ERGEBNISSE.glob("einladung-bewerbung-*.md")
                      if p.name not in rep_before)
    if rep_rest:
        failures.append(f"Test-Reste: Einladungs-Berichte in ergebnisse/: {rep_rest}")

    after = cand_state()
    if after != base["cand"]:
        failures.append(f"Restore verletzt: candidates {base['cand']} -> {after}")
    if _q1("SELECT COUNT(*) FROM applications")[0] != base["app_n"]:
        failures.append("Restore verletzt: applications-Anzahl")
    if _q1("SELECT COUNT(*) FROM notifications")[0] != base["notif_n"]:
        failures.append("Restore verletzt: notifications-Anzahl")
    apps13 = _q("SELECT id, job_id, status FROM applications WHERE candidate_id=? ORDER BY id",
                (CAND_ID,))
    if apps13 != base["apps13"]:
        failures.append(f"Restore verletzt: Bewerbungen #{CAND_ID} {base['apps13']} -> {apps13}")
    files_now = {p.name for p in TESTDATEN.glob(f"kandidat-{CAND_ID}-*")}
    if files_now != base["files"]:
        failures.append(f"Restore verletzt: testdaten {base['files']} -> {files_now}")
    if list(TESTDATEN.glob("e2e-i18n-full-*")):
        failures.append("Restore verletzt: e2e-i18n-full-* Quelldateien verbleiben")
    residue = db_residue_report(pre)
    if residue:
        failures.append(f"Test-Reste: {residue} agent_tasks verbleiben")

    if failures:
        print("E2E I18N FULL CHAIN FAIL:")
        for f in failures:
            print("  -", f)
        return 1
    print("E2E I18N FULL CHAIN PASS (DE/EN/FR/AR: CV -> Bewerbung -> Kette -> "
          "HR-Session -> angesehen -> eingeladen mit Termin -> Einladungs-Artefakte -> "
          "Kandidaten-Karte; Restore + Residue 0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
