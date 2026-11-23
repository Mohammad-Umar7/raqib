"""Investigation orchestration.

An investigation turns an input URL into a stream of events (what the sandbox
browser does, what Raqib finds) and a final case file.

Modes
  replay  - the recorded evidence of a known demo case is "browsed" step by step.
            Detectors, scoring, fingerprinting and linking all run for real on that evidence.
  live    - an isolated Chrome driven by a Claude browser agent (see live.py).
  static  - URL is unknown and live browsing is unavailable: domain triage only.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets

from . import config, fingerprint, hunters, knowledge, ui_spec
from .claude_service import service as claude
from .detectors import analyse, classify_scam, risk_score, verdict_for, SCAM_TYPE_LABELS
from .domains import host_of, registrable
from .events import Run
from .evidence import EvidenceStore


def default_speed() -> float:
    try:
        return max(0.0, float(os.environ.get("RAQIB_SPEED", "1")))
    except ValueError:
        return 1.0


async def _pause(seconds: float, speed: float) -> None:
    if speed > 0:
        await asyncio.sleep(seconds / speed)


# --------------------------------------------------------------------------- context for the AI / UI layer

def build_ctx(case: dict | None, analysis: dict, K: knowledge.Knowledge, store: EvidenceStore, link: dict, *, browsed: bool = True,
              input_url: str = "", mode: str = "replay") -> dict:
    score = analysis["score"]
    verdict = analysis["verdict"]
    scam_type = analysis["scam_type"]
    sl = SCAM_TYPE_LABELS.get(scam_type, SCAM_TYPE_LABELS["unknown"])
    host = case["host"] if case else host_of(input_url)
    related = []
    for r in link["related"]:
        related.append({**r, "emirates": r.get("emirates", [])})
    return {
        "case_id": case["case_id"] if case else "adhoc", "input_url": input_url or (case or {}).get("input_url", ""),
        "final_url": (case or {}).get("final_url", ""), "host": host, "domain": registrable(host), "label": (case or {}).get("label", host),
        "observed_at": (case or {}).get("observed_at", ""), "browsed": browsed, "evidence_mode": mode,
        "score": score, "verdict": verdict, "scam_type": scam_type, "scam_label": {"en": sl[0], "ar": sl[1]},
        "brand": analysis.get("brand"), "signals": analysis["signals"], "contacts": analysis.get("contacts", {}), "iocs": analysis.get("iocs", {}),
        "infra": (case or {}).get("infra", {}), "targeting": (case or {}).get("targeting", {"emirates": []}),
        "related": related, "cluster_id": link.get("cluster_id"), "cluster_size": link.get("cluster_size", 1),
        "on_blocklist": (K.on_blocklist(case["case_id"]) if case["case_id"] in K.cases else registrable(host) in hunters.blocklist()) if case else False,
        "evidence": store.items, "manifest": store.manifest(),
    }


async def analyze_emit(run: Run, case: dict, K: knowledge.Knowledge, seen: set[str], speed: float, upto_page: int | None = None) -> dict:
    """Run every detector over the evidence so far and stream newly found signals and the rising score."""
    analysis = analyse(case, K.reg, upto_page=upto_page)
    shown = [g for g in analysis["signals"] if g["id"] in seen]
    for sig in analysis["signals"]:
        if sig["id"] not in seen:
            seen.add(sig["id"])
            shown.append(sig)
            sc = risk_score(shown)
            run.emit("signal", **sig)
            run.emit("score", score=sc, verdict=verdict_for(sc, False))
            await _pause(0.45, speed)
    score = risk_score(analysis["signals"])
    run.emit("score", score=score, verdict=verdict_for(score, analysis["official"]))
    run.emit("indicators", contacts=analysis["contacts"], iocs=analysis["iocs"], brand=analysis["brand"],
             brand_confidence=analysis["brand_confidence"], lookalike=analysis["lookalike"])
    return analysis


# --------------------------------------------------------------------------- replay

STEP_SECONDS = {"note": 1.0, "navigate": 1.0, "analyze": 0.5, "scroll": 0.8, "move": 0.8, "type": 1.0, "click": 0.7, "redirect": 0.7}


async def run_replay(run: Run, case: dict, K: knowledge.Knowledge, speed: float) -> None:
    store = EvidenceStore()
    reg = K.reg
    pages = case["pages"]
    seen: set[str] = set()
    run.emit("meta", case_id=case["case_id"], input_url=case["input_url"], mode="replay", viewport={"w": 390, "h": 760},
             profile="Mobile Chrome · UAE locale · Arabic/English · no stored data", sandbox="isolated container · destroyed after the run")
    run.emit("status", phase="browsing", label="Isolated browser started")
    await _pause(0.8, speed)

    last_analysis = None
    for step in case["script"]:
        if run.cancelled:
            return
        t = step["type"]
        if t == "note":
            run.emit("note", text=step["text"], text_ar=step.get("text_ar", ""))
            await _pause(0.5 + len(step["text"]) / 90, speed)
        elif t == "redirect":
            run.emit("request", method="GET", url=step["url"], status=step["status"], kind="document", flag="redirect")
            run.emit("note", text=f"The link redirects ({step['status']}) to another domain.", text_ar="الرابط يُحوِّل إلى نطاق آخر.")
            await _pause(STEP_SECONDS["redirect"], speed)
        elif t == "navigate":
            page = pages[step["page_index"]]
            run.emit("frame", page_id=page["page_id"], url=page["url"], title=page["title"], elements=page["elements"],
                     viewport={"w": 390, "h": 760}, kind="wireframe")
            await _pause(STEP_SECONDS["navigate"], speed)
            for req in page.get("network", []):
                run.emit("request", **req)
                await _pause(0.12, speed)
            ev = [store.add("screenshot", f"Page capture · {page['title']}", page["elements"], page["page_id"]),
                  store.add("dom", f"DOM structure · {page['url']}", {"elements": page["elements"], "forms": page["forms"]}, page["page_id"]),
                  store.add("network", f"Network log · {page['url']}", page.get("network", []), page["page_id"])]
            ev += [store.add("script", f"Script · {s['src']}", s["src"], page["page_id"], sha256=s["sha256"]) for s in page["scripts"] if not s.get("library")]
            for item in ev:
                run.emit("evidence", **item)
        elif t == "cursor":
            run.emit("cursor", action=step["action"], target=step["target"], label=step.get("label", ""))
            await _pause(STEP_SECONDS["move" if step["action"] == "move" else step["action"]], speed)
        elif t == "analyze":
            last_analysis = await analyze_emit(run, case, K, seen, speed, upto_page=step["page_index"] + 1)
            await _pause(STEP_SECONDS["analyze"], speed)

    # infrastructure evidence
    infra = case["infra"]
    for kind, label, data in (("whois", f"WHOIS · registered {infra.get('domain_created')}", {k: infra.get(k) for k in ("registrar", "domain_created", "nameservers")}),
                              ("tls", f"TLS certificate · issued {infra.get('cert_issued')}", {k: infra.get(k) for k in ("cert_issued", "cert_issuer")}),
                              ("hosting", f"Hosting · {infra.get('asn_org')} {infra.get('asn')}", {k: infra.get(k) for k in ("ip", "asn", "asn_org", "country")})):
        run.emit("evidence", **store.add(kind, label, data))
    await _pause(0.5, speed)

    await _finish(run, case, K, store, speed)


async def _finish(run: Run, case: dict, K: knowledge.Knowledge, store: EvidenceStore, speed: float) -> None:
    """Shared tail: fingerprint, link to known campaigns, let Claude write the case view, compose the UI."""
    analysis = K.analysis[case["case_id"]] if case["case_id"] in K.analysis else None
    if analysis is None:
        analysis = analyse(case, K.reg)
        score = risk_score(analysis["signals"])
        analysis.update(score=score, verdict=verdict_for(score, analysis["official"]), scam_type=classify_scam(analysis))
    run.emit("status", phase="fingerprinting", label="Building the scam fingerprint")
    fp = K.fps.get(case["case_id"]) or fingerprint.build(case)
    run.emit("fingerprint", domain=fp["domain"], kit_files=len(fp["kit_files"]), exfil=fp["exfil"], wallets=fp["wallets"], phones=fp["phones"] + fp["whatsapp"],
             layout_shingles=len(fp["layout"]))
    await _pause(1.0, speed)

    run.emit("status", phase="linking", label="Comparing against known scam campaigns")
    link = K.link(fp)
    centre = {**K.summary(case["case_id"]), "center": True} if case["case_id"] in K.cases else {"case_id": case["case_id"], "host": case["host"], "label": case["label"], "kind": "site",
                                                                                              "score": analysis["score"], "verdict": analysis["verdict"], "center": True}
    run.emit("graph", reset=True, nodes=[centre], edges=[])
    shown: set[str] = {case["case_id"]}
    for r in link["related"]:
        node = {k: r[k] for k in ("case_id", "host", "label", "kind", "score", "verdict", "scam_type", "cluster_id", "on_blocklist", "emirates")}
        node["center"] = False
        shown.add(r["case_id"])
        edges = [e for e in link["edges"] if (e["source"] == case["case_id"] and e["target"] == r["case_id"]) or
                 (r["case_id"] in (e["source"], e["target"]) and e["source"] in shown and e["target"] in shown and e["source"] != case["case_id"])]
        run.emit("graph", nodes=[node], edges=edges)
        if r["kind"] == "site" and r["strength"] in ("strong", "medium"):
            run.emit("related_case", case_id=r["case_id"], host=r["host"], score=r["score"], verdict=r["verdict"], strength=r["strength"],
                     reason=r["reasons"][0]["text"], on_blocklist=r["on_blocklist"])
        await _pause(0.55, speed)

    ctx = build_ctx(case, analysis, K, store, link, mode="replay")
    label = "Claude is writing the case summary and laying out the view" if claude.enabled else "Writing the case summary (offline mode, no Claude key)"
    run.emit("status", phase="reporting", label=label)
    refined, source = await asyncio.to_thread(claude.refine, ctx)
    blocks = ui_spec.compose(ctx, refined)
    run.emit("ui", blocks=blocks, source=source, headline=refined["headline"], headline_ar=refined["headline_ar"])

    run.result = {"run_id": run.id, "case_id": case["case_id"], "ctx": ctx, "refined": refined, "blocks": blocks, "source": source,
                  "graph": {"nodes": [centre] + [{**{k: r[k] for k in ("case_id", "host", "label", "kind", "score", "verdict", "scam_type", "cluster_id", "on_blocklist", "emirates")}, "center": False} for r in link["related"]],
                            "edges": link["edges"]}, "mode": run.mode}
    run.emit("done", score=analysis["score"], verdict=analysis["verdict"], source=source)
    _persist(run)


# --------------------------------------------------------------------------- static (unknown URL, no browsing)

async def run_static(run: Run, url: str, K: knowledge.Knowledge, speed: float) -> None:
    host = host_of(url)
    t = hunters.triage_host(host, K.reg)
    run.emit("meta", case_id="adhoc", input_url=url, mode="static", viewport={"w": 390, "h": 760}, profile="not browsed", sandbox="none")
    run.emit("status", phase="triage", label="Checking the domain against protected brands")
    await _pause(0.8, speed)
    run.emit("note", text="This URL is not one of the recorded demo cases and live browsing is switched off, so only domain triage can run.",
             text_ar="هذا الرابط ليس من الحالات المسجّلة ولا يتوفر التصفح المباشر، لذا يقتصر التحليل على فحص النطاق.")
    score = t["score"]
    verdict = verdict_for(score) if score >= 30 else "no_indicators"
    analysis = {"signals": [], "brand": K.reg.get(t["brand"]).to_dict() if t["brand"] else None, "score": score, "verdict": verdict,
                "scam_type": K.reg.get(t["brand"]).scam_type if t["brand"] else "unknown", "contacts": {}, "iocs": {}}
    for reason in t["reasons"]:
        run.emit("note", text=f"Triage: {reason['text']} (+{reason['points']})")
        await _pause(0.5, speed)
    run.emit("score", score=score, verdict=verdict)
    store = EvidenceStore()
    run.emit("evidence", **store.add("triage", f"Domain triage · {host}", t))
    ctx = build_ctx(None, analysis, K, store, {"related": [], "edges": [], "cluster_id": None, "cluster_size": 1}, browsed=False, input_url=url, mode="static")
    refined = ui_spec.offline_refine(ctx)
    blocks = ui_spec.compose(ctx, refined)
    blocks.insert(1, {"type": "callout", "tone": "warn", "title": "Not browsed", "title_ar": "لم يتم التصفح",
                      "text": "Raqib could only triage this domain. Run it in live mode (isolated Chrome + Claude agent) to capture forms, scripts and evidence.",
                      "text_ar": "اقتصر رقيب على فحص النطاق. شغّل الوضع المباشر (متصفح معزول ووكيل Claude) لالتقاط النماذج والسكربتات والأدلة."})
    run.emit("ui", blocks=blocks, source="offline", headline=refined["headline"], headline_ar=refined["headline_ar"])
    run.result = {"run_id": run.id, "case_id": "adhoc", "ctx": ctx, "refined": refined, "blocks": blocks, "source": "offline", "graph": {"nodes": [], "edges": []}, "mode": "static"}
    run.emit("done", score=score, verdict=verdict, source="offline")
    _persist(run)


async def run_listing(run: Run, case: dict, K: knowledge.Knowledge, speed: float) -> None:
    """A Google Maps listing has no website to browse: match its contact details against known campaigns."""
    store = EvidenceStore()
    run.emit("meta", case_id=case["case_id"], input_url=case["label"], mode="listing", viewport={"w": 390, "h": 760}, profile="Maps listing (no website)", sandbox="none")
    run.emit("status", phase="browsing", label="Reading the Maps listing")
    await _pause(0.8, speed)
    listing = case["listing"]
    run.emit("note", text=f"“{listing['name']}” in {listing['area']}, {listing['emirate']} has no website to open. Its phone / WhatsApp number is matched against known scam campaigns instead.",
             text_ar=f"«{listing['name']}» في {listing['area']} ليس له موقع إلكتروني. تتم مطابقة رقم الهاتف أو الواتساب مع الحملات المعروفة بدلاً من ذلك.")
    await _pause(1.2, speed)
    analysis = K.analysis[case["case_id"]]
    for r in analysis["triage"]["reasons"]:
        run.emit("note", text=f"Listing check: {r['text']} (+{r['points']})")
        await _pause(0.6, speed)
    run.emit("score", score=analysis["score"], verdict=analysis["verdict"])
    run.emit("evidence", **store.add("listing", f"Maps listing · {listing['name']}", {**listing, "contacts": case["contacts"]}))
    await _finish(run, case, K, store, speed)


def _persist(run: Run) -> None:
    try:
        config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
        (config.RUNS_DIR / f"{run.id}.json").write_text(json.dumps({"result": run.result, "events": run.events}, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


# --------------------------------------------------------------------------- manager

class Manager:
    def __init__(self) -> None:
        self.runs: dict[str, Run] = {}

    def get(self, run_id: str) -> Run | None:
        return self.runs.get(run_id)

    def start(self, url: str, *, mode: str = "auto", speed: float | None = None) -> Run:
        K = knowledge.get()
        spd = default_speed() if speed is None else speed
        cid = K.resolve(url)
        case = K.cases.get(cid) if cid else None
        live_ok = config.requested_mode() == "live" and claude.enabled
        if mode == "auto":
            mode = "replay" if case and case["kind"] == "site" else ("live" if live_ok else "static")
        if case and case["kind"] == "maps_listing":
            mode = "listing"
        elif mode == "replay" and (not case or case["kind"] != "site"):
            mode = "live" if live_ok else "static"
        run = Run(secrets.token_hex(4), url, mode)
        self.runs[run.id] = run
        run.emit("status", phase="queued", label="Investigation queued")

        async def go() -> None:
            try:
                if mode == "replay":
                    await run_replay(run, case, K, spd)  # type: ignore[arg-type]
                elif mode == "listing":
                    await run_listing(run, case, K, spd)  # type: ignore[arg-type]
                elif mode == "live":
                    from . import live

                    await live.run_live(run, url, K, spd)
                else:
                    await run_static(run, url, K, spd)
                run.finish()
            except Exception as exc:  # surface errors in the UI instead of hanging the stream
                run.emit("error", message=f"{type(exc).__name__}: {exc}")
                run.finish(str(exc))

        run.task = asyncio.get_running_loop().create_task(go())
        return run


manager = Manager()
