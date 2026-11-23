"""Indicator-of-compromise extraction from page text and script source.

Used by the live investigator on real page content. For recorded cases the same
indicators are stored pre-extracted in the evidence bundle.
"""

from __future__ import annotations

import re

_TG_BOT = re.compile(r"api\.telegram\.org/bot(\d{6,12}):[A-Za-z0-9_-]{20,}", re.I)
_DISCORD = re.compile(r"discord(?:app)?\.com/api/webhooks/(\d{15,22})/[A-Za-z0-9_-]{20,}", re.I)
_TRC20 = re.compile(r"\bT[1-9A-HJ-NP-Za-km-z]{33}\b")
_ERC20 = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
_BTC = re.compile(r"\b(?:bc1[a-z0-9]{25,60}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")
_PHONE = re.compile(r"(?:\+|00)?971[\s-]?\(?0?\)?[\s-]?(\d{1,2})[\s-]?(\d{3})[\s-]?(\d{4})")
_WA = re.compile(r"wa\.me/(\d{8,15})|api\.whatsapp\.com/send\?phone=(\d{8,15})", re.I)
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_GA = re.compile(r"\b(?:G-[A-Z0-9]{8,12}|UA-\d{4,10}-\d{1,3}|GTM-[A-Z0-9]{6,8})\b")
_PIXEL = re.compile(r"fbq\(\s*['\"]init['\"]\s*,\s*['\"](\d{10,18})['\"]")


def normalise_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 10:
        digits = "971" + digits[1:]
    return "+" + digits if digits else ""


def extract(text: str) -> dict:
    """Pull every shareable indicator out of a blob of text or script source."""
    phones = {normalise_phone("971" + "".join(m.groups())) for m in _PHONE.finditer(text)}
    was = {normalise_phone(a or b) for a, b in _WA.findall(text)}
    return {
        "telegram_bot_ids": sorted(set(_TG_BOT.findall(text))),
        "discord_webhook_ids": sorted(set(_DISCORD.findall(text))),
        "wallets": sorted(set(_TRC20.findall(text)) | set(_ERC20.findall(text)) | set(_BTC.findall(text))),
        "phones": sorted(p for p in phones if p),
        "whatsapp": sorted(w for w in was if w),
        "emails": sorted(set(_EMAIL.findall(text))),
        "analytics_ids": sorted(set(_GA.findall(text)) | set(_PIXEL.findall(text))),
    }
