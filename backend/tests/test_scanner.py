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


def test_browser_launch_is_sandboxed_and_secret_free(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("SERPAPI_KEY", "serp-test")
    monkeypatch.setenv("RAQIB_CHROME_SANDBOX", "1")
    opts = scanner.launch_options("chrome")
    assert opts["chromium_sandbox"] is True and "--no-sandbox" not in opts["args"]
    assert "ANTHROPIC_API_KEY" not in opts["env"] and "SERPAPI_KEY" not in opts["env"] and "PATH" in {k.upper() for k in opts["env"]}
    assert "--force-webrtc-ip-handling-policy=disable_non_proxied_udp" in opts["args"]
    monkeypatch.delenv("RAQIB_CHROME_SANDBOX")
    assert scanner.launch_options()["chromium_sandbox"] is False  # default unchanged on Windows laptops


def test_dead_lookalike_link_is_still_judged():
    import asyncio

    r = asyncio.run(scanner.scan("http://salik-recharge-pay.invalid/", use_browser=False, rdap=False))
    assert r["engine"] == "none" and "url.offline_lookalike" in {g["id"] for g in r["signals"]}
    plain = asyncio.run(scanner.scan("http://weather-today.invalid/", use_browser=False, rdap=False))
    assert "url.offline_lookalike" not in {g["id"] for g in plain["signals"]}


def test_global_brands_are_known():
    reg = load_registry()
    assert reg.official_domain_of("login.microsoftonline.com").id == "microsoft"
    assert reg.official_domain_of("docs.google.com") is None  # user-content hosts must never count as official
    assert scanner.url_signals("https://paypal-account-verify.web.app/", reg)


def _score_html(html: str, url: str, created: str | None = None) -> tuple[set[str], int]:
    page = scanner.html_page(html, url)
    host = url.split("/")[2]
    case = {"case_id": "h", "kind": "site", "final_url": url, "host": host, "observed_at": "2026-11-25", "redirect_chain": [],
            "infra": {"domain_created": created} if created else {}, "contacts": {}, "pages": [scanner._page_from(page, [], [], None, None)],
            "scan": {"extra_signals": scanner.url_signals(url, REG)}}
    a = enrich(analyse(case, REG), case)
    return {g["id"] for g in a["signals"]}, final_score(a)


def test_hosting_provider_warning_page_counts_as_strong_evidence():
    warning = ("<html><head><title>Suspected phishing site | Cloudflare</title></head><body><h1>Warning</h1><h2>Suspected Phishing</h2>"
               "<p>This website has been reported for potential phishing.</p><p>Cloudflare Ray ID: a5faee8a0881e70c</p>"
               "<p>Performance &amp; security by Cloudflare</p></body></html>")
    got, score = _score_html(warning, "https://random-name-h7d2pe83.pages.dev/")
    assert "host.provider_flagged" in got and score >= 85
    # an ordinary article that talks about Cloudflare and phishing is not a warning page
    article = ("<html><head><title>How Cloudflare handles suspected phishing</title></head><body><h1>Security blog</h1><p>"
               + "Cloudflare reviews reports and may show a suspected phishing warning. " * 60 + "</p></body></html>")
    got, score = _score_html(article, "https://blog.example.com/phishing", created="2015-01-01")
    assert "host.provider_flagged" not in got and score < 30


def test_disguised_password_label_is_caught():
    kit = ("<html><head><title>Sign in</title></head><body><h1>Sign in with your account ID</h1><form id='f'>"
           "<label for='e'>Email</label><input id='e' name='f1'><label for='p'>Pàsswørd</label><input id='p' name='f2'>"
           "<button>Let's go</button></form></body></html>")
    got, score = _score_html(kit, "https://user7076013.weebly.com/")
    assert {"fraud.disguised_field", "pay.credentials_unbranded"} <= got and score >= scanner.FRAUD_THRESHOLD
    plain = kit.replace("Pàsswørd", "Password")
    got, _ = _score_html(plain, "https://user7076013.weebly.com/")
    assert "fraud.disguised_field" not in got


def test_money_brand_named_on_free_hosting_is_not_discounted():
    wallet = ("<html><head><title>Metamask Extension - Browser extension</title></head><body><h1>MetaMask Extension</h1>"
              "<p>Download the MetaMask wallet extension and log in.</p></body></html>")
    _, score = _score_html(wallet, "https://wallet-help.gitbook.io/us")
    assert score >= scanner.FRAUD_THRESHOLD
    # a fan or clone page of a streaming brand on free hosting is suspicious but not flagged on its own
    clone = ("<html><head><title>Netflix clone</title></head><body><h1>Netflix</h1><p>Unlimited movies, TV shows and more.</p></body></html>")
    _, score = _score_html(clone, "https://student.github.io/netflix-clone/")
    assert score < scanner.FRAUD_THRESHOLD
