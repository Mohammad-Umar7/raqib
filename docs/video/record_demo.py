"""Record the one-minute demo video of the running app (Playwright screen recording + captions).

    backend\\.venv\\Scripts\\python docs\\video\\record_demo.py           # app must be running on :8600

Writes docs/video/raqib-demo.mp4 (H.264, 1600x900). Needs `imageio-ffmpeg` for the MP4 conversion.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import urllib.request
from pathlib import Path

from playwright.async_api import async_playwright

APP = "http://127.0.0.1:8600"
OUT = Path(__file__).resolve().parent
W, H = 1600, 900

CAPTION_JS = """(t) => {
  let el = document.getElementById('demo-cap');
  if (!el) {
    el = document.createElement('div'); el.id = 'demo-cap';
    Object.assign(el.style, {position:'fixed', left:'50%', bottom:'28px', transform:'translateX(-50%)', zIndex: 9999, maxWidth:'1100px',
      padding:'12px 22px', borderRadius:'14px', background:'rgba(7,7,10,0.9)', border:'1px solid rgba(229,184,92,0.55)', color:'#f2f0ea',
      font:'600 21px Inter Variable, Segoe UI, sans-serif', textAlign:'center', boxShadow:'0 12px 40px rgba(0,0,0,0.6)', transition:'opacity .3s'});
    document.body.appendChild(el);
  }
  el.style.opacity = t ? '1' : '0'; el.textContent = t;
}"""


def api(path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(APP + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"content-type": "application/json"}, method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


async def main() -> None:
    vid_dir = OUT / "_raw"
    shutil.rmtree(vid_dir, ignore_errors=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(channel="chrome", headless=True)
        ctx = await browser.new_context(viewport={"width": W, "height": H}, record_video_dir=str(vid_dir), record_video_size={"width": W, "height": H})
        page = await ctx.new_page()
        await page.add_init_script("localStorage.setItem('raqib.lang','en')")
        cap = lambda t: page.evaluate(CAPTION_JS, t)  # noqa: E731

        # 1. command centre + hunt
        await page.goto(APP + "/#/command")
        await page.wait_for_timeout(1800)
        await cap("Raqib finds scam sites in Search, Maps and new domains before citizens click them")
        await page.wait_for_timeout(2500)
        await page.click(".seg button:has-text('6×')")
        await page.click("button:has-text('Run hunt')")
        await cap("Thousands of candidates are triaged against 36 protected UAE brands")
        await page.wait_for_timeout(4500)
        await page.evaluate("document.querySelector('.live-hunt').scrollIntoView({block:'center'})")
        await page.click(".live-hunt .btn-primary")
        await cap("Live: every domain registered yesterday is checked, about 70,000 a day")
        await page.wait_for_timeout(4000)

        # 2. investigation of an SMS link (recorded demo case)
        run = api("/api/investigations", {"url": "http://track-parcel-ae.test/?id=AE7781-20", "speed": 2.6})
        await page.goto(APP + f"/#/case/{run['id']}")
        await cap("An SMS link opens in an isolated browser: the agent follows the victim's path")
        await page.wait_for_timeout(6000)
        await cap("Detectors flag card + OTP collection and a Telegram bot receiving the stolen data")
        await page.wait_for_timeout(6000)
        await cap("Every point of the risk score has a reason, and every action is logged")
        await page.wait_for_timeout(5500)
        await cap("Fingerprints link it to the other sites run by the same operator")
        await page.wait_for_timeout(5500)

        # 3. generative case file and report
        await page.evaluate("window.scrollTo(0,0)")
        await page.click(".tab:has-text('Case file')")
        await cap("A generative case file is composed for every case: verdict, victim journey, score breakdown")
        await page.wait_for_timeout(2500)
        await page.mouse.wheel(0, 900)
        await page.wait_for_timeout(2500)
        await page.evaluate("window.scrollTo(0,0)")
        await page.click(".tab:has-text('Report pack')")
        await cap("Police-ready evidence: SHA-256 chain of custody, bilingual PDF, takedown drafts")
        await page.wait_for_timeout(3500)

        # 4. accuracy
        sample = api("/api/batch/sample?kind=recorded")
        job = api("/api/batch", {"text": sample["text"], "use_browser": False, "use_ai": False, "concurrency": 4})
        await page.goto(APP + "/#/batch")
        await page.fill(".batch-input", sample["text"])
        await cap("Any URL list, including a hidden test set, is scanned and scored for precision and recall")
        await page.wait_for_timeout(1500)
        await page.click("button:has-text('Scan')")
        await page.wait_for_timeout(4000)
        await page.evaluate("document.querySelector('.metrics-row')?.scrollIntoView({block:'center'})")
        await page.wait_for_timeout(2500)
        await cap("Raqib · رقيب — find scam sites before citizens click them")
        await page.wait_for_timeout(2500)
        del job
        await ctx.close()
        await browser.close()

    webm = next(vid_dir.glob("*.webm"))
    mp4 = OUT / "raqib-demo.mp4"
    try:
        import imageio_ffmpeg

        ff = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run([ff, "-y", "-i", str(webm), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "22", "-preset", "medium", "-movflags", "+faststart", str(mp4)],
                       check=True, capture_output=True)
        print("wrote", mp4)
    except Exception as exc:
        shutil.copy(webm, OUT / "raqib-demo.webm")
        print("MP4 conversion failed, kept WebM:", exc)
    shutil.rmtree(vid_dir, ignore_errors=True)


if __name__ == "__main__":
    asyncio.run(main())
