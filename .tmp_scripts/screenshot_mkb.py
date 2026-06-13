"""Screenshot key Miami Knows Beauty pages for the owner walkthrough PDF."""
import os
import sys

# Avoid /tmp/inspect.py collision - ensure we're not using /tmp as cwd
os.chdir('/home/david')

from playwright.sync_api import sync_playwright

BASE_URL = "https://miami.knowsbeauty.com"
ADMIN_KEY = "CrciS3PurR5OrQWSEU97SSR2VyS2wkFZmvDq8/iuc1A="
OUT_DIR = "/home/david/Code/known-around-town/.tmp_scripts/screenshots"
os.makedirs(OUT_DIR, exist_ok=True)

PAGES = [
    ("homepage", "/"),
    ("hair_category", "/c/hair"),
    ("owners_page", "/owners"),
    ("owner_login", "/owners/login"),
]

def take_screenshots():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            extra_http_headers={"X-API-Key": ADMIN_KEY},
        )
        page = ctx.new_page()

        for name, path in PAGES:
            url = BASE_URL + path
            print(f"Screenshotting {url} ...")
            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)
                out_path = f"{OUT_DIR}/{name}.png"
                page.screenshot(path=out_path, full_page=False)
                print(f"  -> saved {out_path} ({os.path.getsize(out_path)} bytes)")
            except Exception as e:
                print(f"  ERROR {name}: {e}")

        # Try to get a business listing
        try:
            page.goto(BASE_URL + "/c/hair", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)
            # Find first business card link
            href = page.locator("a[href]").evaluate_all("""
                els => {
                    for (const el of els) {
                        const h = el.getAttribute('href');
                        if (h && h.split('/').length >= 4 && !h.startsWith('/c/') && !h.startsWith('/owners') && !h.startsWith('/assets')) {
                            return h;
                        }
                    }
                    return null;
                }
            """)
            if href:
                full_url = BASE_URL + href if href.startswith("/") else href
                print(f"Found listing: {full_url}")
                page.goto(full_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)
                page.screenshot(path=f"{OUT_DIR}/business_listing.png", full_page=False)
                print(f"  -> saved business_listing.png ({os.path.getsize(OUT_DIR+'/business_listing.png')} bytes)")
        except Exception as e:
            print(f"  ERROR business_listing: {e}")

        browser.close()
        print("All done!")

take_screenshots()
