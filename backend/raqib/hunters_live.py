"""Live discovery sources.

* Newly registered domains (WhoisDS daily feed, no key): every domain registered on the last few days
  (about 70,000 a day) is checked for protected UAE brand names. Scam domains are usually registered
  hours or days before the SMS wave, so this catches them before anyone reports them.
* Google Search, sponsored ads and Google Maps via SerpAPI (needs SERPAPI_KEY): high-intent UAE queries
  ("pay rta fine", "salik recharge" ...) and Maps listings for brand helplines.

Results are triaged with the same rules as the recorded feeds and cached for 30 minutes.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
import time
import zipfile
from datetime import date, datetime, timedelta, timezone

import httpx

from . import config, hunters
from .netutil import ssl_context
from .registry import load_registry

NRD_URL = "https://www.whoisds.com//whois-database/newly-registered-domains/{token}/nrd"
_cache: dict[str, tuple[float, dict]] = {}
TTL = 1800


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0), verify=ssl_context(), follow_redirects=True,
                             headers={"User-Agent": "Mozilla/5.0 (raqib-hunter)"})


def brand_tokens() -> tuple[set[str], set[str]]:
    """(long tokens matched as substrings, short tokens matched as whole words) from the protected-brand registry."""
    long_t, short_t = set(), set()
    for e in load_registry().entities:
        cands = {d.split(".")[0] for d in e.domains} | {re.sub(r"[^a-z0-9]", "", k.lower()) for k in e.keywords if re.fullmatch(r"[a-z0-9 &.]+", k.lower())}
        for t in cands:
            if len(t) >= 5:
                long_t.add(t)
            elif len(t) >= 3:
                short_t.add(t)
    return long_t, short_t


async def _nrd_day(client: httpx.AsyncClient, day: date) -> list[str]:
    cache = config.FEEDS_DIR / "nrd" / f"{day.isoformat()}.txt"
    if cache.is_file():
        return cache.read_text(encoding="utf-8").split()
    token = base64.b64encode(f"{day.isoformat()}.zip".encode()).decode()
    r = await client.get(NRD_URL.format(token=token))
    if r.status_code != 200 or r.content[:2] != b"PK":
        raise RuntimeError(f"no list for {day.isoformat()} (HTTP {r.status_code})")
    z = zipfile.ZipFile(io.BytesIO(r.content))
    names = z.read(z.namelist()[0]).decode("utf-8", "ignore").split()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text("\n".join(names), encoding="utf-8")
    return names


async def nrd_hunt(days: int = 3, force: bool = False) -> dict:
    """Brand look-alikes among the domains registered in the last `days` days."""
    key = f"nrd:{days}"
    if not force and key in _cache and time.time() - _cache[key][0] < TTL:
        return {**_cache[key][1], "cached": True}
    reg = load_registry()
    long_t, short_t = brand_tokens()
    today = date.today()
    errors: list[str] = []
    scanned = 0
    hits: dict[str, str] = {}
    async with _client() as client:
        for back in range(1, days + 2):  # today's list is usually published tomorrow
            day = today - timedelta(days=back)
            try:
                names = await _nrd_day(client, day)
            except Exception as exc:
                errors.append(f"{day.isoformat()}: {exc}")
                continue
            scanned += len(names)
            for n in names:
                n = n.strip().lower()
                label = n.split(".")[0]
                parts = set(re.split(r"[-\d]+", label))
                if any(t in label for t in long_t) or parts & short_t:
                    hits.setdefault(n, day.isoformat())
            if len({v for v in hits.values()}) >= days:
                break
    rows = []
    for host, day in hits.items():
        age = (today - date.fromisoformat(day)).days
        t = hunters.triage_host(host, reg, cert_age=age)
        if reg.official_domain_of(host):
            continue
        rows.append({"id": f"nrd:{host}", "source": "ct", "title": host, "host": host, "url": f"http://{host}/", "when": day,
                     "detail": f"Registered {day} ({age} day(s) ago)", "triage": t, "case_id": None, "live": True})
    rows.sort(key=lambda r: -r["triage"]["score"])
    out = {"source": "WhoisDS newly registered domains", "days": days, "scanned": scanned, "total": len(rows),
           "flagged": sum(1 for r in rows if r["triage"]["score"] >= hunters.THRESHOLD), "rows": rows[:300], "errors": errors,
           "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    _cache[key] = (time.time(), out)
    return out


# --------------------------------------------------------------------------- SerpAPI (Google Search, ads, Maps)

SEARCH_QUERIES = ["salik recharge", "pay rta fine", "dubai police fine payment", "emirates post track parcel", "aramex parcel on hold",
                  "uae pass login", "tamm abu dhabi", "adcb account blocked", "emirates nbd verify account", "instant loan uae no salary certificate",
                  "دفع مخالفات المرور", "تتبع شحنة بريد الإمارات"]
MAPS_QUERIES = ["Emirates Post customer service", "Salik customer service", "RTA customer happiness", "ADCB customer service", "Emirates NBD branch",
                "Aramex customer service Dubai", "loan agency Dubai"]


def serpapi_key() -> str:
    return os.environ.get("SERPAPI_KEY", "").strip()


async def serp_hunt(force: bool = False, search_queries: list[str] | None = None, maps_queries: list[str] | None = None) -> dict:
    """Live Google Search + sponsored ads + Maps listings through SerpAPI. Returns {"available": False} without a key.

    The radar passes a small rotating slice of queries so a monthly search budget is never exceeded."""
    key = serpapi_key()
    if not key:
        return {"available": False, "reason": "Set SERPAPI_KEY to hunt live Google Search, ads and Maps. Using the recorded feed meanwhile."}
    sliced = search_queries is not None or maps_queries is not None
    search_queries = SEARCH_QUERIES if search_queries is None else search_queries
    maps_queries = MAPS_QUERIES if maps_queries is None else maps_queries
    if not force and not sliced and "serp" in _cache and time.time() - _cache["serp"][0] < TTL:
        return {**_cache["serp"][1], "cached": True}
    reg = load_registry()
    rows: list[dict] = []
    async with _client() as client:
        async def search(q: str) -> None:
            r = await client.get("https://serpapi.com/search.json", params={"engine": "google", "q": q, "gl": "ae", "hl": "en", "location": "Abu Dhabi, United Arab Emirates", "api_key": key})
            d = r.json()
            for kind, items in (("search_ad", d.get("ads", [])), ("search", d.get("organic_results", [])[:8])):
                for it in items:
                    link = it.get("link") or ""
                    host = hunters.host_of(link)
                    t = hunters.triage_host(host, reg, title=f"{it.get('title', '')} {it.get('snippet') or it.get('description') or ''}", ad=kind == "search_ad")
                    rows.append({"id": f"serp:{q}:{link}", "source": kind, "title": it.get("title", host), "host": host, "url": link, "query": q, "live": True,
                                 "detail": f"“{q}” · {'sponsored' if kind == 'search_ad' else 'organic'} · position {it.get('position', '?')}", "triage": t, "case_id": None,
                                 "when": date.today().isoformat()})

        async def maps(q: str) -> None:
            r = await client.get("https://serpapi.com/search.json", params={"engine": "google_maps", "q": q, "ll": "@24.4539,54.3773,10z", "type": "search", "api_key": key})
            for it in r.json().get("local_results", [])[:10]:
                listing = {"name": it.get("title", ""), "category": it.get("type", ""), "area": it.get("address", ""), "emirate": "", "phone": it.get("phone"),
                           "whatsapp": None, "website": it.get("website"), "rating": it.get("rating", 0), "reviews": it.get("reviews", 0),
                           "claimed": not it.get("unclaimed_listing", False), "tags": [q.lower()]}
                t = hunters.triage_listing(listing, reg)
                rows.append({"id": f"maps:{it.get('place_id', listing['name'])}", "source": "maps", "title": listing["name"], "host": hunters.host_of(listing["website"]) if listing["website"] else "",
                             "url": listing["website"] or "", "detail": f"{listing['category']} · {listing['area']} · {listing['rating']}★ ({listing['reviews']})", "triage": t,
                             "case_id": None, "live": True, "when": date.today().isoformat(), "phone": listing["phone"]})

        results = await asyncio.gather(*(search(q) for q in search_queries), *(maps(q) for q in maps_queries), return_exceptions=True)
    errors = [f"{type(e).__name__}" for e in results if isinstance(e, Exception)]
    out = {"available": True, "rows": sorted(rows, key=lambda r: -r["triage"]["score"]), "errors": errors,
           "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if not sliced:
        _cache["serp"] = (time.time(), out)
    return out
