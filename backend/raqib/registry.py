"""Protected-entity registry: the UAE organisations scammers pretend to be."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache

from . import config
from .domains import is_official


@dataclass
class Entity:
    id: str
    name: str
    name_ar: str
    sector: str
    scam_type: str
    emirate: str
    domains: list[str]
    keywords: list[str]
    aliases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    def mentions(self, text: str) -> int:
        """How many times this entity is named in `text` (EN keywords on word boundaries, AR as substring)."""
        low = text.lower()
        total = 0
        for kw in [*self.keywords, *self.aliases, self.name]:
            k = kw.lower().strip()
            if not k:
                continue
            if re.fullmatch(r"[a-z0-9&. ]+", k):
                total += len(re.findall(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", low))
            else:
                total += low.count(k)
        return total


class Registry:
    def __init__(self, entities: list[Entity]):
        self.entities = entities
        self._by_id = {e.id: e for e in entities}

    def get(self, entity_id: str) -> Entity | None:
        return self._by_id.get(entity_id)

    def detect_brand(self, title: str, headline_text: str, body_text: str) -> tuple[Entity | None, float]:
        """Which protected entity does this page claim to be? Returns (entity, confidence 0..1)."""
        best: Entity | None = None
        best_score = 0.0
        for e in self.entities:
            s = 3 * e.mentions(title) + 3 * e.mentions(headline_text) + e.mentions(body_text)
            if s > best_score:
                best, best_score = e, float(s)
        if best is None or best_score < 3:
            return None, 0.0
        return best, round(min(0.99, 0.45 + 0.08 * best_score), 2)

    def official_domain_of(self, host: str) -> Entity | None:
        for e in self.entities:
            if is_official(host, e.domains):
                return e
        return None

    def to_list(self) -> list[dict]:
        return [e.to_dict() for e in self.entities]


@lru_cache(maxsize=1)
def load_registry() -> Registry:
    raw = json.loads((config.DATA_DIR / "registry.json").read_text(encoding="utf-8"))
    return Registry([Entity(**e) for e in raw["entities"]])
