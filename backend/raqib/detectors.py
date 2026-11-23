"""Evidence analysers: turn what the browser observed into explainable signals.

The same code runs on recorded evidence (replay) and on evidence captured live
by the sandbox browser, so a verdict never depends on which mode produced it.

Every signal carries a weight (its contribution to the noisy-OR risk score),
bilingual wording and pointers to the evidence that triggered it.
"""

from __future__ import annotations

import re
from datetime import date

from .domains import host_of, is_official, lookalike, registrable
from .ioc import normalise_phone
from .registry import Entity, Registry

# --------------------------------------------------------------------------- signal catalogue

CATALOGUE: dict[str, dict] = {
    "imp.brand_mismatch": dict(category="impersonation", weight=0.55,
        en="Presents itself as {brand} but is not an official {brand} domain",
        ar="يقدّم نفسه على أنه {brand} لكنه ليس نطاقاً رسمياً"),
    "imp.lookalike_domain": dict(category="impersonation", weight=0.25,
        en="The domain name imitates the {brand} name",
        ar="اسم النطاق يقلّد اسم {brand}"),
    "imp.contact_mismatch": dict(category="impersonation", weight=0.20,
        en="Uses a mobile / WhatsApp number as 'support' on a page claiming to be {brand}",
        ar="يعرض رقم جوال أو واتساب كدعم فني في صفحة تدّعي أنها {brand}"),
    "pay.card_form": dict(category="payment", weight=0.50,
        en="Asks for card number, expiry date and CVV",
        ar="يطلب رقم البطاقة وتاريخ الانتهاء ورمز CVV"),
    "pay.otp_request": dict(category="payment", weight=0.30,
        en="Asks for the one-time verification code (OTP)",
        ar="يطلب رمز التحقق لمرة واحدة (OTP)"),
    "pay.id_request": dict(category="payment", weight=0.30,
        en="Asks for the Emirates ID number",
        ar="يطلب رقم الهوية الإماراتية"),
    "pay.credentials": dict(category="payment", weight=0.45,
        en="Asks for online-banking username and password on a non-official domain",
        ar="يطلب اسم المستخدم وكلمة المرور للخدمات المصرفية في نطاق غير رسمي"),
    "exfil.messaging_bot": dict(category="exfiltration", weight=0.60,
        en="Page script is wired to a messaging-app bot ({kinds}) used to collect stolen data",
        ar="سكربت الصفحة مرتبط ببوت مراسلة ({kinds}) يُستخدم لجمع البيانات المسروقة"),
    "exfil.cross_origin_form": dict(category="exfiltration", weight=0.30,
        en="A form sends its data to a different domain ({target})",
        ar="نموذج يرسل بياناته إلى نطاق مختلف ({target})"),
    "fraud.guaranteed_returns": dict(category="fraud", weight=0.45,
        en="Promises guaranteed or unrealistic returns",
        ar="يَعِد بعوائد مضمونة أو غير واقعية"),
    "fraud.upfront_fee": dict(category="fraud", weight=0.40,
        en="Demands an upfront 'processing' fee before releasing money",
        ar="يطلب رسوم معالجة مقدّمة قبل صرف الأموال"),
    "fraud.crypto_wallet": dict(category="fraud", weight=0.35,
        en="Asks victims to pay to a cryptocurrency wallet",
        ar="يطلب من الضحايا الدفع إلى محفظة عملات رقمية"),
    "fraud.whatsapp_only": dict(category="fraud", weight=0.20,
        en="Only contact route is WhatsApp / mobile, with no landline or registered address",
        ar="وسيلة التواصل الوحيدة واتساب/جوال دون هاتف أرضي أو عنوان مسجّل"),
    "fraud.urgency": dict(category="fraud", weight=0.25,
        en="Uses countdowns and threats ('suspended', 'impounded') to rush the victim",
        ar="يستخدم عدّاً تنازلياً وتهديدات (إيقاف، حجز) لاستعجال الضحية"),
    "fraud.fake_license": dict(category="fraud", weight=0.20,
        en="Claims to be 'licensed and regulated' without naming a verifiable regulator",
        ar="يدّعي أنه مرخّص وخاضع للرقابة دون ذكر جهة رقابية يمكن التحقق منها"),
    "infra.new_domain": dict(category="infrastructure", weight=0.30,
        en="Domain was registered only {days} days before this investigation",
        ar="تم تسجيل النطاق قبل {days} يوماً فقط من هذا التحقيق"),
    "infra.fresh_cert": dict(category="infrastructure", weight=0.08,
        en="TLS certificate was issued {days} days ago",
        ar="شهادة TLS صدرت قبل {days} يوماً"),
    "infra.redirector": dict(category="infrastructure", weight=0.15,
        en="Link passes through an unrelated redirect domain ({hop}) before the landing page",
        ar="الرابط يمرّ عبر نطاق تحويل غير مرتبط ({hop}) قبل صفحة الهبوط"),
}

SEVERITY_ORDER = {"critical": 3, "high": 2, "medium": 1, "low": 0}


def _severity(weight: float) -> str:
    if weight >= 0.45:
        return "critical"
    if weight >= 0.28:
        return "high"
    if weight >= 0.15:
        return "medium"
    return "low"


def make_signal(sid: str, evidence: list[dict] | None = None, **fmt) -> dict:
    spec = CATALOGUE[sid]
    return {
        "id": sid,
        "category": spec["category"],
        "weight": spec["weight"],
        "severity": _severity(spec["weight"]),
        "label": spec["en"].format(**fmt) if fmt else spec["en"],
        "label_ar": spec["ar"].format(**fmt) if fmt else spec["ar"],
        "evidence": evidence or [],
    }


# --------------------------------------------------------------------------- field classification

_AUTOCOMPLETE = {
    "cc-number": "card_number", "cc-exp": "card_expiry", "cc-exp-month": "card_expiry", "cc-exp-year": "card_expiry",
    "cc-csc": "card_cvv", "cc-name": "card_holder", "one-time-code": "otp", "current-password": "password",
    "new-password": "password", "username": "username", "tel": "phone", "email": "email", "name": "name",
}

_FIELD_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("card_number", re.compile(r"card ?(?:number|no)|cardnumber|ccnum|pan\b|رقم البطاقة", re.I)),
    ("card_cvv", re.compile(r"\bcvv\b|\bcvc\b|security code|رمز الأمان", re.I)),
    ("card_expiry", re.compile(r"expir|\bexp\b|mm ?/ ?yy|تاريخ الانتهاء", re.I)),
    ("otp", re.compile(r"\botp\b|one[- ]time|verification code|sms code|رمز التحقق|رمز التفعيل", re.I)),
    ("emirates_id", re.compile(r"emirates[ _-]?id|784-|هوية", re.I)),
    ("password", re.compile(r"pass(?:word|code)|pin\b|كلمة المرور|الرقم السري", re.I)),
    ("username", re.compile(r"user ?name|user ?id|login id|اسم المستخدم", re.I)),
    ("phone", re.compile(r"mobile|phone|\btel\b|whatsapp|جوال|هاتف", re.I)),
    ("email", re.compile(r"e-?mail|البريد", re.I)),
    ("salary", re.compile(r"salary|income|الراتب", re.I)),
]


def classify_field(field: dict) -> str:
    ac = (field.get("autocomplete") or "").lower().strip()
    if ac in _AUTOCOMPLETE:
        return _AUTOCOMPLETE[ac]
    blob = " ".join(str(field.get(k, "")) for k in ("name", "id", "placeholder", "label", "aria"))
    for kind, pat in _FIELD_PATTERNS:
        if pat.search(blob):
            return kind
    if (field.get("type") or "").lower() == "password":
        return "password"
    return "other"


# --------------------------------------------------------------------------- text lexicons

_GUARANTEED = re.compile(
    r"guarantee[d]?\b.{0,24}\b(?:returns?|profits?|income)|\b\d{2,3}\s?%\s?(?:monthly|weekly|daily|per month|returns?)|"
    r"risk[- ]free|double your|عائد مضمون|أرباح مضمونة|ربح مضمون", re.I)
_UPFRONT = re.compile(
    r"processing fee|refundable (?:fee|deposit)|release (?:the |your )?(?:funds|loan)|insurance fee|"
    r"pay (?:a )?(?:small )?fee to receive|رسوم (?:المعالجة|التأمين|الإفراج)", re.I)
_URGENCY = re.compile(
    r"within \d+ ?(?:hours?|hrs?)|\b24 ?(?:h|hrs?|hours?)\b|suspen(?:d|ded|sion)|impound|final notice|"
    r"act now|expires? in|عاجل|خلال \d+ ساعة|إيقاف|حجز", re.I)
_LICENSE = re.compile(r"licen[sc]ed\s*(?:and|&)\s*regulated|licen[sc]e\s*(?:no\.?|number)\s*[:#]?\s*\w+|regulated by", re.I)
_NAMED_REGULATOR = re.compile(r"\b(?:SCA|DFSA|ADGM|FSRA|central bank|DED|department of economic development)\b", re.I)

LANDLINE = re.compile(r"^\+971(?:2|3|4|6|7|9)\d{7}$")


# --------------------------------------------------------------------------- page helpers

def page_text(page: dict) -> str:
    return " \n".join(el.get("text", "") for el in page.get("elements", []) if el.get("text"))


def bundle_text(bundle: dict) -> str:
    return " \n".join(page_text(p) for p in bundle.get("pages", []))


def headline_text(bundle: dict) -> str:
    out = []
    for p in bundle.get("pages", []):
        out.extend(el.get("text", "") for el in p.get("elements", []) if el.get("kind") in ("header", "heading", "banner"))
    return " \n".join(out)


def forms_of(page: dict) -> list[dict]:
    """Group input elements into forms with classified fields."""
    declared = {f["id"]: f for f in page.get("forms", [])}
    grouped: dict[str, dict] = {}
    for el in page.get("elements", []):
        if el.get("kind") not in ("input", "select"):
            continue
        fid = el.get("form") or "_loose"
        form = grouped.setdefault(fid, {"id": fid, "action": declared.get(fid, {}).get("action", ""), "fields": []})
        field = dict(el.get("field", {}))
        field["element_id"] = el["id"]
        field["kind"] = classify_field({**field, "label": field.get("label") or el.get("text", "")})
        form["fields"].append(field)
    return list(grouped.values())


def collect_contacts(bundle: dict) -> dict:
    phones, whatsapp, emails = set(), set(), set()
    for p in bundle.get("pages", []):
        for el in p.get("elements", []):
            if el.get("phone"):
                phones.add(normalise_phone(el["phone"]))
            if el.get("whatsapp"):
                whatsapp.add(normalise_phone(el["whatsapp"]))
            if el.get("email"):
                emails.add(el["email"].lower())
    declared = bundle.get("contacts", {})
    phones |= {normalise_phone(x) for x in declared.get("phones", [])}
    whatsapp |= {normalise_phone(x) for x in declared.get("whatsapp", [])}
    emails |= {x.lower() for x in declared.get("emails", [])}
    return {"phones": sorted(phones - whatsapp), "whatsapp": sorted(whatsapp), "emails": sorted(emails)}


def collect_iocs(bundle: dict) -> dict:
    out = {"telegram_bot_ids": set(), "discord_webhook_ids": set(), "wallets": set(), "analytics_ids": set()}
    for p in bundle.get("pages", []):
        for s in p.get("scripts", []):
            for key in out:
                out[key] |= set(s.get("iocs", {}).get(key, []))
        out["analytics_ids"] |= set(p.get("meta", {}).get("analytics_ids", []))
        for el in p.get("elements", []):
            if el.get("wallet"):
                out["wallets"].add(el["wallet"])
    return {k: sorted(v) for k, v in out.items()}


def days_between(earlier: str | None, later: str | None) -> int | None:
    try:
        return (date.fromisoformat(later[:10]) - date.fromisoformat(earlier[:10])).days  # type: ignore[index]
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- main analyser

def analyse(bundle: dict, registry: Registry, upto_page: int | None = None, upto_step: bool = True) -> dict:
    """Run every detector over the evidence collected so far.

    `upto_page` limits the analysis to the first N pages so the replay
    investigator can reveal signals in the order a browser would find them.
    """
    view = dict(bundle)
    if upto_page is not None:
        view["pages"] = bundle.get("pages", [])[:upto_page]
    pages = view.get("pages", [])
    signals: list[dict] = []
    if not pages:
        return {"signals": [], "brand": None, "brand_confidence": 0.0, "forms": [], "contacts": collect_contacts(view),
                "iocs": collect_iocs(view), "official": False, "lookalike": {"score": 0, "reasons": []}}

    final_url = bundle.get("final_url") or pages[-1]["url"]
    host = host_of(final_url)
    reg_domain = registrable(host)
    text = bundle_text(view)
    all_forms = [(p, f) for p in pages for f in forms_of(p)]
    kinds = {fld["kind"] for _, f in all_forms for fld in f["fields"]}
    contacts = collect_contacts(view)
    iocs = collect_iocs(view)

    # -- impersonation --------------------------------------------------------------
    title = " ".join(p.get("title", "") for p in pages)
    brand, brand_conf = registry.detect_brand(title, headline_text(view), text)
    official_entity = registry.official_domain_of(host)
    look = {"score": 0.0, "reasons": []}
    if official_entity:
        return {"signals": [], "brand": official_entity.to_dict(), "brand_confidence": 1.0, "forms": [f for _, f in all_forms],
                "contacts": contacts, "iocs": iocs, "official": True, "lookalike": {"score": 0.0, "reasons": ["is an official domain"]}}
    if brand:
        look = lookalike(host, brand.domains, brand.keywords + brand.aliases)
        signals.append(make_signal("imp.brand_mismatch", [{"type": "page", "page": pages[0]["page_id"], "note": f"names {brand.name}"}],
                                   brand=brand.name))
        if look["score"] >= 0.5:
            signals.append(make_signal("imp.lookalike_domain", [{"type": "domain", "value": reg_domain, "note": "; ".join(look["reasons"])}],
                                       brand=brand.name))
        if contacts["whatsapp"] or (contacts["phones"] and not any(LANDLINE.match(p) for p in contacts["phones"])):
            signals.append(make_signal("imp.contact_mismatch", [{"type": "contact", "value": (contacts["whatsapp"] + contacts["phones"])[0]}],
                                       brand=brand.name))
    else:
        # Even without a named brand, a domain can still imitate one.
        for e in registry.entities:
            cand = lookalike(host, e.domains, e.keywords + e.aliases)
            if cand["score"] > look["score"]:
                look, brand = cand, e
        if look["score"] < 0.6:
            brand, look = None, {"score": 0.0, "reasons": []}

    # -- payment / credential harvesting ---------------------------------------------
    def field_evidence(kind_set: set[str]) -> list[dict]:
        ev = []
        for p, f in all_forms:
            for fld in f["fields"]:
                if fld["kind"] in kind_set:
                    ev.append({"type": "field", "page": p["page_id"], "element": fld["element_id"], "note": fld["kind"]})
        return ev

    if {"card_number", "card_cvv"} <= kinds or ("card_number" in kinds and "card_expiry" in kinds):
        signals.append(make_signal("pay.card_form", field_evidence({"card_number", "card_expiry", "card_cvv", "card_holder"})))
    if "otp" in kinds:
        signals.append(make_signal("pay.otp_request", field_evidence({"otp"})))
    if "emirates_id" in kinds:
        signals.append(make_signal("pay.id_request", field_evidence({"emirates_id"})))
    if "password" in kinds and ("username" in kinds or brand is not None):
        signals.append(make_signal("pay.credentials", field_evidence({"password", "username"})))

    # -- exfiltration -----------------------------------------------------------------
    channel_kinds = []
    if iocs["telegram_bot_ids"]:
        channel_kinds.append("Telegram bot")
    if iocs["discord_webhook_ids"]:
        channel_kinds.append("Discord webhook")
    if channel_kinds:
        ev = [{"type": "ioc", "value": f"telegram_bot:{b}"} for b in iocs["telegram_bot_ids"]]
        ev += [{"type": "ioc", "value": f"discord_webhook:{w}"} for w in iocs["discord_webhook_ids"]]
        signals.append(make_signal("exfil.messaging_bot", ev, kinds=" + ".join(channel_kinds)))
    for p, f in all_forms:
        action = f.get("action") or ""
        if action.startswith("http") and registrable(host_of(action)) != reg_domain:
            signals.append(make_signal("exfil.cross_origin_form", [{"type": "form", "page": p["page_id"], "value": f["id"]}],
                                       target=registrable(host_of(action))))
            break

    # -- fraud patterns ---------------------------------------------------------------
    def first_el(pattern: re.Pattern) -> list[dict]:
        for p in pages:
            for el in p.get("elements", []):
                if el.get("text") and pattern.search(el["text"]):
                    return [{"type": "text", "page": p["page_id"], "element": el["id"], "note": el["text"][:90]}]
        return []

    if _GUARANTEED.search(text):
        signals.append(make_signal("fraud.guaranteed_returns", first_el(_GUARANTEED)))
    if _UPFRONT.search(text):
        signals.append(make_signal("fraud.upfront_fee", first_el(_UPFRONT)))
    if iocs["wallets"]:
        signals.append(make_signal("fraud.crypto_wallet", [{"type": "ioc", "value": f"wallet:{w}"} for w in iocs["wallets"]]))
    has_timer = any(el.get("kind") == "timer" for p in pages for el in p.get("elements", []))
    if has_timer or len(_URGENCY.findall(text)) >= 2:
        signals.append(make_signal("fraud.urgency", first_el(_URGENCY)))
    if _LICENSE.search(text) and not _NAMED_REGULATOR.search(text):
        signals.append(make_signal("fraud.fake_license", first_el(_LICENSE)))
    if (contacts["whatsapp"] or contacts["phones"]) and not any(LANDLINE.match(p) for p in contacts["phones"]) \
            and not any(el.get("kind") == "address" for p in pages for el in p.get("elements", [])) and (all_forms or iocs["wallets"]):
        if "imp.contact_mismatch" not in {s["id"] for s in signals}:
            signals.append(make_signal("fraud.whatsapp_only", [{"type": "contact", "value": (contacts["whatsapp"] + contacts["phones"])[0]}]))

    # -- infrastructure ---------------------------------------------------------------
    infra = bundle.get("infra", {})
    observed = bundle.get("observed_at")
    age = days_between(infra.get("domain_created"), observed)
    if age is not None and age <= 30:
        sig = make_signal("infra.new_domain", [{"type": "whois", "value": infra.get("domain_created")}], days=age)
        if age > 14:
            sig["weight"] = 0.2
            sig["severity"] = _severity(0.2)
        signals.append(sig)
    cert_age = days_between(infra.get("cert_issued"), observed)
    if cert_age is not None and cert_age <= 14:
        signals.append(make_signal("infra.fresh_cert", [{"type": "tls", "value": infra.get("cert_issued")}], days=cert_age))
    chain = bundle.get("redirect_chain", [])
    if len(chain) >= 2:
        first_host = registrable(host_of(chain[0]["url"]))
        if first_host != reg_domain and first_host:
            signals.append(make_signal("infra.redirector", [{"type": "redirect", "value": chain[0]["url"]}], hop=first_host))

    # de-duplicate by id (keep first) and order by weight
    seen, unique = set(), []
    for s in signals:
        if s["id"] not in seen:
            seen.add(s["id"])
            unique.append(s)

    return {
        "signals": unique,
        "brand": brand.to_dict() if brand else None,
        "brand_confidence": brand_conf if brand else (0.6 if look["score"] >= 0.6 else 0.0),
        "forms": [f for _, f in all_forms],
        "contacts": contacts,
        "iocs": iocs,
        "official": False,
        "lookalike": look,
        "hints": {
            "job": bool(re.search(r"hiring|vacanc|apply now|free visa|careers|jobs?", text + " " + title, re.I)),
            "loan": bool(re.search(r"loan|salary certificate|قرض", text, re.I)),
        },
    }


# --------------------------------------------------------------------------- scoring and verdict

def risk_score(signals: list[dict]) -> int:
    """Noisy-OR: independent weak signals add up, but no single one decides alone."""
    p_safe = 1.0
    for s in signals:
        p_safe *= 1.0 - float(s["weight"])
    return int(round(100 * (1.0 - p_safe)))


def verdict_for(score: int, official: bool = False) -> str:
    if official:
        return "official"
    if score >= 85:
        return "confirmed_scam"
    if score >= 60:
        return "likely_scam"
    if score >= 30:
        return "suspicious"
    return "no_indicators"


def classify_scam(analysis: dict) -> str:
    ids = {s["id"] for s in analysis["signals"]}
    brand: dict | None = analysis.get("brand")
    if "fraud.guaranteed_returns" in ids:
        return "investment"
    hints = analysis.get("hints", {})
    if "fraud.upfront_fee" in ids:
        return "job_offer" if hints.get("job") and not hints.get("loan") else "advance_fee_loan"
    if brand and ("imp.brand_mismatch" in ids or "imp.lookalike_domain" in ids):
        return brand.get("scam_type", "phishing")
    if "pay.card_form" in ids or "pay.credentials" in ids:
        return "phishing"
    return "unknown" if ids else "none"


SCAM_TYPE_LABELS = {
    "toll_topup": ("Fake toll top-up", "رسوم سالك مزيفة"),
    "traffic_fine": ("Fake traffic-fine payment", "دفع مخالفات مرورية مزيف"),
    "parcel_fee": ("Fake parcel redelivery fee", "رسوم توصيل طرد مزيفة"),
    "bank_verification": ("Bank account verification phishing", "تصيّد للتحقق من حساب مصرفي"),
    "bill_refund": ("Fake bill refund", "استرداد فواتير مزيف"),
    "government_service": ("Fake government service", "خدمة حكومية مزيفة"),
    "investment": ("Investment fraud", "احتيال استثماري"),
    "advance_fee_loan": ("Advance-fee loan scam", "احتيال قروض برسوم مقدّمة"),
    "job_offer": ("Fake job offer", "عرض وظيفي مزيف"),
    "fake_shop": ("Fake online shop", "متجر إلكتروني مزيف"),
    "prize_travel": ("Fake prize / travel offer", "جائزة أو عرض سفر مزيف"),
    "phishing": ("Payment-data phishing", "تصيّد لبيانات الدفع"),
    "unknown": ("Suspicious site", "موقع مشبوه"),
    "none": ("No scam indicators", "لا مؤشرات احتيال"),
}
