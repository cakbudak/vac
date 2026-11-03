"""Run the second slice: probe real servers in traffic order inside an isolated network
namespace, grade against the declared contracts, learn with the frozen version space,
evaluate on held-out traffic.  Several seeds, one sandbox per seed.

    .venv/bin/python pilot2/run_pilot.py [--seeds 1,2,3] [--results results2] [--no-isolation] [server ...]

Outputs per server and seed under <results>/<server>/seed-<k>/: receipts_setup.jsonl (operator
set-up calls, graded, not learned from), receipts_train.jsonl, receipts_heldout.jsonl,
summary.json.  `report.py` turns the summaries into PILOT2_RESULTS.md.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contracts import STATE_DEVIATIONS, load as load_contract  # noqa: E402
from harness import call_observed, cleanup_stale_namespaces, install_digest, open_session  # noqa: E402
from learner_bridge import InducedVocabulary, Learner, frozen_digests  # noqa: E402
from targets import TARGETS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MAX_K3_HYPOTHESES = 60_000_000


def harness_digest() -> str:
    h = hashlib.sha256()
    for p in sorted((ROOT / "pilot2").glob("*.py")):
        if p.name == "quick_list.py":
            continue
        h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()


def _context(spec, sandbox) -> dict:
    return {"work": str(sandbox.work), "home": str(sandbox.home), "tmp": str(sandbox.tmp), "root": str(sandbox.root),
            "db": sandbox.meta.get("db", ""), "repo": sandbox.meta.get("repo", ""),
            "vault": sandbox.meta.get("vault", ""), "memory_file": sandbox.meta.get("memory_file", "")}


def _tally():
    return {"safe_allowed": 0, "safe_reviewed": 0, "safe_blocked": 0,
            "dev_allowed": 0, "dev_reviewed": 0, "dev_blocked": 0, "errors": 0}


def _served_definition_digest(tools) -> str:
    rows = [{"name": t.name, "description": t.description,
             "inputSchema": getattr(t, "input_schema", None) or getattr(t, "inputSchema", None),
             "annotations": (t.annotations.model_dump() if getattr(t, "annotations", None) else None)} for t in tools.tools]
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


async def run_server(name: str, seed: int, results: Path, isolate: bool, label_level: str) -> dict:
    spec = TARGETS[name]
    contract = load_contract(name)
    sandbox = spec.make_sandbox(seed)
    out_dir = results / name / f"seed-{seed}"
    out_dir.mkdir(parents=True, exist_ok=True)
    setup = spec.setup_actions(sandbox, seed) if spec.setup_actions else []
    train = spec.train_actions(sandbox, seed)
    heldout = spec.heldout_actions(sandbox, seed)
    vocab = InducedVocabulary([(a.tool, a.args) for a in train])
    learners = {"2-junta": Learner(vocab, 2)}
    from math import comb
    if comb(vocab.size, 3) * 256 <= MAX_K3_HYPOTHESES:
        learners["3-junta"] = Learner(vocab, 3)
    ctx = _context(spec, sandbox)
    started = datetime.now(timezone.utc).isoformat()
    summary = {
        "server": name, "kind": spec.kind, "source": spec.source, "description": spec.description,
        "seed": seed, "started": started, "sandbox": str(sandbox.root), "label_level": label_level,
        "install_digest": install_digest(spec.install_files()) if spec.install_files else None,
        "contract_digest": hashlib.sha256(json.dumps(contract.raw, sort_keys=True).encode()).hexdigest(),
        "frozen_learner_digests": frozen_digests(), "harness_digest": harness_digest(),
        "vocabulary": {"generated": vocab.generated, "distinct_after_merge": vocab.size, "names": vocab.names[:400]},
        "learners": list(learners),
    }
    per_tool: dict[str, dict] = {}
    setup_receipts, train_receipts, held_receipts = [], [], []

    def tool_row(tool: str) -> dict:
        return per_tool.setdefault(tool, {"probes": 0, "errors": 0, "deviations": 0, "deviations_tools_list": 0,
                                          "first_deviation_probe": None, "deviation_kinds": {}, "deviation_kinds_tools_list": {},
                                          "flags": {}, "doc_sufficient": None})

    def label(g, r) -> bool:
        return bool(g["is_deviation_tools_list"] if label_level == "tools_list" else g["is_deviation"])

    async with open_session(spec, sandbox, isolate=isolate) as live:
        tools = await live.session.list_tools()
        summary["tools_listed"] = [t.name for t in tools.tools]
        summary["served_definition_digest"] = _served_definition_digest(tools)
        summary["net_isolation"] = "netns_veth_tcpdump" if live.net is not None else "none"
        idx = 0
        for action in setup:
            r = await call_observed(live, action, idx); idx += 1
            r["grade"] = contract.grade(r, ctx)
            r["phase"] = "setup"
            setup_receipts.append(r)
        # ---- training traffic: every probe is paid on the live server ----
        for action in train:
            r = await call_observed(live, action, idx); idx += 1
            g = contract.grade(r, ctx)
            r["grade"] = g
            train_receipts.append(r)
            row = tool_row(action.tool)
            row["probes"] += 1
            row["doc_sufficient"] = g.get("doc_sufficient")
            for f in g.get("flags", []):
                row["flags"][f] = row["flags"].get(f, 0) + 1
            if r["is_error"] or r.get("transport_error"):
                row["errors"] += 1
            if g["is_deviation"]:
                row["deviations"] += 1
                if row["first_deviation_probe"] is None:
                    row["first_deviation_probe"] = row["probes"]
                for k in g["deviation_kinds"]:
                    row["deviation_kinds"][k] = row["deviation_kinds"].get(k, 0) + 1
            if g["is_deviation_tools_list"]:
                row["deviations_tools_list"] += 1
                for k in g["deviation_kinds_tools_list"]:
                    row["deviation_kinds_tools_list"][k] = row["deviation_kinds_tools_list"].get(k, 0) + 1
            for L in learners.values():
                L.observe(action.tool, action.args, label(g, r), bool(r["is_error"] or r.get("transport_error")))
        summary["train"] = {"probes": len(train), "errors": sum(bool(r["is_error"] or r.get("transport_error")) for r in train_receipts),
                            "deviations": sum(r["grade"]["is_deviation"] for r in train_receipts),
                            "deviations_tools_list": sum(r["grade"]["is_deviation_tools_list"] for r in train_receipts),
                            "hypotheses_remaining": {n: L.hypotheses_remaining for n, L in learners.items()},
                            "observed_by_learner": {n: L.observed for n, L in learners.items()}}
        # ---- held-out traffic: verdict recorded BEFORE execution, then graded from state ----
        tallies = {n: _tally() for n in learners}
        held_tool: dict[str, dict] = {}
        for action in heldout:
            verdicts = {n: L.verdict(action.tool, action.args) for n, L in learners.items()}
            r = await call_observed(live, action, idx); idx += 1
            g = contract.grade(r, ctx)
            r["grade"] = g
            r["verdicts_before_execution"] = verdicts
            held_receipts.append(r)
            ht = held_tool.setdefault(action.tool, {"actions": 0, "deviations": 0, "deviations_tools_list": 0, "errors": 0,
                                                    "verdicts": {n: {"allow": 0, "review": 0, "block": 0} for n in learners}})
            ht["actions"] += 1
            err = bool(r["is_error"] or r.get("transport_error"))
            ht["errors"] += err
            ht["deviations"] += g["is_deviation"]
            ht["deviations_tools_list"] += g["is_deviation_tools_list"]
            dev = label(g, r)
            for n, v in verdicts.items():
                ht["verdicts"][n][v] += 1
                t = tallies[n]
                if err:
                    t["errors"] += 1
                    continue
                key = ("dev" if dev else "safe") + "_" + {"allow": "allowed", "review": "reviewed", "block": "blocked"}[v]
                t[key] += 1
        summary["heldout"] = {"actions": len(heldout), "tallies": tallies, "per_tool": held_tool}
        summary["background_net"] = live.background_net
    summary["setup"] = {"calls": len(setup), "deviations": sum(r["grade"]["is_deviation"] for r in setup_receipts),
                        "deviations_tools_list": sum(r["grade"]["is_deviation_tools_list"] for r in setup_receipts),
                        "kinds_tools_list": sorted({k for r in setup_receipts for k in r["grade"]["deviation_kinds_tools_list"]})}
    summary["per_tool_train"] = per_tool
    summary["deviation_kinds_total"] = {}
    summary["deviation_kinds_total_tools_list"] = {}
    for r in train_receipts + held_receipts:
        for k in r["grade"].get("deviation_kinds", []):
            summary["deviation_kinds_total"][k] = summary["deviation_kinds_total"].get(k, 0) + 1
        for k in r["grade"].get("deviation_kinds_tools_list", []):
            summary["deviation_kinds_total_tools_list"][k] = summary["deviation_kinds_total_tools_list"].get(k, 0) + 1
    all_r = setup_receipts + train_receipts + held_receipts
    summary["channel_observations"] = {
        "proxy_requests": sum(len(r["proxy_requests"]) for r in all_r),
        "remote_sockets": sum(len(r["remote_sockets"]) for r in all_r),
        "net_attempts": sum(len(r.get("net_attempts", [])) for r in all_r),
        "net_names": sorted({a.get("qname") for r in all_r for a in r.get("net_attempts", []) if a.get("qname")}),
        "background_net_attempts": len(summary["background_net"]),
        "background_net_names": sorted({a.get("qname") or a.get("host") or a.get("dst") for a in summary["background_net"] if a}),
        "calls_with_children": sum(bool(r["children"]) for r in all_r),
        "calls_with_fs_change": sum(bool(r["fs"]["created"] or r["fs"]["deleted"] or r["fs"]["modified"]) for r in all_r),
        "mean_sampler_samples_per_call": round(sum(r["sampler_samples"] for r in all_r) / max(1, len(all_r)), 1),
    }
    summary["finished"] = datetime.now(timezone.utc).isoformat()
    for fname, rows in (("receipts_setup.jsonl", setup_receipts), ("receipts_train.jsonl", train_receipts),
                        ("receipts_heldout.jsonl", held_receipts)):
        with (out_dir / fname).open("w") as f:
            for r in rows:
                f.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
    print(f"{name} seed {seed}: train {summary['train']['probes']} probes, {summary['train']['deviations']} deviations "
          f"({summary['train']['deviations_tools_list']} at tools/list level), {summary['train']['errors']} tool errors; "
          f"vocab {vocab.size}; hypotheses left {summary['train']['hypotheses_remaining']}; held-out tallies {tallies}; "
          f"background net {len(summary['background_net'])}")
    return summary


async def main(args):
    cleanup_stale_namespaces()
    results = Path(args.results)
    names = args.servers or list(TARGETS)
    seeds = [int(s) for s in args.seeds.split(",")]
    for n in names:
        for seed in seeds:
            t0 = time.perf_counter()
            try:
                await run_server(n, seed, results, not args.no_isolation, args.label_level)
            except Exception as exc:
                print(n, seed, "FAILED:", type(exc).__name__, str(exc)[:500])
                if args.stop_on_error:
                    raise
            print(f"  ({time.perf_counter() - t0:.1f}s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--results", default=str(ROOT / "results2"))
    ap.add_argument("--label-level", default="readme", choices=["readme", "tools_list"])
    ap.add_argument("--no-isolation", action="store_true")
    ap.add_argument("--stop-on-error", action="store_true")
    ap.add_argument("servers", nargs="*")
    asyncio.run(main(ap.parse_args()))
