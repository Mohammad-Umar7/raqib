"""Campaign linking: connect sites that belong to the same operation.

Looking alike is not proof of a shared operator (two fake RTA pages look alike
because both copied RTA). So every link carries a strength:

    strong  - the operator's own tooling or contact details are shared
              (same Telegram bot, wallet, phone/WhatsApp, kit file)
    medium  - shared fingerprints that are unlikely by chance
              (favicon, analytics ID, redirector, registration batch)
    weak    - circumstantial (same hosting, similar layout or wording)
"""

from __future__ import annotations

from .fingerprint import layout_similarity, text_similarity

STRENGTH_WEIGHT = {"strong": 0.9, "medium": 0.6, "weak": 0.25}
STRENGTH_LABEL = {"strong": ("Strong", "قوي"), "medium": ("Medium", "متوسط"), "weak": ("Weak", "ضعيف")}


def _reason(kind: str, strength: str, en: str, ar: str, value: str | None = None) -> dict:
    return {"kind": kind, "strength": strength, "text": en, "text_ar": ar, "value": value}


def compare(a: dict, b: dict) -> list[dict]:
    """All reasons why fingerprints `a` and `b` are connected (empty if unrelated)."""
    reasons: list[dict] = []

    for x in sorted(set(a["exfil"]) & set(b["exfil"])):
        kind = "Telegram bot" if x.startswith("telegram") else "Discord webhook"
        reasons.append(_reason("exfil", "strong", f"Same {kind} receives stolen data from both sites ({x.split(':', 1)[1]})",
                               f"يستلم نفس بوت {'تيليجرام' if x.startswith('telegram') else 'ديسكورد'} البيانات المسروقة من الموقعين", x))
    for w in sorted(set(a["wallets"]) & set(b["wallets"])):
        reasons.append(_reason("wallet", "strong", f"Same cryptocurrency wallet collects payments ({w[:8]}…{w[-4:]})",
                               "نفس محفظة العملات الرقمية تجمع المدفوعات", w))
    for n in sorted((set(a["whatsapp"]) | set(a["phones"])) & (set(b["whatsapp"]) | set(b["phones"]))):
        reasons.append(_reason("phone", "strong", f"Same phone / WhatsApp number {n}", f"نفس رقم الهاتف أو الواتساب {n}", n))
    for h in sorted(set(a["kit_files"]) & set(b["kit_files"])):
        name = a["kit_names"].get(h) or b["kit_names"].get(h) or "script"
        reasons.append(_reason("kit", "strong", f"Identical scam-kit file '{name}' (SHA-256 {h[:12]}…)",
                               f"ملف أدوات احتيال مطابق '{name}'", h))
    for e in sorted(set(a["emails"]) & set(b["emails"])):
        reasons.append(_reason("email", "strong", f"Same contact e-mail {e}", f"نفس البريد الإلكتروني {e}", e))

    if a["favicon"] and a["favicon"] == b["favicon"]:
        reasons.append(_reason("favicon", "medium", "Same favicon image", "نفس أيقونة الموقع", a["favicon"]))
    for g in sorted(set(a["analytics"]) & set(b["analytics"])):
        reasons.append(_reason("analytics", "medium", f"Same analytics / pixel ID {g}", f"نفس معرّف التحليلات {g}", g))
    for r in sorted(set(a["redirect_hosts"]) & set(b["redirect_hosts"])):
        reasons.append(_reason("redirect", "medium", f"Both are reached through the same redirect domain {r}",
                               f"كلاهما يُوصَل إليه عبر نفس نطاق التحويل {r}", r))
    ia, ib = a["infra"], b["infra"]
    if ia.get("registrar") and ia["registrar"] == ib.get("registrar") and ia.get("domain_created") \
            and ia["domain_created"] == ib.get("domain_created") and set(ia["nameservers"]) & set(ib["nameservers"]):
        reasons.append(_reason("registration", "medium",
                               f"Registered the same day ({ia['domain_created']}) at {ia['registrar']} with shared name servers",
                               "سُجّل في نفس اليوم لدى نفس المسجّل مع خوادم أسماء مشتركة", ia["domain_created"]))

    if ia.get("ip") and ia["ip"] == ib.get("ip") and not ia.get("cdn"):
        reasons.append(_reason("ip", "weak", f"Hosted on the same server ({ia['ip']})", f"مستضاف على نفس الخادم ({ia['ip']})", ia["ip"]))
    elif ia.get("asn") and ia["asn"] == ib.get("asn") and not (ia.get("cdn") or ib.get("cdn")):
        reasons.append(_reason("asn", "weak", f"Same hosting provider ({ia.get('asn_org') or ia['asn']})",
                               f"نفس مزوّد الاستضافة ({ia.get('asn_org') or ia['asn']})", ia["asn"]))
    lay = layout_similarity(a, b)
    if lay >= 0.7:
        reasons.append(_reason("layout", "weak", f"Page layout is {int(lay * 100)}% similar (could be a copied template)",
                               f"تخطيط الصفحة متشابه بنسبة {int(lay * 100)}٪ (قد يكون قالباً منسوخاً)", f"{lay:.2f}"))
    txt = text_similarity(a, b)
    if txt >= 0.5:
        reasons.append(_reason("text", "weak", f"Wording is {int(txt * 100)}% similar", f"الصياغة متشابهة بنسبة {int(txt * 100)}٪", f"{txt:.2f}"))
    return reasons


def edge_from(a: dict, b: dict) -> dict | None:
    reasons = compare(a, b)
    if not reasons:
        return None
    order = {"strong": 3, "medium": 2, "weak": 1}
    strength = max((r["strength"] for r in reasons), key=order.get)
    # noisy-OR over the reasons, capped
    p = 1.0
    for r in reasons:
        p *= 1 - STRENGTH_WEIGHT[r["strength"]] * (0.6 if r["strength"] == "weak" else 1.0)
    return {
        "source": a["case_id"], "target": b["case_id"], "strength": strength,
        "weight": round(min(0.99, 1 - p), 2), "reasons": sorted(reasons, key=lambda r: -order[r["strength"]]),
    }


def build_graph(fps: dict[str, dict], center: str | None = None, min_strength: str = "weak") -> dict:
    """Edges between all known fingerprints, plus connected-component clusters (strong/medium links only)."""
    ids = sorted(fps)
    edges = []
    for i, x in enumerate(ids):
        for y in ids[i + 1:]:
            e = edge_from(fps[x], fps[y])
            if e and (min_strength == "weak" or e["strength"] != "weak"):
                edges.append(e)

    parent = {i: i for i in ids}

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for e in edges:
        if e["strength"] in ("strong", "medium"):
            parent[find(e["source"])] = find(e["target"])
    clusters: dict[str, list[str]] = {}
    for i in ids:
        clusters.setdefault(find(i), []).append(i)
    cluster_of = {}
    for n, (root, members) in enumerate(sorted(clusters.items(), key=lambda kv: -len(kv[1])), start=1):
        if len(members) > 1:
            for m in members:
                cluster_of[m] = f"CMP-{n:02d}"
    if center:
        edges = [e for e in edges if center in (e["source"], e["target"])]
    return {"edges": edges, "cluster_of": cluster_of}
