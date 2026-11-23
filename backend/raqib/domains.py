"""Domain helpers: registrable-domain parsing and look-alike scoring."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

# Second-level suffixes that need three labels to form a registrable domain.
_SECOND_LEVEL = {
    "co.uk", "org.uk", "gov.uk", "ac.uk", "com.au", "co.in", "co.za", "com.br",
    "gov.ae", "co.ae", "net.ae", "org.ae", "ac.ae", "sch.ae", "ae.org", "com.sa", "gov.sa",
    "com.tr", "com.cn", "co.jp",
}

# Characters attackers swap to imitate a brand name.
_HOMOGLYPHS = str.maketrans({"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "$": "s", "@": "a"})
_DIGRAPHS = (("rn", "m"), ("vv", "w"), ("cl", "d"))

# Words scammers add to a brand to make a domain look official.
LURE_WORDS = {
    "pay", "payment", "payments", "fine", "fines", "topup", "top-up", "recharge", "verify", "verification",
    "secure", "support", "help", "login", "account", "refund", "service", "services", "online", "portal",
    "track", "tracking", "parcel", "redelivery", "delivery", "update", "ae", "uae", "dubai", "abudhabi",
    "gov", "official", "customer", "care", "bill", "bills", "claim", "reward", "prize",
}


def host_of(url: str) -> str:
    """Lower-case host of a URL (accepts bare hosts too)."""
    if "://" not in url:
        url = "http://" + url
    return (urlsplit(url).hostname or "").lower().strip(".")


def registrable(host: str) -> str:
    """Return the registrable domain (eTLD+1) for a host."""
    host = host.lower().strip(".")
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    tail2 = ".".join(labels[-2:])
    if tail2 in _SECOND_LEVEL and len(labels) >= 3:
        return ".".join(labels[-3:])
    return tail2


def tld_of(host: str) -> str:
    return host.rsplit(".", 1)[-1] if "." in host else host


def label_of(domain: str) -> str:
    """The leftmost label of a registrable domain: 'salik-topup-ae.test' -> 'salik-topup-ae'."""
    return registrable(domain).split(".")[0]


def is_official(host: str, official_domains: list[str]) -> bool:
    reg = registrable(host)
    host = host.lower()
    return any(reg == d or host == d or host.endswith("." + d) for d in official_domains)


def normalise_label(label: str) -> str:
    out = label.lower().translate(_HOMOGLYPHS)
    for a, b in _DIGRAPHS:
        out = out.replace(a, b)
    return out


def edit_distance(a: str, b: str) -> int:
    """Damerau-Levenshtein (optimal string alignment) distance."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if not la or not lb:
        return max(la, lb)
    prev2: list[int] | None = None
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if prev2 is not None and i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                cur[j] = min(cur[j], prev2[j - 2] + 1)
        prev2, prev = prev, cur
    return prev[lb]


def lookalike(domain: str, official_domains: list[str], keywords: list[str]) -> dict:
    """Score how strongly `domain` imitates a brand (0..1) and explain why.

    Looks for: the brand token inside the label (salik-topup-ae), lure words
    around it, homoglyph swaps, and a small edit distance to the official label.
    """
    label = label_of(domain)
    norm = normalise_label(label)
    raw_tokens = [t for t in re.split(r"[-_.]", label.lower()) if t]
    tokens = [t for t in re.split(r"[-_.]", norm) if t]
    raw_compact = re.sub(r"[^a-z0-9]", "", label.lower())
    norm_compact = re.sub(r"[^a-z0-9]", "", norm)
    reasons: list[str] = []
    score = 0.0

    brand_tokens = {re.sub(r"[^a-z0-9]", "", k.lower()) for k in keywords if re.fullmatch(r"[a-z0-9&. ]+", k.lower())}
    brand_tokens |= {label_of(d) for d in official_domains}
    # Generic words (uae, gov, pay...) are never a brand, and very short brands must match a whole token
    # so that 'rta' does not fire inside 'smart-alerts'.
    brand_tokens = {b for b in brand_tokens if len(b) >= 3 and b not in LURE_WORDS}

    for brand in sorted(brand_tokens, key=len):
        substring_ok = len(brand) >= 5
        in_raw = brand in raw_tokens or (substring_ok and brand in raw_compact)
        in_norm = brand in tokens or (substring_ok and brand in norm_compact)
        if in_raw or in_norm:
            extra = [t for t in tokens if t != brand]
            lure = [t for t in extra if t in LURE_WORDS]
            score = max(score, 0.55 + min(0.35, 0.12 * len(lure)))
            reasons.append(f"contains the brand name '{brand}'" + (f" plus lure words {', '.join(lure)}" if lure else ""))
            if in_norm and not in_raw:
                score = max(score, 0.75)
                reasons.append("uses look-alike characters (homoglyphs) to imitate the brand")
            break

    for off in official_domains:
        off_label = label_of(off)
        d = edit_distance(norm, off_label)
        if 0 < d <= 2 and len(off_label) >= 4:
            score = max(score, 0.9 - 0.15 * (d - 1))
            reasons.append(f"is {d} character(s) away from the official '{off_label}'")
            break

    if registrable(domain) in {registrable(d) for d in official_domains}:
        return {"score": 0.0, "reasons": ["is an official domain"], "official": True}
    return {"score": round(min(score, 0.98), 2), "reasons": reasons, "official": False}
