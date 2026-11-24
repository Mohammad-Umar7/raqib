"""Batch scanning and accuracy evaluation (precision / recall / F1 on a labelled URL list)."""

from __future__ import annotations

import asyncio
import csv
import io
import os
import random
import re
import secrets
import time

import httpx

from . import knowledge, scanner
from .netutil import ssl_context

FRAUD_WORDS = {"fraud", "phishing", "phish", "scam", "malicious", "bad", "1", "true", "yes", "spam"}
LEGIT_WORDS = {"legit", "legitimate", "benign", "safe", "good", "0", "false", "no", "clean"}
OPENPHISH_FEED = "https://openphish.com/feed.txt"


def parse_label(v: str | None) -> str | None:
    v = (v or "").strip().lower()
    if v in FRAUD_WORDS:
        return "fraud"
    if v in LEGIT_WORDS:
        return "legit"
    return None


def parse_input(text: str) -> list[dict]:
    """One URL per line, or CSV with a url column and an optional label column. Blank lines and # comments are ignored."""
    rows: list[dict] = []
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if lines and re.search(r"\burl\b", lines[0], re.I) and ("," in lines[0] or "\t" in lines[0]):
        reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter="\t" if "\t" in lines[0] else ",")
        for r in reader:
            low = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
            url = low.get("url") or low.get("link") or ""
            if url:
                rows.append({"url": url, "label": parse_label(low.get("label") or low.get("class") or low.get("type"))})
    else:
        for ln in lines:
            parts = re.split(r"[,\t ]+", ln.strip())
            rows.append({"url": parts[0], "label": parse_label(parts[1]) if len(parts) > 1 else None})
    seen, out = set(), []
    for r in rows:
        if r["url"] not in seen:
            seen.add(r["url"])
            out.append(r)
    return out


def metrics(results: list[dict]) -> dict:
    tp = fp = tn = fn = 0
    for r in results:
        if r.get("expected") not in ("fraud", "legit") or r.get("label") not in ("fraud", "legit"):
            continue
        if r["expected"] == "fraud":
            tp += r["label"] == "fraud"
            fn += r["label"] != "fraud"
        else:
            fp += r["label"] == "fraud"
            tn += r["label"] != "fraud"
    n = tp + fp + tn + fn
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else None
    return {"labelled": n, "tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": precision, "recall": recall, "f1": f1,
            "accuracy": (tp + tn) / n if n else None, "false_positive_rate": fp / (fp + tn) if fp + tn else None}


def from_recorded(url: str) -> dict | None:
    """Demo cases (fictional .test domains) cannot be fetched: score them from their recorded evidence."""
    K = knowledge.get()
    cid = K.resolve(url)
    if not cid or K.cases[cid].get("source") == "scan":
        return None
    a, c = K.analysis[cid], K.cases[cid]
    return {"input_url": url, "final_url": c.get("final_url") or url, "host": c["host"], "chain": c.get("redirect_chain", []), "engine": "recorded",
            "score": a["score"], "verdict": a["verdict"], "label": "fraud" if a["score"] >= scanner.FRAUD_THRESHOLD else "legit",
            "scam_type": a["scam_type"], "brand": (a.get("brand") or {}).get("name"), "trusted": None, "cloaking": None,
            "reasons": [g["label"] for g in sorted(a["signals"], key=lambda g: -g["weight"])[:5]],
            "signals": [{"id": g["id"], "label": g["label"], "weight": g["weight"], "severity": g["severity"]} for g in a["signals"]],
            "seconds": 0.0, "error": None}


class Job:
    def __init__(self, rows: list[dict], use_browser: bool, use_ai: bool, concurrency: int, shots_dir: str | None = None):
        self.shots_dir = shots_dir  # save each page's screenshot here (evaluation runs)
        self.id = secrets.token_hex(4)
        self.rows = rows
        self.use_browser, self.use_ai = use_browser, use_ai
        self.concurrency = max(1, min(8, concurrency))
        self.results: list[dict | None] = [None] * len(rows)
        self.done = 0
        self.started = time.time()
        self.finished = False
        self.cancelled = False
        self.task: asyncio.Task | None = None

    def snapshot(self) -> dict:
        res = [r for r in self.results if r]
        return {"id": self.id, "total": len(self.rows), "done": self.done, "finished": self.finished, "seconds": round(time.time() - self.started, 1),
                "threshold": scanner.FRAUD_THRESHOLD, "use_browser": self.use_browser, "use_ai": self.use_ai, "results": res, "metrics": metrics(res)}

    async def run(self) -> None:
        sem = asyncio.Semaphore(self.concurrency)

        async def one(i: int, row: dict) -> None:
            async with sem:
                if self.cancelled:
                    return
                t0 = time.time()
                try:
                    r = from_recorded(row["url"])
                    if r is None:
                        full = await asyncio.wait_for(scanner.scan(row["url"], use_browser=self.use_browser, use_ai=self.use_ai), timeout=90)
                        r = scanner.public(full)
                        if self.shots_dir and full.get("png"):
                            os.makedirs(self.shots_dir, exist_ok=True)
                            r["shot"] = f"{i + 1:03d}.png"
                            with open(os.path.join(self.shots_dir, r["shot"]), "wb") as fh:
                                fh.write(full["png"])
                except Exception as exc:
                    r = {"input_url": row["url"], "error": f"{type(exc).__name__}: {str(exc)[:120]}", "score": 0, "verdict": "no_indicators",
                         "label": "legit", "reasons": [], "signals": [], "seconds": round(time.time() - t0, 1), "engine": "none"}
                r["n"] = i + 1
                r["expected"] = row.get("label")
                r["correct"] = (r["label"] == row["label"]) if row.get("label") else None
                self.results[i] = r
                self.done += 1

        await asyncio.gather(*(one(i, r) for i, r in enumerate(self.rows)))
        self.finished = True


JOBS: dict[str, Job] = {}


def start(text: str, use_browser: bool = True, use_ai: bool = False, concurrency: int = 4) -> Job:
    rows = parse_input(text)[:500]
    if not rows:
        raise ValueError("No URLs found. Paste one URL per line, or a CSV with url,label columns.")
    job = Job(rows, use_browser, use_ai, concurrency)
    JOBS[job.id] = job
    job.task = asyncio.get_running_loop().create_task(job.run())
    return job


def to_csv(job: Job) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["n", "url", "final_url", "expected", "predicted", "correct", "score", "verdict", "scam_type", "impersonates", "engine", "seconds", "top_reasons", "error"])
    for r in sorted((r for r in job.results if r), key=lambda r: r["n"]):
        w.writerow([r["n"], r["input_url"], r.get("final_url", ""), r.get("expected") or "", r["label"], "" if r.get("correct") is None else r["correct"],
                    r["score"], r["verdict"], r.get("scam_type", ""), r.get("brand") or "", r.get("engine", ""), r.get("seconds", ""),
                    " | ".join(r.get("reasons", [])), r.get("error") or ""])
    return buf.getvalue()


# --------------------------------------------------------------------------- sample sets

LEGIT_SAMPLE = ["https://www.rta.ae", "https://www.salik.ae", "https://www.emiratespost.ae", "https://www.adcb.com", "https://www.bankfab.com",
                "https://www.emiratesnbd.com", "https://www.dubaipolice.gov.ae", "https://u.ae", "https://www.tamm.abudhabi", "https://uaepass.ae",
                "https://www.etisalat.ae", "https://www.du.ae", "https://www.noon.com", "https://www.amazon.ae", "https://www.khaleejtimes.com",
                "https://www.thenationalnews.com", "https://www.careem.com", "https://www.dewa.gov.ae", "https://www.aramex.com", "https://example.com"]


def recorded_sample() -> list[dict]:
    K = knowledge.get()
    out = []
    for cid, c in sorted(K.cases.items()):
        if c["kind"] == "site" and c.get("source") != "scan":
            out.append({"url": c["input_url"], "label": "fraud" if c["ground_truth"]["label"] == "scam" else "legit"})
    return out


async def openphish_sample(n: int = 15) -> list[dict]:
    """A few live phishing URLs from the free OpenPhish community feed (labelled fraud)."""
    async with httpx.AsyncClient(timeout=15.0, verify=ssl_context(), follow_redirects=True, headers={"User-Agent": "raqib-evaluator"}) as c:
        r = await c.get(OPENPHISH_FEED)
        r.raise_for_status()
    urls = [u.strip() for u in r.text.splitlines() if u.strip().startswith("http")]
    random.shuffle(urls)
    return [{"url": u, "label": "fraud"} for u in urls[:n]]
