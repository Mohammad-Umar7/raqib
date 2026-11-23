"""Per-investigation event log, streamed to the dashboard over Server-Sent Events."""

from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncIterator


class Run:
    """One investigation: an append-only list of events plus its final result."""

    def __init__(self, run_id: str, input_url: str, mode: str) -> None:
        self.id = run_id
        self.input_url = input_url
        self.mode = mode
        self.events: list[dict] = []
        self.result: dict[str, Any] = {}
        self.finished = False
        self.error: str | None = None
        self.started = time.time()
        self.task: asyncio.Task | None = None
        self.cancelled = False

    def emit(self, type_: str, **data: Any) -> dict:
        ev = {"id": len(self.events), "t": round(time.time() - self.started, 2), "type": type_, "data": data}
        self.events.append(ev)
        return ev

    def finish(self, error: str | None = None) -> None:
        self.error = error
        self.finished = True

    async def stream(self, after: int = -1) -> AsyncIterator[dict | None]:
        """Yield every event after index `after`, then new ones as they arrive. Yields None as a keep-alive."""
        idx = after + 1
        idle = 0
        while True:
            if idx < len(self.events):
                yield self.events[idx]
                idx += 1
                idle = 0
                continue
            if self.finished:
                return
            await asyncio.sleep(0.05)
            idle += 1
            if idle % 300 == 0:
                yield None
