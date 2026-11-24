"""Browser-level proof for the sandbox VM, run as the raqib user with Raqib's own launch settings.

1. Chrome's sandbox is really on: renderer processes run under seccomp, in their own user namespace.
2. From inside a page, private addresses are unreachable: fetch, WebSocket and a DNS-rebinding style name.
3. WebRTC cannot learn the public IP through STUN (UDP is blocked; non-proxied UDP is disabled).
"""

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # run from the backend folder
from raqib.scanner import launch_options  # noqa: E402

PROBE = """async (target) => {
  const out = {};
  const ctl = new AbortController(); setTimeout(() => ctl.abort(), 5000);
  try { await fetch(target.http, {mode: 'no-cors', signal: ctl.signal}); out.fetch = 'reached'; } catch (e) { out.fetch = 'blocked'; }
  out.websocket = await new Promise((r) => { try { const ws = new WebSocket(target.ws); ws.onopen = () => r('reached'); ws.onerror = () => r('blocked'); setTimeout(() => r('blocked'), 5000); } catch (e) { r('blocked'); } });
  const ctl2 = new AbortController(); setTimeout(() => ctl2.abort(), 5000);
  try { await fetch(target.rebind, {mode: 'no-cors', signal: ctl2.signal}); out.rebinding = 'reached'; } catch (e) { out.rebinding = 'blocked'; }
  out.webrtc = await new Promise(async (r) => {
    const types = new Set();
    const pc = new RTCPeerConnection({iceServers: [{urls: 'stun:stun.l.google.com:19302'}]});
    pc.createDataChannel('x');
    pc.onicecandidate = (e) => { if (e.candidate) types.add(e.candidate.type); };
    await pc.setLocalDescription(await pc.createOffer());
    setTimeout(() => { pc.close(); r([...types]); }, 6000);
  });
  return out;
}"""


def proc_info(pid: str) -> dict:
    status = Path(f"/proc/{pid}/status").read_text()
    seccomp = next((ln.split()[1] for ln in status.splitlines() if ln.startswith("Seccomp:")), "?")
    return {"seccomp": seccomp, "userns": os.readlink(f"/proc/{pid}/ns/user")}


def chrome_processes() -> tuple[list[str], list[str]]:
    browsers, renderers = [], []
    for pid in filter(str.isdigit, os.listdir("/proc")):
        try:
            cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
        except OSError:
            continue
        if "ms-playwright" in cmd and ("chrome" in cmd or "headless_shell" in cmd):
            (renderers if "--type=renderer" in cmd else browsers if "--type=" not in cmd else []).append(pid)
    return browsers, renderers


async def main() -> int:
    from playwright.async_api import async_playwright

    ok = True
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(**launch_options())
        page = await browser.new_page()
        await page.goto("https://example.com", wait_until="domcontentloaded")
        browsers, renderers = chrome_processes()
        main_ns = proc_info(browsers[0])["userns"] if browsers else "?"
        for pid in renderers[:3]:
            info = proc_info(pid)
            sandboxed = info["seccomp"] == "2" and info["userns"] != main_ns
            ok &= sandboxed
            print(f"{'PASS' if sandboxed else 'FAIL'}  renderer {pid}: seccomp={info['seccomp']} (2 = filtered), own user namespace={info['userns'] != main_ns}")
        if not renderers:
            ok = False
            print("FAIL  no renderer process found")
        res = await page.evaluate(PROBE, {"http": "http://192.168.1.1/", "ws": "ws://192.168.1.1/", "rebind": "http://192-168-1-1.nip.io/"})
        for k in ("fetch", "websocket", "rebinding"):
            good = res[k] == "blocked"
            ok &= good
            print(f"{'PASS' if good else 'FAIL'}  page {k} to a private address: {res[k]}")
        good = "srflx" not in res["webrtc"]
        ok &= good
        print(f"{'PASS' if good else 'FAIL'}  WebRTC learns no public address via STUN (candidate types: {res['webrtc'] or 'none'})")
        await browser.close()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
