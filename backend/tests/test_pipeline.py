"""Core pipeline checks: detectors, scoring, campaign linking, triage."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from raqib import campaign, fingerprint, hunters, knowledge
from raqib.detectors import analyse, classify_scam, risk_score, verdict_for
from raqib.domains import lookalike, registrable
from raqib.registry import load_registry


@pytest.fixture(scope="module")
def K():
    return knowledge.Knowledge()


def test_registrable_domain():
    assert registrable("pay.salik-topup.example.com") == "example.com"
    assert registrable("portal.rta.gov.ae") == "rta.gov.ae"


def test_lookalike_flags_brand_in_domain_but_not_unrelated_names():
    assert lookalike("salik-topup-ae.com", ["salik.ae"], ["salik"])["score"] >= 0.7
    assert lookalike("marina-yoga-studio-uae.com", ["salik.ae"], ["salik"])["score"] == 0
    # digits in an unrelated name must not look like a homoglyph attack
    assert lookalike("unknown-site-123.com", ["salik.ae"], ["salik"])["score"] == 0
    # but a real homoglyph swap is caught
    assert lookalike("sa1ik-pay.com", ["salik.ae"], ["salik"])["score"] >= 0.7


def test_every_recorded_case_gets_the_expected_verdict(K):
    for cid, case in K.cases.items():
        if case["kind"] != "site":
            continue
        a = K.analysis[cid]
        truth = case["ground_truth"]["label"]
        if truth == "scam":
            assert a["verdict"] in ("confirmed_scam", "likely_scam"), (cid, a["score"])
        else:
            assert a["verdict"] == "no_indicators", (cid, a["score"])


def test_score_is_explainable_noisy_or():
    sigs = [{"weight": 0.5}, {"weight": 0.5}]
    assert risk_score(sigs) == 75
    assert risk_score([]) == 0
    assert verdict_for(90) == "confirmed_scam" and verdict_for(10) == "no_indicators"


def test_shared_bot_links_sites_strongly_but_copied_layout_only_weakly(K):
    edges = {(e["source"], e["target"]): e for e in K.graph["edges"]}

    def edge(a, b):
        return edges.get((a, b)) or edges.get((b, a))

    strong = edge("c_salik_topup", "c_rta_fines")
    assert strong and strong["strength"] == "strong"
    assert any(r["kind"] == "exfil" for r in strong["reasons"])
    # a different operator that copied the RTA look must NOT be linked strongly
    copy = edge("c_rta_fines", "c_rta_copy")
    assert copy is None or copy["strength"] == "weak"
    # a Maps listing is tied to its campaign through the shared WhatsApp number
    assert edge("c_salik_pay", "m_salik_desk")["strength"] == "strong"


def test_campaign_clusters(K):
    clusters = {c["cluster_id"]: c for c in K.clusters()}
    assert len(clusters) >= 4
    biggest = max(clusters.values(), key=lambda c: c["size"])
    assert biggest["size"] >= 8


def test_triage_catches_lookalikes_and_ignores_official_and_benign():
    reg = load_registry()
    assert hunters.triage_host("salik-topup-ae.com", reg)["score"] >= hunters.THRESHOLD
    assert hunters.triage_host("www.salik.ae", reg)["score"] == 0
    assert hunters.triage_host("marina-yoga-studio.com", reg)["score"] < hunters.THRESHOLD


def test_blocklist_membership(K):
    assert K.on_blocklist("c_adcb_verify") is True
    assert K.on_blocklist("c_salik_topup") is False


def test_fingerprint_ignores_shared_libraries(K):
    fp = K.fps["c_salik_topup"]
    assert len(fp["kit_files"]) == 1  # jquery is a library, only the kit counts
