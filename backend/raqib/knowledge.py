"""The knowledge base: every recorded case, its analysis, fingerprint and campaign links."""

from __future__ import annotations

import json
import threading

from . import campaign, config, fingerprint, hunters
from .detectors import analyse, classify_scam, enrich, final_score, verdict_for
from .domains import host_of, registrable
from .registry import load_registry


class Knowledge:
    def __init__(self) -> None:
        self.reg = load_registry()
        self.cases: dict[str, dict] = {}
        self.analysis: dict[str, dict] = {}
        self.fps: dict[str, dict] = {}
        self.graph: dict = {"edges": [], "cluster_of": {}}
        self._lock = threading.Lock()
        self.reload()

    # ------------------------------------------------------------------ loading

    def reload(self) -> None:
        with self._lock:
            self.cases.clear(), self.analysis.clear(), self.fps.clear()
            paths = sorted(config.CASES_DIR.glob("*.json")) + (sorted(config.LIVE_CASES_DIR.glob("*.json")) if config.LIVE_CASES_DIR.is_dir() else [])
            for path in paths:
                c = json.loads(path.read_text(encoding="utf-8"))
                self.cases[c["case_id"]] = c
            for cid, c in self.cases.items():
                self.fps[cid] = fingerprint.build(c)
                self.analysis[cid] = self._analyse_case(c)
            self.graph = campaign.build_graph(self.fps)
            self.index = hunters.case_index(self.cases)

    def add_live(self, case: dict, analysis: dict) -> None:
        """Remember a real scan so later scans can link to it (and persist it across restarts)."""
        with self._lock:
            cid = case["case_id"]
            self.cases[cid] = case
            self.analysis[cid] = analysis
            self.fps[cid] = fingerprint.build(case)
            self.graph = campaign.build_graph(self.fps)
            self.index = hunters.case_index(self.cases)
        try:
            config.LIVE_CASES_DIR.mkdir(parents=True, exist_ok=True)
            (config.LIVE_CASES_DIR / f"{cid}.json").write_text(json.dumps(case, ensure_ascii=False, default=str), encoding="utf-8")
        except OSError:
            pass

    def _analyse_case(self, c: dict) -> dict:
        if c["kind"] == "site":
            a = enrich(analyse(c, self.reg), c)
            score = final_score(a)
            a.update(score=score, verdict=verdict_for(score, a["official"]), scam_type=classify_scam(a))
            return a
        # Maps listing: no site to browse, so score it from listing triage
        listing = next((l for l in hunters._feed("maps_listings.json")["listings"] if l["name"] == c["label"]), None)
        t = hunters.triage_listing(listing, self.reg) if listing else {"score": 0, "reasons": [], "brand": None}
        brand = self.reg.get(t["brand"]) if t["brand"] else None
        return {"signals": [], "brand": brand.to_dict() if brand else None, "score": t["score"], "triage": t,
                "verdict": verdict_for(t["score"]), "scam_type": brand.scam_type if brand else "unknown",
                "contacts": c.get("contacts", {}), "iocs": {}, "forms": [], "official": False, "lookalike": {"score": 0, "reasons": []}}

    # ------------------------------------------------------------------ lookups

    def resolve(self, text: str) -> str | None:
        """Map a pasted URL / host / case id to a recorded case id."""
        t = text.strip()
        if t in self.cases:
            return t
        if t.startswith("case:") and t[5:] in self.cases:
            return t[5:]
        key = t.rstrip("/")
        if key in self.index:
            return self.index[key]
        host = host_of(t)
        return self.index.get(registrable(host)) if host else None

    def on_blocklist(self, case_id: str) -> bool:
        c = self.cases[case_id]
        return c["kind"] == "site" and registrable(c["host"]) in hunters.blocklist()

    def summary(self, cid: str) -> dict:
        c, a = self.cases[cid], self.analysis[cid]
        return {"case_id": cid, "kind": c["kind"], "host": c["host"], "label": c["label"], "score": a["score"], "verdict": a["verdict"],
                "scam_type": a["scam_type"], "brand": (a.get("brand") or {}).get("name"), "cluster_id": self.graph["cluster_of"].get(cid),
                "on_blocklist": self.on_blocklist(cid), "emirates": c.get("targeting", {}).get("emirates", []),
                "family": c.get("ground_truth", {}).get("family")}

    def related(self, cid: str) -> list[dict]:
        out = []
        for e in self.graph["edges"]:
            if cid not in (e["source"], e["target"]):
                continue
            other = e["target"] if e["source"] == cid else e["source"]
            out.append({**self.summary(other), "strength": e["strength"], "weight": e["weight"], "reasons": e["reasons"]})
        return sorted(out, key=lambda r: ({"strong": 0, "medium": 1, "weak": 2}[r["strength"]], -r["score"]))

    def link(self, fp: dict) -> dict:
        """Link a fingerprint (recorded or freshly captured) against everything we already know."""
        cid = fp["case_id"]
        edges = []
        for oid, ofp in self.fps.items():
            if oid != cid:
                e = campaign.edge_from(fp, ofp)
                if e:
                    edges.append(e)
        nbrs = {e["target"] for e in edges}
        mesh = [e for e in self.graph["edges"] if e["source"] in nbrs and e["target"] in nbrs]
        related = sorted(({**self.summary(e["target"]), "strength": e["strength"], "weight": e["weight"], "reasons": e["reasons"]} for e in edges),
                         key=lambda r: ({"strong": 0, "medium": 1, "weak": 2}[r["strength"]], -r["score"]))
        cluster_id = next((r["cluster_id"] for r in related if r["strength"] in ("strong", "medium") and r["cluster_id"]), None)
        size = sum(1 for v in self.graph["cluster_of"].values() if v == cluster_id) + (0 if self.graph["cluster_of"].get(cid) == cluster_id else 1) if cluster_id else 1
        return {"related": related, "edges": edges + mesh, "cluster_id": cluster_id, "cluster_size": size}

    def subgraph(self, cid: str) -> dict:
        """Case + its neighbours + every edge between them (shows the cluster mesh)."""
        nbrs = {cid} | {e["target"] if e["source"] == cid else e["source"] for e in self.graph["edges"] if cid in (e["source"], e["target"])}
        edges = [e for e in self.graph["edges"] if e["source"] in nbrs and e["target"] in nbrs]
        nodes = [{**self.summary(n), "center": n == cid} for n in sorted(nbrs)]
        return {"nodes": nodes, "edges": edges}

    def full_graph(self) -> dict:
        nodes = [self.summary(c) for c in sorted(self.cases)]
        return {"nodes": nodes, "edges": self.graph["edges"]}

    def clusters(self) -> list[dict]:
        groups: dict[str, list[str]] = {}
        for cid, cl in self.graph["cluster_of"].items():
            groups.setdefault(cl, []).append(cid)
        out = []
        for cl, members in sorted(groups.items()):
            sums = [self.summary(m) for m in members]
            fps = [self.fps[m] for m in members]
            shared = sorted({x for f in fps for x in f["exfil"] + f["wallets"] if sum(1 for g in fps if x in g["exfil"] + g["wallets"]) > 1})
            out.append({"cluster_id": cl, "size": len(members), "sites": sums, "shared_indicators": shared,
                        "unblocked": len([s for s in sums if s["kind"] == "site" and not s["on_blocklist"]]),
                        "emirates": sorted({e for s in sums for e in s["emirates"]}),
                        "headline": max(sums, key=lambda s: s["score"])["scam_type"]})
        return sorted(out, key=lambda c: -c["size"])

    def demo_targets(self) -> list[dict]:
        order = ["c_salik_topup", "c_epost_redelivery", "c_adcb_verify", "c_goldtrade", "c_mohre_jobs", "c_rta_copy", "c_bakery"]
        out = []
        for cid in order:
            c = self.cases[cid]
            out.append({"case_id": cid, "label": c["label"], "url": c["input_url"], "source": c["source"], "truth": c["ground_truth"]["label"]})
        return out


_instance: Knowledge | None = None


def get() -> Knowledge:
    global _instance
    if _instance is None:
        _instance = Knowledge()
    return _instance
