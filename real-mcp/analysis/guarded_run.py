"""Guarded run on the git server: frozen controllers on new traffic, then the enforcing proxy.

Drives the frozen harness (`pilot2/`, unchanged) on the official git server with the pilot's own
traffic generator for seeds no earlier run used, in two phases:

  shadow   every call is executed; before each read-only call the run records the verdicts of
           S (index state, `runtime/state_policy.py`), P2 (history), the depth-2 tree selected on
           controller seeds 7-8 (`research/state_eval.py`) and the per-tool baseline fitted on the
           same seeds.  All four are fixed and written to `manifest.json` before the first call.
  enforce  the same seeds again, with `runtime/mcp_proxy.py` installed between the harness client and
           the unmodified server, pinned to the revision of the reported run.  A call the guard holds
           never reaches the server; the kernel's process events and the sandbox snapshots of the
           harness record what did happen.

    .venv/bin/python analysis/guarded_run.py --seeds 32-41 --results results_guarded

Needs the pilot's environment (Linux, CAP_NET_ADMIN, `VAC_SUBMISSION_DIR`), like `pilot2/run_pilot.py`.
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PACKAGE = ROOT.parent
sys.path.insert(0, str(ROOT / "pilot2"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(PACKAGE / "research"))
sys.path.insert(0, str(PACKAGE))
from contracts import load as load_contract  # noqa: E402
from harness import call_observed, cleanup_stale_namespaces, install_digest, open_session  # noqa: E402
from run_pilot import _context, _served_definition_digest, harness_digest  # noqa: E402
from targets import SERVERS, PY_SITE, TARGETS  # noqa: E402
from history_predicate_run import READONLY, WORKTREE_READERS, History, index_written, state_predicate  # noqa: E402
import state_eval  # noqa: E402
from runtime.state_policy import git_index_state  # noqa: E402

CONTROLLERS = ("S_index_state", "P2_stale_since_reset", "tree_seeds_7_8", "per_tool_seeds_7_8")
PIN = PACKAGE / "runtime" / "pins" / "git.json"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def frozen_controllers() -> dict:
    train = [r for seed in (7, 8) for r in state_eval.read(seed) if r["tool"] in READONLY]
    tree = state_eval.fit(train, tuple(sorted(state_eval.attributes(train[0]))))
    per_tool = {t: any(state_eval.outcome(r) for r in train if r["tool"] == t) for t in sorted(READONLY)}
    return {"tree": tree, "per_tool_review": per_tool, "fitted_on": "results_history_predicate/controller/git/seed-7,8",
            "training_calls": len(train)}


def verdicts_for(tool: str, state: dict | None, hist: History, frozen: dict) -> dict:
    if tool not in READONLY:
        return {}
    row = {"tool": tool, "index_state_before": state or {}}
    return {"S_index_state": git_index_state(tool, {"repo_path": state["_repo"]})[0] if state else "review",
            "P2_stale_since_reset": hist.verdicts(tool)["P2_stale_since_reset"],
            "tree_seeds_7_8": state_eval.predict(frozen["tree"], row),
            "per_tool_seeds_7_8": "review" if frozen["per_tool_review"][tool] else "allow"}


def descendants(pid: int) -> set[int]:
    found, todo = set(), [pid]
    while todo:
        p = todo.pop()
        for task in Path(f"/proc/{p}/task").glob("*"):
            try:
                kids = [int(x) for x in (task / "children").read_text().split()]
            except (OSError, ValueError):
                continue
            for k in kids:
                if k not in found:
                    found.add(k)
                    todo.append(k)
    return found


def proxied(spec, out: Path):
    """The git target with the enforcing proxy in front of the unmodified server command."""
    def build(sb):
        argv, cwd, env = spec.build_command(sb)
        wrap = [sys.executable, "-m", "runtime.mcp_proxy", "--pin", str(PIN), "--policy", "git-index-state",
                "--ledger", str(out / "ledger.jsonl"), "--log", str(out / "decisions.jsonl"),
                "--installation-path", str(PY_SITE / "mcp_server_git"), "--installation-base", str(SERVERS),
                "--contract", str(ROOT / "contracts" / "git.yaml"), "--"]
        return wrap + argv, cwd, {**env, "PYTHONPATH": str(PACKAGE)}
    return dataclasses.replace(spec, build_command=build)


async def run_seed(seed: int, mode: str, results: Path, frozen: dict) -> dict:
    base = TARGETS["git"]
    contract = load_contract("git")
    out = results / mode / "git" / f"seed-{seed}"
    out.mkdir(parents=True, exist_ok=True)
    for stale in ("ledger.jsonl", "decisions.jsonl"):
        (out / stale).unlink(missing_ok=True)
    spec = proxied(base, out) if mode == "enforce" else base
    sb = spec.make_sandbox(seed)
    repo = Path(sb.meta["repo"])
    plan = [("train", a) for a in spec.train_actions(sb, seed)] + [("heldout", a) for a in spec.heldout_actions(sb, seed)]
    ctx = _context(spec, sb)
    hist = History()
    receipts = []
    summary = {"server": "git", "seed": seed, "mode": mode, "started": datetime.now(timezone.utc).isoformat(),
               "install_digest": install_digest(spec.install_files()),
               "contract_digest": hashlib.sha256(json.dumps(contract.raw, sort_keys=True).encode()).hexdigest(),
               "harness_digest": harness_digest(), "controller_digest": sha(Path(__file__))}
    async with open_session(spec, sb, isolate=True) as live:
        tools = await live.session.list_tools()
        summary["served_definition_digest"] = _served_definition_digest(tools)
        summary["net_isolation"] = "netns_veth_tcpdump" if live.net is not None else "none"
        if live.procmon is not None:
            # the server process behind the proxy was forked before the monitor started: track it too
            with live.procmon.lock:
                live.procmon.tree.update(descendants(live.pid))
        for i, (phase, action) in enumerate(plan):
            state = state_predicate(repo) if action.tool in READONLY else None
            if state is not None:
                state = {**state, "_repo": str(repo)}
            verdicts = verdicts_for(action.tool, state, hist, frozen)
            r = await call_observed(live, action, i)
            r["grade"] = contract.grade(r, ctx)
            r["phase"] = phase
            r["verdicts_before_execution"] = verdicts
            if state is not None:
                state.pop("_repo")
            r["index_state_before"] = state
            receipts.append(r)
            hist.observe(r)
        summary["background_net"] = live.background_net
    if mode == "enforce":
        decisions = [json.loads(x) for x in (out / "decisions.jsonl").read_text().splitlines()]
        if len(decisions) != len(receipts):
            raise SystemExit(f"seed {seed}: {len(decisions)} proxy decisions for {len(receipts)} calls")
        for r, d in zip(receipts, decisions):
            if d["tool"] != r["tool"]:
                raise SystemExit(f"seed {seed}: decision order differs at call {r['index']}")
            r["proxy_decision"] = d
    summary["calls"] = len(receipts)
    summary["read_only_calls"] = sum(r["tool"] in READONLY for r in receipts)
    summary["rewrites_by_readonly_tools"] = sum(index_written(r) for r in receipts if r["tool"] in READONLY)
    summary["finished"] = datetime.now(timezone.utc).isoformat()
    with (out / "receipts.jsonl").open("w") as f:
        for r in receipts:
            f.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
    print(f"git seed {seed} ({mode}): {summary['calls']} calls, {summary['read_only_calls']} read-only, "
          f"{summary['rewrites_by_readonly_tools']} index rewrites by read-only tools")
    return summary


def parse_seeds(text: str) -> list[int]:
    if "-" in text:
        a, b = text.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(s) for s in text.split(",") if s]


async def main(args):
    cleanup_stale_namespaces()
    results = Path(args.results)
    results.mkdir(parents=True, exist_ok=True)
    seeds = parse_seeds(args.seeds)
    frozen = frozen_controllers()
    manifest = {"written_before_first_call": datetime.now(timezone.utc).isoformat(), "seeds": seeds,
                "phases": ["shadow", "enforce"], "controllers": list(CONTROLLERS), "frozen": frozen,
                "pin": json.loads(PIN.read_text()), "harness_digest": harness_digest(),
                "digests": {str(p.relative_to(PACKAGE)): sha(p) for p in
                            [Path(__file__), HERE / "history_predicate_run.py", PACKAGE / "research" / "state_eval.py",
                             PACKAGE / "runtime" / "mcp_proxy.py", PACKAGE / "runtime" / "guard.py",
                             PACKAGE / "runtime" / "state_policy.py", PACKAGE / "runtime" / "decision_ledger.py", PIN]}}
    (results / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    for mode in ("shadow", "enforce"):
        for seed in seeds:
            t0 = time.perf_counter()
            await run_seed(seed, mode, results, frozen)
            print(f"  ({time.perf_counter() - t0:.1f}s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="32-41")
    ap.add_argument("--results", default=str(ROOT / "results_guarded"))
    os.chdir(PACKAGE)
    asyncio.run(main(ap.parse_args()))
