"""Onboarding + Zurückziehen Detail."""
import sys
from playwright.sync_api import sync_playwright
from e2e_harness import BASE

EMAIL = "test@example.de"
PASSWORD = "test1234"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_viewport_size({"width": 1280, "height": 900})

    page.goto(f"{BASE}/login", wait_until="load")
    page.wait_for_timeout(2000)
    page.get_by_label("E-Mail").fill(EMAIL)
    page.get_by_label("Passwort", exact=True).fill(PASSWORD)
    page.get_by_role("button", name="Einloggen").click()
    page.wait_for_timeout(2500)

    # S8 Onboarding full text
    print("=== S8 ONBOARDING ===")
    page.goto(f"{BASE}/candidate/onboarding", wait_until="load")
    page.wait_for_timeout(3000)
    body = page.inner_text("body")
    print(body[:3000])

    # S6: Check for withdraw button on an active application
    # Candidate 2 has only 1 application (zurückgezogen). Let me check if there's
    # a withdraw button visible for active applications in the UI.
    print("\n=== S6 ZURÜCKZIEHEN - Buttons ===")
    page.goto(f"{BASE}/candidate/bewerbungen", wait_until="load")
    page.wait_for_timeout(2500)
    btns = page.locator("button").all()
    for b in btns:
        txt = b.inner_text().strip()
        if txt:
            print(f"  Button: '{txt[:60]}'")

    browser.close()