"""Certificate Transparency reader: every public HTTPS certificate is logged within minutes of issue.

Scam sites need a certificate to look real, and they get it shortly before the SMS wave, so the
names in brand-new certificates are the earliest public sign of a new scam site. This module reads
the newest entries of public "tiled" CT logs (static-ct-api: plain files of 256 entries) and returns
the host names inside each certificate. No third-party aggregator is needed.

It samples the head of each log within a bandwidth budget, and reports how much of the log it read.
"""

from __future__ import annotations

import asyncio
import os
import time

import httpx

from .netutil import ssl_context

LOG_LIST = "https://www.gstatic.com/ct/log_list/v3/log_list.json"
PREFERRED = ("Let's Encrypt", "Google")  # most scam sites use free Let's Encrypt certificates


def tile_path(n: int) -> str:
    """Tile number -> static-ct-api path: 1234067 -> 'x001/x234/067'."""
    parts = []
    while True:
        parts.insert(0, n % 1000)
        n //= 1000
        if n == 0:
            break
    return "/".join([f"x{p:03d}" for p in parts[:-1]] + [f"{parts[-1]:03d}"])


def _der_len(b: bytes, i: int) -> tuple[int, int]:
    first = b[i]
    if first < 0x80:
        return first, i + 1
    n = first & 0x7F
    return int.from_bytes(b[i + 1:i + 1 + n], "big"), i + 1 + n


def san_names(der: bytes) -> list[str]:
    """DNS names from the subjectAltName extension of a DER certificate or TBSCertificate."""
    i = der.find(b"\x06\x03\x55\x1d\x11")  # OID 2.5.29.17
    if i < 0:
        return []
    try:
        i += 5
        if der[i] == 0x01:  # optional "critical" BOOLEAN
            i += 3
        if der[i] != 0x04:
            return []
        _, i = _der_len(der, i + 1)
        if der[i] != 0x30:
            return []
        ln, i = _der_len(der, i + 1)
        end, out = i + ln, []
        while i < end:
            tag = der[i]
            ln, j = _der_len(der, i + 1)
            if tag == 0x82:  # dNSName
                out.append(der[j:j + ln].decode("ascii", "ignore").lower())
            i = j + ln
        return out
    except IndexError:
        return []


def parse_tile(data: bytes) -> list[list[str]]:
    """Host names of every entry in a static-ct-api data tile (TileLeaf records)."""
    out, i, n = [], 0, len(data)
    u = lambda a, b: int.from_bytes(data[a:b], "big")  # noqa: E731
    try:
        while i < n:
            i += 8  # timestamp
            kind = u(i, i + 2)
            i += 2
            if kind == 1:
                i += 32  # issuer key hash
            ln = u(i, i + 3)
            der = data[i + 3:i + 3 + ln]
            i += 3 + ln
            i += 2 + u(i, i + 2)  # extensions
            if kind == 1:
                i += 3 + u(i, i + 3)  # pre-certificate
            i += 2 + u(i, i + 2)  # chain fingerprints
            out.append(san_names(der))
    except IndexError:
        pass
    return out


async def pick_logs(client: httpx.AsyncClient, limit: int = 2) -> list[dict]:
    """Currently usable tiled logs, Let's Encrypt and Google first. RAQIB_CT_LOGS overrides (comma-separated URLs)."""
    env = [u.strip().rstrip("/") + "/" for u in os.environ.get("RAQIB_CT_LOGS", "").split(",") if u.strip()]
    if env:
        return [{"name": u.split("//")[1].split("/")[0], "url": u} for u in env]
    d = (await client.get(LOG_LIST)).json()
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    found = []
    for op in d.get("operators", []):
        for lg in op.get("tiled_logs", []):
            ti = lg.get("temporal_interval", {})
            if "usable" in lg.get("state", {}) and ti.get("start_inclusive", "") <= now < ti.get("end_exclusive", "9"):
                rank = PREFERRED.index(op["name"]) if op["name"] in PREFERRED else len(PREFERRED)
                found.append((rank, {"name": lg["description"], "url": lg["monitoring_url"].rstrip("/") + "/"}))
                break  # one log per operator: different CAs submit to different operators
    found.sort(key=lambda x: x[0])
    return [f for _, f in found[:limit]]


class Watcher:
    """Follows the head of a few CT logs and calls `on_names(names)` for every certificate read."""

    def __init__(self, on_names, tiles_per_min: int | None = None) -> None:
        self.on_names = on_names
        self.tiles_per_min = tiles_per_min or int(os.environ.get("RAQIB_CT_TILES_PER_MIN", "2"))
        self.logs: list[dict] = []
        self.read = 0  # certificates read
        self.logged = 0  # certificates added to the logs while we watched
        self.error: str | None = None

    async def run(self, stopped, idle=lambda: False) -> None:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0), verify=ssl_context(), headers={"User-Agent": "raqib-ct-watcher"}) as c:
            while not stopped():
                if idle():  # radar paused
                    await asyncio.sleep(5)
                    continue
                try:
                    if not self.logs:
                        self.logs = [{**lg, "next": None, "size": None} for lg in await pick_logs(c)]
                    for lg in self.logs:
                        await self._step(c, lg)
                    self.error = None
                except Exception as exc:  # keep watching; show the error in the radar status
                    self.error = f"{type(exc).__name__}: {str(exc)[:120]}"
                await asyncio.sleep(60 / max(1, self.tiles_per_min))

    async def _step(self, c: httpx.AsyncClient, lg: dict) -> None:
        size = int((await c.get(lg["url"] + "checkpoint")).text.splitlines()[1])
        if lg["size"] is not None:
            self.logged += max(0, size - lg["size"])
        lg["size"] = size
        head = size // 256 - 1  # newest full tile
        if lg["next"] is None or head - lg["next"] > 4:
            lg["next"] = head  # fell behind: jump to the newest certificates (sampling)
        if lg["next"] > head:
            return
        r = await c.get(lg["url"] + "tile/data/" + tile_path(lg["next"]))
        r.raise_for_status()
        lg["next"] += 1
        for names in parse_tile(r.content):
            self.read += 1
            if names:
                self.on_names(names)
