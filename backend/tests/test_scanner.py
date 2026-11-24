"""Scanner checks that need no network: URL tricks, trust rules, HTML fallback, cloaking, batch maths."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from raqib import batch, scanner
from raqib.detectors import analyse, enrich, final_score
from raqib.registry import load_registry

REG = load_registry()


def ids(url: str) -> set[str]:
    return {g["id"] for g in scanner.url_signals(url, REG)}


def test_url_tricks():
    assert "url.shortener" in ids("https://bit.ly/abc")
    assert "url.ip_host" in ids("http://203.0.113.7/pay")
    assert "url.punycode" in ids("https://xn--slik-5qa.com/")
    assert "url.userinfo" in ids("https://www.rta.ae@evil.example/login")
    assert "url.brand_in_subdomain" in ids("https://salik.ae.secure-topup.example/")
    assert "url.free_hosting" in ids("https://uaepass-verify.web.app/")
    assert "url.risky_tld" in ids("https://parcel-fee.top/")
    assert ids("https://www.salik.ae/") == set()


def test_trust_rules():
    assert scanner.trust_of("www.rta.ae", REG)["kind"] == "official"
    assert scanner.trust_of("portal.icp.gov.ae", REG)["kind"] in ("official", "restricted")
    assert scanner.trust_of("newsroom.mof.gov.ae", REG)["kind"] == "restricted"
    assert scanner.trust_of("www.khaleejtimes.com", REG)["kind"] == "trusted"
    assert scanner.trust_of("docs.google.com", REG) is None  # anyone can publish there
    assert scanner.trust_of("rta-fines-payment.com", REG) is None


def test_html_fallback_extracts_forms_and_contacts():
    html = """<html><head><title>SALIK - Pay</title></head><body><h1>SALIK account top-up</h1>
      <form id="f"><label for="c">Card number</label><input id="c" name="cardnumber" autocomplete="cc-number">
      <input name="cvv" autocomplete="cc-csc" placeholder="CVV"><button type="submit">Pay</button></form>
      <a href="https://wa.me/971500000000">WhatsApp</a></body></html>"""
    page = scanner.html_page(html, "https://salik-topup.example/pay")
    kinds = {e["kind"] for e in page["elements"]}
    assert {"input", "heading", "footer"} <= kinds
    assert page["title"].startswith("SALIK")
    case = {"case_id": "t", "kind": "site", "final_url": "https://salik-topup.example/pay", "host": "salik-topup.example", "observed_at": "2026-11-24",
            "redirect_chain": [], "infra": {"domain_created": "2026-11-20"}, "contacts": {},
            "pages": [{**scanner._page_from(page, [], [], None, None)}]}
    a = enrich(analyse(case, REG), case)
    got = {g["id"] for g in a["signals"]}
    assert {"imp.brand_mismatch", "pay.card_form", "infra.new_domain"} <= got
    assert final_score(a) >= scanner.FRAUD_THRESHOLD


def test_brand_only_mentioned_in_body_is_not_impersonation():
    page = scanner.html_page("<html><head><title>City news</title></head><body><h1>Traffic update</h1><p>Salik said the RTA will add new toll gates.</p></body></html>",
                             "https://news.example/story")
    case = {"case_id": "n", "kind": "site", "final_url": "https://news.example/story", "host": "news.example", "observed_at": "2026-11-24",
            "redirect_chain": [], "infra": {"domain_created": "2015-01-01"}, "contacts": {}, "pages": [scanner._page_from(page, [], [], None, None)]}
    a = enrich(analyse(case, REG), case)
    assert "imp.brand_mismatch" not in {g["id"] for g in a["signals"]}
    assert final_score(a) < 30


def test_cloaking_check():
    mobile = {"chain": [{"url": "https://a.example/", "status": 200}], "final_url": "https://scam-pay.example/", "status": 200, "html": "<p>pay now</p>"}
    desktop = {"chain": [{"url": "https://a.example/", "status": 200}], "final_url": "https://www.google.com/", "status": 200, "html": "<p>search</p>"}
    assert "phones are sent to" in scanner.cloaking_check(mobile, desktop)
    same = {**mobile}
    assert scanner.cloaking_check(mobile, same) is None


def test_batch_parsing_and_metrics():
    rows = batch.parse_input("url,label\nhttps://a.example,phishing\nhttps://b.example,benign\nhttps://c.example,\nhttps://a.example,fraud")
    assert [r["label"] for r in rows] == ["fraud", "legit", None]
    plain = batch.parse_input("https://x.example\n# comment\nhttps://y.example legit")
    assert [r["url"] for r in plain] == ["https://x.example", "https://y.example"] and plain[1]["label"] == "legit"
    m = batch.metrics([{"expected": "fraud", "label": "fraud"}, {"expected": "fraud", "label": "legit"},
                       {"expected": "legit", "label": "legit"}, {"expected": "legit", "label": "fraud"}, {"expected": None, "label": "fraud"}])
    assert (m["tp"], m["fn"], m["tn"], m["fp"]) == (1, 1, 1, 1)
    assert m["precision"] == 0.5 and m["recall"] == 0.5 and m["labelled"] == 4


def test_recorded_cases_score_without_network():
    r = batch.from_recorded("http://salik-topup-ae.test/")
    assert r and r["engine"] == "recorded" and r["label"] == "fraud"
    assert batch.from_recorded("https://not-a-demo-case.example/") is None
