"""Raqib API server. Run:  uvicorn raqib.main:app --port 8600"""

from __future__ import annotations

import asyncio
import json
from collections import Counter

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response, StreamingResponse
from pydantic import BaseModel

from . import __version__, config, hunters, knowledge, report
from .domains import host_of
from .claude_service import service as claude
from .investigations import default_speed, manager

app = FastAPI(title="Raqib", version=__version__)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"])


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
    return {"version": __version__, "requested_mode": config.requested_mode(), "claude": claude.status(), "playwright": _playwright_available(),
            "live_ready": config.requested_mode() == "live" and claude.enabled and _playwright_available(), "speed": default_speed(),
            "cases": len(K().cases), "entities": len(K().reg.entities)}


class KeyBody(BaseModel):
    key: str


@app.post("/api/settings/key")
def set_key(body: KeyBody) -> dict:
    key = body.key.strip()
    if not key.startswith("sk-ant-") or len(key) < 20:
        raise HTTPException(400, "That does not look like an Anthropic API key (sk-ant-...).")
    config.set_api_key(key)
    return {"ok": True, "claude": claude.status()}


@app.delete("/api/settings/key")
def clear_key() -> dict:
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
    emirates: Counter = Counter()
    for c in confirmed:
        for e in k.cases[c["case_id"]].get("targeting", {}).get("emirates", []):
            emirates[e] += 1
    countries: Counter = Counter()
    for c in sites:
        infra = k.cases[c["case_id"]].get("infra", {})
        if infra.get("country"):
            countries[infra["country"]] += 1
    by_source = Counter(c["source"] for c in flagged)
    return {
        "funnel": {"scanned": cand["scanned"], "unique": len(rows), "flagged": len(flagged), "investigated": len(investigated), "confirmed": len(confirmed),
                   "unblocked": len(unblocked)},
        "by_source": dict(by_source), "emirates": dict(emirates), "hosting_countries": dict(countries), "clusters": k.clusters(), "threshold": THRESH,
        "entities": len(k.reg.entities),
        "sources": {"ct": len([c for c in rows if c["source"] == "ct"]), "search": len([c for c in rows if c["source"].startswith("search")]),
                    "maps": len([c for c in rows if c["source"] == "maps"]), "report": len([c for c in rows if c["source"] == "report"])},
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


@app.get("/api/triage")
def triage(host: str) -> dict:
    return hunters.triage_host(host_of(host) or host, K().reg)


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
