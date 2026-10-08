"""Detail-Check: S2, S5, S6, S7 Seiteninhalte."""
import sys
from playwright.sync_api import sync_playwright
from e2e_harness import BASE, seed_email

EMAIL = seed_email("test@example.de")
PASSWORD = "test1234"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})

    # Login
    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2000)
    page.get_by_label("E-Mail").fill(EMAIL)
    page.get_by_label("Passwort", exact=True).fill(PASSWORD)
    page.get_by_role("button", name="Einloggen").click()
    page.wait_for_timeout(2500)
    print("Logged in:", page.url)

    # S2: Stellen full text
    print("\n=== S2 STELLEN FULL TEXT ===")
    page.goto(f"{BASE}/candidate/stellen", wait_until="load")
    page.wait_for_timeout(3000)
    body = page.inner_text("body")
    print(body[:3000])

    # S5: Dokumente full text
    print("\n=== S5 DOKUMENTE FULL TEXT ===")
    page.goto(f"{BASE}/candidate/profil", wait_until="load")
    page.wait_for_timeout(3000)
    try:
        page.get_by_text("Dokumente", exact=True).first.click(timeout=8000)
        page.wait_for_timeout(800)
    except Exception:
        pass
    body = page.inner_text("body")
    print(body[:3000])

    # S6: Bewerbungen full text
    print("\n=== S6 BEWERBUNGEN FULL TEXT ===")
    page.goto(f"{BASE}/candidate/bewerbungen", wait_until="load")
    page.wait_for_timeout(3000)
    body = page.inner_text("body")
    print(body[:3000])

    # S7: Sprachtest full text
    print("\n=== S7 SPRACHTEST FULL TEXT ===")
    page.goto(f"{BASE}/candidate/sprachtest", wait_until="load")
    page.wait_for_timeout(3000)
    body = page.inner_text("body")
    print(body[:3000])

    browser.close()