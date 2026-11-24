"""Raqib API server. Run:  uvicorn raqib.main:app --port 8600"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections import Counter

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from pydantic import BaseModel

from . import __version__, batch, config, hunters, hunters_live, knowledge, radar, report
from .claude_service import service as claude
from .investigations import default_speed, manager

app = FastAPI(title="Raqib", version=__version__)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])


# Public demo (a hosted link for judges): only the recorded demo cases can be opened, nothing can be reconfigured,
# and the server never fetches a URL a stranger pastes. Real links are scanned inside the sandbox VM (deploy/vm).
PUBLIC_DEMO = os.environ.get("RAQIB_PUBLIC_DEMO") == "1"
PUBLIC_MSG = "Public demo: only the recorded demo cases can be opened here. Real links are scanned inside Raqib's sandbox VM."


def _no_public(what: str = "This") -> None:
    if PUBLIC_DEMO:
        raise HTTPException(403, f"{what} is switched off in the public demo.")


def K() -> knowledge.Knowledge:
    return knowledge.get()


def _playwright_available() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


# --------------------------------------------------------------------------- status & settings

@app.get("/api/status")
def status() -> dict:
    return {"version": __version__, "model_label": config.model_label(), "requested_mode": config.requested_mode(), "claude": claude.status(), "playwright": _playwright_available(),
            "live_ready": config.requested_mode() == "live" and claude.enabled and _playwright_available(), "speed": default_speed(),
            "cases": len(K().cases), "entities": sum(1 for e in K().reg.entities if e.emirate != "Global"),
            "public_demo": PUBLIC_DEMO, "sources": {"nrd": True, "serpapi": bool(hunters_live.serpapi_key()), "browser": _playwright_available()}}


class KeyBody(BaseModel):
    key: str


@app.post("/api/settings/key")
def set_key(body: KeyBody) -> dict:
    _no_public("Changing settings")
    key = body.key.strip()
    if not key.startswith("sk-ant-") or len(key) < 20:
        raise HTTPException(400, "That does not look like an Anthropic API key (sk-ant-...).")
    config.set_api_key(key)
    return {"ok": True, "claude": claude.status()}


@app.delete("/api/settings/key")
def clear_key() -> dict:
    _no_public("Changing settings")
    config.set_api_key("")
    return {"ok": True, "claude": claude.status()}


@app.get("/api/registry")
def registry() -> dict:
    return {"entities": K().reg.to_list()}


@app.get("/api/demo-targets")
def demo_targets() -> dict:
    return {"targets": K().demo_targets()}


# --------------------------------------------------------------------------- hunting

THRESH = hunters.THRESHOLD


def _flag(c: dict) -> bool:
    return c["triage"]["score"] >= THRESH


@app.get("/api/overview")
def overview() -> dict:
    k = K()
    cand = hunters.candidates(k.cases)
    rows = cand["rows"]
    flagged = [c for c in rows if _flag(c)]
    investigated = [c for c in flagged if c["case_id"]]
    confirmed = [c for c in investigated if k.analysis[c["case_id"]]["verdict"] in ("confirmed_scam", "likely_scam")]
    sites = [c for c in confirmed if k.cases[c["case_id"]]["kind"] == "site"]
    unblocked = [c for c in sites if not k.on_blocklist(c["case_id"])]
    countries: Counter = Counter()
    for c in sites:
        infra = k.cases[c["case_id"]].get("infra", {})
        if infra.get("country"):
            countries[infra["country"]] += 1
    return {
        "funnel": {"scanned": cand["scanned"], "unique": len(rows), "flagged": len(flagged), "investigated": len(investigated), "confirmed": len(confirmed),
                   "unblocked": len(unblocked)},
        "hosting_countries": dict(countries), "clusters": k.clusters(), "threshold": THRESH,
        "entities": sum(1 for e in k.reg.entities if e.emirate != "Global"),
    }


@app.get("/api/hunt/stream")
async def hunt_stream(speed: float = Query(1.0, ge=0.0, le=20.0)) -> StreamingResponse:
    k = K()
    rows = hunters.candidates(k.cases)["rows"]

    async def gen():
        scanned = flagged = 0
        yield _sse({"type": "start", "total": len(rows), "threshold": THRESH})
        for i, c in enumerate(rows, start=1):
            scanned += 1
            is_flag = _flag(c)
            flagged += is_flag
            verdict = k.analysis[c["case_id"]]["verdict"] if is_flag and c["case_id"] else None
            kind = k.cases[c["case_id"]]["kind"] if c["case_id"] else None
            yield _sse({"type": "candidate", "n": i, "flagged": is_flag, "verdict": verdict, "kind": kind,
                        "blocked": bool(c["case_id"] and k.on_blocklist(c["case_id"])),
                        "candidate": {**{key: c[key] for key in ("id", "source", "title", "host", "detail", "case_id", "when", "seen_in") if key in c},
                                      "triage": {"score": c["triage"]["score"], "reasons": c["triage"]["reasons"][:4], "brand": c["triage"]["brand"]}}})
            if i % 10 == 0 or is_flag:
                yield _sse({"type": "funnel", "scanned": scanned, "flagged": flagged})
            if speed > 0:
                await asyncio.sleep((0.45 if is_flag else 0.012) / speed)
        yield _sse({"type": "done", "scanned": scanned, "flagged": flagged})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@app.get("/api/candidates")
def list_candidates() -> dict:
    k = K()
    rows = hunters.candidates(k.cases)["rows"]
    out = []
    for c in rows:
        if _flag(c):
            out.append({**{key: c[key] for key in ("id", "source", "title", "host", "detail", "case_id", "when", "seen_in") if key in c}, "triage": c["triage"],
                        "verdict": k.analysis[c["case_id"]]["verdict"] if c["case_id"] else None,
                        "score": k.analysis[c["case_id"]]["score"] if c["case_id"] else None})
    return {"candidates": sorted(out, key=lambda c: -c["triage"]["score"])}


# --------------------------------------------------------------------------- investigations

class StartBody(BaseModel):
    url: str
    mode: str = "auto"
    speed: float | None = None


@app.post("/api/investigations")
async def start(body: StartBody) -> dict:
    url = body.url.strip()
    if not url:
        raise HTTPException(400, "Enter a URL to investigate.")
    if PUBLIC_DEMO:
        cid = K().resolve(url)
        if not cid or K().cases[cid].get("source") == "scan":
            raise HTTPException(403, PUBLIC_MSG)
        body.mode = "auto"
    run = manager.start(url, mode=body.mode, speed=body.speed)
    return {"id": run.id, "mode": run.mode}


def _run(run_id: str):
    run = manager.get(run_id)
    if not run:
        raise HTTPException(404, "Unknown investigation")
    return run


@app.get("/api/investigations/{run_id}/events")
async def events(run_id: str, after: int = -1) -> StreamingResponse:
    run = _run(run_id)

    async def gen():
        async for ev in run.stream(after):
            yield ": keep-alive\n\n" if ev is None else _sse(ev)

    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/investigations")
def recent_investigations() -> dict:
    return {"investigations": manager.recent()}


@app.get("/api/investigations/{run_id}")
def investigation(run_id: str) -> dict:
    run = _run(run_id)
    return {"id": run.id, "mode": run.mode, "input_url": run.input_url, "finished": run.finished, "error": run.error, "events": len(run.events), "result": run.result}


class AskBody(BaseModel):
    question: str


@app.post("/api/investigations/{run_id}/ask")
async def ask(run_id: str, body: AskBody) -> dict:
    run = _run(run_id)
    if not run.result:
        raise HTTPException(409, "The investigation is still running.")
    out, source = await asyncio.to_thread(claude.answer, run.result["ctx"], body.question)
    return {**out, "source": source}


def _result(run_id: str) -> dict:
    run = _run(run_id)
    if not run.result:
        raise HTTPException(409, "The investigation is still running.")
    return run.result


@app.get("/api/investigations/{run_id}/pack")
def pack(run_id: str) -> dict:
    return report.action_pack(_result(run_id)["ctx"])


@app.get("/api/investigations/{run_id}/report.pdf")
def report_pdf(run_id: str) -> Response:
    data = report.build_pdf(_result(run_id))
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="raqib-case-{run_id}.pdf"'})


@app.get("/api/investigations/{run_id}/blocklist.csv")
def blocklist_csv(run_id: str) -> PlainTextResponse:
    return PlainTextResponse(report.blocklist_csv(_result(run_id)["ctx"]), media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="raqib-blocklist-{run_id}.csv"'})


# --------------------------------------------------------------------------- live hunting

@app.get("/api/hunt/new-domains")
async def hunt_new_domains(days: int = Query(2, ge=1, le=7), force: bool = False) -> dict:
    try:
        return await hunters_live.nrd_hunt(days=days, force=force)
    except Exception as exc:
        raise HTTPException(502, f"New-domain feed unavailable: {exc}")


@app.get("/api/hunt/search-maps")
async def hunt_search_maps(force: bool = False) -> dict:
    return await hunters_live.serp_hunt(force=force)


# --------------------------------------------------------------------------- the radar (autonomous loop)

@app.on_event("startup")
async def _radar_start() -> None:
    if os.environ.get("RAQIB_RADAR", "0") == "1":  # off unless asked: it opens real suspicious sites
        radar.get().start()


@app.on_event("shutdown")
async def _radar_stop() -> None:
    if radar._radar and radar._radar.started:
        await radar._radar.stop()


@app.get("/api/radar")
def radar_status() -> dict:
    return radar.get().snapshot()


@app.get("/api/radar/items")
def radar_items(view: str = "all", limit: int = Query(300, ge=1, le=1000)) -> dict:
    return {"items": radar.get().items(view, limit)}


class DecideBody(BaseModel):
    approve: bool


@app.post("/api/radar/domains/{domain}/decide")
def radar_decide(domain: str, body: DecideBody) -> dict:
    _no_public("The radar")
    r = radar.get()
    if not r.s.q("select 1 from domains where domain=?", domain):
        raise HTTPException(404, "Unknown domain")
    r.decide(domain, body.approve)
    return {"ok": True}


class ControlBody(BaseModel):
    paused: bool | None = None
    auto_actions: bool | None = None
    run: str | None = None


@app.post("/api/radar/control")
def radar_control(body: ControlBody) -> dict:
    _no_public("The radar")
    r = radar.get()
    if body.paused is not None:
        r.set_paused(body.paused)
    if body.auto_actions is not None:
        r.set_auto(body.auto_actions)
    if body.run:
        r.run_now(body.run)
    return r.snapshot()


@app.get("/api/radar/blocklist.txt")
def radar_blocklist() -> PlainTextResponse:
    """Plain domain list a telco DNS resolver or firewall can pull."""
    doms = radar.get().blocklist()
    return PlainTextResponse("".join(f"{line}\n" for line in ["# Raqib blocklist feed: scam domains confirmed by the radar", *doms]))


# --------------------------------------------------------------------------- batch scanning and evaluation

class BatchBody(BaseModel):
    text: str
    use_browser: bool = True
    use_ai: bool = False
    concurrency: int = 4


@app.post("/api/batch")
async def batch_start(body: BatchBody) -> dict:
    if PUBLIC_DEMO and any(batch.from_recorded(r["url"]) is None for r in batch.parse_input(body.text)):
        raise HTTPException(403, PUBLIC_MSG)
    try:
        job = batch.start(body.text, body.use_browser, body.use_ai, body.concurrency)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"id": job.id, "total": len(job.rows)}


def _job(job_id: str) -> batch.Job:
    job = batch.JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown batch")
    return job


@app.get("/api/batch/sample")
async def batch_sample(kind: str = "mixed", n: int = 15) -> dict:
    """Ready-made labelled lists: recorded demo cases, real legitimate UAE sites, live phishing from OpenPhish."""
    rows: list[dict] = []
    if kind in ("mixed", "recorded"):
        rows += batch.recorded_sample()
    if kind in ("mixed", "legit"):
        rows += [{"url": u, "label": "legit"} for u in batch.LEGIT_SAMPLE]
    if kind == "openphish":
        try:
            rows += await batch.openphish_sample(n)
        except Exception as exc:
            raise HTTPException(502, f"OpenPhish feed unavailable: {exc}")
    return {"text": "url,label\n" + "\n".join(f"{r['url']},{r['label']}" for r in rows), "count": len(rows)}


@app.get("/api/batch/{job_id}")
def batch_status(job_id: str) -> dict:
    return _job(job_id).snapshot()


@app.post("/api/batch/{job_id}/cancel")
def batch_cancel(job_id: str) -> dict:
    job = _job(job_id)
    job.cancelled = True
    return {"ok": True}


@app.get("/api/batch/{job_id}/results.csv")
def batch_csv(job_id: str) -> PlainTextResponse:
    return PlainTextResponse(batch.to_csv(_job(job_id)), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="raqib-batch-{job_id}.csv"'})


@app.get("/api/batch/{job_id}/results.json")
def batch_json(job_id: str) -> Response:
    data = json.dumps(_job(job_id).snapshot(), ensure_ascii=False, indent=1, default=str)
    return Response(data, media_type="application/json", headers={"Content-Disposition": f'attachment; filename="raqib-batch-{job_id}.json"'})


# --------------------------------------------------------------------------- evidence files and exports

@app.get("/api/evidence/{run_id}/{name}")
def evidence_file(run_id: str, name: str) -> FileResponse:
    if not run_id.isalnum() or not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or ".." in name:
        raise HTTPException(400, "bad name")
    path = config.EVIDENCE_DIR / run_id / name
    if not path.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(path)


@app.get("/api/investigations/{run_id}/bundle.json")
def evidence_bundle(run_id: str) -> Response:
    """Machine-readable case bundle for takedown partners and other agencies."""
    res = _result(run_id)
    ctx = res["ctx"]
    out = {
        "case": run_id, "generated_by": f"Raqib {__version__}", "input_url": ctx["input_url"], "final_url": ctx.get("final_url"), "domain": ctx["domain"],
        "score": ctx["score"], "verdict": ctx["verdict"], "scam_type": ctx["scam_type"], "impersonates": (ctx.get("brand") or {}).get("name"),
        "signals": [{"id": g["id"], "label": g["label"], "weight": g["weight"]} for g in ctx["signals"]],
        "indicators": {**ctx.get("iocs", {}), **ctx.get("contacts", {})}, "infrastructure": ctx.get("infra", {}),
        "redirect_chain": ctx.get("redirect_chain"), "campaign": ctx.get("cluster_id"),
        "related": [{"domain": r["host"], "strength": r["strength"], "why": r["reasons"][0]["text"]} for r in ctx.get("related", [])],
        "evidence": ctx["evidence"], "manifest_sha256": ctx["manifest"], "actions": report.action_pack(ctx)["takedowns"],
    }
    return Response(json.dumps(out, ensure_ascii=False, indent=1, default=str), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="raqib-case-{run_id}.json"'})


# --------------------------------------------------------------------------- campaigns

@app.get("/api/campaigns")
def campaigns() -> dict:
    return {"clusters": K().clusters()}


@app.get("/api/graph")
def graph() -> dict:
    k = K()
    g = k.full_graph()
    return {**g, "cluster_of": k.graph["cluster_of"]}


# --------------------------------------------------------------------------- frontend

@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    dist = config.FRONTEND_DIST
    if path.startswith("api/"):
        raise HTTPException(404)
    target = (dist / path).resolve()
    if path and dist in target.parents and target.is_file():
        return FileResponse(target)
    index = dist / "index.html"
    if index.is_file():
        return FileResponse(index)
    return PlainTextResponse("Raqib API is running. Build the frontend (npm run build in /frontend) or run the Vite dev server.", status_code=200)
