"""E2E-Nachweis RTL-Drawer-Padding-Fix (03.10.2026).

Bug: In RTL (Arabisch) reserviert Quasar das Drawer-Padding auf der LOGISCHEN
statt physischen Seite. Sobald das Benachrichtigungs-Panel geschlossen wurde,
fiel das schuetzende Padding weg -> der Content lief unter die Nav-Sidebar
(Karten/Kreisdiagramm rechts abgeschnitten). Fix: `webui/i18n.py::apply_direction()`
aktiviert Quasars RTL-Modus (Spec: ergebnisse/entscheidungen.md, RTL-Padding-Bug).

Prueft in AR: nach Schliessen des Benachrichtigungs-Panels darf KEIN
Content-Element unter der Nav-Sidebar liegen und der Content muss vor ihr enden.

Isoliert starten:
  .venv-streamlit/bin/python3 tests/e2e_isolation.py --only e2e_rtl_drawer --port 8091
"""
import sys
from playwright.sync_api import sync_playwright
from e2e_harness import check_server, BASE

EMAIL, PASSWORD = "test@example.de", "test1234"
TIMEOUT = 15000

JS = """() => {
  const page=document.querySelector('.q-page');
  const nav=document.querySelector('.q-drawer--left');
  if(!page||!nav) return {err:'Elemente fehlen'};
  const pb=page.getBoundingClientRect(), nb=nav.getBoundingClientRect();
  const rtl=document.documentElement.dir==='rtl';
  let under=0;
  page.querySelectorAll('*').forEach(el=>{const r=el.getBoundingClientRect();
    if(r.width<10||r.height<10)return;
    const hit = rtl ? (r.right>nb.left+2) : (r.left<nb.right-2);
    if(hit) under++;});
  return {dir:document.documentElement.dir, page:[Math.round(pb.x),Math.round(pb.right)],
          nav:[Math.round(nb.x),Math.round(nb.right)], underNav:under,
          pr:getComputedStyle(document.querySelector('.q-page-container')).paddingRight,
          qrtl:(window.Quasar&&Quasar.lang)?String(Quasar.lang.rtl):'?',
          enUS:!!(window.Quasar&&Quasar.lang&&Quasar.lang.enUS)};
}"""


def main() -> int:
    check_server()
    fails = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(f"{BASE}/login", wait_until="load", timeout=TIMEOUT)
        page.wait_for_timeout(1500)
        page.locator('input[aria-label="E-Mail"]').first.fill(EMAIL)
        page.locator('input[aria-label="Passwort"]').first.fill(PASSWORD)
        page.get_by_role("button", name="Einloggen").click()
        page.wait_for_timeout(2500)
        page.get_by_role("button", name="AR", exact=True).click()
        page.wait_for_timeout(3000)

        # S1: beide Panels offen -> symmetrisch, sauber
        s1 = page.evaluate(JS)
        print(f"S1 beide offen : dir={s1['dir']} page={s1['page']} nav={s1['nav']} "
              f"underNav={s1['underNav']}")
        if s1["underNav"] != 0:
            fails.append(f"S1 underNav={s1['underNav']} (erwartet 0)")

        # S2: Benachrichtigungs-Panel schliessen (Glocke) -> hier war der Bug
        page.locator("header button").nth(1).click()
        page.wait_for_timeout(1500)
        s2 = page.evaluate(JS)
        print(f"S2 Glocke zu   : dir={s2['dir']} page={s2['page']} nav={s2['nav']} "
              f"padding-right={s2['pr']} underNav={s2['underNav']}")
        if s2["underNav"] != 0:
            fails.append(f"S2 underNav={s2['underNav']} (erwartet 0 — Padding-Bug!)")
        if s2["page"][1] > s2["nav"][0] + 2:
            fails.append(f"S2 Content-Ende {s2['page'][1]} > Nav-Start {s2['nav'][0]}")

        # S3: Nav schliessen -> Drawer muss off-screen (rechts) fahren
        page.locator("header button").nth(1).click()   # Notif wieder auf
        page.wait_for_timeout(1000)
        page.locator("header button").first.click()    # Nav zu
        page.wait_for_timeout(1500)
        s3 = page.evaluate(JS)
        print(f"S3 Nav zu      : dir={s3['dir']} page={s3['page']} nav={s3['nav']} "
              f"underNav={s3['underNav']}")
        if s3["nav"][0] < 1280:
            fails.append(f"S3 Nav x={s3['nav'][0]} — nicht off-screen (erwartet >=1280)")

        browser.close()

    if fails:
        print("FAIL:")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS: RTL-Drawer-Padding korrekt (0 Elemente unter der Nav-Sidebar).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
