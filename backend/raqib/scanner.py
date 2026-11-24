"""Real scanner for any URL: the engine behind single investigations, batch evaluation and the CLI.

For each URL it:
  1. checks the URL itself (shortener, raw IP, punycode, '@' tricks, brand hidden in a sub-domain,
     free hosting platform, abused TLD, official / trusted / restricted-zone domains);
  2. follows the redirect chain over HTTP with a phone user-agent (expands shorteners);
  3. fetches the landing page again as a desktop computer to catch cloaking;
  4. opens it in an isolated headless browser (mobile, UAE locale) for a screenshot, the rendered DOM,
     forms, scripts and network log, falling back to the raw HTML when no browser is available;
  5. looks up registration (RDAP) and hosting;
  6. optionally asks Claude (vision) to look at the screenshot (only with an API key);
  7. runs the same detectors as every other mode and returns a case bundle plus a verdict.

Nothing is submitted, downloaded or typed: the page is only loaded and read.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import ipaddress
import re
import time
from datetime import date
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import httpx

from . import config, infra, ioc
from .detectors import analyse, classify_scam, enrich, final_score, make_signal, verdict_for
from .domains import PRIVATE_SUFFIXES, RISKY_TLDS, SHORTENERS, host_of, registrable, restricted_zone
from .netutil import DESKTOP_UA, MOBILE_UA, ssl_context, url_error
from .pagejs import EXTRACT_JS
from .registry import Registry, load_registry

LIBRARY_HOSTS = {"code.jquery.com", "cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com", "ajax.googleapis.com", "fonts.googleapis.com",
                 "fonts.gstatic.com", "www.googletagmanager.com", "www.google-analytics.com", "maxcdn.bootstrapcdn.com", "stackpath.bootstrapcdn.com",
                 "www.gstatic.com", "connect.facebook.net", "static.cloudflareinsights.com", "cdn.shopify.com", "www.google.com"}
FRAUD_THRESHOLD = 60  # score at or above this counts as "fraud" in batch evaluation


@lru_cache(maxsize=1)
def trusted_domains() -> frozenset[str]:
    path = config.DATA_DIR / "trusted_domains.txt"
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().lower()
        if line and not line.startswith("#"):
            out.add(line)
    return frozenset(out)


def normalise_url(raw: str) -> str:
    u = raw.strip().strip("<>\"'")
    if not re.match(r"^[a-z][a-z0-9+.-]*://", u, re.I):
        u = "http://" + u
    return u


# --------------------------------------------------------------------------- 1. URL checks

# Hosts on trusted domains where anyone can publish content (forms, documents, file shares): never trusted.
USER_CONTENT_HOSTS = {"docs.google.com", "sites.google.com", "drive.google.com", "forms.gle", "forms.office.com", "onedrive.live.com", "1drv.ms",
                      "storage.googleapis.com", "github.com", "gist.github.com", "t.me", "linktr.ee", "dropbox.com", "www.dropbox.com"}


def trust_of(host: str, reg: Registry) -> dict | None:
    """Why this host is legitimate, if it is: official brand domain, vetted zone or well-known site."""
    if host in USER_CONTENT_HOSTS:
        return None
    ent = reg.official_domain_of(host)
    if ent:
        return {"kind": "official", "reason": f"official {ent.name} domain", "brand": ent.id}
    zone = restricted_zone(host)
    if zone:
        return {"kind": "restricted", "reason": f"in the vetted .{zone} zone (only approved organisations can register)"}
    if registrable(host) in trusted_domains():
        return {"kind": "trusted", "reason": "well-known legitimate site"}
    return None


def url_signals(url: str, reg: Registry) -> list[dict]:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    out: list[dict] = []
    if not host:
        return out
    reg_dom = registrable(host)
    if reg_dom in SHORTENERS or host in SHORTENERS:
        out.append(make_signal("url.shortener", [{"type": "url", "value": url}], svc=reg_dom))
    try:
        ipaddress.ip_address(host)
        out.append(make_signal("url.ip_host", [{"type": "url", "value": host}]))
    except ValueError:
        pass
    if "xn--" in host:
        out.append(make_signal("url.punycode", [{"type": "domain", "value": host}]))
    if "@" in (parts.netloc or ""):
        out.append(make_signal("url.userinfo", [{"type": "url", "value": url}]))
    if not trust_of(host, reg):
        sub = host[: -len(reg_dom)].strip(".")
        if sub:
            tokens = set(re.split(r"[.\-_]", sub))
            for e in reg.entities:
                labels = {d.split(".")[0] for d in e.domains} | {k for k in e.keywords if re.fullmatch(r"[a-z0-9]{3,}", k)}
                if tokens & labels:
                    out.append(make_signal("url.brand_in_subdomain", [{"type": "domain", "value": host}], brand=e.name, domain=reg_dom))
                    break
        for suf in PRIVATE_SUFFIXES:
            if host.endswith("." + suf):
                out.append(make_signal("url.free_hosting", [{"type": "domain", "value": host}], platform=suf))
                break
        tld = host.rsplit(".", 1)[-1]
        if tld in RISKY_TLDS:
            out.append(make_signal("url.risky_tld", [{"type": "domain", "value": host}], tld=tld))
    return out


# --------------------------------------------------------------------------- 2-3. HTTP: redirects and cloaking

async def follow(url: str, ua: str, max_hops: int = 10) -> dict:
    """Follow redirects hop by hop (HTTP 3xx and simple meta refresh), recording every hop."""
    chain: list[dict] = []
    cur = url
    html, status, ctype, error = "", 0, "", None
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=6.0), verify=ssl_context(), follow_redirects=False,
                                 headers={"User-Agent": ua, "Accept-Language": "en-AE,en;q=0.9,ar;q=0.8"}) as c:
        for _ in range(max_hops):
            err = url_error(cur)
            if err:
                error = err
                break
            try:
                r = await c.get(cur)
            except httpx.HTTPError as exc:
                error = f"{type(exc).__name__}: {str(exc)[:120]}"
                if cur.startswith("http://") and not chain:  # some scam sites only answer on https
                    alt = "https://" + cur[len("http://"):]
                    try:
                        r = await c.get(alt)
                        cur, error = alt, None
                    except httpx.HTTPError:
                        break
                else:
                    break
            status = r.status_code
            chain.append({"url": cur, "status": status})
            if 300 <= status < 400 and r.headers.get("location"):
                cur = urljoin(cur, r.headers["location"])
                continue
            ctype = r.headers.get("content-type", "")
            body = r.content[:1_500_000]
            html = body.decode(r.encoding or "utf-8", "ignore") if "html" in ctype or not ctype else ""
            m = re.search(r'<meta[^>]+http-equiv=["\']?refresh["\']?[^>]+content=["\']?\s*\d+\s*;\s*url=([^"\'>]+)', html, re.I)
            if m and len(chain) < max_hops:
                cur = urljoin(cur, m.group(1).strip())
                continue
            break
    return {"chain": chain, "final_url": chain[-1]["url"] if chain else url, "status": status, "html": html, "content_type": ctype, "error": error}


class _Extractor(HTMLParser):
    """Turns raw HTML into the same element list the in-browser extractor produces (fallback path)."""

    def __init__(self, base: str):
        super().__init__(convert_charrefs=True)
        self.base, self.els, self.forms, self.scripts = base, [], [], []
        self.title, self._stack, self._text, self._form, self._labels = "", [], "", "", {}
        self._in_script = self._in_title = False
        self._label_for: str | None = None

    def _add(self, kind: str, **kw):
        if len(self.els) < 120:
            self.els.append({"id": f"e{len(self.els) + 1}", "kind": kind, **kw})

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        elif tag == "script":
            self._in_script = True
            if a.get("src"):
                self.scripts.append({"src": urljoin(self.base, a["src"]), "inline": ""})
        elif tag == "form":
            fid = a.get("id") or f"form{len(self.forms)}"
            self.forms.append({"id": fid, "action": urljoin(self.base, a["action"]) if a.get("action") else "", "method": (a.get("method") or "get").lower()})
            self._form = fid
        elif tag == "label":
            self._label_for = a.get("for")
            self._text = ""
        elif tag in ("input", "textarea", "select"):
            t = (a.get("type") or ("select" if tag == "select" else "text")).lower()
            if t in ("hidden", "checkbox", "radio", "submit", "button", "image", "reset"):
                if t in ("submit", "button"):
                    self._add("button", text=a.get("value") or "Submit")
                return
            label = self._labels.get(a.get("id", ""), "") or a.get("aria-label", "") or a.get("placeholder", "") or a.get("name", "")
            self._add("select" if tag == "select" else "input", text=label, form=self._form,
                      field={"name": a.get("name", ""), "type": t, "autocomplete": a.get("autocomplete", ""), "placeholder": a.get("placeholder", ""),
                             "label": label, "inputmode": a.get("inputmode", "")})
        elif tag == "a":
            href = a.get("href", "")
            if href.startswith("tel:"):
                self._add("footer", text=href[4:], phone=href[4:])
            elif re.search(r"wa\.me|whatsapp", href, re.I):
                m = re.search(r"(\d{8,15})", href)
                self._add("footer", text=href, whatsapp=m.group(1) if m else "")
            elif href.startswith("mailto:"):
                self._add("footer", text=href[7:], email=href[7:].split("?")[0])
        self._stack.append(tag)
        if tag in ("h1", "h2", "h3", "p", "li", "button", "label"):
            self._text = ""

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "script":
            self._in_script = False
        elif tag == "form":
            self._form = ""
        text = re.sub(r"\s+", " ", self._text).strip()
        if tag == "label" and self._label_for:
            self._labels[self._label_for] = text[:80]
        elif tag in ("h1", "h2", "h3") and text:
            self._add("heading", text=text[:160])
        elif tag in ("p", "li") and len(text) > 3:
            self._add("text", text=text[:240])
        elif tag == "button" and text:
            self._add("button", text=text[:80])
        if self._stack and self._stack[-1] == tag:
            self._stack.pop()

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._in_script:
            if self.scripts and not self.scripts[-1]["src"] and len(self.scripts[-1]["inline"]) < 30000:
                self.scripts[-1]["inline"] += data
            elif not self.scripts or self.scripts[-1]["src"]:
                self.scripts.append({"src": "", "inline": data[:30000]})
        else:
            self._text += data


def html_page(html: str, url: str) -> dict:
    ex = _Extractor(url)
    try:
        ex.feed(html)
    except Exception:
        pass
    body = re.sub(r"<[^>]+>", " ", re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html))
    analytics = sorted(set(re.findall(r"\b(?:G-[A-Z0-9]{8,12}|UA-\d{4,10}-\d{1,3}|GTM-[A-Z0-9]{6,8})\b", html)))
    return {"url": url, "title": re.sub(r"\s+", " ", ex.title).strip(), "elements": ex.els, "forms": ex.forms, "scripts": ex.scripts,
            "analytics": analytics, "body": re.sub(r"\s+", " ", unquote(body))[:20000], "html": html[:200000], "favicon": urljoin(url, "/favicon.ico")}


def _text_shingles(text: str) -> set[str]:
    words = re.findall(r"[a-z؀-ۿ]{3,}", text.lower())
    return {" ".join(words[i:i + 3]) for i in range(max(0, len(words) - 2))}


def cloaking_check(mobile: dict, desktop: dict) -> str | None:
    """Different destination or very different content for phone vs computer visitors."""
    if not mobile.get("chain") or not desktop.get("chain"):
        return None
    mh, dh = registrable(host_of(mobile["final_url"])), registrable(host_of(desktop["final_url"]))
    if mh and dh and mh != dh:
        return f"phones are sent to {mh}, computers to {dh}"
    ms, ds = mobile.get("status", 0), desktop.get("status", 0)
    if (ms < 400) != (ds < 400):
        return f"phones get HTTP {ms}, computers get HTTP {ds}"
    a, b = _text_shingles(html_page(mobile["html"], mobile["final_url"])["body"]), _text_shingles(html_page(desktop["html"], desktop["final_url"])["body"])
    if len(a) > 40 and len(b) > 40:
        j = len(a & b) / len(a | b)
        if j < 0.15:
            return f"only {int(j * 100)}% of the text is the same"
    return None


# --------------------------------------------------------------------------- 4. browser capture

class _Browser:
    """One shared headless browser; each scan gets its own throwaway context."""

    def __init__(self) -> None:
        self.pw = None
        self.browser = None
        self.lock = asyncio.Lock()
        self.failed: str | None = None

    async def get(self):
        async with self.lock:
            if self.browser and self.browser.is_connected():
                return self.browser
            if self.failed:
                return None
            try:
                from playwright.async_api import async_playwright

                self.pw = self.pw or await async_playwright().start()
                import os

                channel = os.environ.get("RAQIB_BROWSER_CHANNEL") or None
                for ch in ([channel] if channel else [None, "chrome", "msedge"]):
                    try:
                        self.browser = await self.pw.chromium.launch(headless=True, channel=ch, args=["--disable-dev-shm-usage"])
                        return self.browser
                    except Exception as exc:
                        self.failed = str(exc)[:200]
                return None
            except Exception as exc:
                self.failed = str(exc)[:200]
                return None


    async def close(self) -> None:
        try:
            if self.browser:
                await self.browser.close()
            if self.pw:
                await self.pw.stop()
        except Exception:
            pass
        self.browser = self.pw = None


BROWSER = _Browser()


def dhash(png: bytes, size: int = 8) -> str | None:
    """64-bit difference hash of a screenshot: near-identical pages have hashes a few bits apart."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(png)).convert("L").resize((size + 1, size))
        px = list(img.getdata())
        bits = "".join("1" if px[r * (size + 1) + c] > px[r * (size + 1) + c + 1] else "0" for r in range(size) for c in range(size))
        return f"{int(bits, 2):016x}"
    except Exception:
        return None


async def browser_capture(url: str, timeout_ms: int = 20000) -> dict | None:
    browser = await BROWSER.get()
    if not browser:
        return None
    ctx = await browser.new_context(viewport={"width": 390, "height": 760}, user_agent=MOBILE_UA, is_mobile=True, has_touch=True,
                                    locale="en-AE", timezone_id="Asia/Dubai", accept_downloads=False, service_workers="block", ignore_https_errors=True)
    network: list[dict] = []
    nav_chain: list[dict] = []

    async def route(r):
        req = r.request
        if req.resource_type in ("media", "websocket", "eventsource"):
            return await r.abort()
        if req.url.startswith(("http:", "https:")) and url_error(req.url):
            return await r.abort()
        await r.continue_()

    try:
        await ctx.route("**/*", route)
        page = await ctx.new_page()
        page.on("popup", lambda p: asyncio.ensure_future(p.close()))

        def on_resp(resp):
            rq = resp.request
            item = {"method": rq.method, "url": resp.url[:300], "status": resp.status, "type": rq.resource_type}
            if len(network) < 150:
                network.append(item)
            if rq.is_navigation_request() and rq.frame == page.main_frame:
                nav_chain.append({"url": resp.url, "status": resp.status})

        page.on("response", on_resp)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        except Exception as exc:
            if not nav_chain:
                return {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}
        try:
            await page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        await page.wait_for_timeout(600)
        data = await page.evaluate(EXTRACT_JS)
        png = await page.screenshot(type="png")
        scripts = []
        for s in data["scripts"][:25]:
            if s["src"]:
                h = host_of(s["src"])
                if h in LIBRARY_HOSTS:
                    scripts.append({"src": s["src"], "sha256": hashlib.sha256(s["src"].encode()).hexdigest(), "size": 0, "library": True, "iocs": {}})
                    continue
                if url_error(s["src"]) or len([x for x in scripts if not x.get("library")]) >= 10:
                    continue
                try:
                    r = await ctx.request.get(s["src"], timeout=6000)
                    body = await r.body()
                    scripts.append({"src": s["src"], "sha256": hashlib.sha256(body).hexdigest(), "size": len(body), "iocs": ioc.extract(body.decode("utf-8", "ignore"))})
                except Exception:
                    continue
            elif s["inline"].strip():
                scripts.append({"src": "(inline script)", "sha256": hashlib.sha256(s["inline"].encode()).hexdigest(), "size": len(s["inline"]), "iocs": ioc.extract(s["inline"])})
        favicon_hash = None
        try:
            if data.get("favicon") and not url_error(data["favicon"]):
                fr = await ctx.request.get(data["favicon"], timeout=5000)
                if fr.ok:
                    favicon_hash = hashlib.sha256(await fr.body()).hexdigest()
        except Exception:
            pass
        return {"data": data, "png": png, "scripts": scripts, "network": network, "chain": nav_chain, "favicon_hash": favicon_hash}
    finally:
        await ctx.close()


# --------------------------------------------------------------------------- orchestration

def _page_from(data: dict, scripts: list[dict], network: list[dict], favicon_hash: str | None, shot_hash: str | None) -> dict:
    found = ioc.extract((data.get("body") or "") + " " + (data.get("html") or ""))
    elements = list(data.get("elements", []))
    for i, w in enumerate(found["wallets"][:3]):
        elements.append({"id": f"w{i}", "kind": "wallet", "text": w, "wallet": w})
    have_phones = {e.get("phone") for e in elements if e.get("phone")} | {e.get("whatsapp") for e in elements if e.get("whatsapp")}
    for i, ph in enumerate([p for p in found["phones"] if p not in have_phones][:3]):
        elements.append({"id": f"ph{i}", "kind": "footer", "text": ph, "phone": ph})
    for i, wa in enumerate(found["whatsapp"][:2]):
        elements.append({"id": f"wa{i}", "kind": "footer", "text": wa, "whatsapp": wa})
    return {"page_id": "p1", "url": data.get("url", ""), "title": data.get("title", ""), "lang": data.get("lang", ""), "elements": elements,
            "forms": data.get("forms", []), "scripts": scripts, "assets": [], "network": network,
            "meta": {"favicon_hash": favicon_hash, "analytics_ids": sorted(set(data.get("analytics", [])) | set(found["analytics_ids"])), "screenshot_dhash": shot_hash}}


async def scan(url: str, *, use_browser: bool = True, use_ai: bool = False, rdap: bool = True, emit=None, reg: Registry | None = None) -> dict:
    """Scan one URL end to end. `emit(kind, **data)` receives progress events when given."""
    reg = reg or load_registry()
    t0 = time.time()
    say = emit or (lambda *_a, **_k: None)
    input_url = normalise_url(url)
    err = url_error(input_url)
    if err:
        return {"input_url": input_url, "error": err, "score": 0, "verdict": "no_indicators", "label": "unknown", "seconds": 0}

    extra = url_signals(input_url, reg)
    say("progress", step="http", text=f"Following the link with a phone user-agent: {input_url}")
    mobile = await follow(input_url, MOBILE_UA)
    for hop in mobile["chain"][:-1]:
        say("request", method="GET", url=hop["url"], status=hop["status"], kind="document", flag="redirect")
    final_url = mobile["final_url"]
    if final_url != input_url:
        extra += [g for g in url_signals(final_url, reg) if g["id"] not in {x["id"] for x in extra}]

    desktop_task = asyncio.create_task(follow(input_url, DESKTOP_UA))
    infra_task = asyncio.create_task(asyncio.wait_for(infra.lookup(host_of(final_url)), timeout=12)) if rdap else None

    cap = None
    if use_browser:
        say("progress", step="browser", text="Opening the page in an isolated browser (mobile, UAE locale)")
        try:
            cap = await asyncio.wait_for(browser_capture(final_url if mobile["chain"] else input_url), timeout=40)
        except Exception as exc:
            cap = {"error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    png = None
    if cap and "data" in cap:
        png = cap["png"]
        if cap["chain"] and registrable(host_of(cap["chain"][-1]["url"])) != registrable(host_of(final_url)):
            final_url = cap["chain"][-1]["url"]  # JavaScript redirect seen only by the browser
            extra += [g for g in url_signals(final_url, reg) if g["id"] not in {x["id"] for x in extra}]
        page = _page_from(cap["data"], cap["scripts"], cap["network"], cap["favicon_hash"], dhash(png))
        engine = "browser"
    else:
        hp = html_page(mobile["html"], final_url)
        scripts = []
        for s in hp["scripts"]:
            if s["inline"].strip():
                scripts.append({"src": "(inline script)", "sha256": hashlib.sha256(s["inline"].encode()).hexdigest(), "size": len(s["inline"]), "iocs": ioc.extract(s["inline"])})
        page = _page_from(hp, scripts, [{"method": "GET", "url": h["url"], "status": h["status"], "type": "document"} for h in mobile["chain"]], None, None)
        engine = "http" if mobile["html"] else "none"

    desktop = await desktop_task
    cloak = cloaking_check(mobile, desktop)
    if cloak:
        extra.append(make_signal("http.cloaking", [{"type": "http", "value": cloak}], detail=cloak))
    try:
        info = (await infra_task) if infra_task else {}
    except Exception:
        info = {}

    host = host_of(final_url)
    chain = (cap or {}).get("chain") or mobile["chain"] or [{"url": input_url, "status": 0}]
    case = {
        "case_id": "scan_" + hashlib.sha1(final_url.encode()).hexdigest()[:10], "kind": "site", "label": host, "input_url": input_url,
        "final_url": final_url, "host": host, "source": "scan", "observed_at": date.today().isoformat(), "redirect_chain": chain,
        "pages": [page] if engine != "none" else [], "infra": info, "contacts": {}, "targeting": {"emirates": []},
        "ground_truth": {"label": "unknown", "family": None},
    }
    if final_url.startswith("http://") and any(e.get("kind") in ("input", "select") for e in page["elements"]):
        extra.append(make_signal("http.insecure_form", [{"type": "url", "value": final_url}]))
    trust = trust_of(host, reg)

    ai = None
    if use_ai and png:
        from .claude_service import service as claude

        if claude.enabled:
            say("progress", step="ai", text=f"{config.model_label()} is looking at the screenshot")
            ai = await asyncio.to_thread(claude.vision_check, png, (page.get("title") or "") + "\n" + " ".join(e.get("text", "") for e in page["elements"][:40]), host)
            if ai and ai.get("impersonates") not in (None, "none") and ai.get("confidence", 0) >= 0.7 and not trust:
                ent = reg.get(ai["impersonates"])
                if ent and not reg.official_domain_of(host):
                    extra.append(make_signal("ai.visual_brand", [{"type": "ai", "value": ai.get("reason", "")}], brand=ent.name, reason=ai.get("reason", "")[:120]))

    case["scan"] = {"extra_signals": extra, "trusted": trust, "engine": engine, "cloaking": cloak, "ai": ai,
                    "error": (cap or {}).get("error") if engine != "browser" else None, "http_error": mobile.get("error")}
    analysis = enrich(analyse(case, reg), case)
    score = final_score(analysis)
    verdict = "official" if trust and trust["kind"] in ("official", "restricted") else verdict_for(score, bool(analysis.get("official")))
    analysis.update(score=score, verdict=verdict, scam_type=classify_scam(analysis))
    return {
        "input_url": input_url, "final_url": final_url, "host": host, "chain": chain, "engine": engine, "score": score, "verdict": verdict,
        "label": "fraud" if score >= FRAUD_THRESHOLD else "legit", "scam_type": analysis["scam_type"], "brand": (analysis.get("brand") or {}).get("name"),
        "trusted": trust, "cloaking": cloak, "reasons": [g["label"] for g in sorted(analysis["signals"], key=lambda g: -g["weight"])[:5]],
        "signals": analysis["signals"], "analysis": analysis, "case": case, "png": png, "seconds": round(time.time() - t0, 1),
        "html": ((cap or {}).get("data") or {}).get("html") or mobile.get("html", ""),
        "error": None if engine != "none" else (mobile.get("error") or (cap or {}).get("error") or "page could not be loaded"),
    }


def public(result: dict) -> dict:
    """JSON-safe summary of a scan (no screenshot bytes, no full bundle)."""
    keep = ("input_url", "final_url", "host", "chain", "engine", "score", "verdict", "label", "scam_type", "brand", "trusted", "cloaking", "reasons", "seconds", "error")
    out = {k: result.get(k) for k in keep}
    out["signals"] = [{"id": g["id"], "label": g["label"], "weight": g["weight"], "severity": g["severity"]} for g in result.get("signals", [])]
    if result.get("png"):
        out["screenshot_sha256"] = hashlib.sha256(result["png"]).hexdigest()
    return out


def save_screenshot(run_id: str, name: str, png: bytes) -> Path:
    d = config.EVIDENCE_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    path = d / name
    path.write_bytes(png)
    return path


def png_b64_jpeg(png: bytes, quality: int = 72) -> str:
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(png)).convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return base64.b64encode(png).decode()

