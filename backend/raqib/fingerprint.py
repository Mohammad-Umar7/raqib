"""Scam fingerprints: compact, comparable summaries of a captured site."""

from __future__ import annotations

import hashlib
import re

from .detectors import bundle_text, collect_contacts, collect_iocs
from .domains import host_of, registrable


def _shingles(seq: list[str], n: int) -> set[str]:
    if len(seq) < n:
        return {" ".join(seq)} if seq else set()
    return {" ".join(seq[i:i + n]) for i in range(len(seq) - n + 1)}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def build(bundle: dict) -> dict:
    """Build the fingerprint used to link this site to others."""
    pages = bundle.get("pages", [])
    final_host = registrable(host_of(bundle.get("final_url") or (pages[-1]["url"] if pages else "")))
    contacts = collect_contacts(bundle)
    iocs = collect_iocs(bundle)

    kit_files, kit_names = set(), {}
    favicon = None
    for p in pages:
        for s in p.get("scripts", []) + p.get("assets", []):
            if s.get("library"):
                continue  # jquery, bootstrap... shared by everyone, says nothing
            if s.get("sha256"):
                kit_files.add(s["sha256"])
                kit_names[s["sha256"]] = s.get("src", "")
        favicon = favicon or p.get("meta", {}).get("favicon_hash")

    layout: list[str] = []
    for p in pages:
        layout.extend(el["kind"] for el in p.get("elements", []))
    words = re.findall(r"[a-z؀-ۿ]{3,}", bundle_text(bundle).lower())

    chain = bundle.get("redirect_chain", [])
    redirect_hosts = sorted({registrable(host_of(h["url"])) for h in chain} - {final_host, ""})
    infra = bundle.get("infra", {})

    exfil = [f"telegram_bot:{b}" for b in iocs["telegram_bot_ids"]] + [f"discord_webhook:{w}" for w in iocs["discord_webhook_ids"]]
    return {
        "case_id": bundle["case_id"],
        "domain": final_host,
        "kit_files": sorted(kit_files),
        "kit_names": kit_names,
        "exfil": exfil,
        "wallets": iocs["wallets"],
        "phones": contacts["phones"],
        "whatsapp": contacts["whatsapp"],
        "emails": contacts["emails"],
        "analytics": iocs["analytics_ids"],
        "favicon": favicon,
        "layout": sorted(_shingles(layout, 3)),
        "text": sorted(hashlib.sha1(s.encode()).hexdigest()[:10] for s in _shingles(words, 4)),
        "redirect_hosts": redirect_hosts,
        "infra": {
            "asn": infra.get("asn"), "asn_org": infra.get("asn_org"), "ip": infra.get("ip"),
            "country": infra.get("country"), "registrar": infra.get("registrar"),
            "domain_created": infra.get("domain_created"), "nameservers": infra.get("nameservers", []),
            "cdn": bool(infra.get("cdn")),
        },
    }


def layout_similarity(a: dict, b: dict) -> float:
    return jaccard(set(a["layout"]), set(b["layout"]))


def text_similarity(a: dict, b: dict) -> float:
    return jaccard(set(a["text"]), set(b["text"]))
