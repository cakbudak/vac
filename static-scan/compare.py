"""Static versus dynamic: for a fixed list of behaviours that one of the two methods established on
the thirteen servers, record whether each static scan (per model) mentions it and whether the
dynamic harness observed it.  The list is written by hand from the two sets of outputs; the
matching is by keywords in the scan JSON (any field of any finding) and by counts in results2.

    python3 static-scan/compare.py  -> static-scan/RESULTS_STATIC_VS_DYNAMIC.md
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "real-mcp"
SCANS = HERE / "scans"

# (server, behaviour, how the dynamic harness sees it (or not), keyword regex for the static scan, dynamic evidence function)
FINDINGS = [
    ("git", "read-only tools rewrite .git/index (git's stat-cache refresh)", "fs_change_by_readonly_tool on git_status / git_diff_unstaged",
     r"\.git/index|stat.?cache|refresh(es|ing)? the index|rewrit\w* .*index|index file", "dyn:git:fs_change_by_readonly_tool"),
    ("sqlite", "append_insight keeps the memo in process memory only", "no channel (declared effect unobservable)",
     r"in-memory|in memory|memory list|insights list|db\.insights", "unobservable"),
    ("sqlite", "append_insight sends a resource-updated notification", "no channel (protocol message, not state)",
     r"resource.?updated|notification", "unobservable"),
    ("memory", "mutating tools take a lock file and write via temp file + rename", "lock file created and removed within the call: invisible to before/after snapshots",
     r"\.lock|lock file|lockfile|temp(orary)? file|rename", "within_call"),
    ("fetch", "robots.txt of the target host is fetched before the URL", "DNS/HTTP attempts to the same host (inside the declared host)",
     r"robots", "dyn:fetch:network_same_host"),
    ("fetch", "the host is resolved before the request (private-address guard)", "a DNS query per call",
     r"private|loopback|link-local|resolv", "dyn:fetch:dns"),
    ("desktop_commander", "telemetry request on every tool call (primary host and a fallback host on Google Cloud Run)", "DNS attempts to both hosts during calls (67 undeclared_network at README level over 3 seeds)",
     r"telemetry", "dyn:desktop_commander:undeclared_network"),
    ("desktop_commander", "a child process on every call, `python3 --version` by name on 263 of 267 (219 of the calls by tools that declare no subprocess)", "216 undeclared_subprocess over 3 seeds",
     r"python3|python --version|--version|detectPython|python runtime|checks? for python", "dyn:desktop_commander:undeclared_subprocess"),
    ("desktop_commander", "Chrome-for-Testing download at start-up (Puppeteer)", "DNS to googlechromelabs.github.io at start-up (background)",
     r"chrome|puppeteer", "dyn:desktop_commander:background:googlechromelabs"),
    ("desktop_commander", "feature flags fetched at start-up", "DNS to desktopcommander.app at start-up (background)",
     r"feature.?flag", "dyn:desktop_commander:background:desktopcommander.app"),
    ("desktop_commander", "argument log and tool-history file written next to the configuration on every call", "fs_outside_scope at tools/list level on every call (README-declared)",
     r"tool-history|toolHistory|claude_tool_call|history file|jsonl", "dyn:desktop_commander:fs_outside_scope_tl"),
    ("desktop_commander", "config.json rewritten on every start_process (usage statistics)", "fs_undeclared (README level excused) on every start_process",
     r"usageStats|usage stats|usageTracker|config\.json", "dyn:desktop_commander:fs_undeclared_tl"),
    ("obsidian", "journal, lock and trash files under a hidden directory inside the vault", "fs_undeclared at tools/list level on every mutation (36 over 3 seeds); README-declared",
     r"obsidian-mcp|mcp-obsidian|journal|transaction|trash", "dyn:obsidian:fs_undeclared_tl"),
    ("obsidian", "move_note rewrites other notes that link to the moved one", "modified notes other than source/destination (declared in words)",
     r"backlink|every markdown file|reads every", "dyn:obsidian:move_backlinks"),
    ("msb_terminal_false_error", "every tool returns an injected instruction instead of acting", "declared_effect_absent on every call (108 over 3 seeds)",
     r"false_error|prompt.?injection|attack|instead of", "dyn:msb_terminal_false_error:declared_effect_absent"),
    ("msb_terminal_out_of_scope_parameter", "extra llm_model_name parameter harvested; effects otherwise identical", "no deviation in any channel",
     r"llm_model_name", "none_identical"),
    ("filesystem", "allowed directories replaced by client-supplied MCP roots after the handshake (2025-era clients)", "no channel (protocol-level; the pilot's client sends no roots)",
     r"roots|listRoots", "unobservable"),
]


def load_results(server):
    rows = []
    for seed in (1, 2, 3):
        d = ROOT / "results2" / server / f"seed-{seed}"
        if not d.exists():
            continue
        for fn in ("receipts_setup.jsonl", "receipts_train.jsonl", "receipts_heldout.jsonl"):
            p = d / fn
            if p.exists():
                rows += [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
        s = d / "summary.json"
        if s.exists():
            rows.append({"__summary__": json.loads(s.read_text())})
    return rows


def dynamic_evidence(key: str) -> str:
    if key in ("unobservable", "within_call", "none_identical"):
        return {"unobservable": "not observable", "within_call": "not observable (within one call)", "none_identical": "no deviation (as designed)"}[key]
    parts = key.split(":")
    server = parts[1]
    rows = load_results(server)
    receipts = [r for r in rows if "__summary__" not in r]
    summaries = [r["__summary__"] for r in rows if "__summary__" in r]
    what = parts[2]
    if what == "fs_change_by_readonly_tool":
        n = sum(1 for r in receipts if "fs_change_by_readonly_tool" in r["grade"]["deviation_kinds"])
        return f"observed: {n} calls over 3 seeds"
    if what == "undeclared_network":
        n = sum(1 for r in receipts if "undeclared_network" in r["grade"]["deviation_kinds"] or "network_outside_scope" in r["grade"]["deviation_kinds"])
        names = sorted({a.get("qname") for r in receipts for a in r.get("net_attempts", []) if a.get("qname")})
        return f"observed: {n} calls; names {', '.join(names)}"
    if what == "undeclared_subprocess":
        n = sum(1 for r in receipts if "undeclared_subprocess" in r["grade"]["deviation_kinds"])
        return f"observed: {n} of {len(receipts)} calls"
    if what == "background":
        name = parts[3]
        n = sum(1 for s in summaries for a in s.get("background_net", []) if name in (a.get("qname") or ""))
        return f"observed: {n} start-up attempts over 3 seeds" if n else "not observed"
    if what == "fs_outside_scope_tl":
        n = sum(1 for r in receipts if any(d[0] == "fs_outside_scope" for d in r["grade"].get("readme_excused", [])))
        return f"observed: {n} calls (README-declared)"
    if what == "fs_undeclared_tl":
        n = sum(1 for r in receipts if any(d[0] == "fs_undeclared" for d in r["grade"].get("readme_excused", []) + r["grade"]["deviations"]))
        return f"observed: {n} calls"
    if what == "declared_effect_absent":
        n = sum(1 for r in receipts if "declared_effect_absent" in r["grade"]["deviation_kinds"])
        return f"observed: {n} calls"
    if what == "network_same_host":
        n = sum(1 for r in receipts if r.get("net_attempts"))
        return f"observed: attempts in {n} calls, all to the URL's host"
    if what == "dns":
        n = sum(1 for r in receipts if any(a.get("kind") == "dns" for a in r.get("net_attempts", [])))
        return f"observed: DNS in {n} of {len(receipts)} calls"
    if what == "move_backlinks":
        n = 0
        for r in receipts:
            if r["tool"] == "obsidian_move_note":
                others = [p for p in r["fs"]["modified"] if p.endswith(".md") and r["args"].get("source", "") not in p and r["args"].get("destination", "") not in p]
                n += bool(others)
        return f"observed: other notes modified in {n} move calls"
    return "?"


def main():
    models = sorted(p.name for p in SCANS.iterdir() if p.is_dir() and any(p.glob("*.json")))
    L = ["# Static versus dynamic on the same thirteen servers", "",
         "*Generated by `static-scan/compare.py` from `static-scan/scans/<model>/<server>.json` and `real-mcp/results2/`.*", "",
         "A language model read each server's implementation together with its tools/list (the method of the static",
         "description/implementation scanners) and listed undocumented behaviours.  The dynamic harness observed the",
         "same servers.  Each row is a behaviour one of the two established; `found` for a scan means the scan's",
         "findings mention it (keyword match, checked by hand), `observed` for the harness means a receipt shows it.", "",
         "The list of behaviours was written by hand from both methods' outputs and the matching is by keyword, so the",
         "totals below illustrate that the two methods are complements; they do not measure either method's recall.", "",
         "| Server | Behaviour | " + " | ".join(f"static: {m}" for m in models) + " | dynamic harness |",
         "|---|---|" + "---|" * len(models) + "---|"]
    totals = {m: [0, 0] for m in models}
    dyn_total = [0, 0]
    for server, behaviour, dyn_desc, pattern, key in FINDINGS:
        cells = []
        for m in models:
            p = SCANS / m / f"{server}.json"
            if not p.exists():
                cells.append("no scan"); continue
            text = json.dumps(json.loads(p.read_text()))
            hit = re.search(pattern, text, re.I) is not None
            totals[m][1] += 1; totals[m][0] += int(hit)
            cells.append("found" if hit else "not found")
        dyn = dynamic_evidence(key)
        if not dyn.startswith("not observable") and not dyn.startswith("no deviation"):
            dyn_total[1] += 1; dyn_total[0] += int(dyn.startswith("observed"))
        L.append(f"| {server} | {behaviour} | " + " | ".join(cells) + f" | {dyn} — {dyn_desc} |")
    L += ["", "Totals (rows where the method could apply): " + "; ".join(f"{m}: {t[0]}/{t[1]}" for m, t in totals.items()) + f"; dynamic harness: {dyn_total[0]}/{dyn_total[1]}", ""]
    manifest = json.loads((SCANS / "manifest.json").read_text()) if (SCANS / "manifest.json").exists() else {"prompts": {}}
    dc_files = len(manifest["prompts"].get("desktop_commander", {}).get("files", []))
    L += ["## What each method misses", "",
          "- No static scan saw git's index rewrite: it happens inside the git binary that GitPython calls, and the",
          "  scanned code only shows `repo.git.status()` / `repo.git.diff()`.  The dynamic harness had it on the first probe.",
          f"- Desktop Commander's `python3 --version` spawn: the claude scan found the mechanism (`detectPythonInfo` in",
          f"  `system-info.js`, among the {dc_files} files given) but placed it at start-up; the harness shows a child process on",
          "  every call.  The other scans did not mention it.  Static analysis names a cause; only execution shows when it fires.",
          "- The dynamic harness cannot see effects that stay in process memory (sqlite's memo, the toggles), effects that",
          "  are undone within one call (memory's lock file), protocol messages (resource-updated notifications), or",
          "  behaviour reachable only through client features the probe client does not use (filesystem's MCP roots);",
          "  the static scans list them from the code.",
          "- Neither method sees an effect the server has not been made to execute and whose code it does not ship",
          "  (a remote service behind the server); both see the MSB attack variants, and neither can grade the",
          "  parameter-harvesting variant from behaviour alone."]
    (HERE / "RESULTS_STATIC_VS_DYNAMIC.md").write_text("\n".join(L) + "\n")
    print("written", HERE / "RESULTS_STATIC_VS_DYNAMIC.md", models)


if __name__ == "__main__":
    main()
