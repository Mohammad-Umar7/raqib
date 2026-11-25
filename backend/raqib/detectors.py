"""Evidence analysers: turn what the browser observed into explainable signals.

The same code runs on recorded evidence (replay) and on evidence captured live
by the sandbox browser, so a verdict never depends on which mode produced it.

Every signal carries a weight (its contribution to the noisy-OR risk score),
bilingual wording and pointers to the evidence that triggered it.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from .domains import PRIVATE_SUFFIXES, host_of, is_official, lookalike, registrable
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
    "pay.credentials_unbranded": dict(category="payment", weight=0.40,
        en="Asks for a password on {where}",
        ar="يطلب كلمة مرور على نطاق جديد جداً أو منصة استضافة مجانية"),
    "url.offline_lookalike": dict(category="impersonation", weight=0.50,
        en="The page is offline, but the link itself looks like a scam: {why}",
        ar="الصفحة غير متاحة، لكن الرابط نفسه يبدو احتيالياً"),
    "host.provider_flagged": dict(category="infrastructure", weight=0.90,
        en="The hosting provider ({provider}) already shows a phishing / malware warning in front of this site",
        ar="مزوّد الاستضافة ({provider}) يعرض بالفعل تحذيراً من التصيّد أو البرمجيات الخبيثة أمام هذا الموقع"),
    "fraud.disguised_field": dict(category="fraud", weight=0.50,
        en="Disguises a sensitive form label with look-alike letters ('{label}') to slip past scanners",
        ar="يموّه اسم حقل حساس بحروف مشابهة ('{label}') للتهرب من أدوات الفحص"),
    "infra.new_domain": dict(category="infrastructure", weight=0.30,
        en="Domain was registered only {days} days before this investigation",
        ar="تم تسجيل النطاق قبل {days} يوماً فقط من هذا التحقيق"),
    "infra.fresh_cert": dict(category="infrastructure", weight=0.08,
        en="TLS certificate was issued {days} days ago",
        ar="شهادة TLS صدرت قبل {days} يوماً"),
    "url.shortener": dict(category="evasion", weight=0.12,
        en="The link uses a URL shortener ({svc}) that hides the real destination",
        ar="الرابط يستخدم خدمة تقصير ({svc}) تخفي الوجهة الحقيقية"),
    "url.ip_host": dict(category="evasion", weight=0.35,
        en="The link points to a raw IP address instead of a domain name",
        ar="الرابط يشير إلى عنوان IP مباشر بدلاً من اسم نطاق"),
    "url.punycode": dict(category="impersonation", weight=0.35,
        en="The domain uses look-alike international characters (punycode)",
        ar="النطاق يستخدم أحرفاً دولية مشابهة (Punycode)"),
    "url.userinfo": dict(category="evasion", weight=0.3,
        en="The URL contains '@', which hides the real host from the reader",
        ar="الرابط يحتوي على '@' التي تخفي النطاق الحقيقي"),
    "url.brand_in_subdomain": dict(category="impersonation", weight=0.4,
        en="The brand name '{brand}' is placed in a sub-domain of an unrelated domain ({domain})",
        ar="اسم الجهة '{brand}' موضوع كنطاق فرعي لنطاق غير مرتبط ({domain})"),
    "url.free_hosting": dict(category="infrastructure", weight=0.15,
        en="Hosted on a free site-builder / hosting platform ({platform}) that scammers often abuse",
        ar="مستضاف على منصة استضافة مجانية ({platform}) يستغلها المحتالون كثيراً"),
    "url.risky_tld": dict(category="infrastructure", weight=0.1,
        en="Uses a top-level domain heavily abused for scams (.{tld})",
        ar="يستخدم امتداد نطاق يُستغل كثيراً في الاحتيال (.{tld})"),
    "http.cloaking": dict(category="evasion", weight=0.35,
        en="Shows different content to phones and computers (cloaking): {detail}",
        ar="يعرض محتوى مختلفاً للهواتف والحواسيب (إخفاء): {detail}"),
    "http.insecure_form": dict(category="payment", weight=0.2,
        en="Asks for sensitive data over an unencrypted (http) connection",
        ar="يطلب بيانات حساسة عبر اتصال غير مشفّر (http)"),
    "ai.visual_brand": dict(category="impersonation", weight=0.35,
        en="AI vision check: the page looks like {brand} ({reason})",
        ar="فحص بصري بالذكاء الاصطناعي: الصفحة تشبه {brand}"),
    "infra.redirector": dict(category="infrastructure", weight=0.15,
        en="Link passes through an unrelated redirect domain ({hop}) before the landing page",
        ar="الرابط يمرّ عبر نطاق تحويل غير مرتبط ({hop}) قبل صفحة الهبوط"),
}


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


# Letters from other scripts that look like Latin ones (Cyrillic, Greek) and letters NFKD does not fold.
_CONFUSABLE = str.maketrans({
    "ø": "o", "Ø": "O", "ð": "d", "đ": "d", "ł": "l", "ı": "i", "ɡ": "g", "ԁ": "d", "ѕ": "s", "ј": "j", "і": "i", "ӏ": "l",
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "х": "x", "у": "y", "к": "k", "м": "m", "н": "h", "т": "t", "в": "b",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X",
    "α": "a", "ο": "o", "ρ": "p", "ν": "v", "τ": "t", "ε": "e", "ι": "i", "κ": "k", "Α": "A", "Ο": "O", "Ρ": "P",
})
SENSITIVE_FIELD_KINDS = {"card_number", "card_cvv", "card_expiry", "otp", "password", "emirates_id", "username"}


def deconfuse(s: str) -> str:
    """Fold accents and look-alike letters to plain Latin ('Pàsswørd' -> 'Password')."""
    s = unicodedata.normalize("NFKD", s).translate(_CONFUSABLE)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def _match_kind(blob: str) -> str | None:
    for kind, pat in _FIELD_PATTERNS:
        if pat.search(blob):
            return kind
    return None


def classify_field(field: dict) -> str:
    ac = (field.get("autocomplete") or "").lower().strip()
    if ac in _AUTOCOMPLETE:
        return _AUTOCOMPLETE[ac]
    blob = " ".join(str(field.get(k, "")) for k in ("name", "id", "placeholder", "label", "aria"))
    kind = _match_kind(blob)
    if kind:
        return kind
    if (field.get("type") or "").lower() == "password":
        return "password"
    folded = deconfuse(blob)
    if folded != blob:
        return _match_kind(folded) or "other"
    return "other"


def disguised_label(field: dict) -> str | None:
    """The visible label of a sensitive field that only reads as sensitive once look-alike letters are folded."""
    text = " ".join(str(field.get(k, "") or "") for k in ("label", "placeholder", "aria")).strip()
    if not text or _match_kind(text):
        return None
    folded = deconfuse(text)
    if folded == text or _match_kind(folded) not in SENSITIVE_FIELD_KINDS:
        return None
    return text[:40]


# A hosting provider's own warning page in front of a reported site (Cloudflare "Suspected Phishing" and similar).
# Matches the warning's own wording (a heading that is only "Suspected Phishing", or its fixed sentence), not articles about it.
_PROVIDER_WARNING = re.compile(
    r"has been reported for potential(?:ly)? (?:phishing|distributing malware)|^\s*suspected (?:phishing|malware)\s*$|"
    r"^\s*(?:deceptive|phishing) site ahead\b", re.I | re.M)
_PROVIDERS = (("Cloudflare", re.compile(r"cloudflare ray id|\bray id:?\s*[0-9a-f]{8,}|security by cloudflare", re.I)),
              ("Google Safe Browsing", re.compile(r"google safe browsing", re.I)), ("Netlify", re.compile(r"netlify", re.I)),
              ("Vercel", re.compile(r"vercel", re.I)))


def provider_warning(title: str, text: str) -> str | None:
    """Name of the provider whose phishing / malware warning page this is (short interstitial pages only)."""
    blob = f"{title}\n{text}"
    if len(text) > 2500 or not _PROVIDER_WARNING.search(blob):
        return None
    return next((name for name, pat in _PROVIDERS if pat.search(blob)), None)


def on_free_hosting(host: str) -> bool:
    return any(host == s or host.endswith("." + s) for s in PRIVATE_SUFFIXES)


# Brands whose name alone is the lure on a throwaway site (wallet "download" pages, fake bank notices).
MONEY_BRANDS = {"paypal", "binance", "coinbase", "metamask", "chase", "wellsfargo", "bankofamerica", "centralbank"}


def is_money_brand(brand: Entity) -> bool:
    return brand.sector == "bank" or brand.id in MONEY_BRANDS


# --------------------------------------------------------------------------- text lexicons

_GUARANTEED = re.compile(
    r"guarantee[d]?\b.{0,24}\b(?:returns?|profits?|income)|\b\d{2,3}\s?%\s?(?:monthly|weekly|daily|per month|returns?)|"
    r"risk[- ]free|double your|عائد مضمون|عوائد مضمونة|أرباح مضمونة|ربح مضمون|ربح يومي|عائد شهري ثابت|استثمار مضمون", re.I)
_UPFRONT = re.compile(
    r"processing fee|refundable (?:fee|deposit)|release (?:the |your )?(?:funds|loan)|insurance fee|"
    r"pay (?:a )?(?:small )?fee to receive|رسوم (?:المعالجة|التأمين|الإفراج|إدارية|التوصيل|إعادة التوصيل)|ادفع رسوم", re.I)
_URGENCY = re.compile(
    r"within \d+ ?(?:hours?|hrs?)|\b24 ?(?:h|hrs?|hours?)\b|suspen(?:d|ded|sion)|impound|final notice|"
    r"act now|expires? in|account (?:is |has been )?(?:blocked|restricted|locked)|عاجل|خلال \d+ ساعة|إيقاف|حجز|تم تعليق|تعليق حسابك|حسابك موقوف|"
    r"آخر فرصة|آخر موعد|غرامة إضافية|تجنب الغرامة|تحديث بياناتك", re.I)
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
        labelled = {**field, "label": field.get("label") or el.get("text", "")}
        field["kind"] = classify_field(labelled)
        field["disguised"] = disguised_label(labelled)
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
    warned_by = provider_warning(title, text)
    if warned_by:
        signals.append(make_signal("host.provider_flagged", [{"type": "page", "page": pages[-1]["page_id"], "note": f"{warned_by} warning page"}],
                                   provider=warned_by))
    hidden = [(p, fld) for p, f in all_forms for fld in f["fields"] if fld.get("disguised")]
    if hidden:
        p0, fld0 = hidden[0]
        signals.append(make_signal("fraud.disguised_field", [{"type": "field", "page": p0["page_id"], "element": fld0["element_id"], "note": fld0["kind"]}],
                                   label=fld0["disguised"]))
    if brand and not (brand.mentions(title) + brand.mentions(headline_text(view))):
        # The brand is only discussed in the body (a news article, a comparison page...): that is not impersonation.
        brand, brand_conf = None, 0.0
    sensitive = kinds & {"card_number", "card_cvv", "card_expiry", "otp", "password", "emirates_id"}
    collects = bool(sensitive or iocs["wallets"] or iocs["telegram_bot_ids"] or iocs["discord_webhook_ids"])
    if brand:
        look = lookalike(host, brand.domains, brand.keywords + brand.aliases)
        sig = make_signal("imp.brand_mismatch", [{"type": "page", "page": pages[0]["page_id"], "note": f"names {brand.name}"}], brand=brand.name)
        if not collects and look["score"] < 0.5:
            # Names the brand but asks for nothing: usually commentary (0.15). On free hosting or a brand-new domain the name
            # is the lure itself, fully for money brands, partly for others (fan pages and clones exist there too).
            early_age = days_between((bundle.get("infra") or {}).get("domain_created"), bundle.get("observed_at"))
            risky_host = on_free_hosting(host) or (early_age is not None and early_age <= 180)
            w = 0.15 if not risky_host else (sig["weight"] if is_money_brand(brand) else 0.35)
            sig["weight"], sig["severity"] = w, _severity(w)
        signals.append(sig)
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

    infra_ = bundle.get("infra", {})
    age_days = days_between(infra_.get("domain_created"), bundle.get("observed_at"))
    context_risk = bool(brand) or look["score"] >= 0.5 or (age_days is not None and age_days <= 180)

    def weighted(sid: str, ev: list[dict], soft: float) -> dict:
        sig = make_signal(sid, ev)
        if not context_risk:
            sig["weight"], sig["severity"] = soft, _severity(soft)  # an ordinary checkout or login page on an established site
        return sig

    if {"card_number", "card_cvv"} <= kinds or ("card_number" in kinds and "card_expiry" in kinds):
        signals.append(weighted("pay.card_form", field_evidence({"card_number", "card_expiry", "card_cvv", "card_holder"}), 0.15))
    if "otp" in kinds:
        signals.append(weighted("pay.otp_request", field_evidence({"otp"}), 0.1))
    if "emirates_id" in kinds:
        signals.append(make_signal("pay.id_request", field_evidence({"emirates_id"})))
    if "password" in kinds and (brand is not None or look["score"] >= 0.5):
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
    # A password form with no named brand still matters on a brand-new or free-hosted site (global phishing kits).
    if "password" in kinds and "pay.credentials" not in {s["id"] for s in signals}:
        fresh = age is not None and age <= 90
        if fresh or on_free_hosting(host):
            signals.append(make_signal("pay.credentials_unbranded", field_evidence({"password", "username"}),
                                       where=f"a domain registered {age} days ago" if fresh else "a free hosting platform"))
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
        "collects": collects,
        "age_days": age_days,
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


def enrich(analysis: dict, case: dict) -> dict:
    """Merge what the URL scanner found outside the page (URL tricks, cloaking, AI vision, trust) into an analysis."""
    scan = case.get("scan") or {}
    have = {g["id"] for g in analysis["signals"]}
    for g in scan.get("extra_signals", []):
        if g["id"] not in have:
            analysis["signals"].append(g)
            have.add(g["id"])
    if scan.get("trusted"):
        analysis["trusted"] = scan["trusted"]
    if scan.get("cap") is not None:
        analysis["cap"] = scan["cap"]
    if scan.get("collects"):
        analysis["collects"] = True
    return analysis


def final_score(analysis: dict) -> int:
    """Risk score with trust caps applied.

    An established domain (2+ years old) that does not collect sensitive data or send data to a bot is
    capped at 25: real banks, ministries and news sites must not be flagged. A compromised old site that
    hosts a card/credential form under someone else's brand still scores high.
    """
    if analysis.get("official") or analysis.get("trusted"):
        return 0
    score = risk_score(analysis["signals"])
    age = analysis.get("age_days")
    provider_flagged = any(s["id"] == "host.provider_flagged" for s in analysis["signals"])
    if age is not None and age >= 730 and not analysis.get("collects") and not provider_flagged:
        score = min(score, 25)
    if analysis.get("cap") is not None:
        score = min(score, int(analysis["cap"]))
    return score


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
