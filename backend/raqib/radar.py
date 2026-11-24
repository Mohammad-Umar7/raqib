"""The radar: Raqib's autonomous loop. Nobody has to paste a link.

  sensors   certificate logs (minutes after a site gets HTTPS), newly registered domains (daily),
            Google Search / ads / Maps (one rotating query at a time, inside a monthly budget)
  triage    the hunters' cheap name checks: only look-alikes of protected UAE brands go further
  probe     one quick HTTP request: is anything online yet? (parked and dead domains never reach the browser)
  scan      full sandbox investigation for live pages: case file, evidence, campaign links
  watch     not live yet / no scam content yet: checked again after 1h, 6h, 24h, 3d and 7d
  confirm   score >= 60: tiered actions + sibling search, then a daily check until the site goes offline

Actions are drafted and logged, never sent. Only hard evidence (score >= 85, a named brand and a card,
OTP, password or ID form, or a data-stealing bot) is actioned automatically; everything else, and every
takedown request, waits for an analyst. Every step is written to the audit log.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
from collections import OrderedDict, deque
from datetime import date

import httpx

from . import config, ct, hunters, hunters_live, report, scanner
from .domains import LURE_WORDS, label_of, registrable
from .netutil import MOBILE_UA, ssl_context
from .registry import load_registry

DB_PATH = config.DATA_DIR / "radar.db"
WATCH_STEPS = [3600, 6 * 3600, 86400, 3 * 86400, 7 * 86400]
LIVE_CHECK, LIVE_CHECKS = 86400, 14
HARD_EVIDENCE = {"pay.card_form", "pay.otp_request", "pay.credentials", "pay.id_request", "exfil.messaging_bot", "exfil.cross_origin_form"}
CDN_WORDS = ("cloudflare", "amazon", "google", "akamai", "fastly", "microsoft", "incapsula", "sucuri", "vercel", "netlify")
PARKED = re.compile(r"domain (?:is |may be )?for sale|buy this domain|parked (?:free|domain|by)|this domain (?:has been|is) (?:registered|parked)|"
                    r"coming soon|under construction|website is (?:not yet|currently not) (?:available|configured)|default (?:web )?page|index of /", re.I)
SOURCE_LABEL = {"ct": "certificate log", "nrd": "new-domain list", "search": "Google Search results", "search_ad": "Google sponsored ads",
                "maps": "Google Maps", "sibling": "sibling search"}
ACTIONS = [("blocklist", True), ("safebrowsing", True), ("brand_alert", True), ("registrar", False), ("host", False)]  # (kind, may run automatically)

SCHEMA = """
create table if not exists domains(domain text primary key, host text, url text, state text, sources text, first_seen real, last_seen real,
  triage int, reasons text, brand text, score int, verdict text, scam_type text, run_id text, checks int default 0, next_check real,
  content_hash text, ip text, parent text, depth int default 0, why text, tier text, updated real);
create index if not exists domains_state on domains(state, next_check);
create table if not exists actions(id integer primary key, domain text, kind text, mode text, status text, created real, decided real, by text, draft text);
create table if not exists events(id integer primary key, ts real, kind text, domain text, text text);
create table if not exists kv(k text primary key, v text);
"""


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _ago(seconds: float) -> str:
    return f"{int(seconds // 3600)} h" if seconds < 86400 else f"{int(seconds // 86400)} day(s)"


class Store:
    def __init__(self, path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self.db.executescript(SCHEMA)

    def q(self, sql: str, *args) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def x(self, sql: str, *args) -> int:
        with self.lock:
            return self.db.execute(sql, args).lastrowid or 0


class Radar:
    def __init__(self, path=DB_PATH) -> None:
        self.s = Store(path)
        self.reg = load_registry()
        self.long_t, self.short_t = hunters_live.brand_tokens()
        self.cap = _env_int("RAQIB_RADAR_SCANS_PER_HOUR", 120)
        self.ai = os.environ.get("RAQIB_RADAR_AI") == "1"
        self.ct = ct.Watcher(self._on_cert)
        self.recent: OrderedDict[str, None] = OrderedDict()  # de-duplicates certificate names
        self.corpus: deque[str] = deque(maxlen=60000)  # brand-word names from certificates, for sibling search
        self.scan_times: deque[float] = deque()
        self.sensors = {k: {"key": k, "last_run": None, "next_run": None, "seen": 0, "flagged": 0, "error": None, "on": True, "note": ""}
                        for k in ("ct", "nrd", "serp")}
        self.tasks: list[asyncio.Task] = []
        self.started = self.stopping = False
        self.day, self.counters = date.today().isoformat(), {}
        self.counters = self.kv(f"day:{self.day}", {})
        self.wake: asyncio.Event | None = None
        self.triggers: dict[str, asyncio.Event] = {}

    # ------------------------------------------------------------------ small helpers

    def kv(self, k: str, default=None):
        r = self.s.q("select v from kv where k=?", k)
        return json.loads(r[0]["v"]) if r else default

    def kv_put(self, k: str, v) -> None:
        self.s.x("insert into kv(k,v) values(?,?) on conflict(k) do update set v=excluded.v", k, json.dumps(v))

    @property
    def paused(self) -> bool:
        return bool(self.kv("paused", False))

    @property
    def auto_actions(self) -> bool:
        return bool(self.kv("auto_actions", True))

    def bump(self, k: str, n: int = 1) -> None:
        today = date.today().isoformat()
        if today != self.day:
            self.kv_put(f"day:{self.day}", self.counters)
            self.day, self.counters = today, {}
        self.counters[k] = self.counters.get(k, 0) + n

    def log(self, kind: str, domain: str | None, text: str, by: str = "radar") -> None:
        self.s.x("insert into events(ts,kind,domain,text) values(?,?,?,?)", time.time(), kind, domain, text if by == "radar" else f"{text} (by {by})")

    def _set(self, dom: str, **f) -> None:
        f["updated"] = time.time()
        self.s.x(f"update domains set {', '.join(k + '=?' for k in f)} where domain=?", *f.values(), dom)

    def brand_words(self, text: str) -> set[str]:
        parts = set(re.split(r"[-.\d]+", text))
        return {t for t in self.long_t if t in text} | (parts & self.short_t)

    def _brand_name(self, brand_id: str | None) -> str | None:
        e = self.reg.get(brand_id) if brand_id else None
        return e.name if e else None

    # ------------------------------------------------------------------ intake

    def ingest(self, host: str, source: str, triage: dict | None = None, url: str | None = None, parent: str | None = None,
               why: str | None = None, boost: int = 0, depth: int = 0) -> bool:
        """Add a candidate to the queue. Returns False for known, official or trusted domains."""
        host = host.lower().strip().strip(".").removeprefix("*.")
        dom = registrable(host)
        if not dom or "." not in dom or dom.endswith(".test") or scanner.trust_of(host, self.reg):
            return False
        t = triage or hunters.triage_host(host, self.reg)
        now = time.time()
        old = self.s.q("select sources from domains where domain=?", dom)
        if old:
            srcs = sorted(set(json.loads(old[0]["sources"])) | {source})
            self.s.x("update domains set sources=?, last_seen=?, triage=max(triage,?) where domain=?", json.dumps(srcs), now, min(100, t["score"] + boost), dom)
            return False
        self.s.x("insert into domains(domain,host,url,state,sources,first_seen,last_seen,triage,reasons,brand,parent,depth,why,checks,updated) "
                 "values(?,?,?,'queued',?,?,?,?,?,?,?,?,?,0,?)", dom, host, url or f"http://{host}/", json.dumps([source]), now, now,
                 min(100, t["score"] + boost), json.dumps(t["reasons"][:4]), self._brand_name(t.get("brand")), parent, depth, why, now)
        self.bump("flagged")
        self.log("found", dom, f"Spotted {host} in the {SOURCE_LABEL.get(source, source)}" + (f" ({why})" if why else "") + f", triage score {min(100, t['score'] + boost)}")
        if self.wake:
            self.wake.set()
        return True

    def _on_cert(self, names: list[str]) -> None:
        self.bump("certs")
        for n in names:
            n = n.removeprefix("*.")
            dom = registrable(n)
            if dom in self.recent:
                continue
            self.recent[dom] = None
            if len(self.recent) > 200_000:
                self.recent.popitem(last=False)
            self.bump("names")
            if not self.brand_words(n.rsplit(".", 1)[0]):
                continue
            self.corpus.append(dom)
            t = hunters.triage_host(n, self.reg, cert_age=0)
            if t["score"] >= hunters.THRESHOLD:
                self.sensors["ct"]["flagged"] += self.ingest(n, "ct", t, why="certificate issued minutes ago")

    # ------------------------------------------------------------------ sensors

    async def _sleep(self, key: str, seconds: float) -> None:
        ev = self.triggers[key]
        try:
            await asyncio.wait_for(ev.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass
        ev.clear()

    async def _every(self, key: str, interval, job, first: float = 8) -> None:
        st, delay = self.sensors[key], first
        while not self.stopping:
            st["next_run"] = time.time() + delay
            await self._sleep(key, delay)
            if self.stopping:
                break
            if self.paused and not st.pop("force", False):
                delay = 30
                continue
            st.pop("force", None)
            try:
                await job(st)
                st["error"] = None
            except Exception as exc:  # a broken feed must not stop the radar
                st["error"] = f"{type(exc).__name__}: {str(exc)[:160]}"
            st["last_run"] = time.time()
            delay = interval()

    async def _ct_loop(self) -> None:
        st = self.sensors["ct"]
        task = asyncio.create_task(self.ct.run(lambda: self.stopping, lambda: self.paused))
        while not self.stopping:
            st.update(seen=self.ct.read, error=self.ct.error, last_run=time.time(),
                      note=", ".join(lg["name"] for lg in self.ct.logs) or "connecting to the logs")
            st["coverage"] = round(self.ct.read / self.ct.logged, 3) if self.ct.logged else None
            await asyncio.sleep(3)
        task.cancel()

    async def _nrd(self, st: dict) -> None:
        res = await hunters_live.nrd_hunt(days=2, force=True)
        if not res["scanned"] and res["errors"]:
            raise RuntimeError(res["errors"][0])
        st["seen"] = res["scanned"]
        self.counters["nrd"] = res["scanned"]
        for r in res["rows"]:
            if r["triage"]["score"] >= hunters.THRESHOLD:
                st["flagged"] += self.ingest(r["host"], "nrd", r["triage"], why=r["detail"].lower())

    def _serp_interval(self) -> float:
        if not hunters_live.serpapi_key():
            return 3600
        return max(900, 30 * 86400 / max(1, _env_int("SERPAPI_MONTHLY_BUDGET", 250)))  # one search per slot

    async def _serp(self, st: dict) -> None:
        if not hunters_live.serpapi_key():
            st.update(on=False, note="Add SERPAPI_KEY to watch Google Search, ads and Maps")
            return
        st["on"] = True
        queries = [("s", q) for q in hunters_live.SEARCH_QUERIES] + [("m", q) for q in hunters_live.MAPS_QUERIES]
        i = self.kv("serp_i", 0) % len(queries)
        self.kv_put("serp_i", i + 1)
        kind, q = queries[i]
        res = await hunters_live.serp_hunt(force=True, search_queries=[q] if kind == "s" else [], maps_queries=[q] if kind == "m" else [])
        rows = res.get("rows", [])
        st["seen"] += len(rows)
        st["note"] = f"Last query: “{q}” · {_env_int('SERPAPI_MONTHLY_BUDGET', 250)} searches a month"
        for r in rows:
            if r.get("host") and r["triage"]["score"] >= hunters.THRESHOLD:
                st["flagged"] += self.ingest(r["host"], r["source"], r["triage"], url=r.get("url") or None, why=r["detail"])

    def run_now(self, key: str) -> None:
        if key in self.triggers:
            self.sensors[key]["force"] = True
            self.triggers[key].set()

    # ------------------------------------------------------------------ checking

    def _claim(self) -> dict | None:
        with self.s.lock:
            db = self.s.db
            r = db.execute("select * from domains where state='queued' order by triage desc, first_seen limit 1").fetchone() or \
                db.execute("select * from domains where state in ('watching','confirmed') and next_check<=? order by next_check limit 1", (time.time(),)).fetchone()
            if r:
                db.execute("update domains set state='checking' where domain=?", (r["domain"],))
            return dict(r) if r else None

    async def _worker(self) -> None:
        while not self.stopping:
            if self.paused:
                await asyncio.sleep(3)
                continue
            now = time.time()
            while self.scan_times and now - self.scan_times[0] > 3600:
                self.scan_times.popleft()
            item = self._claim() if len(self.scan_times) < self.cap else None
            if not item:
                self.wake.clear()
                try:
                    await asyncio.wait_for(self.wake.wait(), 15)
                except asyncio.TimeoutError:
                    pass
                continue
            try:
                await self.check(item)
            except Exception as exc:
                self.log("error", item["domain"], f"Check of {item['domain']} failed: {type(exc).__name__}: {str(exc)[:120]}")
                self._watch(item, "check failed")

    def _watch(self, it: dict, why: str, chash: str | None = None) -> None:
        dom, n = it["domain"], it["checks"] or 0
        if n >= len(WATCH_STEPS):
            self._set(dom, state="cleared", why=f"{why}; stopped watching after 7 days", next_check=None)
            self.log("cleared", dom, f"Stopped watching {dom}: still {why} after 7 days")
            return
        self._set(dom, state="watching", why=why, checks=n + 1, next_check=time.time() + WATCH_STEPS[n], content_hash=chash or it["content_hash"])
        if it["state"] == "queued":
            self.log("watch", dom, f"Watching {dom}: {why}. Checking again in {_ago(WATCH_STEPS[n])}")

    async def check(self, it: dict) -> None:
        from .investigations import manager

        dom, url, state = it["domain"], it["url"], it["state"]
        probe = await scanner.follow(url, MOBILE_UA)
        alive = bool(probe["chain"]) and 0 < probe["status"] < 400
        text = scanner.html_page(probe["html"], probe["final_url"])["body"] if probe["html"] else ""
        chash = hashlib.sha1(re.sub(r"\d+", "", text).encode()).hexdigest()[:16] if text else None
        self.bump("probed")
        if state == "confirmed":  # after action: is it still up?
            if not alive:
                self._set(dom, state="down", next_check=None)
                self.bump("down")
                self.log("down", dom, f"{dom} is offline now ({'HTTP ' + str(probe['status']) if probe['status'] else 'no answer'}): taken down or abandoned")
            else:
                n = (it["checks"] or 0) + 1
                self._set(dom, state="confirmed", checks=n, next_check=time.time() + LIVE_CHECK if n < LIVE_CHECKS else None)
            return
        if not alive:
            return self._watch(it, "not online yet" if not probe["chain"] else f"answers HTTP {probe['status']}")
        if state == "watching" and chash and chash == it["content_hash"]:
            return self._watch(it, it["why"] or "page unchanged", chash)
        if PARKED.search(text[:5000]):
            return self._watch(it, "parked or placeholder page", chash)

        self.scan_times.append(time.time())
        self.bump("scanned")
        run = manager.start(url, mode="scan", speed=0, ai=self.ai)
        self._set(dom, run_id=run.id)
        self.log("scan", dom, f"{dom} is online: investigating it in the sandbox browser")
        await run.task
        ctx = (run.result or {}).get("ctx")
        if not ctx:
            return self._watch(it, f"scan failed ({run.error or 'no result'})", chash)
        brand = (ctx.get("brand") or {}).get("name")
        fields = dict(score=ctx["score"], verdict=ctx["verdict"], scam_type=ctx["scam_type"], brand=brand or it["brand"],
                      ip=(ctx.get("infra") or {}).get("ip"), content_hash=chash)
        if ctx["verdict"] == "official" or (ctx.get("scan") or {}).get("trusted"):
            self._set(dom, state="cleared", why="legitimate site", next_check=None, **fields)
            self.log("cleared", dom, f"{dom} is a legitimate site")
        elif ctx["score"] >= scanner.FRAUD_THRESHOLD:
            self._set(dom, state="confirmed", why=None, checks=0, next_check=time.time() + LIVE_CHECK, **fields)
            self.bump("confirmed")
            self.log("confirmed", dom, f"Confirmed scam: {dom} scored {ctx['score']}" + (f" and imitates {brand}" if brand else ""))
            self.act(dom, ctx)
            await self.siblings(dom, ctx, it["depth"] or 0)
        else:
            self._set(dom, **fields)
            self._watch(it, f"no scam content yet (score {ctx['score']})", chash)

    # ------------------------------------------------------------------ actions

    def tier(self, ctx: dict) -> tuple[bool, str]:
        hard = sorted({g["id"] for g in ctx["signals"]} & HARD_EVIDENCE)
        if ctx["score"] >= 85 and ctx.get("brand") and hard:
            return True, f"score {ctx['score']}, imitates {ctx['brand']['name']}, " + ", ".join(next(g["label"] for g in ctx["signals"] if g["id"] == h).lower() for h in hard)
        missing = [m for m, ok in (("score below 85", ctx["score"] >= 85), ("no protected brand named", ctx.get("brand")), ("no card, OTP, password or ID form", hard)) if not ok]
        return False, ", ".join(missing)

    def _draft(self, kind: str, ctx: dict) -> dict:
        if kind in ("registrar", "host", "safebrowsing"):
            return report.takedown_draft(ctx, kind)
        brand = (ctx.get("brand") or {}).get("name", "")
        if kind == "brand_alert":
            return {"to": f"{brand} security team", "subject": f"Site imitating {brand}: {ctx['domain']}",
                    "body": f"Raqib found {ctx['domain']} imitating {brand} (risk score {ctx['score']}). The case file and evidence hashes are attached.\n"
                            "This is a draft prepared by Raqib for officer review. It has not been sent."}
        return {"entry": ctx["domain"], "feed": "/api/radar/blocklist.txt"}

    def act(self, dom: str, ctx: dict) -> None:
        hard, why = self.tier(ctx)
        auto = hard and self.auto_actions
        brand = (ctx.get("brand") or {}).get("name")
        for kind, may_auto in ACTIONS:
            if kind == "brand_alert" and not brand:
                continue
            run_now = auto and may_auto
            self.s.x("insert into actions(domain,kind,mode,status,created,by,draft) values(?,?,?,?,?,?,?)", dom, kind, "auto" if run_now else "approval",
                     ("done" if kind == "blocklist" else "drafted") if run_now else "pending", time.time(), "radar", json.dumps(self._draft(kind, ctx), ensure_ascii=False))
        self._set(dom, tier="auto" if auto else "approval")
        if auto:
            self.bump("auto")
            self.log("auto", dom, f"Hard evidence ({why}): added {dom} to the blocklist feed and drafted reports to Google Safe Browsing"
                                  + (f" and {brand}" if brand else "") + ". Registrar and host takedowns wait for an analyst")
        else:
            self.log("approval", dom, f"{dom} waits for an analyst: " + (why if not hard else "automatic actions are switched off"))

    def decide(self, dom: str, approve: bool, by: str = "analyst") -> None:
        if approve:
            self.s.x("update actions set status='approved', decided=?, by=? where domain=? and status='pending'", time.time(), by, dom)
            self.log("approved", dom, f"Approved actions for {dom}: blocklist entry and takedown drafts are ready to send", by)
        else:
            self.s.x("update actions set status=case when status='pending' then 'rejected' else 'revoked' end, decided=?, by=? where domain=? and status!='rejected'",
                     time.time(), by, dom)
            self._set(dom, state="dismissed", next_check=None, why="marked not a scam by an analyst")
            self.log("dismissed", dom, f"Marked {dom} as not a scam: removed from the blocklist feed, drafts withdrawn", by)

    def blocklist(self) -> list[str]:
        return [r["domain"] for r in self.s.q("select distinct a.domain from actions a join domains d on d.domain=a.domain "
                                               "where a.kind='blocklist' and a.status in ('done','approved') and d.state!='dismissed' order by a.domain")]

    # ------------------------------------------------------------------ sibling search

    def _new_names(self) -> list[str]:
        """Brand-new domains seen recently: certificate names plus the cached new-domain lists."""
        names = list(self.corpus)
        nrd_dir = config.FEEDS_DIR / "nrd"
        for path in sorted(nrd_dir.glob("*.txt"))[-3:] if nrd_dir.is_dir() else []:
            names += path.read_text(encoding="utf-8").split()
        return names

    def pattern_siblings(self, dom: str, names: list[str], limit: int = 20) -> list[tuple[str, str]]:
        """Domains with the same brand word and the same TLD or lure word: 'salik-topup-ae.xyz' -> 'salik-recharge-ae.xyz'."""
        lab, tld = label_of(dom), dom.rsplit(".", 1)[-1]
        brands = self.brand_words(lab)
        lures = set(re.split(r"[-\d]+", lab)) & LURE_WORDS
        out, seen = [], {dom}
        for n in names:
            n = registrable(n.lower())
            if n in seen or not brands:
                continue
            cl = label_of(n)
            b = {x for x in brands if x in cl}
            if not b:
                continue
            shared = set(re.split(r"[-\d]+", cl)) & lures
            if n.rsplit(".", 1)[-1] == tld or shared:
                seen.add(n)
                out.append((n, f"same naming pattern as {dom} (brand word '{sorted(b)[0]}'" + (f", .{tld}" if n.endswith("." + tld) else f", '{sorted(shared)[0]}'") + ")"))
                if len(out) >= limit:
                    break
        return out

    async def _reverse_ip(self, ip: str) -> list[str]:
        """Other domains on the same server (HackerTarget free API, at most 20 lookups a day)."""
        used = self.kv(f"revip:{date.today().isoformat()}", 0)
        if used >= 20:
            return []
        self.kv_put(f"revip:{date.today().isoformat()}", used + 1)
        try:
            async with httpx.AsyncClient(timeout=15, verify=ssl_context()) as c:
                r = await c.get("https://api.hackertarget.com/reverseiplookup/", params={"q": ip})
            lines = [ln.strip().lower() for ln in r.text.splitlines() if ln.strip()]
            return [] if not lines or " " in lines[0] else lines
        except httpx.HTTPError:
            return []

    async def siblings(self, dom: str, ctx: dict, depth: int) -> None:
        if depth >= 2:
            return
        found = 0
        for r in ctx.get("related", []):  # same kit file, Telegram bot, wallet, phone... as a site Raqib already scanned
            if r.get("kind") == "site" and r["strength"] in ("strong", "medium") and str(r.get("case_id", "")).startswith("scan_"):
                found += self.ingest(r["host"], "sibling", parent=dom, depth=depth + 1, boost=20, why=f"linked to {dom}: {r['reasons'][0]['text'].lower()}")
        for n, why in self.pattern_siblings(dom, self._new_names()):
            found += self.ingest(n, "sibling", parent=dom, depth=depth + 1, boost=15, why=why)
        infra = ctx.get("infra") or {}
        ip = infra.get("ip")
        if ip and not any(w in (infra.get("asn_org") or "").lower() for w in CDN_WORDS):
            names = await self._reverse_ip(ip)
            for n in names[:300]:
                if self.brand_words(n.rsplit(".", 1)[0]) or len(names) <= 25:
                    found += self.ingest(n, "sibling", parent=dom, depth=depth + 1, boost=10, why=f"same server ({ip}) as {dom}")
        self.log("siblings", dom, f"Sibling search from {dom}: {found} new candidate(s) queued" if found else f"Sibling search from {dom}: nothing new yet")

    # ------------------------------------------------------------------ lifecycle and views

    async def _housekeeping(self) -> None:
        while not self.stopping:
            self.kv_put(f"day:{self.day}", self.counters)
            await asyncio.sleep(30)

    def start(self) -> None:
        if self.started:
            return
        self.started, self.stopping = True, False
        self.wake = asyncio.Event()
        self.triggers = {k: asyncio.Event() for k in self.sensors}
        self.s.x("update domains set state='queued' where state='checking'")  # interrupted by a restart
        self.log("system", None, "Radar started: watching certificate logs, new domains and Google Search / Maps")
        jobs = [self._ct_loop(), self._every("nrd", lambda: 6 * 3600, self._nrd), self._every("serp", self._serp_interval, self._serp, first=20),
                self._housekeeping()] + [self._worker() for _ in range(_env_int("RAQIB_RADAR_WORKERS", 2))]
        self.tasks = [asyncio.create_task(j) for j in jobs]

    async def stop(self) -> None:
        self.stopping = True
        self.kv_put(f"day:{self.day}", self.counters)
        for t in self.tasks:
            t.cancel()
        self.tasks, self.started = [], False

    def set_paused(self, paused: bool, by: str = "analyst") -> None:
        self.kv_put("paused", paused)
        self.log("system", None, "Radar paused: no feeds read, no sites checked" if paused else "Radar resumed", by)

    def set_auto(self, on: bool, by: str = "analyst") -> None:
        self.kv_put("auto_actions", on)
        self.log("system", None, "Automatic actions switched on (hard evidence only)" if on else "Automatic actions switched off: everything waits for an analyst", by)

    def snapshot(self) -> dict:
        states = {r["state"]: r["n"] for r in self.s.q("select state, count(*) n from domains group by state")}
        pending = self.s.q("select count(distinct domain) n from actions where status='pending'")[0]["n"]
        sensors = [{k: v for k, v in s.items() if k != "force"} for s in self.sensors.values()]
        return {"started": self.started, "paused": self.paused, "auto_actions": self.auto_actions, "ai": self.ai, "cap": self.cap,
                "scans_last_hour": len(self.scan_times), "today": self.counters, "states": states, "pending": pending, "sensors": sensors,
                "blocklisted": len(self.blocklist()), "events": self.s.q("select * from events order by id desc limit 60")}

    def items(self, view: str = "all", limit: int = 300) -> list[dict]:
        where = {"approval": "domain in (select domain from actions where status='pending')", "auto": "tier='auto'",
                 "watching": "state in ('queued','checking','watching')", "confirmed": "state in ('confirmed','down')",
                 "dismissed": "state in ('dismissed','cleared')"}.get(view, "1=1")
        rows = self.s.q(f"select * from domains where {where} order by coalesce(score, triage) desc, last_seen desc limit ?", limit)
        if rows:
            acts: dict[str, list] = {}
            marks = ",".join("?" * len(rows))
            for a in self.s.q(f"select id,domain,kind,mode,status,created,decided,by,draft from actions where domain in ({marks}) order by id", *[r["domain"] for r in rows]):
                acts.setdefault(a["domain"], []).append({**a, "draft": json.loads(a["draft"] or "{}")})
            for r in rows:
                r["sources"], r["reasons"], r["actions"] = json.loads(r["sources"] or "[]"), json.loads(r["reasons"] or "[]"), acts.get(r["domain"], [])
        return rows


_radar: Radar | None = None


def get() -> Radar:
    global _radar
    if _radar is None:
        _radar = Radar()
    return _radar
