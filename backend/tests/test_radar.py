"""The radar loop, offline: certificate parsing, intake, watchlist, tiers, analyst decisions, sibling patterns."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from raqib import ct, radar, scanner


def _san_der(*names: str) -> bytes:
    items = b"".join(b"\x82" + bytes([len(n)]) + n.encode() for n in names)
    seq = b"\x30" + bytes([len(items)]) + items
    return b"\x30\x00junk" + b"\x06\x03\x55\x1d\x11" + b"\x04" + bytes([len(seq)]) + seq


def _leaf(der: bytes, precert: bool) -> bytes:
    out = (123).to_bytes(8, "big") + (1 if precert else 0).to_bytes(2, "big")
    if precert:
        out += b"\x00" * 32
    out += len(der).to_bytes(3, "big") + der + (0).to_bytes(2, "big")
    if precert:
        out += (3).to_bytes(3, "big") + b"abc"
    return out + (32).to_bytes(2, "big") + b"\x11" * 32


def test_tile_parsing():
    assert ct.tile_path(1234067) == "x001/x234/067" and ct.tile_path(5) == "005"
    tile = _leaf(_san_der("salik-topup.xyz", "www.salik-topup.xyz"), False) + _leaf(_san_der("*.example.com"), True)
    assert ct.parse_tile(tile) == [["salik-topup.xyz", "www.salik-topup.xyz"], ["*.example.com"]]


@pytest.fixture
def rd(tmp_path):
    return radar.Radar(tmp_path / "radar.db")


def test_ingest_skips_official_and_dedupes(rd):
    assert not rd.ingest("www.salik.ae", "ct")
    assert rd.ingest("salik-topup-ae.xyz", "ct")
    assert not rd.ingest("salik-topup-ae.xyz", "nrd")
    row = rd.items()[0]
    assert row["state"] == "queued" and row["sources"] == ["ct", "nrd"]


def test_dead_and_parked_sites_go_on_the_watchlist(rd, monkeypatch):
    rd.ingest("salik-pay-fines.xyz", "ct")
    rd.ingest("rta-fines-pay.xyz", "ct")
    pages = {"salik": {"chain": [], "status": 0, "html": "", "final_url": ""},
             "rta": {"chain": [{"url": "x", "status": 200}], "status": 200, "html": "<h1>This domain is for sale</h1>", "final_url": "http://rta-fines-pay.xyz/"}}

    async def fake_follow(url, ua):
        return pages["salik" if "salik" in url else "rta"]

    monkeypatch.setattr(scanner, "follow", fake_follow)
    for _ in range(2):
        asyncio.run(rd.check(rd._claim()))
    rows = {r["domain"]: r for r in rd.items("watching")}
    assert rows["salik-pay-fines.xyz"]["why"] == "not online yet" and rows["rta-fines-pay.xyz"]["why"] == "parked or placeholder page"
    assert all(r["next_check"] > r["updated"] for r in rows.values())


def _ctx(score, signals, brand=True):
    return {"domain": "salik-topup-ae.xyz", "input_url": "http://salik-topup-ae.xyz/", "score": score, "brand": {"name": "Salik"} if brand else None, "manifest": "0" * 64, "evidence": [],
            "infra": {}, "signals": [{"id": s, "label": s, "weight": 0.5} for s in signals]}


def test_tiers_and_analyst_decisions(rd):
    assert rd.tier(_ctx(92, ["pay.card_form", "imp.brand_mismatch"]))[0]
    assert not rd.tier(_ctx(92, ["imp.brand_mismatch"]))[0]
    assert not rd.tier(_ctx(70, ["pay.card_form"]))[0]

    rd.ingest("salik-topup-ae.xyz", "ct")
    rd.act("salik-topup-ae.xyz", _ctx(92, ["pay.card_form"]))
    acts = {a["kind"]: a["status"] for a in rd.items()[0]["actions"]}
    assert acts == {"blocklist": "done", "safebrowsing": "drafted", "brand_alert": "drafted", "registrar": "pending", "host": "pending"}
    assert rd.blocklist() == ["salik-topup-ae.xyz"]

    rd.decide("salik-topup-ae.xyz", approve=False)
    assert rd.blocklist() == [] and rd.items()[0]["state"] == "dismissed"
    assert {a["status"] for a in rd.items()[0]["actions"]} == {"revoked", "rejected"}


def test_auto_actions_off_sends_everything_to_an_analyst(rd):
    rd.set_auto(False)
    rd.ingest("salik-topup-ae.xyz", "ct")
    rd.act("salik-topup-ae.xyz", _ctx(95, ["pay.otp_request"]))
    assert {a["status"] for a in rd.items()[0]["actions"]} == {"pending"} and rd.blocklist() == []
    rd.decide("salik-topup-ae.xyz", approve=True)
    assert rd.blocklist() == ["salik-topup-ae.xyz"]


def test_sibling_naming_pattern(rd):
    names = ["salik-recharge-ae.xyz", "salik-topup.top", "weather-today.xyz", "aramex-topup.com", "salik-topup-ae.xyz"]
    found = dict(rd.pattern_siblings("salik-topup-ae.xyz", names))
    assert set(found) == {"salik-recharge-ae.xyz", "salik-topup.top"}
