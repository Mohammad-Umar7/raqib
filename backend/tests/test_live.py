"""Exercise the live executor against a harmless local page with a scripted stand-in for Claude.

No API key or network is needed: `live._create` is replaced by a fake model that issues
browser-toolset calls. The test proves the guardrails: typing into a card field is refused,
typing into an ordinary field works, and evidence is recorded either way.
"""

import asyncio
import functools
import http.server
import socketserver
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from raqib import config, knowledge, live
from raqib.events import Run

HOME = b"""<!doctype html><title>Parcel tracking</title><h1>Track your parcel</h1><p>Enter your tracking number below.</p>
<form id="t"><label for="trk">Tracking number</label><input id="trk" name="tracking" placeholder="AE1234"><button type="button">Track</button></form>
<a class="btn" href="/pay.html">Pay delivery fee</a>"""
PAY = b"""<!doctype html><title>Pay</title><h2>Delivery fee AED 7.50</h2>
<form id="p"><label for="cn">Card number</label><input id="cn" name="cardnumber" autocomplete="cc-number" placeholder="1234 5678 9012 3456">
<input name="cvv" autocomplete="cc-csc" placeholder="CVV"><button type="submit">Pay</button></form>"""


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = PAY if self.path.startswith("/pay") else HOME
        if self.path == "/favicon.ico":
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def site():
    srv = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


@dataclass
class Block:
    type: str
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)
    text: str = ""

    def model_dump(self, exclude_none=True):
        d = {"type": self.type}
        if self.type == "tool_use":
            d.update(id=self.id, name=self.name, input=self.input, toolset_name="browser")
        else:
            d["text"] = self.text
        return d


@dataclass
class Resp:
    content: list
    stop_reason: str = "tool_use"


def script(site_url):
    """What a well-behaved agent would do, plus one attempt to type a card number."""
    steps = [
        [Block("text", text="Opening the page."), Block("tool_use", "t1", "navigate", {"url": site_url})],
        [Block("tool_use", "t2", "read_page", {"filter": "interactive"})],
        [Block("tool_use", "t3", "left_click", {"target": {"type": "ref", "ref": "ref_1"}}), Block("tool_use", "t4", "type", {"text": "AE1234"})],
        [Block("tool_use", "t5", "left_click", {"target": {"type": "ref", "ref": "ref_3"}})],
        [Block("tool_use", "t6", "read_page", {"filter": "interactive"})],
        [Block("tool_use", "t7", "left_click", {"target": {"type": "ref", "ref": "ref_1"}}), Block("tool_use", "t8", "type", {"text": "4111111111111111"})],
        [Block("text", text="The site asks for a card number and CVV.")],
    ]
    return iter(steps)


def test_guardrails_and_evidence(site, monkeypatch, tmp_path):
    monkeypatch.setattr(config, "EVIDENCE_DIR", tmp_path)
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path)
    monkeypatch.setenv("RAQIB_ALLOW_PRIVATE", "1")
    monkeypatch.setattr(config, "anthropic_key", lambda: "sk-ant-test-key-000000000000")
    steps = script(site)
    seen_results: list = []

    async def fake_create(client, **kw):
        msgs = kw["messages"]
        if len(msgs) > 1:
            seen_results.append(msgs[-1]["content"])
        blocks = next(steps)
        return Resp(blocks, "tool_use" if any(b.type == "tool_use" for b in blocks) else "end_turn")

    monkeypatch.setattr(live, "_create", fake_create)

    async def go():
        from raqib.claude_service import service

        assert service.enabled
        run = Run("t1", site, "live")
        await live.run_live(run, site, knowledge.Knowledge(), 0)
        run.finish()
        return run

    run = asyncio.run(go())
    types = [e["type"] for e in run.events]
    assert "frame" in types and "evidence" in types and "done" in types
    # the typed tracking number went through; the card number was refused by policy
    flat = [r for batch in seen_results for r in batch]
    blocked = [r for r in flat if r.get("is_error") and "policy blocks" in str(r["content"])]
    assert blocked, "typing into the card field must be refused"
    typed_ok = [r for r in flat if not r.get("is_error") and r["content"] == [{"type": "text", "text": "Typed the text."}]]
    assert typed_ok, "typing into an ordinary field must work"
    # detectors saw the card form on the second page
    ids = {e["data"]["id"] for e in run.events if e["type"] == "signal"}
    assert "pay.card_form" in ids
    assert run.result["ctx"]["manifest"]


def test_url_policy():
    assert live.url_error("file:///etc/passwd")
    assert live.url_error("javascript:alert(1)")
    assert live.url_error("http://127.0.0.1/")
    assert live.url_error("http://169.254.169.254/latest/meta-data")
    assert live.url_error("https://example.com/") is None
