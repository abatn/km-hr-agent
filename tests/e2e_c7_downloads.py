"""P3 E2E: C7 Downloads #8–12 + Skill-8 Cat-Map + Onboarding-Freigabe.

Paritaet:
#8  app.py:2250  st.download_button Selbstpräsentationen (Skill 6 Einsicht)
NiceGUI-Ist (seit 30.09.2026): "Ansehen" oeffnet Dialog (_show_file,
webui/components.py) — KEIN Download-Angebot. Test prueft daher
Dialog-Öffnung + richtige Datei + Vorschau (Design-Entscheidung,
Download-Event #8 entfaellt; MD: skills/nicegui-migration/SKILL.md C7).
#9  app.py:2361  st.download_button Pre-Screen Generator (Skill 6)
#10 app.py:2391  st.download_button Candidate Onboarding (Skill 7 Freigabe)
#11 app.py:2515  st.download_button Onboarding-Generator (Skill 7)
#12 app.py:2686  st.download_button Skill-8 Feedback (Admin)

D28: kein Status-Gate. D29: testdaten-Profile, match_id={stem}-{date}.
R5-4/S3g (30.09.2026): Generatoren haben keine hartcodierte Stelle mehr —
der Test setzt "Stelle:" explizit (profil-anna-schuster hat keinen
DB-Kandidaten, daher keine Vorbelegung; vorher maskiert durch den #8-Abbruch).
Cat-Map Skill-8: Weak -> 'Schwach' (i18n P9.3, 06.10.2026: vereinheitlicht mit
der Employer-/app.py-Paritaet; vorher 'Nicht passend').

Ablauf:
  Pre: snapshot (app8, hist/gew max, heutige feedback+export, neue Dateien abwesend)
  A   Admin /admin/prescreen  → #8 Ansehen-Dialog (statt Download) + #9 Generator
  B   Admin /admin/onboarding → #11 Generator (Default +30d = 2026-10-22)
  C   Admin /admin/feedback   → #12 Skill-8 Save (score 30, Eingeladen=Ja)
                                kategorie='Schwach', kein Weight-Adjust,
                                export_report-Task
  D   Employer smoke (3 Seiten rendern + Section-Headings)
  E   Candidate: leerer Onboarding-Tab → Flip app8 eingestellt + Fixture
      → /candidate/onboarding Expansion → #10 Freigabe-Download
  Restore (finally): DB (feedback/gew/tasks/app8) + Path.unlink() aller neuen Dateien

Ausfuehren: .venv-streamlit/bin/python3 tests/e2e_c7_downloads.py
Hinweis: agent-runner waehrend Test gestoppt (kein export_report / Status-Mail).
"""
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from e2e_harness import check_server, db_residue_report, pre_max_tasks, seed_email

from e2e_harness import BASE  # Env KMHR_E2E_BASE (E2E-Isolation 27.09.2026)
ROOT = Path(__file__).resolve().parents[1]
from e2e_harness import DB  # Env KMHR_DB_PATH (E2E-Isolation 27.09.2026)
ERG = ROOT / "ergebnisse"
TODAY = date.today().isoformat()
ONB_SD = (date.today() + timedelta(days=30)).isoformat()  # Default date_input +30d

CAND_EMAIL = seed_email("batniniabdelkader@yahoo.com")
CAND_PW = "Abdel15121978!"
EMP_EMAIL = seed_email("hr@techvision.de")
EMP_PW = "sicher123"
ADMIN_EMAIL = seed_email("admin@km-hr-agent.local")
ADMIN_PW = "admin-agent-2026"

PROFILE = "profil-anna-schuster.md"
NEW_FILES = [
    ERG / f"pre-screen-anna-schuster-{TODAY}.md",
    ERG / f"onboarding-anna-schuster-{ONB_SD}.md",
    ERG / f"feedback-anna-schuster-{TODAY}.md",
]
FIXTURE = ERG / "onboarding-freigabe-bewerbung-8.md"


def read_state() -> dict:
    conn = sqlite3.connect(DB)
    app8 = conn.execute(
        "SELECT status, aktualisiert_am FROM applications WHERE id=8"
    ).fetchone()
    hist_max = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM application_status_history"
    ).fetchone()[0]
    gew_max = conn.execute(
        "SELECT COALESCE(MAX(id), 0) FROM gewichtung_historie"
    ).fetchone()[0]
    fb_today = conn.execute(
        "SELECT id, match_id, kategorie FROM feedback WHERE match_id LIKE ?",
        (f"%-{TODAY}",),
    ).fetchall()
    tasks = conn.execute(
        "SELECT id, payload FROM agent_tasks WHERE task_type='export_report' "
        "AND payload LIKE ?",
        (f"%{TODAY}%",),
    ).fetchall()
    # E-Normalisierung: alle Bewerbungen von Kandidat 1 (CAND_EMAIL) — der
    # Leer-Zustand des Onboarding-Tabs verlangt, dass KEINE 'eingestellt' ist.
    cand1_apps = conn.execute(
        "SELECT id, status, aktualisiert_am FROM applications "
        "WHERE candidate_id=1 ORDER BY id"
    ).fetchall()
    conn.close()
    return {
        "app8": app8,
        "hist_max": hist_max,
        "gew_max": gew_max,
        "fb_today": fb_today,
        "tasks": tasks,
        "cand1_apps": cand1_apps,
    }


def restore(pre: dict, failures: list) -> None:
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM feedback WHERE match_id LIKE ?", (f"%-{TODAY}",))
    conn.execute(
        "DELETE FROM agent_tasks WHERE task_type='export_report' AND payload LIKE ?",
        (f"%{TODAY}%",),
    )
    conn.execute(
        "DELETE FROM gewichtung_historie WHERE id > ?", (pre["gew_max"],)
    )
    conn.execute(
        "UPDATE applications SET status=?, aktualisiert_am=? WHERE id=8",
        (pre["app8"][0], pre["app8"][1]),
    )
    # E-Normalisierung rueckgaengig: ALLE Bewerbungen von Kandidat 1 auf den
    # Pre-Zustand (app8 ist darin enthalten, Update oben bleibt redundant).
    for _aid, _st, _am in pre["cand1_apps"]:
        conn.execute(
            "UPDATE applications SET status=?, aktualisiert_am=? WHERE id=?",
            (_st, _am, _aid),
        )
    conn.commit()
    conn.close()

    for path in [*NEW_FILES, FIXTURE]:
        try:
            if path.exists():
                path.unlink()
        except OSError as e:
            failures.append(f"Restore unlink {path.name}: {e}")

    final = read_state()
    print("Final:", final)
    if final["app8"] != pre["app8"]:
        failures.append(f"Restore app8: {final['app8']} != {pre['app8']}")
    if final["cand1_apps"] != pre["cand1_apps"]:
        failures.append(
            f"Restore cand1_apps: {final['cand1_apps']} != {pre['cand1_apps']}"
        )
    if final["hist_max"] != pre["hist_max"]:
        failures.append(
            f"Restore hist_max: {final['hist_max']} != {pre['hist_max']}"
        )
    if final["gew_max"] != pre["gew_max"]:
        failures.append(
            f"Restore gew_max: {final['gew_max']} != {pre['gew_max']}"
        )
    if final["fb_today"] != pre["fb_today"]:
        failures.append(
            f"Restore feedback: {final['fb_today']} != {pre['fb_today']}"
        )
    if final["tasks"] != pre["tasks"]:
        failures.append(
            f"Restore export_report: {len(final['tasks'])} != {len(pre['tasks'])}"
        )
    for path in [*NEW_FILES, FIXTURE]:
        if path.exists():
            failures.append(f"Restore file noch vorhanden: {path.name}")


def _visible_panel(page):
    return page.locator(".q-tab-panel:visible").first


def login_admin(page):
    page.goto(f"{BASE}/login", wait_until="load", timeout=20000)
    page.get_by_role("tab", name="Admin", exact=True).click()
    page.wait_for_timeout(600)
    panel = page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile("Admin-Login", re.I))
    ).first
    panel.get_by_label("Admin-E-Mail").fill(ADMIN_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(ADMIN_PW)
    panel.get_by_role("button", name=re.compile("Admin-Login", re.I)).click()
    page.wait_for_url("**/admin**", timeout=15000)


def login_employer(page):
    page.goto(f"{BASE}/login", wait_until="load", timeout=20000)
    page.wait_for_timeout(1500)
    page.get_by_role("tab", name="Arbeitgeber", exact=True).click()
    page.wait_for_timeout(700)
    panel = page.locator(".q-tab-panel:visible").filter(
        has=page.get_by_role("button", name=re.compile("Arbeitgeber-Login", re.I))
    ).first
    panel.get_by_label("E-Mail").fill(EMP_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(EMP_PW)
    panel.get_by_role(
        "button", name=re.compile("Arbeitgeber-Login", re.I)
    ).click()
    page.wait_for_url("**/employer**", timeout=15000)


def login_candidate(page):
    page.goto(f"{BASE}/login", wait_until="load", timeout=20000)
    page.wait_for_timeout(1500)
    panel = _visible_panel(page)
    panel.get_by_label("E-Mail").fill(CAND_EMAIL)
    panel.get_by_label("Passwort", exact=True).fill(CAND_PW)
    panel.get_by_role("button").first.click()
    page.wait_for_url("**/candidate**", timeout=15000)


def select_profile(page, label: str = "Kandidat:") -> None:
    """Waehlt PROFILE im Generator-/Skill-8-Select (Index statt Dateiname).

    NiceGUI zeigt das Options-Label = Klartext-Name (profile_display_name,
    P0 28.09.2026) — NICHT den Dateinamen; zudem tragen zwei Profile den
    Klartext 'Anna Schuster' (Doppel-Datei profil---**name:**-...). Auswahl
    daher ueber den Index in der sortierten profil-*.md-Liste = Reihenfolge
    von logic.list_profiles() (ui.select-Dict-Key = Pfad, Label = Klartext).
    """
    profiles = sorted((ROOT / "testdaten").glob("profil-*.md"))
    idx = next((i for i, p in enumerate(profiles) if p.name == PROFILE), -1)
    if idx < 0:
        raise RuntimeError(f"Profil {PROFILE} fehlt unter testdaten/")
    page.get_by_label(label, exact=True).click()
    page.wait_for_timeout(300)
    page.get_by_role("option").nth(idx).click()
    page.wait_for_timeout(300)


def main() -> int:
    check_server()
    pre_tasks = pre_max_tasks()
    pre = read_state()
    print("Pre:", pre)
    failures: list[str] = []

    # Vorbedingung: Zieldateien duerfen nicht schon existieren
    for path in NEW_FILES:
        if path.exists():
            failures.append(f"Vorbedingung: {path.name} existiert bereits")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            # ── A: Admin Pre-Screen #8 Einsicht + #9 Generator ──
            ctx = browser.new_context(accept_downloads=True)
            page = ctx.new_page()
            login_admin(page)

            page.goto(f"{BASE}/admin/prescreen", wait_until="load", timeout=30000)
            page.wait_for_timeout(1500)
            print("A URL:", page.url)

            if page.get_by_text("Selbstpräsentationen der Kandidaten", exact=False).count() < 1:
                failures.append("A: Einsicht-Heading fehlt")
            ansehen = page.get_by_role("button", name="Ansehen")
            if ansehen.count() < 1:
                failures.append("A: 'Ansehen'-Button fehlt (#8)")
            else:
                # S2/S3 06.10.2026: "Ansehen" oeffnet seit 30.09.2026 einen
                # Dialog (_show_file) statt herunterzuladen; Dialog hat KEIN
                # Download-Angebot, App nicht defekt (richtiger Dateiname +
                # MD-Vorschau) -> Assertion auf Dialog-Öffnung/Datei/Vorschau.
                row = ansehen.first.locator("xpath=..")
                # Zeile = [Dateiname-Label, Ansehen-Button]; inner_text des
                # Buttons enthaelt Icon-Ligatur ('visibility') + CSS-uppercase.
                want = row.locator("div").first.inner_text().strip()
                ansehen.first.click()
                dlg = page.locator(".q-dialog:visible")
                opened = False
                dlg_text = ""
                try:
                    dlg.wait_for(state="visible", timeout=8000)
                    opened = True
                    dlg_text = dlg.inner_text()
                except Exception as e:  # noqa: BLE001
                    failures.append(f"A #8: Dialog oeffnet nicht: {e}")
                if opened:
                    print(f"A #8 Dialog statt Download: {want}")
                    if (
                        not want.startswith("self-presentation-kandidat-")
                        or not want.endswith(".md")
                    ):
                        failures.append(f"A #8: Zeilen-Dateiname={want!r}")
                    if want not in dlg_text:
                        failures.append(
                            f"A #8: Dialog zeigt nicht {want!r} "
                            f"(Ausschnitt: {dlg_text[:80]!r})"
                        )
                    if len(dlg_text.strip()) <= len(want):
                        failures.append("A #8: Dialog ohne Vorschau-Inhalt")
                    try:
                        dlg.get_by_role(
                            "button", name="Schließen"
                        ).click(timeout=5000)
                        dlg.wait_for(state="hidden", timeout=8000)
                    except Exception as e:  # noqa: BLE001
                        failures.append(f"A #8: Dialog nicht schliessbar: {e}")

            select_profile(page)
            # R5-4/S3g (30.09.2026): Generator hat KEINE hartcodierte Stelle
            # mehr — das Feld wird aus der Bewerbung des Profils vorbelegt.
            # Fuer profil-anna-schuster gibt es keinen DB-Kandidaten -> leer
            # (gemessen mit logic.aktuelle_stelle_fuer_profil) -> Pflichtfeld
            # muss der Test setzen, sonst greift die Pflichtpruefung.
            page.get_by_label("Stelle:", exact=True).fill("Senior Cloud/DevOps Engineer")
            if page.get_by_text("Pre-Screen erstellen", exact=False).count() < 1:
                failures.append("A: Generator-Button fehlt (#9)")
            page.get_by_role(
                "button", name=re.compile("Pre-Screen erstellen")
            ).click()
            page.wait_for_selector("text=Pre-Screen gespeichert", timeout=10000)
            with page.expect_download(timeout=8000) as dl_info:
                page.get_by_role(
                    "button", name=re.compile("Herunterladen")
                ).first.click()
            name9 = dl_info.value.suggested_filename
            print(f"A #9 download: {name9}")
            if name9 != f"pre-screen-anna-schuster-{TODAY}.md":
                failures.append(f"A #9: suggested={name9!r} erwartet pre-screen-anna-schuster-{TODAY}.md")
            if not NEW_FILES[0].exists():
                failures.append("A #9: Datei pre-screen-anna-schuster-* nicht geschrieben")
            ctx.close()

            # ── B: Admin Onboarding #11 Generator ──
            ctx = browser.new_context(accept_downloads=True)
            page = ctx.new_page()
            login_admin(page)
            page.goto(f"{BASE}/admin/onboarding", wait_until="load", timeout=30000)
            page.wait_for_timeout(1500)
            print("B URL:", page.url)

            if page.get_by_text("Onboarding-Checkliste generieren", exact=False).count() < 1:
                failures.append("B: Generator-Heading fehlt (#11)")
            select_profile(page)
            # R5-4/S3g: Pflichtfeld "Stelle" (wie A) — anna-schuster ohne DB-Bezug.
            page.get_by_label("Stelle:", exact=True).fill("Senior Cloud/DevOps Engineer")
            page.get_by_role(
                "button", name=re.compile("Onboarding generieren")
            ).click()
            page.wait_for_selector(
                "text=Onboarding-Checkliste gespeichert", timeout=10000
            )
            with page.expect_download(timeout=8000) as dl_info:
                page.get_by_role(
                    "button", name=re.compile("Herunterladen")
                ).first.click()
            name11 = dl_info.value.suggested_filename
            print(f"B #11 download: {name11} (Startdatum-Default {ONB_SD})")
            if name11 != f"onboarding-anna-schuster-{ONB_SD}.md":
                failures.append(
                    f"B #11: suggested={name11!r} erwartet onboarding-anna-schuster-{ONB_SD}.md"
                )
            if not NEW_FILES[1].exists():
                failures.append("B #11: Datei onboarding-anna-schuster-* nicht geschrieben")
            ctx.close()

            # ── C: Admin Skill-8 #12 Save + Download + Cat-Map ──
            ctx = browser.new_context(accept_downloads=True)
            page = ctx.new_page()
            login_admin(page)
            page.goto(f"{BASE}/admin/feedback", wait_until="load", timeout=30000)
            page.wait_for_timeout(1500)
            print("C URL:", page.url)

            if page.get_by_text("Skill 8: Feedback speichern", exact=False).count() < 1:
                failures.append("C: Skill-8-Heading fehlt (#12)")
            select_profile(page)
            page.get_by_label("Match-Score (0-100)").fill("30")
            # Eingeladen default Ja → kein Weight-Adjust (Ja + 30 < 80)
            page.get_by_role(
                "button", name=re.compile("Feedback speichern")
            ).click()
            page.wait_for_selector("text=Feedback gespeichert", timeout=10000)
            with page.expect_download(timeout=8000) as dl_info:
                page.get_by_role(
                    "button", name=re.compile("Herunterladen")
                ).first.click()
            name12 = dl_info.value.suggested_filename
            print(f"C #12 download: {name12}")
            if name12 != f"feedback-anna-schuster-{TODAY}.md":
                failures.append(
                    f"C #12: suggested={name12!r} erwartet feedback-anna-schuster-{TODAY}.md"
                )
            if not NEW_FILES[2].exists():
                failures.append("C #12: Datei feedback-anna-schuster-* nicht geschrieben")

            post = read_state()
            print("C fb_today:", post["fb_today"], "gew_max:", post["gew_max"])
            new_rows = [
                r for r in post["fb_today"]
                if r[0] not in {x[0] for x in pre["fb_today"]}
            ]
            if not new_rows:
                failures.append("C: keine neue feedback-Row")
            else:
                for _id, match_id, kategorie in new_rows:
                    if kategorie != "Schwach":
                        failures.append(
                            f"C: kategorie={kategorie!r} != 'Schwach' "
                            f"(match {match_id}) — Skill-8 Cat-Map (P9.3)"
                        )
                    else:
                        print(f"OK C: {match_id} -> kategorie='Schwach'")
            if post["gew_max"] != pre["gew_max"]:
                failures.append(
                    f"C: gewichtung wuchs ({pre['gew_max']}→{post['gew_max']}) "
                    "trotz Eingeladen=Ja + Score 30"
                )
            new_tasks = [
                t for t in post["tasks"]
                if t[0] not in {x[0] for x in pre["tasks"]}
            ]
            if not new_tasks:
                failures.append("C: kein export_report-Task nach INSERT")
            else:
                print(f"OK C: export_report Task id={new_tasks[0][0]}")
            ctx.close()

            # ── D: Employer Smoke (view-only) ──
            ctx = browser.new_context()
            page = ctx.new_page()
            login_employer(page)
            smoke = [
                ("/employer/prescreen", "Pre-Screen erstellen"),
                ("/employer/onboarding", "Onboarding-Checkliste generieren"),
                ("/employer/feedback", "Skill 8: Feedback speichern"),
            ]
            for path, heading in smoke:
                page.goto(f"{BASE}{path}", wait_until="load", timeout=30000)
                page.wait_for_timeout(1200)
                print("D URL:", page.url)
                if page.get_by_text(heading, exact=False).count() < 1:
                    failures.append(f"D: '{heading}' fehlt auf {path}")
            ctx.close()

            # ── E: Candidate Onboarding #10 (Write + Flip + Restore) ──
            # Normalisierung 06.10.2026: Kandidat 1 traegt in der Live-/Spiegel-DB
            # MEHRERE 'eingestellt'-Bewerbungen (8, 27, 31; verifiziert 06.10.2026),
            # nicht nur app8. Der Leer-Zustand ("Noch kein Onboarding aktiv") zeigt
            # nur, wenn KEINE Bewerbung 'eingestellt' ist (`_tab_onboarding`, Query
            # a.status='eingestellt'). Daher ALLE 'eingestellt'-Bewerbungen von
            # Kandidat 1 vor dem Leer-Check auf 'eingeladen' setzen — Restore stellt
            # den Pre-Zustand aller wieder her (kein Live-Eingriff; Live-Diff=0).
            conn = sqlite3.connect(DB)
            conn.execute(
                "UPDATE applications SET status='eingeladen', "
                "aktualisiert_am=? WHERE candidate_id=1 AND status='eingestellt'",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),),
            )
            conn.commit()
            conn.close()
            ctx = browser.new_context(accept_downloads=True)
            page = ctx.new_page()
            login_candidate(page)
            page.goto(
                f"{BASE}/candidate/onboarding", wait_until="load", timeout=30000
            )
            page.wait_for_timeout(1500)
            print("E URL (vorher):", page.url)
            body = page.locator("body").inner_text()
            if "Noch kein Onboarding aktiv" not in body:
                failures.append("E: empty_state vor Flip fehlt (app8 war eingeladen)")

            # Flip + Fixture (Restore in finally)
            conn = sqlite3.connect(DB)
            conn.execute(
                "UPDATE applications SET status='eingestellt', "
                "aktualisiert_am=? WHERE id=8",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),),
            )
            conn.commit()
            conn.close()
            FIXTURE.write_text(
                "# Onboarding-Freigabe (E2E Fixture)\n\nBewerbung 8 — Testartefakt.\n",
                encoding="utf-8",
            )

            page.reload(wait_until="load")
            page.wait_for_timeout(1500)
            body = page.locator("body").inner_text()
            if "Noch kein Onboarding aktiv" in body:
                failures.append("E: empty_state nach Flip noch sichtbar")
            exp = page.get_by_text(
                "Senior Cloud/DevOps Engineer – TechVision GmbH", exact=False
            )
            if exp.count() < 1:
                failures.append("E: Onboarding-Expansion fehlt nach Flip")
            else:
                exp.first.click()
                page.wait_for_timeout(700)
                with page.expect_download(timeout=8000) as dl_info:
                    page.get_by_role(
                        "button", name=re.compile("Herunterladen")
                    ).first.click()
                name10 = dl_info.value.suggested_filename
                print(f"E #10 download: {name10}")
                if not name10.startswith("onboarding-freigabe-bewerbung-8"):
                    failures.append(f"E #10: suggested={name10!r}")
            ctx.close()

        except Exception as e:  # noqa: BLE001
            failures.append(f"EXC: {type(e).__name__}: {e}")
        finally:
            browser.close()
            restore(pre, failures)

    residue = db_residue_report(pre_tasks)
    if residue:
        failures.append(f"F3 Test-Reste: {residue} agent_tasks verbleiben")
    if failures:
        print("FAIL:")
        for f in failures:
            print(" -", f)
        return 1
    print(
        "PASS: C7 — #8 Einsicht + #9 Pre-Screen + #10 Candidate-Onboarding-Freigabe "
        "+ #11 Onboarding-Generator + #12 Skill-8 (Cat-Map 'Schwach', "
        "kein Weight-Adjust, export_report) + Employer-Smoke + Restore"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
