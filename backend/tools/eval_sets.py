"""Build the labelled URL lists for an accuracy run. Nothing here opens any of the URLs.

  fraud  live phishing URLs from the OpenPhish community feed, at most one per domain
  legit  random sites from the Tranco research top-1M list (ranks 1,000-200,000) that are NOT on Raqib's
         trusted list and are not official brand domains, so the allowlist cannot flatter the false-positive rate
  guard  the official UAE sites in batch.LEGIT_SAMPLE: shows the allowlist never flags them (reported separately)

  python tools/eval_sets.py --fraud 40 --legit 40 --out ../docs/eval/raw/eval.csv
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import random
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from raqib import batch, scanner  # noqa: E402
from raqib.domains import host_of, registrable  # noqa: E402
from raqib.netutil import ssl_context  # noqa: E402
from raqib.registry import load_registry  # noqa: E402

TRANCO = "https://tranco-list.eu/top-1m.csv.zip"


def fraud_urls(client: httpx.Client, n: int, rng: random.Random) -> list[str]:
    feed = client.get(batch.OPENPHISH_FEED)
    feed.raise_for_status()
    urls = [u.strip() for u in feed.text.splitlines() if u.strip().startswith(("http://", "https://"))]
    rng.shuffle(urls)
    seen, out = set(), []
    for u in urls:
        dom = registrable(host_of(u))
        if dom and dom not in seen:
            seen.add(dom)
            out.append(u)
        if len(out) >= n:
            break
    return out


def legit_urls(client: httpx.Client, n: int, rng: random.Random) -> list[str]:
    raw = client.get(TRANCO, follow_redirects=True)
    raw.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(raw.content))
    rows = list(csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8")))
    reg = load_registry()
    pool = [d for rank, d in rows if 1000 <= int(rank) <= 200_000]
    rng.shuffle(pool)
    out = []
    for d in pool:
        if scanner.trust_of(d, reg) is None:  # not allowlisted, not official, not a vetted zone
            out.append(f"https://{d}/")
        if len(out) >= n:
            break
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fraud", type=int, default=40)
    ap.add_argument("--legit", type=int, default=40)
    ap.add_argument("--seed", type=int, default=None, help="random seed (default: from the current time, recorded in the meta file)")
    ap.add_argument("--out", default="eval.csv")
    a = ap.parse_args()
    seed = a.seed if a.seed is not None else int(datetime.now().timestamp())
    rng = random.Random(seed)
    with httpx.Client(timeout=60, verify=ssl_context(), follow_redirects=True, headers={"User-Agent": "raqib-evaluator"}) as c:
        rows = [("fraud", "fraud", u) for u in fraud_urls(c, a.fraud, rng)]
        rows += [("legit", "legit", u) for u in legit_urls(c, a.legit, rng)]
    rows += [("guard", "legit", u) for u in batch.LEGIT_SAMPLE]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["url", "label", "set"])
        for s, label, u in rows:
            w.writerow([u, label, s])
    meta = {"built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "seed": seed, "sources": {"fraud": batch.OPENPHISH_FEED, "legit": TRANCO},
            "counts": {s: sum(1 for r in rows if r[0] == s) for s in ("fraud", "legit", "guard")}}
    out.with_suffix(".meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"wrote {out}: {meta['counts']} (seed {seed})")


if __name__ == "__main__":
    main()
