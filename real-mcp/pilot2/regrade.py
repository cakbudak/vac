"""Re-grade recorded receipts with the current contracts and recompute the tallies.

Used after a logged contract correction (CONTRACT_CHANGES.md).  The receipts (what the server did)
and the learner's verdicts (recorded before execution) are left untouched; only the `grade` field
and the summary's tallies are recomputed.  The script refuses to re-grade a run whose *training*
labels would change, because the recorded verdicts were learned from those labels; such a run has
to be re-run instead.  Every re-graded summary records the contract digest at run time and now.

    .venv/bin/python pilot2/regrade.py results2 results2_agent
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from contracts import load as load_contract  # noqa: E402
from run_pilot import _tally  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def context_from(summary: dict) -> dict:
    sb = Path(summary["sandbox"]) if "sandbox" in summary else None
    if sb is None:   # agent summaries carry no sandbox path; derive it from the first receipt's paths later
        return {}
    return {"work": str(sb / "work"), "home": str(sb / "home"), "tmp": str(sb / "tmp"), "root": str(sb),
            "db": str(sb / "work" / "pilot.db"), "repo": str(sb / "work" / "repo"),
            "vault": str(sb / "work" / "notes"), "memory_file": str(sb / "work" / "memory.json")}


def context_from_receipts(rows: list[dict], server: str) -> dict:
    # the sandbox root is the longest common prefix of the paths the receipts mention, up to "/<server-sandbox>-<seed>/"
    import re
    for r in rows:
        for v in list(r["args"].values()) + r["fs"]["created"] + r["fs"]["modified"] + r["fs"]["deleted"]:
            if isinstance(v, str):
                m = re.search(r"^(.*/sandboxes(?:/agent-[^/]+)?/[^/]+-\d+)/", v)
                if m:
                    sb = Path(m.group(1))
                    return {"work": str(sb / "work"), "home": str(sb / "home"), "tmp": str(sb / "tmp"), "root": str(sb),
                            "db": str(sb / "work" / "pilot.db"), "repo": str(sb / "work" / "repo"),
                            "vault": str(sb / "work" / "notes"), "memory_file": str(sb / "work" / "memory.json")}
    return {}


def regrade_dir(d: Path) -> str:
    summary = json.loads((d / "summary.json").read_text())
    server = summary["server"]
    contract = load_contract(server)
    digest_now = hashlib.sha256(json.dumps(contract.raw, sort_keys=True).encode()).hexdigest()
    if summary.get("contract_digest") == digest_now:
        return "unchanged"
    files = {fn: [json.loads(l) for l in (d / fn).read_text().splitlines() if l.strip()]
             for fn in ("receipts_setup.jsonl", "receipts_train.jsonl", "receipts_heldout.jsonl", "receipts_agent.jsonl") if (d / fn).exists()}
    ctx = context_from(summary) or context_from_receipts(sum(files.values(), []), server)
    # training labels must not change
    for r in files.get("receipts_train.jsonl", []):
        g = contract.grade(r, ctx)
        if bool(g["is_deviation"]) != bool(r["grade"]["is_deviation"]):
            return f"REFUSED: training label of {r['tool']} #{r['index']} would change; re-run this directory"
    changed = 0
    for fn, rows in files.items():
        for r in rows:
            g = contract.grade(r, ctx)
            if g != r["grade"]:
                changed += 1
            r["grade"] = g
        with (d / fn).open("w") as f:
            for r in rows:
                f.write(json.dumps(r, sort_keys=True, default=str) + "\n")
    # recompute tallies for the evaluated set (held-out or agent)
    ev = files.get("receipts_agent.jsonl") if "receipts_agent.jsonl" in files else files.get("receipts_heldout.jsonl", [])
    learners = list((summary.get("heldout") or summary.get("agent"))["tallies"].keys())
    tallies = {n: _tally() for n in learners}
    per_tool: dict = {}
    for r in ev:
        g = r["grade"]; err = bool(r["is_error"] or r.get("transport_error"))
        pt = per_tool.setdefault(r["tool"], {"actions": 0, "deviations": 0, "errors": 0, "verdicts": {n: {"allow": 0, "review": 0, "block": 0} for n in learners}})
        pt["actions"] += 1; pt["errors"] += err; pt["deviations"] += g["is_deviation"]
        for n, v in r["verdicts_before_execution"].items():
            pt["verdicts"][n][v] += 1
            t = tallies[n]
            if err:
                t["errors"] += 1; continue
            key = ("dev" if g["is_deviation"] else "safe") + "_" + {"allow": "allowed", "review": "reviewed", "block": "blocked"}[v]
            t[key] += 1
    block = summary["agent"] if "agent" in summary else summary["heldout"]
    block["tallies"] = tallies
    for tool, pt in per_tool.items():
        block["per_tool"].setdefault(tool, {}).update(pt)
    if "train" in summary:
        tr = files.get("receipts_train.jsonl", [])
        summary["train"]["deviations"] = sum(r["grade"]["is_deviation"] for r in tr)
        summary["train"]["deviations_tools_list"] = sum(r["grade"]["is_deviation_tools_list"] for r in tr)
    if "deviation_kinds_total" in summary:
        kinds, kinds_tl = {}, {}
        for r in files.get("receipts_train.jsonl", []) + files.get("receipts_heldout.jsonl", []):
            for k in r["grade"].get("deviation_kinds", []):
                kinds[k] = kinds.get(k, 0) + 1
            for k in r["grade"].get("deviation_kinds_tools_list", []):
                kinds_tl[k] = kinds_tl.get(k, 0) + 1
        summary["deviation_kinds_total"], summary["deviation_kinds_total_tools_list"] = kinds, kinds_tl
    summary.setdefault("regraded", []).append({"contract_digest_at_run": summary.get("contract_digest"), "contract_digest_now": digest_now, "receipts_changed": changed})
    summary["contract_digest"] = digest_now
    (d / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n")
    return f"re-graded ({changed} receipts changed)"


def main():
    for name in sys.argv[1:] or ["results2", "results2_agent"]:
        base = ROOT / name
        for d in sorted(base.glob("**/summary.json")):
            print(d.parent.relative_to(ROOT), regrade_dir(d.parent))


if __name__ == "__main__":
    main()
