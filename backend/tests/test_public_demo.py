"""The hosted demo must never fetch a stranger's URL or accept new settings."""

import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient


def test_public_demo_locks_the_server(monkeypatch):
    monkeypatch.setenv("RAQIB_PUBLIC_DEMO", "1")
    from raqib import main
    main = importlib.reload(main)
    c = TestClient(main.app)
    assert c.get("/api/status").json()["public_demo"] is True
    assert c.post("/api/investigations", json={"url": "http://example.com/"}).status_code == 403
    assert c.post("/api/settings/key", json={"key": "sk-ant-" + "x" * 30}).status_code == 403
    assert c.post("/api/radar/control", json={"paused": True}).status_code == 403
    assert c.post("/api/batch", json={"text": "http://example.com/"}).status_code == 403
    target = main.K().demo_targets()[0]["url"]
    assert c.post("/api/investigations", json={"url": target, "speed": 0}).status_code == 200
    monkeypatch.delenv("RAQIB_PUBLIC_DEMO")
    importlib.reload(main)
