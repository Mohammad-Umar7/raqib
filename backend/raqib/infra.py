"""Best-effort infrastructure lookups for live investigations (DNS + public RDAP)."""

from __future__ import annotations

import asyncio
import socket

import httpx

from .domains import registrable
from .netutil import ssl_context


async def lookup(host: str) -> dict:
    """IP, registration date, registrar, name servers and hosting info. Every field is optional."""
    out: dict = {}
    try:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, None, socket.AF_INET)
        out["ip"] = infos[0][4][0]
    except OSError:
        pass
    domain = registrable(host)
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True, verify=ssl_context(), headers={"User-Agent": "raqib-investigator"}) as c:
            r = await c.get(f"https://rdap.org/domain/{domain}")
            if r.status_code == 200:
                d = r.json()
                for ev in d.get("events", []):
                    if ev.get("eventAction") == "registration":
                        out["domain_created"] = ev["eventDate"][:10]
                out["nameservers"] = sorted(n["ldhName"].lower() for n in d.get("nameservers", []) if n.get("ldhName"))
                for ent in d.get("entities", []):
                    if "registrar" in ent.get("roles", []):
                        for item in ent.get("vcardArray", [None, []])[1]:
                            if item[0] == "fn":
                                out["registrar"] = item[3]
                for ev in d.get("events", []):
                    if ev.get("eventAction") == "expiration":
                        out["domain_expires"] = ev["eventDate"][:10]
            if out.get("ip"):
                r = await c.get(f"https://rdap.org/ip/{out['ip']}")
                if r.status_code == 200:
                    d = r.json()
                    out["asn_org"] = d.get("name")
                    out["country"] = d.get("country")
    except (httpx.HTTPError, ValueError, KeyError, IndexError):
        pass
    return out
