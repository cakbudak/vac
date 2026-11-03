"""Static description/implementation scan by a language model (the MCPDiFF / Cisco-scanner style),
run on the same servers the dynamic harness probed, so that the two methods can be compared on
identical targets.

For each server the model receives tools/list verbatim and the installed implementation (source
files, largest first, under a character budget) and is asked to list, per tool and for start-up,
every behaviour the implementation performs that the tool description does not state -- file
writes, child processes, network, hidden state -- with evidence and a judgement of whether the
behaviour would be observable from outside the process.  Output is JSON.

    python3 static-scan/static_scan.py --models claude-sonnet-4-6,kimi-k2-6 [--servers ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "real-mcp"
SERVERS_DIR = ROOT / "servers"
OUT = HERE / "scans"
E = os.environ
MODELS = {
    "claude-sonnet-4-6": (E.get("XKIRO_BASE_URL"), E.get("XKIRO_API_KEY"), "anthropic/claude-sonnet-4.6"),
    "kimi-k2-6": (E.get("INTERN_BASE_URL"), E.get("INTERN_API_KEY"), "kimi-k2.6"),
    "k2-horizon-375b": (E.get("IFM_BASE_URL"), E.get("IFM_API_KEY"), "IFM/K2-Horizon-375B-A23B"),
    "gpt-oss-120b": (E.get("GROQ_BASE_URL"), E.get("GROQ_API_KEY"), "openai/gpt-oss-120b"),
    "deepseek-v4-1-flash": (E.get("DIALAGRAM_ENDPOINT"), E.get("DIALAGRAM_API_KEY"), "deepseek-v4.1-flash"),
}
NM = SERVERS_DIR / "node_modules"
PY = SERVERS_DIR / "pyenv" / "lib" / "python3.13" / "site-packages"
PYS = SERVERS_DIR / "pyenv-sqlite" / "lib" / "python3.13" / "site-packages"
MSB = SERVERS_DIR / "msb" / "data" / "tools" / "attack_tools" / "it_development_management" / "Terminal_Controller"
DC = NM / "@wonderwhy-er" / "desktop-commander" / "dist"
SOURCES = {   # server -> list of files or directories (globs) in priority order
    "filesystem": [NM / "@modelcontextprotocol/server-filesystem/dist"],
    "git": [PY / "mcp_server_git"],
    "sqlite": [PYS / "mcp_server_sqlite"],
    "memory": [NM / "@modelcontextprotocol/server-memory/dist"],
    "everything": [NM / "@modelcontextprotocol/server-everything/dist/tools", NM / "@modelcontextprotocol/server-everything/dist/server",
                   NM / "@modelcontextprotocol/server-everything/dist/index.js", NM / "@modelcontextprotocol/server-everything/dist/transports/stdio.js"],
    "fetch": [PY / "mcp_server_fetch"],
    "time": [PY / "mcp_server_time"],
    "msb_terminal_normal": [MSB / "terminal_controller.py"],
    "msb_terminal_tool_transfer": [MSB / "terminal_controller-tool_transfer.py", SERVERS_DIR / "msb/data/prompt_template.py", SERVERS_DIR / "msb/data/attack_task.jsonl"],
    "msb_terminal_out_of_scope_parameter": [MSB / "terminal_controller-out_of_scope_parameter.py", SERVERS_DIR / "msb/data/prompt_template.py", SERVERS_DIR / "msb/data/attack_task.jsonl"],
    "msb_terminal_false_error": [MSB / "terminal_controller-out_of_scope_parameter.py", SERVERS_DIR / "msb/data/prompt_template.py", SERVERS_DIR / "msb/data/attack_task.jsonl"],
    "desktop_commander": [DC / "index.js", DC / "bootstrap.js", DC / "server.js", DC / "config-manager.js", DC / "config.js", DC / "utils/capture.js",
                          DC / "utils/toolHistory.js", DC / "utils/usageTracker.js", DC / "utils/process-detection.js", DC / "utils/system-info.js",
                          DC / "track-installation.js", DC / "handlers/filesystem-handlers.js", DC / "tools/filesystem.js", DC / "tools/edit.js",
                          DC / "tools/improved-process-tools.js", DC / "terminal-manager.js", DC / "command-manager.js", DC / "search-manager.js",
                          DC / "custom-stdio.js", DC / "utils/files/text.js", DC / "handlers"],
    "obsidian": [NM / "obsidian-mcp/dist/main.js", NM / "obsidian-mcp/dist/cli.js", NM / "obsidian-mcp/dist/utils", NM / "obsidian-mcp/dist/tools"],
}
BUDGET = 360_000   # characters of source per server
STARTUP_NOTE = {"msb_terminal_false_error": "This server is started with the arguments: false_error kill_process pilot (sys.argv[-3:]).",
                "msb_terminal_tool_transfer": "This server is started with the arguments: tool_transfer kill_process pilot (sys.argv[-3:]).",
                "msb_terminal_out_of_scope_parameter": "This server is started with the arguments: out_of_scope_parameter kill_process pilot (sys.argv[-3:])."}

SYSTEM = ("You are a meticulous software security auditor comparing an MCP server's tool descriptions with its implementation. "
          "You report only what the code shows, with file and function names as evidence. Answer with one JSON object in a ```json block and nothing else.")

FORMAT = """
Return JSON with this shape:
{
  "server": "<name>",
  "startup": [ {"behaviour": "...", "evidence": "file: function/line", "kind": "file_write|subprocess|network|config|state|other",
                "documented_in_tool_descriptions": false, "observable_from_outside": "file|process|network|none", "security_relevance": "none|low|medium|high"} ],
  "tools": {
    "<tool name>": {
      "matches_description": true|false,
      "undocumented_behaviours": [ {"behaviour": "...", "evidence": "...", "kind": "...", "trigger": "every call|conditional on input|conditional on state|conditional on configuration|on error",
                                     "observable_from_outside": "file|process|network|none", "security_relevance": "none|low|medium|high"} ],
      "declared_effect_not_implemented": "..." or null
    }
  },
  "overall": {"description_implementation_mismatch": "none|minor|substantial", "summary": "two sentences"}
}
List every tool of tools/list.  Behaviours that the description states (e.g. 'executes the command') are not undocumented.
Library behaviour that the code triggers counts (e.g. a library that refreshes a cache file or fetches a URL) if the code
visibly calls it; say so in the evidence.  Do not speculate beyond the code.
"""


def collect_source(server: str) -> tuple[str, list[str]]:
    parts, used, total = [], [], 0
    for src in SOURCES[server]:
        files = sorted(x for x in src.rglob("*") if x.is_file() and x.suffix in (".py", ".js", ".mjs", ".cjs", ".jsonl", ".json")) if src.is_dir() else [src]
        files = [f for f in files if ".d.ts" not in f.name and "__pycache__" not in f.parts and not f.name.endswith(".map")]
        for f in files:
            if f.suffix == ".json" and f.name != "package.json":
                continue
            try:
                text = f.read_text(errors="replace")
            except OSError:
                continue
            if total + len(text) > BUDGET:
                remaining = BUDGET - total
                if remaining < 2000:
                    break
                text = text[:remaining] + "\n[... truncated by the scan budget ...]\n"
            try:
                rel = str(f.relative_to(SERVERS_DIR))
            except ValueError:
                rel = f.name
            parts.append(f"\n\n===== FILE: {rel} =====\n{text}")
            used.append(rel); total += len(text)
            if total >= BUDGET:
                break
        if total >= BUDGET:
            break
    return "".join(parts), used


def build_prompt(server: str) -> tuple[str, str, list[str]]:
    tools = json.loads((ROOT / "contracts" / f"{server}.tools.json").read_text())
    source, used = collect_source(server)
    user = (f"{FORMAT}\n\n## Server: {server}\n{STARTUP_NOTE.get(server, '')}\n\n## tools/list (verbatim)\n\n```json\n{json.dumps(tools, indent=1, sort_keys=True)}\n```\n\n"
            f"## Implementation ({len(used)} files)\n{source}\n\n## Task\n\nCompare every tool description with the implementation and report, per tool and for start-up, "
            f"all behaviour the descriptions do not state. Return only the JSON.")
    return SYSTEM, user, used


def chat(base, key, model, system, user, timeout=1200):
    body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": 0, "max_tokens": 16000}
    for attempt in range(1, 6):
        req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "vac-static-scan/1.0 (research harness)"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                d = json.loads(resp.read().decode())
            msg = d["choices"][0]["message"]
            text = msg.get("content") or msg.get("reasoning_content") or ""
            return text, {"usage": d.get("usage", {}), "seconds": round(time.time() - t0, 1), "provider_model": d.get("model"), "attempts": attempt}
        except urllib.error.HTTPError as exc:
            body_txt = exc.read().decode(errors="replace")
            if exc.code in (429, 500, 502, 503, 504) and attempt < 5:
                m = re.search(r"try again in ([0-9.]+)s", body_txt)
                time.sleep(max(15 * attempt, float(m.group(1)) + 1 if m else 0)); continue
            raise RuntimeError(f"HTTP {exc.code}: {body_txt[:300]}")
        except (TimeoutError, urllib.error.URLError) as exc:
            if attempt < 3:
                time.sleep(20); continue
            raise RuntimeError(f"{type(exc).__name__}: {exc}")


def extract_json(text: str):
    m = re.search(r"```json\s*\n(.*?)```", text, re.S)
    block = m.group(1) if m else text
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        i, j = block.find("{"), block.rfind("}")
        if i >= 0 and j > i:
            try:
                return json.loads(block[i:j + 1])
            except json.JSONDecodeError:
                return None
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--servers", default=",".join(SOURCES))
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    log = (OUT / "log.jsonl").open("a")
    manifest_path = OUT / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"created": datetime.now(timezone.utc).isoformat(), "prompts": {}}
    for s in args.servers.split(","):
        system, user, used = build_prompt(s)
        manifest["prompts"][s] = {"user_sha256": hashlib.sha256(user.encode()).hexdigest(), "chars": len(user), "files": used}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    for m in args.models.split(","):
        base, key, model_id = MODELS[m]
        (OUT / m).mkdir(exist_ok=True)
        for s in args.servers.split(","):
            out = OUT / m / f"{s}.json"
            if out.exists():
                print(m, s, "exists"); continue
            system, user, used = build_prompt(s)
            entry = {"model": m, "server": s, "started": datetime.now(timezone.utc).isoformat(), "prompt_chars": len(user), "files": len(used)}
            try:
                text, meta = chat(base, key, model_id, system, user)
                (OUT / m / f"{s}.raw.txt").write_text(text)
                doc = extract_json(text)
                entry.update(meta); entry["parsed"] = doc is not None
                if doc is not None:
                    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
                print(f"{m:20s} {s:38s} parsed={doc is not None} {meta['seconds']}s tokens={meta['usage'].get('total_tokens')} prompt_chars={len(user)}", flush=True)
            except RuntimeError as exc:
                entry["error"] = str(exc)
                print(f"{m:20s} {s:38s} ERROR {exc}", flush=True)
            entry["finished"] = datetime.now(timezone.utc).isoformat()
            log.write(json.dumps(entry, sort_keys=True) + "\n"); log.flush()


if __name__ == "__main__":
    main()
