"""Capture screenshots of the running Raqib dashboard for the pitch deck.

Run with the backend venv while the app is up on http://127.0.0.1:8600:
    backend\\.venv\\Scripts\\python.exe docs\\deck\\capture_shots.py

Only the local app is opened; no external site is visited.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8600"
OUT = Path(__file__).resolve().parent / "shots"
CASE = "case:c_epost_redelivery"

LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 64 64">
<defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#e5b85c"/><stop offset="1" stop-color="#b0a6ff"/></linearGradient></defs>
<path d="M32 8 12 16v15c0 12 8.5 20.5 20 25 11.5-4.5 20-13 20-25V16L32 8Z" fill="none" stroke="url(#lg)" stroke-width="4" stroke-linejoin="round"/>
<circle cx="32" cy="30" r="8" fill="none" stroke="url(#lg)" stroke-width="4"/><circle cx="32" cy="30" r="3" fill="#e5b85c"/></svg>"""


def start_case(speed: float = 0) -> str:
    req = urllib.request.Request(
        f"{BASE}/api/investigations",
        data=json.dumps({"url": CASE, "speed": speed}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["id"]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=2,
                                  color_scheme="dark", locale="en-US")
        ctx.add_init_script("try { localStorage.setItem('raqib.lang', 'en') } catch (e) {}")
        page = ctx.new_page()

        def shot(name: str, route: str, wait: float) -> None:
            if only and name not in only:
                return
            page.goto(f"{BASE}/#{route}")
            page.reload()  # hash routes: make sure the app boots on this view with lang=en
            time.sleep(wait)
            page.screenshot(path=str(OUT / f"{name}.png"))
            print("saved", name)

        shot("command", "/command", 5)

        # live tab mid-run: a real-time replay (speed 1) caught while the agent is on the card page
        if not only or "live" in only:
            live_id = start_case(speed=1)
            page.goto(f"{BASE}/#/case/{live_id}")
            t0 = time.time()
            for name, at in (("live", 29), ("live_late", 35)):
                while time.time() - t0 < at:
                    time.sleep(0.2)
                page.screenshot(path=str(OUT / f"{name}.png"))
                print("saved", name)

        run_id = start_case()
        time.sleep(1.5)
        shot("casefile", f"/case/{run_id}?tab=case", 5)
        shot("campaign", f"/case/{run_id}?tab=campaign", 5)
        shot("report", f"/case/{run_id}?tab=report", 4)
        shot("campaigns", "/campaigns", 5)
        shot("cases", "/cases", 4)

        # logo (transparent PNG) for the title slide
        if not only or "logo" in only:
            lp = ctx.new_page()
            lp.set_viewport_size({"width": 512, "height": 512})
            lp.set_content(f"<html><body style='margin:0;background:transparent'>{LOGO_SVG}</body></html>")
            lp.screenshot(path=str(OUT / "logo.png"), omit_background=True,
                          clip={"x": 0, "y": 0, "width": 512, "height": 512})
            print("saved logo")
        browser.close()


if __name__ == "__main__":
    main()
