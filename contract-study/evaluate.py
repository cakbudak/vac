"""Evaluate the language-model-drafted contracts against the human contracts and against the
recorded behaviour of the servers.

For every (model, server) draft that parsed:
  * coverage: which tools of tools/list the draft covers;
  * flag agreement per tool with the human contract and with the MCP annotations
    (read_only, subprocess, network, doc_sufficient);
  * behavioural agreement: the reported run's receipts (seed 1, set-up + training + held-out) are
    re-graded with the draft, and the draft's verdict per receipt (deviation / no deviation at
    README level) is compared with the human contract's verdict; false alarms (draft flags, human
    does not) and misses (human flags, draft does not) are counted, with the deviation kinds;
  * known findings: whether the draft flags the receipts behind the package's
    findings (git's index rewrite by read-only tools, MSB's declared-effect-absent variants,
    Desktop Commander's undeclared subprocess and telemetry hosts).

    python3 contract-study/evaluate.py   -> contract-study/summary.json, contract-study/RESULTS_CONTRACTS.md
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "real-mcp"
sys.path.insert(0, str(ROOT / "pilot2"))
from contracts import Contract  # noqa: E402

DRAFTS = HERE / "drafts"
RESULTS = ROOT / "results2"
SERVERS = ["filesystem", "git", "sqlite", "memory", "everything", "fetch", "time", "msb_terminal_normal",
           "msb_terminal_tool_transfer", "msb_terminal_out_of_scope_parameter", "msb_terminal_false_error",
           "desktop_commander", "obsidian"]
KNOWN = {   # server -> (tool, deviation kind) pairs that the human contract flags and that are real findings
    "git": [("git_status", "fs_change_by_readonly_tool"), ("git_diff_unstaged", "fs_change_by_readonly_tool")],
    "msb_terminal_false_error": [("execute_command", "declared_effect_absent")],
    "msb_terminal_tool_transfer": [("execute_the_command", "declared_effect_absent")],
    "desktop_commander": [("write_file", "undeclared_subprocess"), ("read_file", "undeclared_subprocess"), ("write_file", "undeclared_network")],
}


class DraftContract(Contract):
    def __init__(self, raw: dict, server: str):
        self.raw = raw
        self.server = raw.get("server", server)
        self.scope_roots = (raw.get("scope") or {}).get("roots") or []
        self.defaults = raw.get("defaults") or {}
        self.tools = raw.get("tools") or {}
        self.aliases = raw.get("tool_aliases") or {}
        self.readme = raw.get("readme_declared") or {}


def human_contract(server: str) -> Contract:
    name = "msb_terminal" if server.startswith("msb_terminal") else server
    return Contract(ROOT / "contracts" / f"{name}.yaml")


def context_for(summary: dict) -> dict:
    sb = Path(summary["sandbox"])
    return {"work": str(sb / "work"), "home": str(sb / "home"), "tmp": str(sb / "tmp"), "root": str(sb),
            "db": str(sb / "work" / "pilot.db"), "repo": str(sb / "work" / "repo"),
            "vault": str(sb / "work" / "notes"), "memory_file": str(sb / "work" / "memory.json")}


def receipts(server: str, seed: int = 1) -> tuple[list[dict], dict]:
    d = RESULTS / server / f"seed-{seed}"
    rows = []
    for fname in ("receipts_setup.jsonl", "receipts_train.jsonl", "receipts_heldout.jsonl"):
        p = d / fname
        if p.exists():
            rows += [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    return rows, json.loads((d / "summary.json").read_text())


def tool_flags(c: Contract, tool: str) -> dict | None:
    spec = c.tool_spec(tool)
    if spec is None:
        return None
    return {"read_only": bool(spec.get("read_only", False)),
            "subprocess": bool(spec.get("subprocess", c.defaults.get("subprocess", False))),
            "network": bool(spec.get("network", c.defaults.get("network", False))),
            "doc_sufficient": bool(spec.get("doc_sufficient", True))}


def evaluate_one(model: str, server: str, raw: dict) -> dict:
    draft = DraftContract(raw, server)
    human = human_contract(server)
    tools_json = json.loads((ROOT / "contracts" / f"{server}.tools.json").read_text())
    names = [t["name"] for t in tools_json]
    ann = {t["name"]: (t.get("annotations") or {}) for t in tools_json}
    covered = [n for n in names if draft.tool_spec(n) is not None]
    agree = Counter(); compared = Counter(); ann_agree = Counter(); ann_compared = Counter()
    doc_insufficient_draft = [n for n in covered if not draft.tool_spec(n).get("doc_sufficient", True)]
    doc_insufficient_human = [n for n in names if human.tool_spec(n) and not human.tool_spec(n).get("doc_sufficient", True)]
    for n in covered:
        df, hf = tool_flags(draft, n), tool_flags(human, n)
        if hf is None:
            continue
        for k in ("read_only", "subprocess", "network", "doc_sufficient"):
            compared[k] += 1
            agree[k] += int(df[k] == hf[k])
        roh = ann[n].get("read_only_hint")
        if roh is not None:
            ann_compared["read_only"] += 1
            ann_agree["read_only"] += int(df["read_only"] == bool(roh))
    rows, summary = receipts(server)
    ctx = context_for(summary)
    conf = Counter(); kinds_false = Counter(); kinds_missed = Counter(); unknown_tool_calls = 0
    per_tool_false = Counter()
    known_hits = {}
    for r in rows:
        if r.get("transport_error"):
            continue
        gh = human.grade(r, ctx)
        gd = draft.grade(r, ctx)
        if not gd["known_tool"]:
            unknown_tool_calls += 1
        h, d = bool(gh["is_deviation"]), bool(gd["is_deviation"])
        conf[("human_dev" if h else "human_ok", "draft_dev" if d else "draft_ok")] += 1
        if d and not h:
            for k in gd["deviation_kinds"]:
                kinds_false[k] += 1
            per_tool_false[r["tool"]] += 1
        if h and not d:
            for k in gh["deviation_kinds"]:
                kinds_missed[k] += 1
        for tool, kind in KNOWN.get(server, []):
            if r["tool"] == tool and kind in gh["deviation_kinds"]:
                known_hits.setdefault(f"{tool}:{kind}", [0, 0])
                known_hits[f"{tool}:{kind}"][1] += 1
                known_hits[f"{tool}:{kind}"][0] += int(kind in gd["deviation_kinds"] or d)
    n = sum(conf.values())
    tp = conf[("human_dev", "draft_dev")]; fn = conf[("human_dev", "draft_ok")]
    fp = conf[("human_ok", "draft_dev")]; tn = conf[("human_ok", "draft_ok")]
    return {"model": model, "server": server, "tools": len(names), "covered": len(covered),
            "scope_roots": draft.scope_roots, "has_readme_declared": bool(draft.readme),
            "flag_agreement": {k: f"{agree[k]}/{compared[k]}" for k in compared},
            "flag_agreement_rate": {k: round(agree[k] / compared[k], 3) for k in compared if compared[k]},
            "read_only_vs_annotation": (f"{ann_agree['read_only']}/{ann_compared['read_only']}" if ann_compared["read_only"] else None),
            "doc_insufficient_draft": doc_insufficient_draft, "doc_insufficient_human": doc_insufficient_human,
            "receipts": n, "agreement_rate": round((tp + tn) / n, 3) if n else None,
            "confusion": {"both_deviation": tp, "draft_misses": fn, "draft_false_alarms": fp, "both_ok": tn},
            "false_alarm_kinds": dict(kinds_false), "missed_kinds": dict(kinds_missed),
            "false_alarm_tools": dict(per_tool_false.most_common(6)), "unknown_tool_calls": unknown_tool_calls,
            "known_findings": {k: f"{v[0]}/{v[1]}" for k, v in known_hits.items()}}


def main():
    log = [json.loads(l) for l in (DRAFTS / "log.jsonl").read_text().splitlines() if l.strip()] if (DRAFTS / "log.jsonl").exists() else []
    cost = defaultdict(lambda: {"calls": 0, "parsed": 0, "errors": 0, "tokens": 0, "seconds": 0.0})
    for e in log:
        c = cost[e["model"]]
        c["calls"] += 1; c["parsed"] += int(bool(e.get("parsed"))); c["errors"] += int("error" in e)
        c["tokens"] += (e.get("usage") or {}).get("total_tokens", 0) or 0; c["seconds"] += e.get("seconds", 0) or 0
    results = []
    models = sorted(p.name for p in DRAFTS.iterdir() if p.is_dir() and p.name != "old" and any(p.glob("*.yaml")))
    for m in models:
        for s in SERVERS:
            p = DRAFTS / m / f"{s}.run1.yaml"
            if not p.exists():
                continue
            raw = yaml.safe_load(p.read_text())
            try:
                results.append(evaluate_one(m, s, raw))
            except Exception as exc:
                results.append({"model": m, "server": s, "error": f"{type(exc).__name__}: {exc}"})
    out = {"models": models, "cost": dict(cost), "results": results}
    (HERE / "summary.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    # ---- report ----
    L = ["# Who writes the contract? Language models as contract authors", "",
         "*Generated by `contract-study/evaluate.py` from `contract-study/drafts/` and `real-mcp/results2/` (seed 1).*", "",
         "Each model received the pilot's contract format, the server's `tools/list` verbatim and the package README",
         "excerpt -- the same material the human contracts were written from -- and nothing else (no probe, no receipt,",
         "no human contract).  Its contract is then applied to the recorded receipts of the same server and compared",
         "with the human contract's grading.  Temperature 0, one draft per (model, server).", "",
         "## 1. Drafts, parse rate, cost", "", "| Model | Calls | Parsed | Errors | Total tokens | Seconds |", "|---|---:|---:|---:|---:|---:|"]
    for m, c in sorted(cost.items()):
        L.append(f"| {m} | {c['calls']} | {c['parsed']} | {c['errors']} | {c['tokens']:,} | {c['seconds']:.0f} |")
    L += ["", "## 2. Agreement with the human contract and with the server's recorded behaviour", "",
          "`flags` = per-tool agreement on read_only / subprocess / network / doc_sufficient with the human contract;",
          "`behaviour` = per-receipt agreement on whether a recorded call deviates (README level); `false alarms` = the",
          "draft flags a call the human contract accepts; `misses` = the reverse.", "",
          "| Model | Server | Tools covered | read_only agree | subprocess | network | doc_suff. | Draft says doc insufficient | Behaviour agree | False alarms | Misses | Known findings caught |",
          "|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---|"]
    for r in results:
        if "error" in r:
            L.append(f"| {r['model']} | {r['server']} | error: {r['error'][:60]} | | | | | | | | | |")
            continue
        fa = r["flag_agreement"]
        L.append(f"| {r['model']} | {r['server']} | {r['covered']}/{r['tools']} | {fa.get('read_only','')} | {fa.get('subprocess','')} | {fa.get('network','')} | {fa.get('doc_sufficient','')} | "
                 f"{', '.join(r['doc_insufficient_draft']) or '—'} | {r['agreement_rate']} | {r['confusion']['draft_false_alarms']} | {r['confusion']['draft_misses']} | "
                 f"{', '.join(f'{k} {v}' for k, v in r['known_findings'].items()) or '—'} |")
    L += ["", "## 3. Per model, pooled over servers", "", "| Model | Servers | Tools covered | read_only agreement | Behaviour agreement | False alarms | Misses | Most common false-alarm kinds |", "|---|---:|---:|---:|---:|---:|---:|---|"]
    for m in models:
        rs = [r for r in results if r["model"] == m and "error" not in r]
        if not rs:
            continue
        cov = sum(r["covered"] for r in rs); tot = sum(r["tools"] for r in rs)
        ro_a = sum(int(r["flag_agreement"].get("read_only", "0/0").split("/")[0]) for r in rs)
        ro_c = sum(int(r["flag_agreement"].get("read_only", "0/0").split("/")[1]) for r in rs)
        n = sum(r["receipts"] for r in rs)
        ok = sum(r["confusion"]["both_deviation"] + r["confusion"]["both_ok"] for r in rs)
        fa = sum(r["confusion"]["draft_false_alarms"] for r in rs); mi = sum(r["confusion"]["draft_misses"] for r in rs)
        kinds = Counter()
        for r in rs:
            kinds.update(r["false_alarm_kinds"])
        L.append(f"| {m} | {len(rs)} | {cov}/{tot} | {ro_a}/{ro_c} | {ok}/{n} ({100*ok/max(1,n):.0f} %) | {fa} | {mi} | {', '.join(f'{k} ×{v}' for k, v in kinds.most_common(3)) or '—'} |")
    L += ["", "## 4. Documentation sufficiency as judged by the drafts", "", "| Server | Human: insufficient for | Models saying insufficient (tool: n of models) |", "|---|---|---|"]
    for s in SERVERS:
        rs = [r for r in results if r["server"] == s and "error" not in r]
        if not rs:
            continue
        cnt = Counter()
        for r in rs:
            cnt.update(r["doc_insufficient_draft"])
        L.append(f"| {s} | {', '.join(rs[0]['doc_insufficient_human']) or '—'} | {', '.join(f'{t}: {n}/{len(rs)}' for t, n in cnt.most_common()) or '—'} |")
    (HERE / "RESULTS_CONTRACTS.md").write_text("\n".join(L) + "\n")
    print("written", HERE / "RESULTS_CONTRACTS.md", "models:", models, "results:", len(results))


if __name__ == "__main__":
    main()
