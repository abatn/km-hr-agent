"""P4 Candidate UX Review — 8 Schritte, NiceGUI :8080.
Read-only: kein Upload, kein Zurückziehen.

KLASSE d (14.10.2026): S2/S3/S5/S7/S8 Findings werden jetzt in `fails` gewertet
(vorher nur Report-Liste). S4/S6 bleiben konditional (nicht testbar ohne
jeweilige Vorbedingung).
"""
import sys
from playwright.sync_api import sync_playwright
from e2e_harness import check_server, BASE, seed_email

EMAIL = seed_email("test@example.de")
PASSWORD = "test1234"
TIMEOUT = 10000


def main():
    check_server()
    F = []  # findings
    fails = []

    def snap(label):
        try:
            return page.inner_text("body")[:1500]
        except Exception:
            return "(no body)"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_viewport_size({"width": 1280, "height": 900})

        # ── STEP 1: Login ──
        print("=== S1 Login/Profil ===")
        page.goto(f"{BASE}/login", wait_until="load", timeout=TIMEOUT)
        page.wait_for_timeout(1500)
        page.get_by_label("E-Mail").fill(EMAIL)
        page.get_by_label("Passwort", exact=True).fill(PASSWORD)
        page.get_by_role("button", name="Einloggen").click()
        page.wait_for_timeout(2500)
        url = page.url
        print(f"URL={url}")
        ok_login = "/candidate" in url or "/employer" in url
        print(f"Login OK: {ok_login}" + (" ✓" if ok_login else " ✗"))
        if not ok_login:
            fails.append("S1: Login fehlgeschlagen")
        body = snap("S1")
        F.append({"step": "S1 Login", "klicks": "Einloggen", "was": url.split("/")[-1] or "login", "druck": "OK" if ok_login else "FEHLER"})

        # ── STEP 2: Stellen ──
        print("\n=== S2 Stellen ===")
        page.goto(f"{BASE}/candidate/stellen", wait_until="load", timeout=TIMEOUT)
        page.wait_for_timeout(2500)
        body = snap("S2")
        found = [kw for kw in ["Cloud", "DevOps", "AWS", "Senior"] if kw in body]
        print(f"Stellen-Keywords gefunden: {found}")
        F.append({"step": "S2 Stellen", "klicks": "Tab Stellen", "was": f"{len(found)}/4 Keywords", "druck": "Stellen sichtbar" if found else "Keine Stellen"})
        # Klasse d (14.10.2026): S2-Finding in fails (vorher nur Report)
        if not found:
            fails.append("S2: Keine Stellen-Keywords gefunden")

        # ── STEP 3: Bewerbungen ──
        print("\n=== S3 Bewerbungen ===")
        page.goto(f"{BASE}/candidate/bewerbungen", wait_until="load", timeout=TIMEOUT)
        page.wait_for_timeout(2500)
        body = snap("S3")
        statuses = [s for s in ["eingegangen", "eingeladen", "abgelehnt", "eingestellt", "zurückgezogen"] if s in body.lower()]
        print(f"Statuses sichtbar: {statuses}")
        F.append({"step": "S3 Bewerbungen", "klicks": "Tab Bewerbungen", "was": f"Status: {','.join(statuses) or 'keine'}", "druck": "Status OK" if statuses else "Kein Status"})
        # Klasse d (14.10.2026): S3-Finding in fails
        if not statuses:
            fails.append("S3: Keine Bewerbungs-Status sichtbar")

        # ── STEP 4: Einladung ──
        print("\n=== S4 Einladung ===")
        has_invite = "eingeladen" in body.lower()
        if has_invite:
            for kw in ["ICS", "Datum", "Uhrzeit", "vdo.ninja", "Meeting"]:
                print(f"  {kw}: {'✓' if kw in body else '✗'}")
        else:
            print("  Kein eingeladen-Status → nicht testbar")
        F.append({"step": "S4 Einladung", "klicks": "Bewerbungen → Einladung", "was": "Einladung sichtbar" if has_invite else "Nicht eingeladen", "druck": "Testbar" if has_invite else "Nicht testbar"})
        # Klasse d: S4 ist konditional (nur bei eingeladen) — kein Fail bei Nicht-Einladung

        # ── STEP 5: Dokumente ──
        print("\n=== S5 Dokumente ===")
        page.goto(f"{BASE}/candidate/profil", wait_until="load", timeout=TIMEOUT)
        page.wait_for_timeout(2500)
        body = snap("S5")
        docs = [d for d in ["Lebenslauf", "PDF", "Dokument", "hochgeladen"] if d in body]
        print(f"Dokumente sichtbar: {docs}")
        F.append({"step": "S5 Dokumente", "klicks": "Tab Dokumente", "was": f"{len(docs)} Typen", "druck": "Dokumente sichtbar" if docs else "Keine"})
        # Klasse d (14.10.2026): S5-Finding in fails
        if not docs:
            fails.append("S5: Keine Dokumente/Keywords sichtbar")

        # ── STEP 6: Zurückziehen ──
        print("\n=== S6 Zurückziehen ===")
        page.goto(f"{BASE}/candidate/bewerbungen", wait_until="load", timeout=TIMEOUT)
        page.wait_for_timeout(2500)
        body = snap("S6")
        # Check for withdraw buttons
        btns = page.locator("button").all()
        withdraw = [b.inner_text().strip() for b in btns if any(w in b.inner_text().lower() for w in ["zurück", "withdraw", "abbrechen"])]
        print(f"Zurückziehen-Buttons: {withdraw}")
        F.append({"step": "S6 Zurückziehen", "klicks": "Tab Bewerbungen → Zurückziehen", "was": f"{len(withdraw)} Buttons", "druck": "Möglich" if withdraw else "Nicht möglich"})
        # Klasse d: S6 ist konditional (nur bei aktiver Bewerbung) — kein Fail bei 0 Buttons

        # ── STEP 7: Sprachtest ──
        print("\n=== S7 Sprachtest ===")
        page.goto(f"{BASE}/candidate/sprachtest", wait_until="load", timeout=TIMEOUT)
        page.wait_for_timeout(3000)
        body = snap("S7")
        langs = [l for l in ["Deutsch", "Englisch", "Französisch"] if l in body]
        print(f"Sprachen sichtbar: {langs}")
        F.append({"step": "S7 Sprachtest", "klicks": "Tab Sprachtest", "was": f"{len(langs)}/3 Sprachen", "druck": "Verständlich" if langs else "Leer/unverständlich"})
        # Klasse d (14.10.2026): S7-Finding in fails — mind. 1 Sprache muss sichtbar sein
        # (3/3 ist zu streng: Seed-DB zeigt evtl. nur verfügbare Sprachen)
        if not langs:
            fails.append("S7: Keine Sprachen sichtbar")

        # ── STEP 8: Onboarding ──
        print("\n=== S8 Onboarding ===")
        page.goto(f"{BASE}/candidate/onboarding", wait_until="load", timeout=TIMEOUT)
        page.wait_for_timeout(2500)
        body = snap("S8")
        ob = [k for k in ["Onboarding", "Willkommen", "Vertrag", "Release"] if k in body]
        print(f"Onboarding Keywords: {ob}")
        F.append({"step": "S8 Onboarding", "klicks": "Tab Onboarding", "was": f"{len(ob)} Keywords", "druck": "Sichtbar" if ob else "Leer"})
        # Klasse d (14.10.2026): S8-Finding in fails
        if not ob:
            fails.append("S8: Keine Onboarding-Keywords sichtbar")

        browser.close()

    # ── OUTPUT ──
    print("\n" + "=" * 60)
    print("UX-REVIEW KANDIDAT (test@example.de)")
    print("=" * 60)
    print(f"1. Hauptaufgabe erledigbar? {'Teilweise' if fails else 'Ja'}")
    print("\n2. Top-5 Steine:")
    for i, e in enumerate(F[:5], 1):
        print(f"   {i}. {e['step']}")
        print(f"      Wo: {e['klicks']}")
        print(f"      Was: {e['was']}")
        print(f"      Druck: {e['druck']}")
    vertrauen = "Tab-Index klar, kein Datenverlust-Risiko" if not fails else f"{len(fails)} Lücken"
    print(f"\n3. Vertrauen: {vertrauen}")
    print(f"4. Zuerst ändern: {fails[0] if fails else 'Nichts'}")
    if fails:
        print(f"\nFAILURES: {fails}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())