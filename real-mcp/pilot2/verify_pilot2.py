"""Verify the second slice from its receipts.

`PILOT2_RESULTS.md` is generated from `summary.json` files, and those were written by the harness
that also wrote the receipts.  This script closes that loop without trusting the summaries: it
re-reads every receipt under `results2/` and `results2_agent/`, checks each receipt's own digest
(computed by the harness before grading and verdicts were attached), recomputes every aggregate
that the report prints -- training deviations, held-out and agent tallies per learner, per-tool
rows, deviation-kind totals, channel observations, the new-token rate -- and compares them with
the summaries.  With `--report` it also regenerates `PILOT2_RESULTS.md` into a temporary file and
diffs it against the committed one.  Exit status 0 means every check passed.

    python3 pilot2/verify_pilot2.py            # summaries against receipts
    python3 pilot2/verify_pilot2.py --report   # plus report against summaries

It needs nothing but the standard library.  It does not re-grade receipts against the contracts
(`pilot2/regrade.py` does that, with the contract files); it checks that the numbers quoted in the
report are the numbers in the receipts.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results2"
AGENT = ROOT / "results2_agent"
ATTACHED_AFTER_DIGEST = ("grade", "verdicts_before_execution", "phase", "task_id", "step")

failures: list[str] = []
checked = Counter()


def fail(msg: str) -> None:
    failures.append(msg)


def read_jsonl(p: Path) -> list[dict]:
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def check_digest(r: dict, where: str) -> None:
    body = {k: v for k, v in r.items() if k != "digest" and k not in ATTACHED_AFTER_DIGEST}
    h = hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()
    checked["receipt digests"] += 1
    if h != r.get("digest"):
        fail(f"{where}: receipt {r.get('index')} digest mismatch")


def is_err(r: dict) -> bool:
    return bool(r["is_error"] or r.get("transport_error"))


def tally(receipts: list[dict], learners: list[str], label) -> dict:
    t = {n: {"safe_allowed": 0, "safe_reviewed": 0, "safe_blocked": 0,
             "dev_allowed": 0, "dev_reviewed": 0, "dev_blocked": 0, "errors": 0} for n in learners}
    for r in receipts:
        for n in learners:
            v = r["verdicts_before_execution"][n]
            if is_err(r):
                t[n]["errors"] += 1
                continue
            key = ("dev" if label(r) else "safe") + "_" + {"allow": "allowed", "review": "reviewed", "block": "blocked"}[v]
            t[n][key] += 1
    return t


def compare(where: str, what: str, got, want) -> None:
    checked[what] += 1
    if got != want:
        fail(f"{where}: {what} recomputed {json.dumps(got, sort_keys=True)} != summary {json.dumps(want, sort_keys=True)}")


def verify_scripted(seed_dir: Path) -> None:
    where = str(seed_dir.relative_to(ROOT))
    s = json.loads((seed_dir / "summary.json").read_text())
    level = s.get("label_level", "readme")

    def label(r):
        return bool(r["grade"]["is_deviation_tools_list"] if level == "tools_list" else r["grade"]["is_deviation"])

    setup = read_jsonl(seed_dir / "receipts_setup.jsonl")
    train = read_jsonl(seed_dir / "receipts_train.jsonl")
    held = read_jsonl(seed_dir / "receipts_heldout.jsonl")
    for r in setup + train + held:
        check_digest(r, where)
    learners = s["learners"]

    compare(where, "train.probes", len(train), s["train"]["probes"])
    compare(where, "train.errors", sum(is_err(r) for r in train), s["train"]["errors"])
    compare(where, "train.deviations", sum(r["grade"]["is_deviation"] for r in train), s["train"]["deviations"])
    compare(where, "train.deviations_tools_list", sum(r["grade"]["is_deviation_tools_list"] for r in train),
            s["train"]["deviations_tools_list"])
    compare(where, "heldout.actions", len(held), s["heldout"]["actions"])
    compare(where, "heldout.tallies", tally(held, learners, label), s["heldout"]["tallies"])

    # per-tool training rows
    per_tool: dict[str, dict] = {}
    for r in train:
        g = r["grade"]
        row = per_tool.setdefault(r["tool"], {"probes": 0, "errors": 0, "deviations": 0, "deviations_tools_list": 0,
                                               "first_deviation_probe": None, "deviation_kinds": {},
                                               "deviation_kinds_tools_list": {}, "flags": {}, "doc_sufficient": None})
        row["probes"] += 1
        row["doc_sufficient"] = g.get("doc_sufficient")
        for f in g.get("flags", []):
            row["flags"][f] = row["flags"].get(f, 0) + 1
        row["errors"] += int(is_err(r))
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
    compare(where, "per_tool_train", per_tool, s["per_tool_train"])

    # per-tool held-out rows
    held_tool: dict[str, dict] = {}
    for r in held:
        g = r["grade"]
        ht = held_tool.setdefault(r["tool"], {"actions": 0, "deviations": 0, "deviations_tools_list": 0, "errors": 0,
                                              "verdicts": {n: {"allow": 0, "review": 0, "block": 0} for n in learners}})
        ht["actions"] += 1
        ht["errors"] += int(is_err(r))
        ht["deviations"] += g["is_deviation"]
        ht["deviations_tools_list"] += g["is_deviation_tools_list"]
        for n, v in r["verdicts_before_execution"].items():
            ht["verdicts"][n][v] += 1
    compare(where, "heldout.per_tool", held_tool, s["heldout"]["per_tool"])

    # deviation-kind totals over train + held-out
    kinds, kinds_tl = {}, {}
    for r in train + held:
        for k in r["grade"].get("deviation_kinds", []):
            kinds[k] = kinds.get(k, 0) + 1
        for k in r["grade"].get("deviation_kinds_tools_list", []):
            kinds_tl[k] = kinds_tl.get(k, 0) + 1
    compare(where, "deviation_kinds_total", kinds, s["deviation_kinds_total"])
    compare(where, "deviation_kinds_total_tools_list", kinds_tl, s["deviation_kinds_total_tools_list"])

    # set-up calls
    compare(where, "setup", {"calls": len(setup), "deviations": sum(r["grade"]["is_deviation"] for r in setup),
                             "deviations_tools_list": sum(r["grade"]["is_deviation_tools_list"] for r in setup),
                             "kinds_tools_list": sorted({k for r in setup for k in r["grade"]["deviation_kinds_tools_list"]})},
            s["setup"])

    # channel observations (background_net is only in the summary; its count is checked for consistency)
    all_r = setup + train + held
    co = {
        "proxy_requests": sum(len(r["proxy_requests"]) for r in all_r),
        "remote_sockets": sum(len(r["remote_sockets"]) for r in all_r),
        "net_attempts": sum(len(r.get("net_attempts", [])) for r in all_r),
        "net_names": sorted({a.get("qname") for r in all_r for a in r.get("net_attempts", []) if a.get("qname")}),
        "background_net_attempts": len(s["background_net"]),
        "background_net_names": sorted({a.get("qname") or a.get("host") or a.get("dst") for a in s["background_net"] if a}),
        "calls_with_children": sum(bool(r["children"]) for r in all_r),
        "calls_with_fs_change": sum(bool(r["fs"]["created"] or r["fs"]["deleted"] or r["fs"]["modified"]) for r in all_r),
        "mean_sampler_samples_per_call": round(sum(r["sampler_samples"] for r in all_r) / max(1, len(all_r)), 1),
    }
    compare(where, "channel_observations", co, s["channel_observations"])


def verify_agent(seed_dir: Path) -> None:
    where = str(seed_dir.relative_to(ROOT))
    s = json.loads((seed_dir / "summary.json").read_text())
    train = read_jsonl(seed_dir / "receipts_train.jsonl")
    agent = read_jsonl(seed_dir / "receipts_agent.jsonl")
    for r in train + agent:
        check_digest(r, where)
    learners = list(s["agent"]["tallies"].keys())
    compare(where, "train.probes", len(train), s["train"]["probes"])
    compare(where, "train.deviations", sum(r["grade"]["is_deviation"] for r in train), s["train"]["deviations"])
    compare(where, "agent.calls", len(agent), s["agent"]["calls"])
    compare(where, "agent.tallies", tally(agent, learners, lambda r: bool(r["grade"]["is_deviation"])), s["agent"]["tallies"])
    per_tool: dict[str, dict] = {}
    for r in agent:
        g = r["grade"]
        pt = per_tool.setdefault(r["tool"], {"actions": 0, "deviations": 0, "errors": 0, "unknown_tool": 0,
                                             "verdicts": {n: {"allow": 0, "review": 0, "block": 0} for n in learners}})
        pt["actions"] += 1
        pt["errors"] += int(is_err(r))
        pt["deviations"] += g["is_deviation"]
        pt["unknown_tool"] += int(not g["known_tool"])
        for n, v in r["verdicts_before_execution"].items():
            pt["verdicts"][n][v] += 1
    compare(where, "agent.per_tool", per_tool, s["agent"]["per_tool"])
    compare(where, "agent.tool_errors", sum(bool(r["is_error"]) for r in agent), s["agent"]["tool_errors"])
    compare(where, "agent.unknown_tool_calls", sum(int(not r["grade"]["known_tool"]) for r in agent),
            s["agent"]["unknown_tool_calls"])
    # new-token rate: share of agent calls with a token in a string argument that no training call had
    train_tokens = {tok for r in train for v in r["args"].values() if isinstance(v, str) for tok in re.findall(r"[A-Za-z0-9]+", v)}
    new = sum(int(bool({tok for v in r["args"].values() if isinstance(v, str) for tok in re.findall(r"[A-Za-z0-9]+", v)} - train_tokens))
              for r in agent)
    compare(where, "agent.new_tokens_rate", round(new / max(1, len(agent)), 3), s["agent"]["new_tokens_rate"])


def headline(all_scripted: list[Path]) -> None:
    """The totals the proposal quotes, recomputed from receipts and printed for the reader."""
    calls = 0
    per_seed_calls = Counter()
    dc_calls = dc_python = dc_python_undeclared_tools = dc_undeclared_subprocess = dc_undeclared_subprocess_graded = 0
    dc_children = dc_telemetry = dc_fallback = dc_net_graded = 0
    identical = 0
    servers = sorted({p.parent.name for p in all_scripted})
    for srv in servers:
        tallies = []
        for p in sorted(all_scripted):
            if p.parent.name != srv:
                continue
            setup, train, held = (read_jsonl(p / f) for f in ("receipts_setup.jsonl", "receipts_train.jsonl", "receipts_heldout.jsonl"))
            n = len(setup) + len(train) + len(held)
            calls += n
            per_seed_calls[p.name] += n
            s = json.loads((p / "summary.json").read_text())
            tallies.append(json.dumps([s["train"]["deviations"], s["heldout"]["tallies"]], sort_keys=True))
            if srv == "desktop_commander":
                for r in setup + train + held:
                    dc_calls += 1
                    py = any("python3" in c for c in r["children"])
                    dc_python += int(py)
                    dc_children += int(bool(r["children"]))
                    names = [a.get("qname") or "" for a in r.get("net_attempts", [])]
                    dc_telemetry += int(any("telemetry" in q for q in names))
                    dc_fallback += int(any("dc-telemetry-proxy" in q for q in names))
                    kinds = r["grade"]["deviation_kinds"]
                    dc_net_graded += int("undeclared_network" in kinds or "network_outside_scope" in kinds)
                    if "undeclared_subprocess" in r["grade"]["deviation_kinds"]:
                        dc_undeclared_subprocess += 1
                        if r in train or r in held:
                            dc_undeclared_subprocess_graded += 1
                    if py and r["tool"] not in ("start_process", "start_search", "interact_with_process"):
                        dc_python_undeclared_tools += 1
        if len(set(tallies)) == 1 and len(tallies) > 1:
            identical += 1
    print(f"graded calls over all seeds: {calls} ({dict(sorted(per_seed_calls.items()))})")
    print(f"servers whose training deviations and held-out tallies are identical in every seed: {identical} of {len(servers)}")
    print(f"desktop_commander: {dc_calls} calls (set-up, training and held-out, 3 seeds); a child process in {dc_children}, "
          f"python3 named in {dc_python}; {dc_python_undeclared_tools} of those by tools that declare no subprocess; receipts graded "
          f"undeclared_subprocess: {dc_undeclared_subprocess} including the 3 set-up calls, {dc_undeclared_subprocess_graded} in the "
          f"training and held-out totals of the report")
    print(f"desktop_commander telemetry: DNS to a telemetry host during {dc_telemetry} calls, to the fallback host "
          f"(dc-telemetry-proxy-*.run.app) during {dc_fallback} of them; {dc_net_graded} calls graded undeclared_network or "
          f"network_outside_scope at README level")
    other = RESULTS.parent / "results2_second_machine"
    if other.exists():
        same = []
        for srv in servers:
            a = [json.loads((RESULTS / srv / f"seed-{s}" / "summary.json").read_text()) for s in (1, 2, 3)]
            b = [json.loads((other / srv / f"seed-{s}" / "summary.json").read_text()) for s in (1, 2, 3)
                 if (other / srv / f"seed-{s}" / "summary.json").exists()]
            if len(b) == 3 and all(x["train"]["deviations"] == y["train"]["deviations"] and x["heldout"]["tallies"] == y["heldout"]["tallies"]
                                   and x["deviation_kinds_total"] == y["deviation_kinds_total"] for x, y in zip(a, b)):
                same.append(srv)
        print(f"second machine ({other.name}): {len(same)} of {len(servers)} servers identical in training deviations, held-out "
              f"tallies and deviation kinds; differing: {sorted(set(servers) - set(same))}")


def main(argv: list[str]) -> int:
    scripted = sorted(p.parent for p in RESULTS.glob("*/seed-*/summary.json"))
    agent = sorted(p.parent for p in AGENT.glob("*/*/seed-*/summary.json"))
    if not scripted:
        print("no results under", RESULTS)
        return 2
    for d in scripted:
        verify_scripted(d)
    for d in agent:
        verify_agent(d)
    headline(scripted)
    if "--report" in argv:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "PILOT2_RESULTS.md"
            subprocess.run([sys.executable, str(ROOT / "pilot2" / "report.py"), str(out)], check=True, capture_output=True)
            checked["report regeneration"] += 1
            if out.read_text() != (ROOT / "PILOT2_RESULTS.md").read_text():
                fail("PILOT2_RESULTS.md differs from a fresh regeneration from the summaries")
    print(f"checked {len(scripted)} scripted runs and {len(agent)} agent runs; "
          + ", ".join(f"{v} {k}" for k, v in sorted(checked.items())))
    if failures:
        print(f"FAILED: {len(failures)} mismatch(es)")
        for f in failures:
            print("  -", f)
        return 1
    print("OK: every summary agrees with its receipts")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
