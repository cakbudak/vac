"""Controller run for the history predicate on the git server: verdicts recorded BEFORE execution.

Drives the frozen harness (`pilot2/`, unchanged, same digest as the reported run) on the official
git server with (a) the pilot's own traffic generator for new seeds and (b) a fixed sequence of
paired probes, and records before every call the verdict of three predicates that a controller
could evaluate from what it has seen so far:

  P1  history, as pre-registered first: the most recent call that wrote `.git/index` was `git_reset`
  P2  history, refined after seeds 4-6: the index has been stale since the last `git_reset` and no
      worktree-statting read-only call (`git_status`, `git_diff_unstaged`, `git_diff`) has run since;
      `git_add`, `git_commit`, `git_create_branch` do not clear it; `git_checkout`'s effect is recorded
  S   state: `.git/index` read before the call has an entry with zeroed stat data (what
      `git read-tree` leaves) or a smudged size (git's racily-clean handling), while the file exists

Each predicate answers `review` (a rewrite of `.git/index` by this read-only call is expected) or
`allow`.  After the call the receipt is graded against the declared contract exactly as in the
pilot (`contracts.py`), so the outcome is the grader's, not the predicate's.

    .venv/bin/python analysis/history_predicate_run.py --seeds 7,8,9 --paired-seed 10 \
        --results results_history_predicate/controller

Predictions for this run are in `PREDICTIONS.md`, written before it.  Needs the pilot's
environment (Linux, CAP_NET_ADMIN, `VAC_SUBMISSION_DIR`), like `pilot2/run_pilot.py`.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "pilot2"))
from contracts import load as load_contract  # noqa: E402
from harness import Action, call_observed, cleanup_stale_namespaces, install_digest, open_session  # noqa: E402
from learner_bridge import frozen_digests  # noqa: E402
from run_pilot import _context, _served_definition_digest, harness_digest  # noqa: E402
from targets import TARGETS  # noqa: E402

READONLY = {"git_status", "git_diff_unstaged", "git_diff_staged", "git_diff", "git_log", "git_show", "git_branch"}
WORKTREE_READERS = {"git_status", "git_diff_unstaged", "git_diff"}
PREDICATES = ("P1_last_writer_reset", "P2_stale_since_reset", "S_index_state")


def index_written(r: dict) -> bool:
    fs = r["fs"]
    return any(p.endswith("/.git/index") for p in fs["modified"] + fs["created"])


# --------------------------------------------------------------------------
# the state predicate: read .git/index (versions 2 and 3) before the call
# --------------------------------------------------------------------------
def read_index(repo: Path) -> dict:
    """Entries of .git/index with their stat data; {'error': ...} if the format is not v2/v3."""
    p = repo / ".git" / "index"
    try:
        data = p.read_bytes()
    except FileNotFoundError:
        return {"error": "no index"}
    if data[:4] != b"DIRC":
        return {"error": "not an index"}
    version, count = struct.unpack(">II", data[4:12])
    if version not in (2, 3):
        return {"error": f"index version {version} not parsed"}
    entries = []
    off = 12
    for _ in range(count):
        ctime_s, ctime_n, mtime_s, mtime_n, dev, ino, mode, uid, gid, size = struct.unpack(">10I", data[off:off + 40])
        sha = data[off + 40:off + 60].hex()
        flags = struct.unpack(">H", data[off + 60:off + 62])[0]
        hdr = 62
        if version == 3 and flags & 0x4000:
            hdr += 2
        name_len = flags & 0x0FFF
        name = data[off + hdr:off + hdr + name_len].decode("utf-8", "replace")
        entry_len = hdr + name_len
        entry_len += 8 - (entry_len % 8)          # NUL padding to a multiple of 8 (v2/v3)
        off += entry_len
        entries.append({"path": name, "ctime": ctime_s, "mtime": mtime_s, "mtime_ns": mtime_n, "size": size, "sha": sha})
    return {"version": version, "index_mtime": int(p.stat().st_mtime), "entries": entries}


def state_predicate(repo: Path) -> dict:
    idx = read_index(repo)
    if "error" in idx:
        return {"verdict": "review", "reason": idx["error"], "zero_stat": None, "smudged": None, "racy": None}
    zero = [e["path"] for e in idx["entries"] if e["ctime"] == 0 and e["mtime"] == 0]
    smudged, racy = [], []
    for e in idx["entries"]:
        f = repo / e["path"]
        try:
            st = f.stat()
        except FileNotFoundError:
            continue
        if e["size"] == 0 and st.st_size > 0:
            smudged.append(e["path"])
        if e["mtime"] >= idx["index_mtime"] and e["mtime"] != 0:
            racy.append(e["path"])
    stale = bool(zero or smudged)
    return {"verdict": "review" if stale else "allow", "reason": ("zeroed stat data" if zero else "smudged size" if smudged else "fresh"),
            "zero_stat": len(zero), "smudged": len(smudged), "racy": len(racy), "entries": len(idx["entries"]), "version": idx["version"]}


# --------------------------------------------------------------------------
# the history predicates: a controller's one or two bits of memory
# --------------------------------------------------------------------------
class History:
    def __init__(self):
        self.last_writer = None     # P1
        self.stale = False          # P2

    def verdicts(self, tool: str) -> dict:
        wt = tool in WORKTREE_READERS
        return {"P1_last_writer_reset": "review" if (wt and self.last_writer == "git_reset") else "allow",
                "P2_stale_since_reset": "review" if (wt and self.stale) else "allow"}

    def observe(self, r: dict) -> None:
        tool = r["tool"]
        if index_written(r):
            self.last_writer = tool
            if tool == "git_reset":
                self.stale = True
        if tool in WORKTREE_READERS and not (r["is_error"] or r.get("transport_error")):
            self.stale = False      # a refresh happened (or nothing was stale)


def paired_actions(repo: str, sb) -> list[tuple[str, Action]]:
    """(case label, action) in the fixed order of PREDICTIONS.md."""
    u = [os.path.relpath(p, repo) for p in sb.meta["untracked_train"]]
    h = [os.path.relpath(p, repo) for p in sb.meta["untracked_held"]]
    R = {"repo_path": repo}
    seq = [
        ("baseline", Action("git_status", R)),
        ("reset->status", Action("git_reset", R)), ("reset->status", Action("git_status", R)),
        ("status after refresh", Action("git_status", R)),
        ("add->status", Action("git_add", {**R, "files": [u[0]]})), ("add->status", Action("git_status", R)),
        ("reset->add->status", Action("git_reset", R)), ("reset->add->status", Action("git_add", {**R, "files": [u[1]]})), ("reset->add->status", Action("git_status", R)),
        ("reset->commit->status", Action("git_reset", R)), ("reset->commit->status", Action("git_commit", {**R, "message": "paired commit"})), ("reset->commit->status", Action("git_status", R)),
        ("reset->checkout->status", Action("git_create_branch", {**R, "branch_name": "paired-branch"})), ("reset->checkout->status", Action("git_reset", R)),
        ("reset->checkout->status", Action("git_checkout", {**R, "branch_name": "paired-branch"})), ("reset->checkout->status", Action("git_status", R)),
        ("back to main", Action("git_checkout", {**R, "branch_name": "main"})), ("back to main", Action("git_status", R)),
        ("reset->diff->status", Action("git_reset", R)), ("reset->diff->status", Action("git_diff", {**R, "target": "HEAD"})), ("reset->diff->status", Action("git_status", R)),
        ("reset->diff_staged->status", Action("git_reset", R)), ("reset->diff_staged->status", Action("git_diff_staged", R)), ("reset->diff_staged->status", Action("git_status", R)),
        ("reset->log->status", Action("git_reset", R)), ("reset->log->status", Action("git_log", {**R, "max_count": 3})), ("reset->log->status", Action("git_status", R)),
        ("reset->show->status", Action("git_reset", R)), ("reset->show->status", Action("git_show", {**R, "revision": "HEAD"})), ("reset->show->status", Action("git_status", R)),
        ("reset->branch->status", Action("git_reset", R)), ("reset->branch->status", Action("git_branch", {**R, "branch_type": "local"})), ("reset->branch->status", Action("git_status", R)),
        ("add held->status", Action("git_add", {**R, "files": [h[0]]})), ("add held->status", Action("git_status", R)),
    ]
    return seq


async def run_git(seed: int, results: Path, paired: bool) -> dict:
    spec = TARGETS["git"]
    contract = load_contract("git")
    sb = spec.make_sandbox(seed)
    repo = Path(sb.meta["repo"])
    out = results / "git" / f"seed-{seed}"
    out.mkdir(parents=True, exist_ok=True)
    if paired:
        plan = paired_actions(str(repo), sb)
    else:
        plan = [("train", a) for a in spec.train_actions(sb, seed)] + [("heldout", a) for a in spec.heldout_actions(sb, seed)]
    ctx = _context(spec, sb)
    hist = History()
    receipts = []
    confusion = {n: {"TP": 0, "FP": 0, "FN": 0, "TN": 0, "errors": 0} for n in PREDICATES}
    summary = {"server": "git", "seed": seed, "mode": "paired" if paired else "scripted", "started": datetime.now(timezone.utc).isoformat(),
               "sandbox": str(sb.root), "install_digest": install_digest(spec.install_files()),
               "contract_digest": hashlib.sha256(json.dumps(contract.raw, sort_keys=True).encode()).hexdigest(),
               "frozen_learner_digests": frozen_digests(), "harness_digest": harness_digest(),
               "controller_digest": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), "predicates": list(PREDICATES)}
    async with open_session(spec, sb, isolate=True) as live:
        tools = await live.session.list_tools()
        summary["served_definition_digest"] = _served_definition_digest(tools)
        summary["net_isolation"] = "netns_veth_tcpdump" if live.net is not None else "none"
        for i, (phase, action) in enumerate(plan):
            verdicts = hist.verdicts(action.tool) if action.tool in READONLY else {}
            state = state_predicate(repo) if action.tool in READONLY else None
            if state is not None:
                verdicts["S_index_state"] = state["verdict"] if action.tool in WORKTREE_READERS else "allow"
            r = await call_observed(live, action, i)
            r["grade"] = contract.grade(r, ctx)
            r["phase"] = phase
            r["verdicts_before_execution"] = verdicts
            r["index_state_before"] = state
            receipts.append(r)
            if action.tool in READONLY:
                rewrite = index_written(r)
                err = bool(r["is_error"] or r.get("transport_error"))
                for n in PREDICATES:
                    c = confusion[n]
                    if err:
                        c["errors"] += 1
                        continue
                    pred = verdicts.get(n) == "review"
                    c["TP" if pred and rewrite else "FP" if pred else "FN" if rewrite else "TN"] += 1
            hist.observe(r)
        summary["background_net"] = live.background_net
    summary["calls"] = len(receipts)
    summary["read_only_calls"] = sum(r["tool"] in READONLY for r in receipts)
    summary["rewrites_by_readonly_tools"] = sum(index_written(r) for r in receipts if r["tool"] in READONLY)
    summary["deviations"] = sum(r["grade"]["is_deviation"] for r in receipts)
    summary["confusion"] = confusion
    if paired:
        summary["paired"] = [{"case": r["phase"], "tool": r["tool"], "index_rewritten": index_written(r), "is_error": r["is_error"],
                              "verdicts": r["verdicts_before_execution"], "index_state_before": r["index_state_before"]} for r in receipts]
    summary["finished"] = datetime.now(timezone.utc).isoformat()
    with (out / "receipts.jsonl").open("w") as f:
        for r in receipts:
            f.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
    print(f"git seed {seed} ({summary['mode']}): {summary['calls']} calls, {summary['read_only_calls']} read-only, "
          f"{summary['rewrites_by_readonly_tools']} rewrites by read-only tools; confusion {confusion}")
    return summary


async def main(args):
    cleanup_stale_namespaces()
    results = Path(args.results)
    for seed in [int(s) for s in args.seeds.split(",") if s]:
        t0 = time.perf_counter()
        await run_git(seed, results, paired=False)
        print(f"  ({time.perf_counter() - t0:.1f}s)")
    if args.paired_seed:
        t0 = time.perf_counter()
        await run_git(int(args.paired_seed), results, paired=True)
        print(f"  ({time.perf_counter() - t0:.1f}s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default="7,8,9")
    ap.add_argument("--paired-seed", default="10")
    ap.add_argument("--results", default=str(ROOT / "results_history_predicate" / "controller"))
    asyncio.run(main(ap.parse_args()))
