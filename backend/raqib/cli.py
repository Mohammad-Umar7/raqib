"""Command-line scanner for URL lists (e.g. the judges' hidden test set).

    python -m raqib.cli urls.txt                     # one URL per line
    python -m raqib.cli test.csv --out results.csv   # CSV with url[,label]; prints precision/recall when labels are present
    python -m raqib.cli urls.txt --no-browser        # HTTP-only (faster, no screenshots)
    python -m raqib.cli urls.txt --ai                # add the Claude vision check (needs ANTHROPIC_API_KEY)

Run from the backend/ folder.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from . import batch, scanner


def _fmt(v):
    return "n/a" if v is None else f"{v:.3f}"


async def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="raqib", description="Scan URLs for scams and report verdicts with reasons.")
    ap.add_argument("input", help="text file (one URL per line) or CSV with url[,label]")
    ap.add_argument("--out", default="raqib_results.csv", help="CSV output path")
    ap.add_argument("--json", help="also write full JSON results here")
    ap.add_argument("--no-browser", action="store_true", help="skip the headless browser (HTTP fetch only)")
    ap.add_argument("--ai", action="store_true", help="use the Claude vision check (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--threshold", type=int, default=scanner.FRAUD_THRESHOLD, help="score at or above which a URL is labelled fraud")
    a = ap.parse_args(argv)

    scanner.FRAUD_THRESHOLD = a.threshold
    text = Path(a.input).read_text(encoding="utf-8-sig")
    job = batch.Job(batch.parse_input(text), use_browser=not a.no_browser, use_ai=a.ai, concurrency=a.concurrency)
    print(f"Scanning {len(job.rows)} URL(s) with concurrency {job.concurrency} ...", file=sys.stderr)
    runner = asyncio.create_task(job.run())
    last = -1
    while not runner.done():
        await asyncio.sleep(1)
        if job.done != last:
            last = job.done
            print(f"  {job.done}/{len(job.rows)} done", file=sys.stderr)
    await runner
    await scanner.BROWSER.close()

    Path(a.out).write_text(batch.to_csv(job), encoding="utf-8")
    if a.json:
        Path(a.json).write_text(json.dumps(job.snapshot(), ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    m = batch.metrics([r for r in job.results if r])
    flagged = sum(1 for r in job.results if r and r["label"] == "fraud")
    print(f"\nWrote {a.out}. Flagged {flagged} of {len(job.rows)} as fraud (score >= {a.threshold}).")
    if m["labelled"]:
        print(f"Labelled: {m['labelled']}  TP {m['tp']}  FP {m['fp']}  TN {m['tn']}  FN {m['fn']}")
        print(f"Precision {_fmt(m['precision'])}  Recall {_fmt(m['recall'])}  F1 {_fmt(m['f1'])}  Accuracy {_fmt(m['accuracy'])}  FPR {_fmt(m['false_positive_rate'])}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
