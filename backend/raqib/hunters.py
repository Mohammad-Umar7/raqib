"""Hunters: proactive discovery of suspicious candidates before anyone reports them.

Four sources feed one triage funnel:
  search  - Google Search results and sponsored ads for high-intent queries
  maps    - Google Maps listings that claim to be a bank, courier or authority
  ct      - newly issued TLS certificates (certificate-transparency log)
  report  - citizen / hotline reports

Triage is cheap (no browser): it scores domain look-alikes, brand mentions on
unofficial domains, listing oddities and certificate age. Only candidates above
THRESHOLD are sent to the sandbox browser for a full investigation.

In this repository the feeds are recorded demo datasets; in production the same
interfaces are backed by SERP/Maps APIs and a CT log stream.
"""

from __future__ import annotations

import json
import re
from datetime import date
from functools import lru_cache

from . import config
from .detectors import LANDLINE, days_between
from .domains import LURE_WORDS, host_of, label_of, lookalike, registrable
from .ioc import normalise_phone
from .registry import Registry, load_registry

THRESHOLD = 40
# Scams that pretend to be nobody in particular (investment, loans, jobs, prizes) still leave marks:
THEME_WORDS = {"invest", "investment", "crypto", "forex", "trading", "gold", "signal", "signals", "profit", "loan", "loans", "cash", "credit",
               "visa", "jobs", "careers", "prize", "reward", "claim", "refund", "kyc", "bonus", "airdrop", "mining"}
RISKY_CATEGORIES = {"loan agency", "investment service", "money exchange", "visa services", "job agency", "recruitment agency", "car rental", "real estate"}
_PITCH = re.compile(r"guarantee[d]?.{0,24}(?:returns?|profit)|no salary certificate|approval in \d+ ?min|processing fee|risk[- ]free|double your|free visa", re.I)
RISKY_TLDS = {"xyz", "top", "click", "icu", "vip", "live", "site", "online", "shop", "buzz", "cfd", "sbs"}
OBSERVED = "2026-11-24"


def _feed(name: str) -> dict:
    return json.loads((config.FEEDS_DIR / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def blocklist() -> set[str]:
    return {registrable(d) for d in _feed("blocklist.json")["domains"]}


# Brands whose name is also an everyday word or a common foreign brand: only suspicious with UAE or lure context.
AMBIGUOUS_BRANDS = {"amazonae", "fta", "moi", "cbd", "emirates", "noon", "careem", "du", "fab", "dib", "icp", "tamm", "lulu", "dhl", "adnoc", "uae_gov", "etihad"}
UAE_MARKERS = {"ae", "uae", "dubai", "dxb", "abudhabi", "auh", "sharjah", "shj", "ajman", "rak", "fujairah", "emirati", "gov", "khaleej"}


def _uae_context(host: str) -> bool:
    tokens = {t for t in re.split(r"[-_.\d]+", host.lower()) if t}
    return bool(tokens & UAE_MARKERS) or host.endswith(".ae") or _lure_count(host) >= 1


def themes_in_label(host: str) -> bool:
    compact = re.sub(r"[^a-z]", "", label_of(host))
    return any(w in compact for w in THEME_WORDS if len(w) >= 4)


def _lure_count(host: str) -> int:
    tokens = [t for t in label_of(host).replace("_", "-").split("-") if t]
    return len({t for t in tokens if t in LURE_WORDS})


def _best_lookalike(host: str, reg: Registry) -> tuple[float, str | None, list[str]]:
    best = (0.0, None, [])
    for e in reg.entities:
        r = lookalike(host, e.domains, e.keywords + e.aliases)
        if r["official"]:
            return 0.0, None, ["official domain"]
        if r["score"] > best[0]:
            best = (r["score"], e.id, r["reasons"])
    return best


def triage_host(host: str, reg: Registry, *, title: str = "", ad: bool = False, cert_age: int | None = None,
                reported_brand: str | None = None) -> dict:
    """Score a bare domain (0-100) with human-readable reasons."""
    host = host.lower()
    if reg.official_domain_of(host):
        return {"score": 0, "reasons": [], "brand": None}
    score, reasons = 0, []
    look, brand_id, why = _best_lookalike(host, reg)
    if brand_id in AMBIGUOUS_BRANDS and not _uae_context(host):
        look, brand_id, why = 0.0, None, []  # "amazon", "tax", "emirates"... are ordinary words without a UAE or lure context
    if look >= 0.55:
        pts = int(30 + 30 * look)
        score += pts
        reasons.append({"text": f"Domain imitates a protected brand ({'; '.join(why)})", "points": pts})
    brand = reg.get(brand_id) if brand_id else None
    if not brand and (title or reported_brand):
        b, _ = reg.detect_brand(title, title, reported_brand or "")
        brand = b
    if brand and look < 0.55:
        score += 30
        reasons.append({"text": f"Names {brand.name} but the domain is not {brand.domains[0]}", "points": 30})
    if ad and brand:
        score += 15
        reasons.append({"text": "Appears as a sponsored ad on a brand search", "points": 15})
    lure = _lure_count(host)
    if lure >= 2:
        score += 10
        reasons.append({"text": f"{lure} lure words in the domain (pay, verify, fines...)", "points": 10})
    if cert_age is not None and cert_age <= 10:
        pts = 15 if brand or look >= 0.55 else (8 if themes_in_label(host) else 4)
        score += pts
        reasons.append({"text": f"Certificate issued {cert_age} days ago", "points": pts})
    compact = re.sub(r"[^a-z]", "", label_of(host))
    themes = sorted({w for w in THEME_WORDS if len(w) >= 4 and w in compact})
    if themes and not brand:
        pts = min(25, 15 * len(themes))
        score += pts
        reasons.append({"text": f"Domain uses scam-theme words ({', '.join(themes)})", "points": pts})
    if _PITCH.search(title):
        score += 30
        reasons.append({"text": "Ad or snippet makes a scam-style promise (guaranteed returns, no salary certificate, fee to release funds...)", "points": 30})
    if host.rsplit(".", 1)[-1] in RISKY_TLDS:
        score += 10
        reasons.append({"text": "High-abuse top-level domain", "points": 10})
    return {"score": min(score, 100), "reasons": reasons, "brand": brand.id if brand else None}


def triage_listing(l: dict, reg: Registry) -> dict:
    """Score a Google Maps listing."""
    score, reasons = 0, []
    brand = None
    b, _ = reg.detect_brand(l["name"], l["name"], " ".join(l.get("tags", [])))
    brand = b
    site = l.get("website")
    site_host = host_of(site) if site else None
    official_site = bool(site_host and reg.official_domain_of(site_host))
    if brand and not official_site:
        score += 25
        reasons.append({"text": f"Presents as {brand.name} but its website is not an official one" if site else f"Presents as {brand.name} with no website", "points": 25})
        if site_host:
            t = triage_host(site_host, reg, title=l["name"])
            if t["score"] >= 40:
                score += 20
                reasons.append({"text": "Website domain looks like a scam domain", "points": 20})
    contact = l.get("whatsapp") or l.get("phone")
    if contact and brand and not official_site:
        n = normalise_phone(contact)
        if not LANDLINE.match(n) and not n.startswith("+971600") and not n.startswith("+971800"):
            score += 20
            reasons.append({"text": "Support number is a mobile / WhatsApp line, not a landline", "points": 20})
    risky = l.get("category", "").lower() in RISKY_CATEGORIES
    if risky:
        score += 15
        reasons.append({"text": f"High-risk category for scams ({l['category']})", "points": 15})
        if l.get("whatsapp") and not l.get("phone"):
            score += 20
            reasons.append({"text": "Only contact route is WhatsApp", "points": 20})
        if site_host and triage_host(site_host, reg, title=l["name"])["score"] >= 40:
            score += 15
            reasons.append({"text": "Website domain looks like a scam domain", "points": 15})
    if brand or risky:
        if not l.get("claimed", True):
            score += 10
            reasons.append({"text": "Listing is unclaimed", "points": 10})
        if l.get("rating", 0) >= 4.9 and l.get("reviews", 999) < 15:
            score += 10
            reasons.append({"text": f"Near-perfect rating from only {l['reviews']} reviews", "points": 10})
    return {"score": min(score, 100), "reasons": reasons, "brand": brand.id if brand else None}


def case_index(cases: dict[str, dict]) -> dict[str, str]:
    """Map every URL / host a recorded case answers to onto its case id."""
    idx: dict[str, str] = {}
    for cid, c in cases.items():
        if c["kind"] != "site":
            continue
        idx[registrable(c["host"])] = cid
        for u in (c["input_url"], c["final_url"]):
            idx[u.rstrip("/")] = cid
        for hop in c.get("redirect_chain", []):
            idx[registrable(host_of(hop["url"]))] = cid
    return idx


def candidates(cases: dict[str, dict]) -> dict:
    """All discovery candidates from every feed, triaged, sorted by discovery order.

    Returns {"rows": [...unique sites...], "scanned": raw number of feed entries}.
    """
    reg = load_registry()
    idx = case_index(cases)
    out: list[dict] = []
    seen_hosts: set[str] = set()

    def match(url_or_host: str) -> str | None:
        return idx.get(url_or_host.rstrip("/")) or idx.get(registrable(host_of(url_or_host)))

    for entry in _feed("ct_log.json")["entries"]:
        host = entry["host"]
        age = days_between(entry["issued_at"], OBSERVED)
        t = triage_host(host, reg, cert_age=age)
        out.append({"id": f"ct:{host}", "source": "ct", "title": host, "host": host, "url": f"http://{host}/", "detail": f"Certificate issued {entry['issued_at'][:10]} ({entry['issuer']})",
                    "triage": t, "case_id": match(host), "when": entry["issued_at"]})
        seen_hosts.add(registrable(host))

    for q in _feed("search_results.json")["queries"]:
        for r in q["results"]:
            host = host_of(r["url"])
            t = triage_host(host, reg, title=r["title"] + " " + r.get("snippet", ""), ad=r["type"] == "ad")
            out.append({"id": f"s:{q['query']}:{r['rank']}", "source": "search_ad" if r["type"] == "ad" else "search", "title": r["title"], "host": host, "url": r["url"],
                        "detail": f"“{q['query']}” · rank {r['rank']} · {'sponsored' if r['type'] == 'ad' else 'organic'}", "query": q["query"],
                        "triage": t, "case_id": match(r["url"]), "when": "2026-11-24T06:00:00Z"})

    for l in _feed("maps_listings.json")["listings"]:
        t = triage_listing(l, reg)
        cid = None
        if l.get("website"):
            cid = match(l["website"])
        if not cid:  # listings without a site link to a recorded listing case by name/phone
            for k, c in cases.items():
                if c["kind"] == "maps_listing" and c["label"] == l["name"]:
                    cid = k
        out.append({"id": f"m:{l['id']}", "source": "maps", "title": l["name"], "host": host_of(l["website"]) if l.get("website") else "", "url": l.get("website") or "",
                    "detail": f"{l['category']} · {l['area']}, {l['emirate']} · {l.get('rating')}★ ({l.get('reviews')})", "emirate": l["emirate"],
                    "triage": t, "case_id": cid, "when": "2026-11-24T06:20:00Z"})

    for r in _feed("reports.json")["reports"]:
        host = host_of(r["url"])
        t = triage_host(host, reg, title=r["text"], reported_brand=r["text"])
        t["score"] = min(100, t["score"] + 10)
        t["reasons"].append({"text": "Reported by a citizen via " + r["channel"], "points": 10})
        out.append({"id": f"r:{r['id']}", "source": "report", "title": r["text"][:90], "host": host, "url": r["url"], "detail": f"{r['channel'].upper()} report · {r['emirate']}",
                    "emirate": r["emirate"], "triage": t, "case_id": match(r["url"]), "when": r["received"]})

    # Several feeds can surface the same site: keep one row per site, preferring the strongest triage.
    best: dict[str, dict] = {}
    for c in out:
        key = c["case_id"] or c["id"]
        if key not in best or c["triage"]["score"] > best[key]["triage"]["score"]:
            c.setdefault("seen_in", [])
            best[key] = c
        else:
            best[key].setdefault("seen_in", []).append(c["source"])
    for c in out:
        key = c["case_id"] or c["id"]
        if best[key] is not c and c["source"] not in best[key].setdefault("seen_in", []):
            best[key]["seen_in"].append(c["source"])
    rows = sorted(best.values(), key=lambda c: c["when"])
    return {"rows": rows, "scanned": len(out)}
