"""Evidence items and the chain-of-custody manifest.

Every artefact the browser records (page capture, DOM, network log, script,
WHOIS and TLS data) is hashed with SHA-256 and time-stamped when it is stored.
The manifest hash covers all items, so changing any artefact later is detectable.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone


def canonical(data) -> bytes:
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        return data.encode("utf-8")
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class EvidenceStore:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, kind: str, label: str, data, page_id: str | None = None, sha256: str | None = None) -> dict:
        raw = canonical(data)
        item = {
            "id": f"EV-{len(self.items) + 1:03d}",
            "kind": kind,
            "label": label,
            "page": page_id,
            "sha256": sha256 or hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
            "ts": now_iso(),
        }
        self.items.append(item)
        return item

    def manifest(self) -> str:
        blob = "\n".join(f"{i['id']}:{i['sha256']}" for i in sorted(self.items, key=lambda x: x["id"]))
        return hashlib.sha256(blob.encode()).hexdigest()
