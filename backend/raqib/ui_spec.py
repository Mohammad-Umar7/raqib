"""Generative UI: turn a case into a layout of typed blocks the dashboard renders.

Claude (or the offline fallback) decides *which* blocks to show, in what order,
with what emphasis and wording. The numbers inside the blocks always come from
the deterministic evidence pipeline, so the model cannot invent figures.

Block types understood by the frontend registry:
  verdict_hero, stat_row, callout, markdown, journey, signal_list, score_breakdown,
  campaign_card, indicators, kv_table, evidence_list, action_list, emirate_map
"""

from __future__ import annotations

from collections import Counter

from .detectors import SCAM_TYPE_LABELS, forms_of

LAYOUT_BLOCKS = ["verdict", "stats", "callout", "narrative", "journey", "signals", "breakdown", "campaign", "indicators", "infrastructure", "evidence", "actions", "map"]

VICTIM_FLOW = {
    "toll_topup": ("Victims are told their {brand} balance is low or fines are pending, then sent to a look-alike page that collects card details and the SMS verification code.",
                   "يُبلَّغ الضحايا بأن رصيد {brand} منخفض أو أن هناك غرامات، ثم يُحوَّلون إلى صفحة مشابهة تجمع بيانات البطاقة ورمز التحقق."),
    "traffic_fine": ("Victims are told they have an unpaid fine with a 24-hour penalty, then sent to a look-alike {brand} page that collects card details and the SMS code.",
                     "يُبلَّغ الضحايا بوجود مخالفة غير مسددة مع غرامة خلال 24 ساعة، ثم يُحوَّلون إلى صفحة {brand} مشابهة تجمع بيانات البطاقة ورمز الرسالة."),
    "parcel_fee": ("Victims get an SMS about a parcel on hold and are asked for a small redelivery fee on a look-alike {brand} page that collects card details and the SMS code.",
                   "يتلقى الضحايا رسالة عن طرد معلّق ويُطلب منهم رسوم توصيل صغيرة في صفحة {brand} مشابهة تجمع بيانات البطاقة ورمز الرسالة."),
    "bank_verification": ("Victims are told their {brand} account is restricted and are asked for online-banking credentials, an SMS code and their Emirates ID, which gives the operator full account access.",
                          "يُبلَّغ الضحايا بتقييد حسابهم في {brand} ويُطلب منهم بيانات الدخول المصرفي ورمز الرسالة والهوية الإماراتية، ما يمنح المحتال وصولاً كاملاً للحساب."),
    "investment": ("Victims are lured by guaranteed returns and asked to send cryptocurrency to a wallet controlled by the operator. The payouts shown on the site are fabricated.",
                   "يُستدرج الضحايا بعوائد مضمونة ويُطلب منهم إرسال عملات رقمية إلى محفظة يتحكم بها المحتال، وأرباح الموقع المعروضة مفبركة."),
    "advance_fee_loan": ("Victims are told a loan is approved and must first pay a 'processing fee' that is never refunded. The loan does not exist.",
                         "يُبلَّغ الضحايا بالموافقة على قرض ويُطلب منهم دفع «رسوم معالجة» لا تُسترد، والقرض غير موجود."),
    "job_offer": ("Job seekers are offered a well-paid role and asked to pay visa or processing fees before an offer letter that never arrives.",
                  "يُعرض على الباحثين عن عمل منصب بأجر مغرٍ ويُطلب منهم دفع رسوم تأشيرة أو معالجة قبل خطاب عرض لا يصل أبداً."),
}
GENERIC_FLOW = ("Victims are steered to a page that collects payment or identity data for the operator.",
                "يُوجَّه الضحايا إلى صفحة تجمع بيانات الدفع أو الهوية لصالح المحتال.")

VERDICT_TEXT = {
    "confirmed_scam": ("Confirmed scam", "احتيال مؤكد", "danger"),
    "likely_scam": ("Likely scam", "احتيال محتمل", "danger"),
    "suspicious": ("Suspicious", "مشبوه", "warn"),
    "no_indicators": ("No scam indicators", "لا مؤشرات احتيال", "ok"),
    "official": ("Official domain", "نطاق رسمي", "ok"),
}


def flow_text(ctx: dict) -> tuple[str, str]:
    en, ar = VICTIM_FLOW.get(ctx["scam_type"], GENERIC_FLOW)
    name = (ctx.get("brand") or {}).get("name", "the brand")
    name_ar = (ctx.get("brand") or {}).get("name_ar", "الجهة")
    return en.format(brand=name), ar.format(brand=name_ar)


# ---------------------------------------------------------------- victim journey

LURE = {
    "sms": ("Link received by SMS", "رابط وصل برسالة نصية", "sms"),
    "search_ad": ("Sponsored search ad", "إعلان ممول في البحث", "search"),
    "search": ("Search result", "نتيجة بحث", "search"),
    "maps": ("Google Maps listing", "موقع على خرائط جوجل", "map"),
    "ct": ("New look-alike domain", "نطاق جديد مشابه", "globe"),
    "report": ("Citizen report", "بلاغ مواطن", "message"),
    "live": ("Link under investigation", "الرابط قيد التحقيق", "link"),
}
KIND_TEXT = {
    "card_number": ("card number", "رقم البطاقة"), "card_expiry": ("expiry date", "تاريخ الانتهاء"), "card_cvv": ("CVV", "رمز CVV"),
    "card_holder": ("cardholder name", "اسم حامل البطاقة"), "otp": ("SMS code (OTP)", "رمز الرسالة (OTP)"), "password": ("password", "كلمة المرور"),
    "username": ("username", "اسم المستخدم"), "emirates_id": ("Emirates ID", "الهوية الإماراتية"), "phone": ("mobile number", "رقم الجوال"),
    "name": ("full name", "الاسم الكامل"), "email": ("e-mail", "البريد الإلكتروني"), "salary": ("salary", "الراتب"),
}


def _step(icon: str, title: str, title_ar: str, detail: str, detail_ar: str, tone: str) -> dict:
    return {"icon": icon, "title": title, "title_ar": title_ar, "detail": detail, "detail_ar": detail_ar, "tone": tone}


def journey_steps(case: dict | None, analysis: dict) -> list[dict]:
    """The victim's path through the site, reconstructed from the recorded pages."""
    if not case:
        return []
    en, ar, icon = LURE.get(case.get("source", "live"), LURE["live"])
    steps = [_step(icon, en, ar, case.get("host", ""), case.get("host", ""), "info")]
    if case.get("kind") == "maps_listing":
        c = case.get("contacts", {})
        contact = (c.get("whatsapp") or c.get("phones") or [""])[0]
        steps.append(_step("phone", "Victim calls or messages the listed number", "الضحية يتصل أو يراسل الرقم المعروض", contact, contact, "danger"))
        steps.append(_step("card", "Payment or details taken off-platform", "يؤخذ الدفع أو البيانات خارج المنصة", "", "", "danger"))
        return steps
    for page in case.get("pages", [])[:5]:
        kinds = list(dict.fromkeys(f["kind"] for form in forms_of(page) for f in form["fields"] if f["kind"] in KIND_TEXT))
        ic = "card" if any(k.startswith("card") for k in kinds) else "otp" if "otp" in kinds else "id" if "emirates_id" in kinds else "login" if "password" in kinds else "form" if kinds else "page"
        tone = "danger" if ic in ("card", "otp", "id", "login") else "warn" if kinds else "info"
        heading = next((e.get("text", "") for e in page.get("elements", []) if e["kind"] in ("banner", "heading", "text") and e.get("text")), "")
        title = page["title"].split(" - ")[-1][:48] or "Page"
        steps.append(_step(ic, title, title, ("Asks for: " + ", ".join(KIND_TEXT[k][0] for k in kinds[:4])) if kinds else heading[:80],
                           ("يطلب: " + "، ".join(KIND_TEXT[k][1] for k in kinds[:4])) if kinds else heading[:80], tone))
    io, ct = analysis.get("iocs", {}), analysis.get("contacts", {})
    if io.get("telegram_bot_ids"):
        b = io["telegram_bot_ids"][0]
        steps.append(_step("bot", "Entered data is relayed to a Telegram bot", "تُرسل البيانات المدخلة إلى بوت تيليجرام", f"Bot ID {b}", f"معرّف البوت {b}", "danger"))
    elif io.get("discord_webhook_ids"):
        b = io["discord_webhook_ids"][0]
        steps.append(_step("bot", "Entered data is relayed to a Discord webhook", "تُرسل البيانات المدخلة إلى ويب هوك ديسكورد", f"Webhook {b}", f"ويب هوك {b}", "danger"))
    if io.get("wallets"):
        w = io["wallets"][0]
        short = f"{w[:8]}…{w[-4:]}"
        steps.append(_step("wallet", "Victim is told to pay a crypto wallet", "يُطلب من الضحية الدفع إلى محفظة رقمية", short, short, "danger"))
    if ct.get("whatsapp"):
        n = ct["whatsapp"][0]
        steps.append(_step("phone", "Victim is pushed to WhatsApp", "يُدفَع الضحية إلى واتساب", n, n, "warn"))
    return steps


# ---------------------------------------------------------------- recommended actions

def recommended_actions(ctx: dict) -> list[dict]:
    infra = ctx.get("infra", {})
    host = ctx.get("domain") or ctx.get("host", "")
    out: list[dict] = []
    strong = [r for r in ctx.get("related", []) if r["strength"] == "strong"]
    if ctx["verdict"] in ("confirmed_scam", "likely_scam"):
        out.append({"id": "blocklist", "kind": "blocklist", "priority": "now",
                    "label": f"Block {host} and {len(strong)} linked site(s) at national DNS / ISP level" if strong else f"Block {host} at national DNS / ISP level",
                    "label_ar": f"حجب {host} و{len(strong)} موقعاً مرتبطاً على مستوى DNS ومزودي الخدمة" if strong else f"حجب {host} على مستوى DNS ومزودي الخدمة",
                    "detail": "Export includes every domain in the campaign cluster."})
        if infra.get("registrar"):
            out.append({"id": "registrar", "kind": "takedown", "target": "registrar", "priority": "now",
                        "label": f"Ask {infra['registrar']} to suspend the domain", "label_ar": f"مطالبة {infra['registrar']} بتعليق النطاق",
                        "detail": "Draft request with evidence hashes is ready."})
        if infra.get("asn_org"):
            out.append({"id": "host", "kind": "takedown", "target": "host", "priority": "now",
                        "label": f"Send an abuse report to the hosting provider ({infra['asn_org']})", "label_ar": f"إرسال بلاغ إساءة إلى مزود الاستضافة ({infra['asn_org']})",
                        "detail": "Hosting country is an infrastructure indicator, not proof of where the operator is."})
        out.append({"id": "safebrowsing", "kind": "takedown", "target": "safebrowsing", "priority": "soon",
                    "label": "Report to Google Safe Browsing so browsers warn visitors", "label_ar": "الإبلاغ إلى Google Safe Browsing لتحذير زوار الموقع",
                    "detail": "Draft report is ready."})
        if any(r.get("kind") == "maps_listing" for r in ctx.get("related", [])):
            out.append({"id": "maps", "kind": "takedown", "target": "maps", "priority": "now",
                        "label": "Report the linked fake Google Maps listing(s) for removal", "label_ar": "الإبلاغ عن قوائم خرائط جوجل المزيفة المرتبطة لإزالتها",
                        "detail": "Listings share a phone / WhatsApp number with this campaign."})
        if ctx["iocs"].get("telegram_bot_ids") or ctx["iocs"].get("discord_webhook_ids"):
            out.append({"id": "platform", "kind": "report", "priority": "soon",
                        "label": "Refer the data-collection bot / webhook to the cybercrime unit for a platform legal request", "label_ar": "إحالة بوت/ويب هوك جمع البيانات إلى إدارة الجرائم الإلكترونية لطلب قانوني للمنصة",
                        "detail": "The bot identifier links every site in the cluster to one operator."})
        if ctx["iocs"].get("wallets"):
            out.append({"id": "wallet", "kind": "report", "priority": "soon",
                        "label": "Flag the cryptocurrency wallet to exchanges for freezing", "label_ar": "إبلاغ منصات التداول عن المحفظة الرقمية لتجميدها",
                        "detail": "Wallet address is in the indicator list."})
        out.append({"id": "warning", "kind": "warning", "priority": "soon",
                    "label": "Publish a public warning (Arabic and English)", "label_ar": "نشر تحذير للجمهور (عربي وإنجليزي)", "detail": "Text is generated in the report pack."})
    elif ctx["verdict"] == "suspicious":
        out.append({"id": "monitor", "kind": "report", "priority": "soon",
                    "label": "Keep monitoring; re-investigate in 24 hours", "label_ar": "مواصلة المراقبة وإعادة التحقيق بعد 24 ساعة", "detail": "Weak signals can become strong once the site goes live."})
    else:
        out.append({"id": "none", "kind": "report", "priority": "later", "label": "No action needed", "label_ar": "لا إجراء مطلوب", "detail": ""})
    return out


# ---------------------------------------------------------------- offline "model"

def offline_refine(ctx: dict) -> dict:
    v_en, v_ar, tone = VERDICT_TEXT[ctx["verdict"]]
    sl_en, sl_ar = SCAM_TYPE_LABELS.get(ctx["scam_type"], SCAM_TYPE_LABELS["unknown"])
    brand = ctx.get("brand") or {}
    flow_en, flow_ar = flow_text(ctx)
    n_rel = len([r for r in ctx.get("related", []) if r["strength"] in ("strong", "medium")])
    top = sorted(ctx["signals"], key=lambda s: -s["weight"])[:3]
    headline = f"{v_en}: {sl_en.lower()}" + (f" imitating {brand['name']}" if brand and ctx["verdict"] not in ("no_indicators", "official") else "")
    headline_ar = f"{v_ar}: {sl_ar}" + (f" ينتحل صفة {brand['name_ar']}" if brand and ctx["verdict"] not in ("no_indicators", "official") else "")
    if ctx["verdict"] in ("no_indicators", "official"):
        summary = "The investigation found no payment or identity collection, no brand impersonation and no infrastructure red flags."
        summary_ar = "لم يجد التحقيق جمعاً لبيانات الدفع أو الهوية ولا انتحال صفة جهة ولا مؤشرات مشبوهة في البنية التحتية."
    else:
        summary = (f"Raqib scored this site {ctx['score']}/100. Strongest evidence: " + "; ".join(s["label"].rstrip(".") for s in top) + ".")
        summary_ar = f"منح رقيب هذا الموقع {ctx['score']}/100. أقوى الأدلة: " + "؛ ".join(s["label_ar"].rstrip(".") for s in top) + "."
        if n_rel:
            summary += f" It is linked to {n_rel} other site(s) in the same campaign."
            summary_ar += f" وهو مرتبط بـ {n_rel} موقعاً آخر في الحملة نفسها."
    scam = ctx["verdict"] not in ("no_indicators", "official")

    def L(b, t="", ta="", tn="info", text="", text_ar=""):
        return {"block": b, "title": t, "title_ar": ta, "text": text, "text_ar": text_ar, "tone": tn}

    layout = [L("verdict", tn=tone), L("stats")]
    if scam:
        if len(ctx.get("journey", [])) >= 3:
            layout.append(L("journey", "How the victim is deceived", "كيف يُخدع الضحية"))
        else:
            layout.append(L("callout", "How the victim is deceived", "كيف يُخدع الضحية", "danger", flow_en, flow_ar))
    layout += [L("signals", "Why this score", "سبب هذه النتيجة"), L("breakdown", "How the score adds up", "كيف تتراكم الدرجة")]
    if any(r["strength"] in ("strong", "medium") for r in ctx.get("related", [])):
        layout.append(L("campaign", "Campaign connections", "روابط الحملة"))
    layout += [L("indicators", "Indicators to share", "مؤشرات للمشاركة"), L("infrastructure", "Infrastructure indicators", "مؤشرات البنية التحتية")]
    if scam:
        layout.append(L("map", "Who is being targeted", "من المستهدف"))
    layout += [L("evidence", "Evidence chain of custody", "سلسلة حيازة الأدلة"), L("actions", "Recommended actions", "الإجراءات الموصى بها")]
    follow_ups = [{"q": "Why this score?", "q_ar": "لماذا هذه النتيجة؟"}]
    if scam:
        follow_ups.append({"q": "Walk me through the victim's journey", "q_ar": "اشرح لي رحلة الضحية خطوة بخطوة"})
    if ctx.get("related"):
        follow_ups.append({"q": "What else is linked to this campaign?", "q_ar": "ما المرتبط بهذه الحملة أيضاً؟"})
    if scam:
        follow_ups.append({"q": "What should we do next?", "q_ar": "ماذا نفعل الآن؟"})
    return {"headline": headline, "headline_ar": headline_ar, "summary": summary, "summary_ar": summary_ar,
            "victim_impact": flow_en, "victim_impact_ar": flow_ar, "layout": layout, "follow_ups": follow_ups,
            "recommended_actions": [{"id": a["id"], "label": a["label"], "label_ar": a["label_ar"], "detail": a["detail"], "priority": a["priority"]} for a in recommended_actions(ctx)]}


# ---------------------------------------------------------------- composition

def _block_verdict(ctx: dict, refined: dict, item: dict) -> dict:
    v_en, v_ar, tone = VERDICT_TEXT[ctx["verdict"]]
    chips = []
    if ctx.get("brand") and ctx["verdict"] not in ("no_indicators", "official"):
        chips.append({"label": f"Imitates {ctx['brand']['name']}", "label_ar": f"ينتحل {ctx['brand']['name_ar']}", "tone": "danger"})
    if ctx.get("cluster_id"):
        chips.append({"label": f"{ctx['cluster_id']} · {ctx['cluster_size']} sites", "label_ar": f"{ctx['cluster_id']} · {ctx['cluster_size']} موقعاً", "tone": "warn"})
    if ctx.get("on_blocklist") is False and ctx["verdict"] in ("confirmed_scam", "likely_scam"):
        chips.append({"label": "Not on any public blocklist yet", "label_ar": "غير مدرج في أي قائمة حجب عامة", "tone": "warn"})
    elif ctx.get("on_blocklist"):
        chips.append({"label": "Already on a public blocklist", "label_ar": "مدرج في قائمة حجب عامة", "tone": "info"})
    return {"type": "verdict_hero", "score": ctx["score"], "verdict": ctx["verdict"], "verdict_label": v_en, "verdict_label_ar": v_ar, "tone": tone,
            "headline": refined["headline"], "headline_ar": refined["headline_ar"], "summary": refined["summary"], "summary_ar": refined["summary_ar"], "chips": chips}


def _block_signals(ctx: dict, item: dict) -> dict:
    order = {"critical": 3, "high": 2, "medium": 1, "low": 0}
    sigs = sorted(ctx["signals"], key=lambda s: (-order[s["severity"]], -s["weight"]))
    return {"type": "signal_list", "title": item.get("title") or "Why this score", "title_ar": item.get("title_ar") or "سبب هذه النتيجة",
            "items": [{"id": s["id"], "label": s["label"], "label_ar": s["label_ar"], "weight": s["weight"], "severity": s["severity"], "category": s["category"]} for s in sigs]}


def _block_campaign(ctx: dict, item: dict) -> dict | None:
    rel = ctx.get("related", [])
    if not rel:
        return None
    rel = sorted(rel, key=lambda r: ({"strong": 0, "medium": 1, "weak": 2}[r["strength"]], -r["score"]))
    return {"type": "campaign_card", "title": item.get("title") or "Campaign connections", "title_ar": item.get("title_ar") or "روابط الحملة",
            "cluster_id": ctx.get("cluster_id"), "cluster_size": ctx.get("cluster_size", 1),
            "unblocked": len([r for r in rel if r["strength"] in ("strong", "medium") and not r.get("on_blocklist") and r.get("kind") == "site"]),
            "items": [{"case_id": r["case_id"], "host": r["host"], "label": r["label"], "kind": r.get("kind", "site"), "score": r["score"], "verdict": r["verdict"],
                       "strength": r["strength"], "on_blocklist": r.get("on_blocklist", False),
                       "reason": r["reasons"][0]["text"], "reason_ar": r["reasons"][0]["text_ar"]} for r in rel]}


def _block_stats(ctx: dict, item: dict) -> dict:
    v_en, v_ar, tone = VERDICT_TEXT[ctx["verdict"]]
    linked = [r for r in ctx.get("related", []) if r["strength"] in ("strong", "medium") and r.get("kind") == "site"]
    items = [{"label": "Risk score", "label_ar": "درجة الخطورة", "value": ctx["score"], "suffix": "/100", "hint": v_en, "hint_ar": v_ar, "tone": tone, "icon": "gauge"},
             {"label": "Signals found", "label_ar": "مؤشرات مرصودة", "value": len(ctx["signals"]), "hint": "independent signals", "hint_ar": "مؤشرات مستقلة", "tone": "info", "icon": "radar"}]
    if linked or ctx.get("cluster_id"):
        items.append({"label": "Linked sites", "label_ar": "مواقع مرتبطة", "value": len(linked), "hint": ctx.get("cluster_id") or "", "hint_ar": ctx.get("cluster_id") or "", "tone": "warn", "icon": "network"})
        unb = len([r for r in linked if not r.get("on_blocklist")])
        if unb:
            items.append({"label": "Not blocklisted", "label_ar": "غير محجوبة", "value": unb, "hint": "linked sites still live", "hint_ar": "مواقع مرتبطة ما زالت تعمل", "tone": "danger", "icon": "shield"})
    created, seen = ctx.get("infra", {}).get("domain_created"), ctx.get("observed_at")
    if created and seen:
        try:
            from datetime import date

            days = (date.fromisoformat(seen[:10]) - date.fromisoformat(created[:10])).days
            items.append({"label": "Domain age", "label_ar": "عمر النطاق", "value": days, "suffix": " d", "hint": f"registered {created}", "hint_ar": f"سُجّل في {created}",
                          "tone": "warn" if days <= 30 else "info", "icon": "calendar"})
        except ValueError:
            pass
    items.append({"label": "Evidence items", "label_ar": "عناصر الأدلة", "value": len(ctx.get("evidence", [])), "hint": "SHA-256 hashed", "hint_ar": "مُجزّأة بـ SHA-256", "tone": "ok", "icon": "file"})
    return {"type": "stat_row", "items": items[:5]}


def _block_journey(ctx: dict, item: dict) -> dict | None:
    steps = ctx.get("journey", [])
    if len(steps) < 2:
        return None
    en, ar = flow_text(ctx)
    return {"type": "journey", "title": item.get("title") or "How the victim is deceived", "title_ar": item.get("title_ar") or "كيف يُخدع الضحية", "steps": steps, "summary": en, "summary_ar": ar}


def _block_breakdown(ctx: dict, item: dict) -> dict | None:
    if not ctx["signals"]:
        return None
    p_safe, prev, rows = 1.0, 0, []
    for s in sorted(ctx["signals"], key=lambda g: -g["weight"]):
        p_safe *= 1 - s["weight"]
        cum = round(100 * (1 - p_safe))
        rows.append({"id": s["id"], "label": s["label"], "label_ar": s["label_ar"], "weight": round(s["weight"] * 100), "start": prev, "end": cum, "severity": s["severity"]})
        prev = cum
    return {"type": "score_breakdown", "title": item.get("title") or "How the score adds up", "title_ar": item.get("title_ar") or "كيف تتراكم الدرجة", "items": rows, "score": ctx["score"],
            "note": "Independent signals combine: each one raises the score but none decides alone.", "note_ar": "المؤشرات المستقلة تتراكم: كل مؤشر يرفع الدرجة ولا يحسمها وحده."}


def _block_indicators(ctx: dict, item: dict) -> dict | None:
    io, ct, groups = ctx.get("iocs", {}), ctx.get("contacts", {}), []

    def grp(title, title_ar, items):
        if items:
            groups.append({"title": title, "title_ar": title_ar, "items": items})

    grp("Data-theft channels", "قنوات سرقة البيانات", [{"value": f"telegram_bot:{b}", "tone": "danger"} for b in io.get("telegram_bot_ids", [])]
        + [{"value": f"discord_webhook:{w}", "tone": "danger"} for w in io.get("discord_webhook_ids", [])])
    grp("Payment", "الدفع", [{"value": w, "tone": "danger"} for w in io.get("wallets", [])])
    grp("Contact", "التواصل", [{"value": n, "tone": "warn"} for n in ct.get("whatsapp", [])] + [{"value": n, "tone": "info"} for n in ct.get("phones", []) + ct.get("emails", [])])
    grp("Domain and server", "النطاق والخادم", ([{"value": ctx["domain"], "tone": "info"}] if ctx.get("browsed", True) and ctx.get("domain") else [])
        + ([{"value": ctx["infra"]["ip"], "tone": "info"}] if ctx.get("infra", {}).get("ip") else []))
    grp("Scam-kit files", "ملفات أدوات الاحتيال", [{"value": f"{k['name']}  sha256:{k['sha256'][:16]}…", "tone": "warn", "copy": k["sha256"]} for k in ctx.get("kit_files", [])])
    if not groups:
        return None
    return {"type": "indicators", "title": item.get("title") or "Indicators to share", "title_ar": item.get("title_ar") or "مؤشرات للمشاركة", "groups": groups}


def _block_infra(ctx: dict, item: dict) -> dict:
    i = ctx.get("infra", {})
    rows = []
    if ctx.get("browsed", True) and i:
        rows = [
            {"k": "Registered", "k_ar": "تاريخ التسجيل", "v": i.get("domain_created", "-"), "tone": "warn" if i.get("domain_created", "0")[:4] == "2026" else None},
            {"k": "Registrar", "k_ar": "المسجّل", "v": i.get("registrar", "-")},
            {"k": "Hosting", "k_ar": "الاستضافة", "v": f"{i.get('asn_org', '-')} ({i.get('asn', '-')})"},
            {"k": "Hosting country (indicator)", "k_ar": "بلد الاستضافة (مؤشر)", "v": i.get("country", "-")},
            {"k": "Server IP", "k_ar": "عنوان الخادم", "v": i.get("ip", "-"), "mono": True},
            {"k": "TLS certificate", "k_ar": "شهادة TLS", "v": f"issued {i.get('cert_issued', '-')} by {i.get('cert_issuer', '-')}"},
            {"k": "Name servers", "k_ar": "خوادم الأسماء", "v": ", ".join(i.get("nameservers", [])) or "-", "mono": True},
        ]
    c = ctx.get("contacts", {})
    for n in c.get("whatsapp", []):
        rows.append({"k": "WhatsApp", "k_ar": "واتساب", "v": n, "mono": True, "tone": "danger"})
    for n in c.get("phones", []):
        rows.append({"k": "Phone", "k_ar": "هاتف", "v": n, "mono": True})
    for n in c.get("emails", []):
        rows.append({"k": "E-mail", "k_ar": "بريد إلكتروني", "v": n, "mono": True})
    io = ctx.get("iocs", {})
    for b in io.get("telegram_bot_ids", []):
        rows.append({"k": "Telegram bot ID", "k_ar": "معرّف بوت تيليجرام", "v": b, "mono": True, "tone": "danger"})
    for w in io.get("discord_webhook_ids", []):
        rows.append({"k": "Discord webhook ID", "k_ar": "معرّف ويب هوك ديسكورد", "v": w, "mono": True, "tone": "danger"})
    for w in io.get("wallets", []):
        rows.append({"k": "Crypto wallet", "k_ar": "محفظة رقمية", "v": w, "mono": True, "tone": "danger"})
    return {"type": "kv_table", "title": item.get("title") or "Infrastructure indicators", "title_ar": item.get("title_ar") or "مؤشرات البنية التحتية", "rows": rows,
            "note": "Hosting location is an infrastructure indicator only. It does not show where the operator is.",
            "note_ar": "موقع الاستضافة مؤشر تقني فقط ولا يدل على مكان وجود المحتال."}


def _block_map(ctx: dict, item: dict) -> dict:
    counts: Counter = Counter()
    for e in ctx.get("targeting", {}).get("emirates", []):
        counts[e] += 1
    for r in ctx.get("related", []):
        if r["strength"] in ("strong", "medium"):
            for e in r.get("emirates", []):
                counts[e] += 1
    return {"type": "emirate_map", "title": item.get("title") or "Who is being targeted", "title_ar": item.get("title_ar") or "من المستهدف", "counts": dict(counts),
            "note": "Emirates the lure is aimed at (sites in this campaign).", "note_ar": "الإمارات التي تستهدفها الحملة."}


def _block_evidence(ctx: dict, item: dict) -> dict:
    return {"type": "evidence_list", "title": item.get("title") or "Evidence chain of custody", "title_ar": item.get("title_ar") or "سلسلة حيازة الأدلة",
            "items": ctx.get("evidence", []), "manifest": ctx.get("manifest", ""), "mode": ctx.get("evidence_mode", "replay")}


def _block_actions(ctx: dict, refined: dict, item: dict) -> dict:
    base = {a["id"]: a for a in recommended_actions(ctx)}
    items = []
    for a in refined.get("recommended_actions", []):
        merged = {**base.get(a["id"], {"kind": "report"}), **{k: v for k, v in a.items() if v}}
        items.append(merged)
    for aid, a in base.items():
        if aid not in {i["id"] for i in items}:
            items.append(a)
    return {"type": "action_list", "title": item.get("title") or "Recommended actions", "title_ar": item.get("title_ar") or "الإجراءات الموصى بها", "items": items}


def compose(ctx: dict, refined: dict) -> list[dict]:
    """Build the final block list. Always includes a verdict; unknown layout entries are skipped."""
    blocks: list[dict] = []
    seen_verdict = False
    for item in refined.get("layout", []):
        kind = item.get("block")
        block: dict | None = None
        if kind == "verdict":
            block, seen_verdict = _block_verdict(ctx, refined, item), True
        elif kind == "callout":
            block = {"type": "callout", "tone": item.get("tone") or "info", "title": item.get("title", ""), "title_ar": item.get("title_ar", ""),
                     "text": item.get("text", ""), "text_ar": item.get("text_ar", "")}
        elif kind == "narrative":
            block = {"type": "markdown", "title": item.get("title", ""), "title_ar": item.get("title_ar", ""), "text": item.get("text", ""), "text_ar": item.get("text_ar", "")}
        elif kind == "stats":
            block = _block_stats(ctx, item)
        elif kind == "journey":
            block = _block_journey(ctx, item)
        elif kind == "breakdown":
            block = _block_breakdown(ctx, item)
        elif kind == "indicators":
            block = _block_indicators(ctx, item)
        elif kind == "signals":
            block = _block_signals(ctx, item)
        elif kind == "campaign":
            block = _block_campaign(ctx, item)
        elif kind == "infrastructure":
            block = _block_infra(ctx, item)
        elif kind == "evidence":
            block = _block_evidence(ctx, item)
        elif kind == "actions":
            block = _block_actions(ctx, refined, item)
        elif kind == "map":
            block = _block_map(ctx, item)
        if block:
            blocks.append(block)
    if not seen_verdict:
        blocks.insert(0, _block_verdict(ctx, refined, {}))
    return blocks


# ---------------------------------------------------------------- question answering (offline)

def answer_offline(ctx: dict, question: str) -> dict:
    q = question.lower()
    refined = offline_refine(ctx)
    strong = [r for r in ctx.get("related", []) if r["strength"] == "strong"]
    if any(w in q for w in ("why", "score", "reason", "explain", "لماذا", "سبب")):
        top = sorted(ctx["signals"], key=lambda s: -s["weight"])
        text = f"The score is {ctx['score']}/100. It comes from independent signals combined (a noisy-OR, so no single signal decides alone): " + ", ".join(f"{s['label']} ({int(s['weight'] * 100)})" for s in top[:5]) + "."
        text_ar = f"النتيجة {ctx['score']}/100 وهي ناتجة عن دمج مؤشرات مستقلة: " + "، ".join(s["label_ar"] for s in top[:5]) + "."
        return {"answer": text, "answer_ar": text_ar, "blocks": [_block_signals(ctx, {})]}
    if any(w in q for w in ("link", "related", "campaign", "same", "other", "مرتبط", "حملة")):
        if not ctx.get("related"):
            return {"answer": "No other known site shares indicators with this one.", "answer_ar": "لا يوجد موقع آخر معروف يشترك بمؤشرات مع هذا الموقع.", "blocks": []}
        e = strong[0]["reasons"][0]["text"] if strong else ctx["related"][0]["reasons"][0]["text"]
        return {"answer": f"{len(ctx['related'])} site(s) are connected, {len(strong)} of them strongly. Example: {e}.",
                "answer_ar": f"يوجد {len(ctx['related'])} موقعاً مرتبطاً، منها {len(strong)} بشكل قوي.", "blocks": [_block_campaign(ctx, {})]}
    if any(w in q for w in ("journey", "victim's", "walk me", "step", "رحلة", "خطوة")):
        j = _block_journey(ctx, {})
        en, ar = flow_text(ctx)
        return {"answer": en, "answer_ar": ar, "blocks": [j] if j else []}
    if any(w in q for w in ("breakdown", "add up", "calculated", "تتراكم")):
        b = _block_breakdown(ctx, {})
        return {"answer": "Each signal raises the score; they combine so that no single one decides alone.", "answer_ar": "كل مؤشر يرفع الدرجة وهي تتراكم بحيث لا يحسمها مؤشر واحد.", "blocks": [b] if b else []}
    if any(w in q for w in ("indicator", "ioc", "share", "bot", "wallet", "مؤشرات")):
        i = _block_indicators(ctx, {})
        return {"answer": "These indicators can be shared with banks, platforms and other agencies.", "answer_ar": "يمكن مشاركة هذه المؤشرات مع البنوك والمنصات والجهات الأخرى.", "blocks": [i] if i else []}
    if any(w in q for w in ("do", "action", "next", "takedown", "recommend", "إجراء", "ماذا")):
        return {"answer": "Here are the recommended actions, most urgent first.", "answer_ar": "هذه الإجراءات الموصى بها بدءاً بالأكثر إلحاحاً.", "blocks": [_block_actions(ctx, refined, {})]}
    if any(w in q for w in ("where", "host", "country", "infra", "أين", "استضافة")):
        return {"answer": "Infrastructure indicators below. Hosting location shows where the server is, not where the operator is.",
                "answer_ar": "مؤشرات البنية التحتية أدناه. موقع الاستضافة يدل على مكان الخادم لا على مكان المحتال.", "blocks": [_block_infra(ctx, {})]}
    if any(w in q for w in ("who", "target", "victim", "emirate", "المستهدف", "ضحية")):
        return {"answer": refined["victim_impact"], "answer_ar": refined["victim_impact_ar"], "blocks": [_block_map(ctx, {})]}
    return {"answer": refined["summary"], "answer_ar": refined["summary_ar"], "blocks": [_block_verdict(ctx, refined, {})]}
