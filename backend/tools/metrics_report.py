"""Turn an evaluation run into presentation numbers, with honest error bars and every mistake listed.

  python tools/metrics_report.py <run folder with results.json and eval.csv> --out ../docs/eval

Writes results.md (tables for the deck) and results.csv (one row per URL). URLs are defanged
(hxxp, [.]) so no live phishing link ends up clickable in the repository.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import statistics
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from raqib import batch  # noqa: E402
from raqib.hunters_live import brand_tokens  # noqa: E402

SWEEP = (40, 50, 60, 70, 80)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    """95% Wilson score interval for k successes out of n."""
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def defang(url: str) -> str:
    p = urlsplit(url)
    return f"{p.scheme.replace('http', 'hxxp')}://{(p.netloc or '').replace('.', '[.]')}{p.path[:60]}"


def pct(x: float | None) -> str:
    return "–" if x is None else f"{100 * x:.0f}%"


def rate(k: int, n: int) -> str:
    ci = wilson(k, n)
    return "–" if not ci else f"{pct(k / n)} ({k}/{n}, 95% CI {pct(ci[0])}–{pct(ci[1])})"


def uae_related(url: str, long_t: set[str], short_t: set[str]) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    parts = set(host.replace("-", ".").split("."))
    return host.endswith(".ae") or any(t in host for t in long_t) or bool(parts & short_t)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run", help="folder with results.json, eval.csv and shots/")
    ap.add_argument("--out", default="docs/eval")
    a = ap.parse_args()
    run, out = Path(a.run), Path(a.out)
    snap = json.loads((run / "results.json").read_text(encoding="utf-8"))
    sets = {r["url"]: r["set"] for r in csv.DictReader((run / "eval.csv").open(encoding="utf-8"))}
    res = [{**r, "set": sets.get(r["input_url"], "?")} for r in snap["results"]]
    head = [r for r in res if r["set"] in ("fraud", "legit")]
    guard = [r for r in res if r["set"] == "guard"]
    m = batch.metrics(head)
    tp, fp, tn, fn = m["tp"], m["fp"], m["tn"], m["fn"]
    long_t, short_t = brand_tokens()
    live = lambda r: r.get("engine") not in ("none", None)  # noqa: E731

    lines = [f"# Raqib accuracy run · {snap.get('seconds', 0):.0f} s · threshold {snap['threshold']}", "",
             "Scanned inside the locked-down sandbox VM (no API key, deterministic rules only, no Claude).", "",
             "## Headline (OpenPhish phishing vs. Tranco sites that are not on Raqib's allowlist)", "",
             "| | Predicted scam | Predicted legit |", "|---|---|---|", f"| **Phishing** | {tp} (TP) | {fn} (FN) |", f"| **Legit** | {fp} (FP) | {tn} (TN) |", "",
             "| Metric | Value |", "|---|---|",
             f"| Precision | {rate(tp, tp + fp)} |", f"| Recall (detection rate) | {rate(tp, tp + fn)} |",
             f"| F1 | {pct(m['f1'])} |", f"| Accuracy | {rate(tp + tn, tp + tn + fp + fn)} |",
             f"| False-positive rate | {rate(fp, fp + tn)} |",
             f"| Official UAE sites wrongly flagged (allowlist guard) | {rate(sum(r['label'] == 'fraud' for r in guard), len(guard))} |",
             f"| Median time per URL | {statistics.median([r.get('seconds') or 0 for r in res]):.1f} s |", "",
             "## Threshold sweep (same scans, no re-run)", "", "| Score ≥ | Precision | Recall | False-positive rate |", "|---|---|---|---|"]
    for t in SWEEP:
        stp = sum(1 for r in head if r["set"] == "fraud" and r["score"] >= t)
        sfp = sum(1 for r in head if r["set"] == "legit" and r["score"] >= t)
        nf, nl = sum(r["set"] == "fraud" for r in head), sum(r["set"] == "legit" for r in head)
        lines.append(f"| {t} | {pct(stp / (stp + sfp) if stp + sfp else None)} | {pct(stp / nf if nf else None)} | {pct(sfp / nl if nl else None)} |")

    lines += ["", "## Where it misses", "", "| Slice | Recall |", "|---|---|"]
    fr = [r for r in head if r["set"] == "fraud"]
    for name, sub in (("Phishing page still online when scanned", [r for r in fr if live(r)]),
                      ("Phishing link already dead", [r for r in fr if not live(r)]),
                      ("Mentions a UAE brand or uses .ae", [r for r in fr if uae_related(r["input_url"], long_t, short_t)]),
                      ("Global brands (Microsoft, banks abroad, ...)", [r for r in fr if not uae_related(r["input_url"], long_t, short_t)])):
        lines.append(f"| {name} | {rate(sum(r['label'] == 'fraud' for r in sub), len(sub))} |")
    lg = [r for r in head if r["set"] == "legit"]
    lines += ["", f"Legit sites that actually loaded: {sum(live(r) for r in lg)} of {len(lg)}; "
                  f"false-positive rate among them: {rate(sum(r['label'] == 'fraud' for r in lg if live(r)), sum(live(r) for r in lg))}."]

    lines += ["", "## Every mistake (for review)", "", "| Kind | URL (defanged) | Score | Page | Top reasons | Screenshot |", "|---|---|---|---|---|---|"]
    shots = out / "shots"
    for r in sorted(res, key=lambda r: (r["set"], -r["score"])):
        kind = "FN" if r["set"] == "fraud" and r["label"] != "fraud" else "FP" if r["set"] != "fraud" and r["label"] == "fraud" else None
        if not kind:
            continue
        shot = ""
        if r.get("shot") and (run / "shots" / r["shot"]).is_file():
            shots.mkdir(parents=True, exist_ok=True)
            shutil.copy(run / "shots" / r["shot"], shots / r["shot"])
            shot = f"shots/{r['shot']}"
        lines.append(f"| {kind} ({r['set']}) | `{defang(r['input_url'])}` | {r['score']} | {r.get('engine')} | {'; '.join((r.get('reasons') or [])[:2]) or '–'} | {shot} |")

    out.mkdir(parents=True, exist_ok=True)
    (out / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (out / "results.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["set", "expected", "predicted", "score", "verdict", "engine", "impersonates", "url_defanged", "top_reasons", "seconds"])
        for r in sorted(res, key=lambda r: r.get("n", 0)):
            w.writerow([r["set"], r.get("expected"), r["label"], r["score"], r["verdict"], r.get("engine"), r.get("brand") or "", defang(r["input_url"]),
                        " | ".join((r.get("reasons") or [])[:3]), r.get("seconds")])
    print("\n".join(lines[:22]))


if __name__ == "__main__":
    main()
