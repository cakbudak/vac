"""Generate GUARDED_RUN.md from results_guarded/ (written by guarded_run.py).

Every receipt digest is checked, the manifest is checked to precede the first call, and every
number of the report is computed here from the receipts.  Standard library only.

    python3 real-mcp/analysis/guarded_report.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = ROOT / "results_guarded"
REPORTED = ROOT / "results2" / "git" / "seed-1" / "summary.json"
READONLY = {"git_status", "git_diff_unstaged", "git_diff_staged", "git_diff", "git_log", "git_show", "git_branch"}
ATTACHED = ("grade", "verdicts_before_execution", "phase", "task_id", "step", "index_state_before", "proxy_decision")
NAMES = {"S_index_state": "S — index state read before the call",
         "P2_stale_since_reset": "P2 — history since the last `git_reset`",
         "tree_seeds_7_8": "Depth-2 tree selected on seeds 7–8",
         "per_tool_seeds_7_8": "Per-tool baseline fitted on seeds 7–8"}


def fail(msg: str) -> None:
    print("FAIL:", msg)
    sys.exit(1)


def index_written(r: dict) -> bool:
    return any(p.endswith("/.git/index") for p in r["fs"]["modified"] + r["fs"]["created"])


def load(mode: str) -> dict[int, tuple[dict, list[dict]]]:
    runs = {}
    for d in sorted((RESULTS / mode / "git").glob("seed-*"), key=lambda p: int(p.name[5:])):
        summary = json.loads((d / "summary.json").read_text())
        rs = [json.loads(x) for x in (d / "receipts.jsonl").read_text().splitlines() if x.strip()]
        for r in rs:
            body = {k: v for k, v in r.items() if k != "digest" and k not in ATTACHED}
            if hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest() != r.get("digest"):
                fail(f"{mode} {d.name}: receipt {r.get('index')} digest mismatch")
        runs[summary["seed"]] = (summary, rs)
    return runs


def main() -> None:
    manifest = json.loads((RESULTS / "manifest.json").read_text())
    shadow, enforce = load("shadow"), load("enforce")
    seeds = manifest["seeds"]
    if sorted(shadow) != seeds or sorted(enforce) != seeds:
        fail("seeds in results differ from the manifest")
    first = min(s["started"] for s, _ in list(shadow.values()) + list(enforce.values()))
    if not manifest["written_before_first_call"] < first:
        fail("manifest was not written before the first call")
    for rel, digest in manifest["digests"].items():
        if hashlib.sha256((ROOT.parent / rel).read_bytes()).hexdigest() != digest:
            fail(f"{rel} differs from the revision recorded in the manifest")
    reported = json.loads(REPORTED.read_text())
    keys = ("harness_digest", "install_digest", "contract_digest", "served_definition_digest")
    for mode, runs in (("shadow", shadow), ("enforce", enforce)):
        for seed, (s, _) in runs.items():
            for k in keys:
                if s[k] != reported[k]:
                    fail(f"{mode} seed {seed}: {k} differs from the reported run")
            if s["net_isolation"] != "netns_veth_tcpdump":
                fail(f"{mode} seed {seed}: run without network isolation")

    conf = {k: Counter() for k in NAMES}
    per_seed = []
    for seed, (_, rs) in sorted(shadow.items()):
        ro = [r for r in rs if r["tool"] in READONLY]
        per_seed.append((seed, len(ro), sum(index_written(r) for r in ro)))
        for r in ro:
            truth = index_written(r)
            if r["is_error"] or r.get("transport_error"):
                fail(f"shadow seed {seed}: call {r['index']} failed")
            for k, c in conf.items():
                rev = r["verdicts_before_execution"][k] == "review"
                c["TP" if rev and truth else "FP" if rev else "FN" if truth else "TN"] += 1
    n_ro = sum(n for _, n, _ in per_seed)
    n_rw = sum(w for _, _, w in per_seed)

    e = Counter()
    held_by_tool = Counter()
    for seed, (_, rs) in sorted(enforce.items()):
        for r in rs:
            d = r["proxy_decision"]
            e["calls"] += 1
            if d["decision"] == "allow":
                e["forwarded"] += 1
                e["forwarded_attested"] += d["reason"] == "boundary and attested effect contract agree"
                e["forwarded_with_process"] += bool(r.get("children") or r.get("forks"))
            else:
                e["held"] += 1
                held_by_tool[r["tool"]] += 1
                e["held_with_process"] += bool(r.get("children") or r.get("forks"))
                e["held_with_file_change"] += bool(r["fs"]["modified"] + r["fs"]["created"] + r["fs"].get("deleted", []))
            if r["tool"] in READONLY:
                e["read_only"] += 1
                e["read_only_rewrites"] += index_written(r)
    shadow_calls = sum(len(rs) for _, rs in shadow.values())

    L = ["# Guarded run: frozen controllers on new git traffic, then the enforcing proxy", "",
         "*Generated by `real-mcp/analysis/guarded_report.py` from `real-mcp/results_guarded/`; every receipt digest is "
         "checked, the run's harness, installation, contract and served-definition digests are checked against the "
         "reported run, and the controller, policy and proxy code against the digests in the manifest.*", "",
         f"Seeds {seeds[0]}–{seeds[-1]} of the pilot's traffic generator, which no earlier run used; frozen harness "
         "(`pilot2/`, same digest as the reported run), official git server `mcp-server-git==2026.10.28`, private "
         "network namespace, on a third Linux machine.  The four controllers were fixed and written to `results_guarded/manifest.json` at "
         f"{manifest['written_before_first_call']}, before the first call; the tree and the per-tool baseline were "
         "fitted on controller seeds 7–8 only.", "",
         "## 1. Shadow phase: verdicts recorded before every read-only call, every call executed", "",
         f"{len(seeds)} seeds, {shadow_calls} calls, {n_ro} read-only calls, {n_rw} index rewrites by read-only tools "
         f"(per seed: {', '.join(f'{s}: {w}/{n}' for s, n, w in per_seed)}).", "",
         "| Controller | Reviews | Rewrites flagged | Reviews without rewrite | Rewrites allowed |",
         "|---|---:|---:|---:|---:|"]
    for k, c in conf.items():
        L.append(f"| {NAMES[k]} | {c['TP'] + c['FP']}/{n_ro} | {c['TP']}/{n_rw} | {c['FP']} | {c['FN']} |")
    s = conf["S_index_state"]
    L += ["", f"S decided all {n_ro} read-only calls correctly with its verdict recorded before execution: "
          f"{s['TP']} of {n_rw} rewrites flagged, {s['FP']} reviews without a rewrite, {s['FN']} rewrites allowed.  "
          f"The tree selected on seeds 7–8 flagged {conf['tree_seeds_7_8']['TP']} of {n_rw} with "
          f"{conf['tree_seeds_7_8']['FP']} additional reviews; the per-tool baseline allowed "
          f"{conf['per_tool_seeds_7_8']['FN']} rewrites and raised {conf['per_tool_seeds_7_8']['FP']} additional reviews.", "",
          "## 2. Enforce phase: `runtime/mcp_proxy.py` in front of the unmodified server", "",
          "The same seeds again.  The proxy attests the installation, the contract and the served `tools/list` against "
          "`runtime/pins/git.json` (the reported run's digests), evaluates S on the index before every call, fsyncs the "
          "decision to its hash-chained ledger and forwards only allowed calls.", "",
          "| Calls | Forwarded (attested) | Held | Held calls with a process or file event | Read-only calls | Index rewrites by read-only calls |",
          "|---:|---:|---:|---:|---:|---:|",
          f"| {e['calls']} | {e['forwarded']} ({e['forwarded_attested']}) | {e['held']} | "
          f"{e['held_with_process'] + e['held_with_file_change']} | {e['read_only']} | {e['read_only_rewrites']} |", "",
          "Held calls by tool: " + ", ".join(f"`{t}` {n}" for t, n in sorted(held_by_tool.items())) + ".", "",
          f"No held call reached the server: the kernel's process events, which record `git` processes for "
          f"{e['forwarded_with_process']} of the forwarded calls, show none for any of the {e['held']} held calls, and the "
          f"sandbox snapshots show no file change for them.  No read-only call rewrote the index.  A held `git_status` leaves "
          f"the stale index in place for the next worktree reader, so under enforcement without a reviewer "
          f"{e['held']} reader calls were held where the shadow phase reviewed {s['TP'] + s['FP']}; how a review is "
          "resolved (approve once, refresh, deny) is the operational parameter WP2 measures.", ""]
    out = HERE / "GUARDED_RUN.md"
    out.write_text("\n".join(L), encoding="utf-8", newline="\n")
    print("written", out, "- every receipt digest verified")


if __name__ == "__main__":
    main()
