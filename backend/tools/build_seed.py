"""Generate the recorded-evidence cases and discovery feeds used by replay mode.

Everything here is FICTIONAL demo data: invented domains on the reserved `.test`
TLD, documentation-range IP addresses (RFC 5737), documentation AS numbers
(RFC 5398) and made-up contact numbers and indicators. A case is the *evidence
a sandbox browser would record* (page structure, field metadata, extracted
indicators, infrastructure facts), not a working copy of any website.

Run:  python backend/tools/build_seed.py
"""

from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "raqib" / "data"
OBSERVED = "2026-11-24"
rng = random.Random(7)


def sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


# ------------------------------------------------------------------ page builder

class Page:
    def __init__(self, n: int, url: str, title: str, lang: str = "en"):
        self.n = 0
        self.d = {"page_id": f"p{n}", "url": url, "title": title, "lang": lang,
                  "elements": [], "forms": [], "scripts": [], "assets": [], "meta": {}, "network": []}

    def add(self, kind: str, text: str = "", **kw) -> str:
        self.n += 1
        el = {"id": f"e{self.n}", "kind": kind}
        if text:
            el["text"] = text
        el.update(kw)
        self.d["elements"].append(el)
        return el["id"]

    def field(self, form: str, name: str, label: str, type_: str = "text", ac: str = "", ph: str = "", mode: str = "", maxlen: int | None = None) -> str:
        f = {"name": name, "type": type_, "autocomplete": ac, "placeholder": ph, "inputmode": mode, "label": label}
        if maxlen:
            f["maxlength"] = maxlen
        return self.add("select" if type_ == "select" else "input", label, form=form, field=f)

    def form(self, fid: str, action: str = "") -> None:
        self.d["forms"].append({"id": fid, "action": action, "method": "post"})

    def scripts(self, kit: dict | None, host: str) -> None:
        net = [{"method": "GET", "url": self.d["url"], "status": 200, "type": "document"}]
        self.d["scripts"].append({"src": "https://code.jquery.com/jquery-3.6.0.min.js", "sha256": sha("jquery-3.6.0"), "size": 89501, "library": True, "iocs": {}})
        net.append({"method": "GET", "url": "https://code.jquery.com/jquery-3.6.0.min.js", "status": 200, "type": "script"})
        if kit:
            self.d["scripts"].append({"src": kit["src"], "sha256": sha(kit["content"]), "size": kit.get("size", 4800), "iocs": kit.get("iocs", {}), "kit": kit["content"]})
            net.append({"method": "GET", "url": f"http://{host}/{kit['src']}", "status": 200, "type": "script", "flag": "kit"})
        net.append({"method": "GET", "url": f"http://{host}/favicon.ico", "status": 200, "type": "image"})
        self.d["network"] = net
        if kit and kit["content"].startswith("tolltrap"):
            self.d["meta"]["favicon_hash"] = sha("favicon-tolltrap")
        if kit and kit["content"].startswith("jobbait"):
            self.d["meta"]["analytics_ids"] = ["G-4F7Q2LM9XA"]


KITS = {
    "K1": {"src": "assets/kit.js", "content": "tolltrap-v1", "iocs": {"telegram_bot_ids": ["7139462058"]}},
    "K1b": {"src": "assets/pay.js", "content": "tolltrap-v1b", "iocs": {"telegram_bot_ids": ["7139462058"]}},
    "K2": {"src": "assets/app.js", "content": "banklure-v2", "iocs": {"discord_webhook_ids": ["1187733521900044288"]}},
    "K3": {"src": "assets/gr.js", "content": "goldrush-v3", "iocs": {"wallets": ["TQ7hX2mVpR9kLc4sN8wB3yF6dJ1eZ5aGuK"]}},
    "K4": {"src": "js/main.js", "content": "jobbait-v1", "iocs": {}},
    "K5": {"src": "assets/site.js", "content": "rtacopy-v1", "iocs": {"telegram_bot_ids": ["5520183374"]}},
}
WALLET = "TQ7hX2mVpR9kLc4sN8wB3yF6dJ1eZ5aGuK"

CARD = [("cardholder", "Cardholder name", "text", "cc-name", "", "", None),
        ("cardnumber", "Card number", "text", "cc-number", "1234 5678 9012 3456", "numeric", 19),
        ("exp", "Expiry date", "text", "cc-exp", "MM/YY", "numeric", 5),
        ("cvv", "CVV", "text", "cc-csc", "CVV", "numeric", 4)]


def card_form(p: Page, form: str) -> None:
    p.form(form)
    for name, label, t, ac, ph, mode, ml in CARD:
        p.field(form, name, label, t, ac, ph, mode, ml)


def otp_page(n: int, host: str, brand: str, kit: dict | None) -> Page:
    p = Page(n, f"http://{host}/otp.html", f"{brand} - Verification")
    p.add("header", brand)
    p.add("text", "Enter the 6-digit verification code sent to your mobile number to complete the payment.")
    p.form("otpForm")
    p.field("otpForm", "otp", "Verification code", "text", "one-time-code", "000000", "numeric", 6)
    p.add("button", "Verify")
    p.scripts(kit, host)
    return p


# ------------------------------------------------------------------ page templates per scam type

def toll(host: str, brand: str, kit: dict, wa: str, plate: str = "Dubai A 48213", amount: str = "50.00") -> list[Page]:
    p1 = Page(1, f"http://{host}/", f"{brand} - Account balance")
    p1.add("header", brand)
    p1.add("banner", f"Insufficient balance: your {brand} account will be suspended")
    p1.add("text", f"Vehicle {plate} has unpaid toll charges of AED {amount}.")
    p1.add("timer", "23:59:41")
    p1.add("button", "Top up now")
    p1.add("badge", "Secure payment")
    p1.add("footer", f"Customer care on WhatsApp: {wa}", whatsapp=wa)
    p1.scripts(kit, host)
    p2 = Page(2, f"http://{host}/pay.html", f"{brand} - Pay securely")
    p2.add("header", brand)
    p2.add("text", f"Amount due: AED {amount}")
    card_form(p2, "payForm")
    p2.add("button", "Pay securely")
    p2.add("footer", f"Customer care on WhatsApp: {wa}", whatsapp=wa)
    p2.scripts(kit, host)
    return [p1, p2, otp_page(3, host, brand, kit)]


def fines(host: str, brand: str, kit: dict, wa: str, amount: str = "400.00", brand_line: str = "Traffic fines inquiry") -> list[Page]:
    p1 = Page(1, f"http://{host}/", f"{brand} - {brand_line}")
    p1.add("header", brand)
    p1.add("heading", brand_line)
    p1.form("plateForm")
    p1.field("plateForm", "plate_code", "Plate code", "text", "", "A")
    p1.field("plateForm", "plate_number", "Plate number", "text", "", "e.g. 48213")
    p1.add("button", "Search fines")
    p1.scripts(kit, host)
    p2 = Page(2, f"http://{host}/fines.html", f"{brand} - Fines found")
    p2.add("header", brand)
    p2.add("banner", "Pay within 24 hours to avoid a 50% penalty and vehicle impoundment")
    p2.add("text", f"1 unpaid fine: exceeding the speed limit, AED {amount}")
    p2.add("timer", "23:12:09")
    p2.add("button", "Pay now")
    p2.add("footer", f"Support: {wa}", whatsapp=wa)
    p2.scripts(kit, host)
    p3 = Page(3, f"http://{host}/pay.html", f"{brand} - Payment")
    p3.add("header", brand)
    p3.add("text", f"Amount due: AED {amount}")
    card_form(p3, "payForm")
    p3.add("button", "Pay now")
    p3.scripts(kit, host)
    return [p1, p2, p3, otp_page(4, host, brand, kit)]


def parcel(host: str, brand: str, kit: dict, wa: str, fee: str = "7.50", tracking: str = "AE7781-20") -> list[Page]:
    p1 = Page(1, f"http://{host}/", f"{brand} - Parcel on hold")
    p1.add("header", brand)
    p1.add("banner", f"Your parcel {tracking} is on hold: incomplete address")
    p1.add("text", f"A redelivery fee of AED {fee} applies. Reschedule within 24 hours or the parcel is returned.")
    p1.add("button", "Reschedule delivery")
    p1.add("footer", f"Support: {wa}", whatsapp=wa)
    p1.scripts(kit, host)
    p2 = Page(2, f"http://{host}/address.html", f"{brand} - Delivery details")
    p2.add("header", brand)
    p2.form("addressForm")
    p2.field("addressForm", "fullname", "Full name", "text", "name")
    p2.field("addressForm", "mobile", "Mobile number", "tel", "tel", "05X XXX XXXX", "tel")
    p2.field("addressForm", "emirate", "Emirate", "select")
    p2.field("addressForm", "street", "Street / building", "text", "street-address")
    p2.add("button", "Continue to payment")
    p2.scripts(kit, host)
    p3 = Page(3, f"http://{host}/pay.html", f"{brand} - Pay delivery fee")
    p3.add("header", brand)
    p3.add("text", f"Delivery fee: AED {fee}")
    card_form(p3, "payForm")
    p3.add("button", "Pay AED " + fee)
    p3.scripts(kit, host)
    return [p1, p2, p3, otp_page(4, host, brand, kit)]


def bank(host: str, brand: str, kit: dict, phone: str | None = None) -> list[Page]:
    p1 = Page(1, f"http://{host}/", f"{brand} - Account verification")
    p1.add("header", brand)
    p1.add("banner", "Your account has been temporarily restricted. Verify your identity within 12 hours.")
    p1.form("loginForm")
    p1.field("loginForm", "username", "Username", "text", "username")
    p1.field("loginForm", "password", "Password", "password", "current-password")
    p1.add("button", "Verify and restore")
    if phone:
        p1.add("footer", f"Account support: {phone}", phone=phone)
    p1.scripts(kit, host)
    p2 = Page(2, f"http://{host}/verify.html", f"{brand} - Confirm identity")
    p2.add("header", brand)
    p2.form("idForm")
    p2.field("idForm", "otp", "One-time code", "text", "one-time-code", "000000", "numeric", 6)
    p2.field("idForm", "emirates_id", "Emirates ID", "text", "", "784-XXXX-XXXXXXX-X", "numeric")
    p2.add("button", "Confirm")
    p2.scripts(kit, host)
    return [p1, p2]


def invest(host: str, brand: str, kit: dict, wa: str, wallet: str = WALLET) -> list[Page]:
    p = Page(1, f"http://{host}/", f"{brand} - AI-powered trading")
    p.add("header", brand)
    p.add("heading", "Guaranteed 30% monthly returns with AI-powered trading")
    p.add("ticker", "Recent payouts: AED 12,400 · AED 8,950 · AED 31,000")
    p.add("badge", "Licensed and regulated - licence no. FX-77120")
    p.add("text", "Deposit USDT (TRC20) to the address below to start earning today.")
    p.add("wallet", wallet, wallet=wallet)
    p.add("footer", f"Investor desk on WhatsApp: {wa}", whatsapp=wa)
    p.form("signupForm")
    p.field("signupForm", "fullname", "Full name", "text", "name")
    p.field("signupForm", "mobile", "Mobile", "tel", "tel", "", "tel")
    p.field("signupForm", "email", "Email", "email", "email")
    p.field("signupForm", "emirates_id", "Emirates ID", "text", "", "784-XXXX-XXXXXXX-X")
    p.add("button", "Start investing")
    p.scripts(kit, host)
    return [p]


def loan(host: str, brand: str, kit: dict, wa: str, wallet: str = WALLET) -> list[Page]:
    p1 = Page(1, f"http://{host}/", f"{brand} - Instant loans")
    p1.add("header", brand)
    p1.add("heading", "Instant personal loan up to AED 250,000. No salary certificate, approval in 10 minutes.")
    p1.form("loanForm")
    p1.field("loanForm", "fullname", "Full name", "text", "name")
    p1.field("loanForm", "mobile", "Mobile", "tel", "tel", "", "tel")
    p1.field("loanForm", "emirates_id", "Emirates ID", "text", "", "784-XXXX-XXXXXXX-X")
    p1.field("loanForm", "salary", "Monthly salary", "select")
    p1.add("button", "Check eligibility")
    p1.scripts(kit, host)
    p2 = Page(2, f"http://{host}/fee.html", f"{brand} - Approved")
    p2.add("header", brand)
    p2.add("banner", "Approved: AED 120,000. Pay the AED 99 refundable processing fee to release the funds.")
    p2.add("wallet", wallet, wallet=wallet)
    p2.add("footer", f"Loan officer on WhatsApp: {wa}", whatsapp=wa)
    p2.scripts(kit, host)
    return [p1, p2]


def job(host: str, brand: str, kit: dict, wa: str, email: str) -> list[Page]:
    p1 = Page(1, f"http://{host}/", f"{brand} - Vacancies")
    p1.add("header", brand)
    p1.add("heading", "Hiring now in Abu Dhabi: warehouse and office staff, salary AED 6,500 + free visa")
    p1.add("button", "Apply now")
    p1.add("footer", f"HR on WhatsApp: {wa}", whatsapp=wa, email=email)
    p1.scripts(kit, host)
    p2 = Page(2, f"http://{host}/apply.html", f"{brand} - Apply")
    p2.add("header", brand)
    p2.add("text", "Selected candidates pay a visa processing fee of AED 750 before the offer letter is issued.")
    p2.form("applyForm")
    p2.field("applyForm", "fullname", "Full name", "text", "name")
    p2.field("applyForm", "passport", "Passport number", "text")
    p2.field("applyForm", "email", "Email", "email", "email")
    p2.add("button", "Submit application")
    p2.scripts(kit, host)
    return [p1, p2]


def bakery(host: str) -> list[Page]:
    p = Page(1, f"http://{host}/", "Al Noor Bakery - Abu Dhabi")
    p.add("header", "Al Noor Bakery")
    p.add("heading", "Fresh bread and Arabic sweets since 2011")
    p.add("text", "Open daily 6am to 11pm. Al Khalidiyah, Abu Dhabi.")
    p.add("address", "Street 14, Al Khalidiyah, Abu Dhabi")
    p.add("footer", "Call us: +971 2 667 4410", phone="+971 2 667 4410")
    p.form("newsletter")
    p.field("newsletter", "email", "Email for our newsletter", "email", "email")
    p.add("button", "Subscribe")
    p.scripts(None, host)
    return [p]


def courier(host: str, brand: str, with_scamlike_layout: bool = True) -> list[Page]:
    p = Page(1, f"http://{host}/", f"{brand} - Track your parcel")
    p.add("header", brand)
    p.add("banner", "Track a shipment in seconds")
    p.add("text", "Enter your tracking number to see where your parcel is. Pay on delivery, no online payment.")
    p.form("trackForm")
    p.field("trackForm", "tracking", "Tracking number", "text")
    p.add("button", "Track")
    p.add("address", "Warehouse 7, Mussafah Industrial Area, Abu Dhabi")
    p.add("footer", "Customer service: +971 2 555 0148", phone="+971 2 555 0148")
    p.scripts(None, host)
    return [p]


# ------------------------------------------------------------------ narration script

NOTE_AR = {
    "open": "فتح الرابط داخل متصفح معزول بملف جوال إماراتي…",
    "loaded": "تم تحميل الصفحة: {title}",
    "field_sensitive": "حقل «{label}» حساس: الوكيل لا يدخل أي بيانات.",
    "field_plain": "حقل «{label}»: إدخال قيمة تجريبية غير حساسة.",
    "click": "الضغط على «{label}» لمتابعة مسار الضحية.",
    "scripts": "تحليل سكربتات الصفحة بحثاً عن مؤشرات…",
}
SENSITIVE = {"card_number", "card_cvv", "card_expiry", "card_holder", "otp", "password", "emirates_id", "username"}


def auto_script(pages: list[Page], chain: list[dict], kinds_of) -> list[dict]:
    steps: list[dict] = []
    first = True
    for i, page in enumerate(pages):
        d = page.d
        if first:
            steps.append({"type": "note", "text": "Opening the link in an isolated browser (mobile profile, UAE locale, no stored data).", "text_ar": NOTE_AR["open"]})
            for hop in chain[:-1]:
                steps.append({"type": "redirect", "url": hop["url"], "status": hop["status"]})
            first = False
        steps.append({"type": "navigate", "page_index": i})
        steps.append({"type": "note", "text": f"Loaded “{d['title']}”.", "text_ar": NOTE_AR["loaded"].format(title=d["title"])})
        if d["scripts"] and any(not s.get("library") for s in d["scripts"]):
            steps.append({"type": "note", "text": "Inspecting the page's scripts for known indicators.", "text_ar": NOTE_AR["scripts"]})
        steps.append({"type": "cursor", "action": "scroll", "target": d["elements"][0]["id"], "label": "scroll"})
        fields = [e for e in d["elements"] if e["kind"] in ("input", "select")]
        for e in fields:
            kind = kinds_of(e)
            if kind in SENSITIVE:
                steps.append({"type": "cursor", "action": "move", "target": e["id"], "label": e["text"]})
                steps.append({"type": "note", "text": f"“{e['text']}” is a sensitive field. The agent does not enter any data.", "text_ar": NOTE_AR["field_sensitive"].format(label=e["text"])})
            else:
                steps.append({"type": "cursor", "action": "type", "target": e["id"], "label": e["text"]})
        steps.append({"type": "analyze", "page_index": i})
        buttons = [e for e in d["elements"] if e["kind"] == "button"]
        if buttons and i < len(pages) - 1:
            b = buttons[0]
            steps.append({"type": "note", "text": f"Clicking “{b['text']}” to follow the victim's path.", "text_ar": NOTE_AR["click"].format(label=b["text"])})
            steps.append({"type": "cursor", "action": "click", "target": b["id"], "label": b["text"]})
    return steps


# ------------------------------------------------------------------ cases

def infra(ip: str, asn: int, org: str, country: str, registrar: str, created: str, cert: str, ns: list[str], cdn: bool = False) -> dict:
    return {"ip": ip, "asn": f"AS{asn}", "asn_org": org, "country": country, "registrar": registrar, "domain_created": created,
            "cert_issued": cert, "cert_issuer": rng.choice(["R11", "E6", "WE1"]), "nameservers": ns, "cdn": cdn}


CASES: list[dict] = []


def add_case(cid: str, host: str, family: str | None, label: str, pages: list[Page], inf: dict, source: str, emirates: list[str],
             truth: str, chain_from: str | None = None, contacts: dict | None = None, blocked: bool = False) -> None:
    final = pages[0].d["url"]
    chain = [{"url": final, "status": 200}]
    input_url = final
    if chain_from:
        input_url = f"http://{chain_from}/?id=AE7781-20"
        chain = [{"url": input_url, "status": 302}, {"url": final, "status": 200}]
    CASES.append({
        "case_id": cid, "kind": "site", "label": label, "input_url": input_url, "final_url": final, "host": host,
        "source": source, "observed_at": OBSERVED, "redirect_chain": chain,
        "pages": [p.d for p in pages], "infra": inf, "contacts": contacts or {},
        "targeting": {"emirates": emirates}, "on_blocklist": blocked,
        "ground_truth": {"label": truth, "family": family},
    })


NS1, NS2, NS3 = ["ns1.example-dns.test", "ns2.example-dns.test"], ["dns-a.hostmesh.test", "dns-b.hostmesh.test"], ["ns.quickzone.test", "ns2.quickzone.test"]
WA_A, WA_A2 = "+971524187730", "+971504418802"
WA_C, WA_D = "+971569023318", "+971581116040"

# Family A - "TollTrap" operator (Telegram bot 7139462058)
add_case("c_salik_topup", "salik-topup-ae.test", "A", "Salik top-up lure", toll("salik-topup-ae.test", "SALIK", KITS["K1"], WA_A),
         infra("203.0.113.17", 64500, "ExampleHost B.V.", "NL", "NameHub Ltd", "2026-11-20", "2026-11-21", NS1), "search_ad", ["Dubai"], "scam")
add_case("c_rta_fines", "rta-fines-payment.test", "A", "RTA fines lure", fines("rta-fines-payment.test", "RTA", KITS["K1"], WA_A),
         infra("203.0.113.17", 64500, "ExampleHost B.V.", "NL", "NameHub Ltd", "2026-11-20", "2026-11-21", NS1), "search_ad", ["Dubai", "Sharjah"], "scam")
add_case("c_epost_redelivery", "emiratespost-redelivery.test", "A", "Emirates Post redelivery lure (SMS)",
         parcel("emiratespost-redelivery.test", "EMIRATES POST", KITS["K1"], WA_A),
         infra("198.51.100.44", 64501, "NorthVPS Inc.", "US", "NameHub Ltd", "2026-11-19", "2026-11-19", NS1), "sms", ["Abu Dhabi", "Dubai", "Sharjah", "Ajman"],
         "scam", chain_from="track-parcel-ae.test")
add_case("c_salik_pay", "salik-pay-uae.test", "A", "Salik variant", toll("salik-pay-uae.test", "SALIK", KITS["K1b"], WA_A2, "Dubai B 11902", "35.00"),
         infra("198.51.100.44", 64501, "NorthVPS Inc.", "US", "NameHub Ltd", "2026-11-18", "2026-11-18", NS1), "ct", ["Dubai"], "scam", blocked=True)
add_case("c_rta_ae_fines", "rta-ae-fines.test", "A", "RTA variant", fines("rta-ae-fines.test", "RTA", KITS["K1"], WA_A, "250.00"),
         infra("203.0.113.90", 64502, "CloudEdge", "DE", "NameHub Ltd", "2026-11-20", "2026-11-21", NS1, True), "ct", ["Dubai"], "scam")
add_case("c_dp_fines", "dubai-fines-gov.test", "A", "Dubai Police fines lure", fines("dubai-fines-gov.test", "DUBAI POLICE", KITS["K1"], WA_A2, "600.00", "Pay your fine online"),
         infra("203.0.113.91", 64502, "CloudEdge", "DE", "QuickReg", "2026-11-21", "2026-11-22", NS3, True), "search_ad", ["Dubai"], "scam")
add_case("c_aramex_hold", "aramex-parcel-hold.test", "A", "Aramex parcel lure", parcel("aramex-parcel-hold.test", "ARAMEX", KITS["K1b"], WA_A2, "9.00", "AX90417"),
         infra("198.51.100.71", 64503, "BulkNode Hosting", "TR", "QuickReg", "2026-11-21", "2026-11-21", NS3), "sms", ["Dubai", "Abu Dhabi"], "scam")

# Family B - "BankLure" operator (Discord webhook 1187733521900044288)
add_case("c_adcb_verify", "adcb-secure-verify.test", "B", "ADCB account verification", bank("adcb-secure-verify.test", "ADCB", KITS["K2"], "+971557301194"),
         infra("192.0.2.58", 64504, "PrimeVPS GmbH", "DE", "BlueGate Registrar", "2026-11-17", "2026-11-17", NS2), "sms", ["Abu Dhabi", "Dubai"], "scam", blocked=True)
add_case("c_enbd_restore", "enbd-account-restore.test", "B", "Emirates NBD restore", bank("enbd-account-restore.test", "EMIRATES NBD", KITS["K2"]),
         infra("192.0.2.59", 64504, "PrimeVPS GmbH", "DE", "BlueGate Registrar", "2026-11-17", "2026-11-18", NS2), "ct", ["Dubai"], "scam")
add_case("c_fab_login", "bankfab-verify-login.test", "B", "FAB verification", bank("bankfab-verify-login.test", "FIRST ABU DHABI BANK", KITS["K2"]),
         infra("192.0.2.60", 64504, "PrimeVPS GmbH", "DE", "BlueGate Registrar", "2026-11-19", "2026-11-19", NS2), "sms", ["Abu Dhabi"], "scam")

# Family C - "GoldRush" operator (USDT wallet + WhatsApp)
add_case("c_goldtrade", "goldtrade-invest-ae.test", "C", "GoldTrade investment scam", invest("goldtrade-invest-ae.test", "GOLDTRADE CAPITAL", KITS["K3"], WA_C),
         infra("203.0.113.120", 64505, "SwiftServe", "SG", "QuickReg", "2026-11-12", "2026-11-13", NS3), "search_ad", ["Dubai", "Abu Dhabi"], "scam")
add_case("c_quickloan", "quickloan-uae-now.test", "C", "QuickLoan advance-fee scam", loan("quickloan-uae-now.test", "QUICKLOAN UAE", KITS["K3"], WA_C),
         infra("203.0.113.121", 64505, "SwiftServe", "SG", "QuickReg", "2026-11-12", "2026-11-13", NS3), "search_ad", ["Abu Dhabi", "Sharjah", "Ajman"], "scam")
add_case("c_cryptomax", "cryptomax-uae-signal.test", "C", "CryptoMax signals scam", invest("cryptomax-uae-signal.test", "CRYPTOMAX UAE", KITS["K3"], "+971547730021"),
         infra("203.0.113.122", 64505, "SwiftServe", "SG", "NameHub Ltd", "2026-11-14", "2026-11-14", NS1), "ct", ["Dubai"], "scam")

# Family D - "JobBait" (separate operator)
add_case("c_mohre_jobs", "mohre-jobs-uae.test", "D", "Fake MOHRE job offers", job("mohre-jobs-uae.test", "MOHRE JOBS", KITS["K4"], WA_D, "hr.recruit.uae@mailbox.test"),
         infra("198.51.100.120", 64506, "VeloHost", "US", "BlueGate Registrar", "2026-11-10", "2026-11-11", NS2), "search_ad", ["Abu Dhabi", "Dubai", "Ras Al Khaimah"], "scam")
add_case("c_careers_visa", "emirates-careers-visa.test", "D", "Fake airline careers", job("emirates-careers-visa.test", "EMIRATES CAREERS", KITS["K4"], WA_D, "hr.recruit.uae@mailbox.test"),
         infra("198.51.100.121", 64506, "VeloHost", "US", "BlueGate Registrar", "2026-11-10", "2026-11-11", NS2), "ct", ["Dubai"], "scam")

# Family F - a different operator copying the same RTA look (similar is not the same operator)
add_case("c_rta_copy", "rta-ae-payfine.test", "F", "RTA look-alike by another operator", fines("rta-ae-payfine.test", "RTA", KITS["K5"], "+971555093341", "300.00"),
         infra("192.0.2.200", 64507, "AlphaRack", "AE", "OtherReg", "2026-11-22", "2026-11-22", ["ns.otherdns.test", "ns2.otherdns.test"]), "ct", ["Dubai"], "scam")

# Benign
add_case("c_bakery", "alnoor-bakery.test", None, "Local bakery (benign)", bakery("alnoor-bakery.test"),
         infra("192.0.2.14", 64508, "GulfWeb Hosting", "AE", "DomainPlus", "2021-03-04", "2026-10-02", ["ns1.gulfweb.test", "ns2.gulfweb.test"]), "ct", ["Abu Dhabi"], "benign")
add_case("c_courier", "gulf-courier-express.test", None, "Genuine courier (benign look-alike)", courier("gulf-courier-express.test", "GULF COURIER EXPRESS"),
         infra("192.0.2.15", 64508, "GulfWeb Hosting", "AE", "DomainPlus", "2019-08-21", "2026-09-11", ["ns1.gulfweb.test", "ns2.gulfweb.test"]), "search", ["Abu Dhabi"], "benign")


# Maps listings that have no website to browse; they link to campaigns by phone
def listing_case(cid: str, name: str, phone: str | None, wa: str | None, area: str, emirate: str, family: str | None, truth: str) -> None:
    CASES.append({"case_id": cid, "kind": "maps_listing", "label": name, "input_url": f"maps://{cid}", "final_url": "", "host": name,
                  "source": "maps", "observed_at": OBSERVED, "redirect_chain": [], "pages": [], "infra": {},
                  "contacts": {"phones": [phone] if phone else [], "whatsapp": [wa] if wa else []},
                  "listing": {"name": name, "area": area, "emirate": emirate}, "targeting": {"emirates": [emirate]},
                  "ground_truth": {"label": truth, "family": family}})


listing_case("m_epost_center", "Emirates Post Customer Service Center", None, WA_A, "Al Nahda", "Sharjah", "A", "scam")
listing_case("m_salik_desk", "Salik Recharge & Fines Help Desk", None, WA_A2, "Deira", "Dubai", "A", "scam")
listing_case("m_adcb_support", "ADCB Account Support 24/7", "+971557301194", None, "Al Markaziyah", "Abu Dhabi", "B", "scam")
listing_case("m_quickloan", "Quick Loan UAE - Fast Approval", None, WA_C, "Business Bay", "Dubai", "C", "scam")


# ------------------------------------------------------------------ discovery feeds

def write(path: str, obj) -> None:
    p = OUT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def feeds() -> None:
    S = {c["case_id"]: c for c in CASES if c["kind"] == "site"}
    def u(cid): return S[cid]["input_url"]
    queries = [
        ("salik recharge", "en", [("ad", "c_salik_topup", "Salik Account Top-up | Pay Toll Balance Online", "Your Salik account balance is low. Top up securely now."),
                                 ("organic", None, "Salik - Dubai's Toll Gate System", "https://www.salik.ae/"), ("ad", "c_salik_pay", "Salik Pay UAE - Instant Recharge", "Recharge your Salik tag in 60 seconds.")]),
        ("pay rta fine", "en", [("ad", "c_rta_fines", "RTA Traffic Fines Payment - Pay Now", "Check and pay your RTA fines online. 50% penalty after 24h."),
                               ("ad", "c_rta_copy", "Pay RTA Fine Online | Fast & Secure", "Search by plate number and pay instantly."),
                               ("organic", None, "RTA - Roads & Transport Authority", "https://www.rta.ae/")]),
        ("traffic fines dubai police", "en", [("ad", "c_dp_fines", "Dubai Police Fines - Pay Your Fine Online", "Official online payment for traffic fines."),
                                              ("organic", None, "Dubai Police", "https://www.dubaipolice.gov.ae/")]),
        ("emirates post track parcel", "en", [("ad", "c_epost_redelivery", "Emirates Post Redelivery - Reschedule Your Parcel", "Parcel on hold? Update your address and pay a small fee."),
                                             ("organic", None, "Emirates Post Group", "https://www.emiratespost.ae/"), ("organic", "c_courier", "Gulf Courier Express - Track Your Parcel", "Track a shipment in seconds.")]),
        ("aramex parcel on hold", "en", [("ad", "c_aramex_hold", "Aramex Parcel Hold - Confirm Delivery", "Confirm delivery details to release your parcel."),
                                        ("organic", None, "Aramex", "https://www.aramex.com/")]),
        ("adcb account blocked", "en", [("organic", "c_adcb_verify", "ADCB Secure Verification Portal", "Verify your identity to restore access."),
                                       ("organic", None, "Abu Dhabi Commercial Bank", "https://www.adcb.com/")]),
        ("instant loan uae no salary certificate", "en", [("ad", "c_quickloan", "QuickLoan UAE - Up to AED 250,000", "No salary certificate. Approval in 10 minutes."),
                                                         ("organic", None, "Personal loans in the UAE | Compare rates", "https://www.bank-compare-uae.test/loans")]),
        ("gold investment uae guaranteed return", "en", [("ad", "c_goldtrade", "GoldTrade Capital - AI Gold Trading", "Guaranteed monthly returns. Licensed and regulated."),
                                                         ("ad", "c_cryptomax", "CryptoMax UAE - Signals & Auto-Trading", "Join 4,000+ UAE investors.")]),
        ("jobs in abu dhabi with visa", "en", [("ad", "c_mohre_jobs", "MOHRE Jobs UAE - Apply Now", "Free visa. Salary AED 6,500."), ("ad", "c_careers_visa", "Emirates Careers - Cabin Crew & Ground Staff", "Apply today, visa provided."),
                                              ("organic", None, "Jobs in Abu Dhabi | Careers portal", "https://www.job-board-ae.test/abu-dhabi")]),
        ("دفع مخالفات المرور", "ar", [("ad", "c_rta_fines", "دفع مخالفات هيئة الطرق والمواصلات", "ادفع مخالفاتك الآن بأمان."), ("organic", None, "هيئة الطرق والمواصلات", "https://www.rta.ae/")]),
        ("تتبع شحنة بريد الإمارات", "ar", [("ad", "c_epost_redelivery", "بريد الإمارات - إعادة جدولة التوصيل", "طردك معلّق، حدّث العنوان."), ("organic", None, "بريد الإمارات", "https://www.emiratespost.ae/")]),
    ]
    out = []
    for q, lang, results in queries:
        rs = []
        for rank, (typ, cid, title, snip) in enumerate(results, start=1):
            if cid and cid in S:
                url, disp = S[cid]["final_url"], S[cid]["host"]
            else:
                url, disp = snip, snip.split("//")[-1].split("/")[0]
                snip = ""
            rs.append({"rank": rank, "type": typ, "title": title, "url": url, "display_url": disp, "snippet": snip})
        out.append({"query": q, "lang": lang, "location": "Abu Dhabi, UAE", "results": rs})
    write("feeds/search_results.json", {"generated_for": "demo", "queries": out})

    L = [
        ("m01", "Emirates Post - Main Post Office", "Government post office", "Al Khalidiyah", "Abu Dhabi", "+97126171555", None, "https://www.emiratespost.ae/", 4.1, 912, True, ["emirates post"]),
        ("m02", "Emirates Post Customer Service Center", "Post office", "Al Nahda", "Sharjah", None, WA_A, "http://emiratespost-redelivery.test/", 4.8, 6, False, ["emirates post", "parcel"]),
        ("m03", "RTA Customer Happiness Center", "Government office", "Al Barsha", "Dubai", "+97148009090", None, "https://www.rta.ae/", 4.0, 2210, True, ["rta"]),
        ("m04", "Salik Recharge & Fines Help Desk", "Government service", "Deira", "Dubai", None, WA_A2, "http://salik-topup-ae.test/", 5.0, 3, False, ["salik", "rta"]),
        ("m05", "ADCB - Al Markaziyah Branch", "Bank", "Al Markaziyah", "Abu Dhabi", "+97126210090", None, "https://www.adcb.com/", 4.2, 640, True, ["adcb"]),
        ("m06", "ADCB Account Support 24/7", "Bank", "Al Markaziyah", "Abu Dhabi", "+971557301194", None, None, 4.9, 4, False, ["adcb"]),
        ("m07", "Quick Loan UAE - Fast Approval", "Loan agency", "Business Bay", "Dubai", None, WA_C, "http://quickloan-uae-now.test/", 4.9, 11, False, ["loan"]),
        ("m08", "Gold Investment Advisors Dubai", "Investment service", "DIFC", "Dubai", None, WA_C, "http://goldtrade-invest-ae.test/", 5.0, 7, False, ["gold", "investment"]),
        ("m09", "Al Noor Bakery", "Bakery", "Al Khalidiyah", "Abu Dhabi", "+97126674410", None, "http://alnoor-bakery.test/", 4.5, 233, True, []),
        ("m10", "Gulf Courier Express", "Courier service", "Mussafah", "Abu Dhabi", "+97125550148", None, "http://gulf-courier-express.test/", 4.3, 118, True, []),
        ("m11", "Marina Pharmacy", "Pharmacy", "Dubai Marina", "Dubai", "+97144213377", None, None, 4.4, 301, True, []),
        ("m12", "Corniche Cafe", "Cafe", "Corniche", "Abu Dhabi", "+97126760011", None, None, 4.6, 872, True, []),
        ("m13", "Sparkle Car Wash", "Car wash", "Mussafah", "Abu Dhabi", "+97125559090", None, None, 4.1, 96, True, []),
        ("m14", "Al Majaz Dental Clinic", "Dental clinic", "Al Majaz", "Sharjah", "+97165551234", None, None, 4.7, 204, True, []),
        ("m15", "Etisalat Business Center", "Telecom", "Al Ain", "Abu Dhabi", "+97137555900", None, "https://www.etisalat.ae/", 3.9, 344, True, ["etisalat"]),
        ("m16", "DEWA Customer Service", "Utility", "Al Quoz", "Dubai", "+97148009000", None, "https://www.dewa.gov.ae/", 3.8, 489, True, ["dewa"]),
    ]
    write("feeds/maps_listings.json", {"listings": [dict(zip(
        ["id", "name", "category", "area", "emirate", "phone", "whatsapp", "website", "rating", "reviews", "claimed", "tags"], row)) for row in L]})

    # certificate-transparency style feed: scam domains hidden among ordinary new sites
    words_a = ["marina", "palm", "desert", "oasis", "falcon", "pearl", "dune", "coral", "saffron", "harbor", "skyline", "date", "jasmine", "noor", "wadi"]
    words_b = ["yoga", "studio", "dental", "bakery", "florist", "tutoring", "cafe", "fitness", "salon", "repairs", "tours", "garage", "catering", "legal", "design"]
    ct = []
    for cid, c in S.items():
        created = c["infra"].get("cert_issued", "2026-11-20")
        ct.append({"host": c["host"], "issued_at": created + "T0%d:%02d:00Z" % (rng.randint(1, 9), rng.randint(0, 59)), "issuer": c["infra"].get("cert_issuer", "R11"), "case_id": cid})
    seen = {e["host"] for e in ct}
    ct.append({"host": "track-parcel-ae.test", "issued_at": "2026-11-19T09:12:00Z", "issuer": "R11", "case_id": None})
    for extra in ["salik-recharge-ae.test", "emiratespost-ae-track.test", "adcb-verify-account.test", "rta-gov-fine.test", "dubai-police-payfine.test"]:
        ct.append({"host": extra, "issued_at": "2026-11-2%dT1%d:%02d:00Z" % (rng.randint(0, 3), rng.randint(0, 9), rng.randint(0, 59)), "issuer": "E6", "case_id": None})
    while len(ct) < 320:
        host = f"{rng.choice(words_a)}-{rng.choice(words_b)}{rng.choice(['', '-uae', '-ae', '-dubai', ''])}.test"
        if host in seen:
            continue
        seen.add(host)
        ct.append({"host": host, "issued_at": "2026-11-%02dT%02d:%02d:00Z" % (rng.randint(14, 23), rng.randint(0, 23), rng.randint(0, 59)), "issuer": rng.choice(["R11", "E6", "WE1"]), "case_id": None})
    ct.sort(key=lambda e: e["issued_at"])
    write("feeds/ct_log.json", {"entries": ct})

    write("feeds/blocklist.json", {"source": "public blocklist (simulated for the demo)", "domains": [c["host"] for c in S.values() if c.get("on_blocklist")]})

    write("feeds/reports.json", {"reports": [
        {"id": "r01", "channel": "sms", "received": "2026-11-23T08:14:00Z", "emirate": "Dubai", "url": S["c_epost_redelivery"]["input_url"],
         "text": "Emirates Post: your parcel AE7781-20 is on hold, update address: " + S["c_epost_redelivery"]["input_url"]},
        {"id": "r02", "channel": "sms", "received": "2026-11-23T09:41:00Z", "emirate": "Sharjah", "url": S["c_aramex_hold"]["input_url"],
         "text": "Aramex: confirm delivery of your shipment " + S["c_aramex_hold"]["input_url"]},
        {"id": "r03", "channel": "sms", "received": "2026-11-23T11:02:00Z", "emirate": "Abu Dhabi", "url": S["c_adcb_verify"]["input_url"],
         "text": "Your bank account has been restricted. Verify now: " + S["c_adcb_verify"]["input_url"]},
        {"id": "r04", "channel": "hotline", "received": "2026-11-23T13:30:00Z", "emirate": "Abu Dhabi", "url": S["c_fab_login"]["input_url"],
         "text": "Caller received an SMS asking to verify a banking login: " + S["c_fab_login"]["input_url"]},
    ]})


def main() -> None:
    reg = json.loads((OUT / "registry.json").read_text(encoding="utf-8"))
    from raqib.detectors import classify_field  # imported late so the script can run from the repo root
    ent = {e["id"] for e in reg["entities"]}
    assert ent

    def kinds_of(el: dict) -> str:
        return classify_field({**el.get("field", {}), "label": el.get("text", "")})

    for c in CASES:
        if c["kind"] == "site":
            pages = c["pages"]
            wrapped = []
            for pd in pages:
                pg = Page(1, "", "")
                pg.d = pd
                wrapped.append(pg)
            c["script"] = auto_script(wrapped, c["redirect_chain"], kinds_of)
        write(f"cases/{c['case_id']}.json", c)
    feeds()
    print(f"wrote {len(CASES)} cases and feeds to {OUT}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main()
