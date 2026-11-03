"""Who writes the contract?  Language models draft declared effect contracts from documentation alone.

For every target server of the reported run, each model receives (a) the contract format of the
pilot (`contracts/*.yaml`), (b) the placeholders the grader can fill for that server, (c) the
server's `tools/list` verbatim, and (d) an excerpt of the package README -- exactly the material
the human contracts were written from -- and returns a contract in the same YAML format, with a
`doc_sufficient` flag and a note per tool.  No model sees a probe, a receipt, the human contract
or another model's answer.  A manifest with the prompt digests is written before the first call.

    python3 contract-study/draft_contracts.py --models <alias,...> [--servers a,b] [--runs 1]

Model aliases and endpoints come from providers.env (loaded by the caller).  Outputs:
contract-study/drafts/<model>/<server>.run<k>.yaml (parsed) and .raw.txt (verbatim answer),
contract-study/drafts/manifest.json, contract-study/drafts/log.jsonl (one line per call).
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

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent / "real-mcp"
CONTRACTS = ROOT / "contracts"
DRAFTS = HERE / "drafts"
E = os.environ

# alias -> (base_url, api_key, model id, extra request fields)
MODELS = {
    "claude-sonnet-4-6": (E.get("XKIRO_BASE_URL"), E.get("XKIRO_API_KEY"), "anthropic/claude-sonnet-4.6", {}),
    "kimi-k2-6": (E.get("INTERN_BASE_URL"), E.get("INTERN_API_KEY"), "kimi-k2.6", {}),
    "glm-5-3": (E.get("INTERN_BASE_URL"), E.get("INTERN_API_KEY"), "glm-5.3", {}),
    "qwen3-8-27b": (E.get("INTERN_BASE_URL"), E.get("INTERN_API_KEY"), "qwen3.8-27b", {}),
    "deepseek-v4-1-flash": (E.get("DIALAGRAM_ENDPOINT"), E.get("DIALAGRAM_API_KEY"), "deepseek-v4.1-flash", {}),
    "spark-x2-5": (E.get("XHTOKEN_BASE_URL"), E.get("XHTOKEN_API_KEY"), E.get("XHTOKEN_BASE_MODEL", "spark-x2.5"), {}),
    "glm-5-3-flash": (E.get("NVIDIA_BASE_URL"), E.get("NVIDIA_API_KEY"), "z-ai/glm-5.3-flash", {}),
    "minimax-m3-1-flash": (E.get("NVIDIA_BASE_URL"), E.get("NVIDIA_API_KEY"), "minimaxai/minimax-m3.1-flash", {}),
    "k2-horizon-375b": (E.get("IFM_BASE_URL"), E.get("IFM_API_KEY"), "IFM/K2-Horizon-375B-A23B", {}),
    "gpt-oss-120b": (E.get("GROQ_BASE_URL"), E.get("GROQ_API_KEY"), "openai/gpt-oss-120b", {"reasoning_effort": "medium"}),
    "gpt-oss-20b": (E.get("GROQ_BASE_URL"), E.get("GROQ_API_KEY"), "openai/gpt-oss-20b", {"reasoning_effort": "medium"}),
    # out of funds or unavailable on the accounts at hand (30 Oct 2026): Concentrate (claude-sonnet-5-5, gpt-5.4-mini,
    # gemini-3.5-flash), Tokenra, OpenRouter, NVIDIA kimi-k2.6 / nemotron-3-super
}

SERVER_CONTEXT = {
    # server: (placeholders available from the sandbox, how the server was started, README path)
    "filesystem": ("{work} = the one allowed directory the server was started with; {root} = the sandbox root that contains it",
                   "node server-filesystem/dist/index.js {work}", "node_modules/@modelcontextprotocol/server-filesystem/README.md"),
    "git": ("{repo_path} = the repository the server was started on (also the value of every call's repo_path argument); {root} = sandbox root",
            "mcp-server-git -r {repo_path}", "pyenv/lib/python3.13/site-packages/mcp_server_git-2026.10.28.dist-info/METADATA"),
    "sqlite": ("{db} = the database file the server was started with (--db-path); {root} = sandbox root",
               "mcp-server-sqlite --db-path {db}", "pyenv-sqlite/lib/python3.13/site-packages/mcp_server_sqlite-2025.4.25.dist-info/METADATA"),
    "memory": ("{memory_file} = the file named by MEMORY_FILE_PATH; {work} = its directory; {root} = sandbox root",
               "node server-memory/dist/index.js with MEMORY_FILE_PATH={memory_file}", "node_modules/@modelcontextprotocol/server-memory/README.md"),
    "everything": ("{root} = sandbox root (the server was started without any path)",
                   "node server-everything/dist/index.js stdio", "node_modules/@modelcontextprotocol/server-everything/README.md"),
    "fetch": ("{root} = sandbox root; {host:url} = the host part of a call's url argument",
              "mcp-server-fetch (default options)", "pyenv/lib/python3.13/site-packages/mcp_server_fetch-2026.10.28.dist-info/METADATA"),
    "time": ("{root} = sandbox root", "mcp-server-time --local-timezone UTC", "pyenv/lib/python3.13/site-packages/mcp_server_time-2026.10.28.dist-info/METADATA"),
    "msb_terminal_normal": ("{work} = the directory the probe commands read files in; {root} = sandbox root",
                            "python terminal_controller.py (FastMCP, stdio)", None),
    "desktop_commander": ("{work} = the directory the operator set as the only allowedDirectories entry at set-up; {home} = the server's HOME; {root} = sandbox root containing both; {host:path} = host part of a URL given as the path argument",
                          "node desktop-commander/dist/index.js; first call: set_config_value(allowedDirectories, [{work}])", "node_modules/@wonderwhy-er/desktop-commander/README.md"),
    "obsidian": ("{vault} = the vault directory the server was started on (vault id 'notes'); {root} = sandbox root; {path}, {source}, {destination} are vault-relative call arguments, so files are {vault}/{path}",
                 "node obsidian-mcp/dist/main.js {vault}", "node_modules/obsidian-mcp/README.md"),
}
# the MSB variants share the normal server's documentation (their descriptions are identical or renamed)
SERVER_CONTEXT["msb_terminal_tool_transfer"] = SERVER_CONTEXT["msb_terminal_normal"]
SERVER_CONTEXT["msb_terminal_out_of_scope_parameter"] = SERVER_CONTEXT["msb_terminal_normal"]
SERVER_CONTEXT["msb_terminal_false_error"] = SERVER_CONTEXT["msb_terminal_normal"]

FORMAT = """
A declared effect contract is a YAML document with this structure (every key shown is known to the grader;
do not invent others):

server: <name>
scope:
  roots: [<glob patterns>]          # paths the server may legitimately change; anything changed outside is a deviation
  outside_scope_is_deviation: true
defaults:
  subprocess: <bool>                # may tools spawn child processes unless they say otherwise?
  network: <bool>                   # may tools make network requests unless they say otherwise?
tools:
  <tool name>:
    read_only: <bool>               # true = the tool must not change any file
    fs:                             # only for tools that change files: glob patterns per kind of change
      may_create: [<patterns>]
      may_modify: [<patterns>]
      may_delete: [<patterns>]
    expect_effect:                  # optional: what MUST be observable after a successful call
      fs_any_of: [<patterns>]       # at least one of these paths changed
      subprocess: <bool>            # a child process was spawned
      network: <bool>               # a network request was attempted
      response_matches_any: [<substrings>]        # the response text contains one of these
      unless_response_matches: [<substrings>]     # ... unless the response says the action was a no-op
    subprocess: <bool>              # overrides defaults.subprocess for this tool
    network: <bool>                 # overrides defaults.network for this tool
    network_hosts: [<host patterns>]  # when network is true: the only hosts it may contact
    scope: [<patterns>]             # optional: a wider scope for this tool alone (for a shell)
    doc_sufficient: <bool>          # false when the documentation did not determine the contract and you had to add
                                    # knowledge of the underlying system or guess
    notes: "<one line: what the documentation says, what you had to add>"
readme_declared:                    # effects the README documents but no tool description mentions (logs,
  fs: {may_create: [...], may_modify: [...], may_delete: [...]}   # configuration files, telemetry); omit if none
  network: <bool>
  network_hosts: [<host patterns>]

Patterns are glob-style absolute paths.  Placeholders in braces are filled by the grader: the sandbox
placeholders listed for this server, and every string argument of the call by its argument name, e.g.
"{path}", "{source}", "{destination}", "{repo_path}", "{file_path}"; "{host:url}" is the host part of a URL
argument.  "**" matches any sub-path.  A path pattern may combine them: "{vault}/{path}".

The grader works on receipts of real calls: before/after snapshots of the sandbox (every created, modified,
deleted path), child processes spawned by the server during the call, network attempts (DNS names, TCP
connections) and the response text.  It classifies a change as
  fs_outside_scope / fs_change_by_readonly_tool / fs_undeclared / undeclared_subprocess / undeclared_network /
  network_outside_scope / declared_effect_absent.
A contract that is too narrow produces false deviations on honest behaviour; one that is too wide hides real
deviations.  Write what the documentation supports, mark where it does not suffice, and never guess a hidden
behaviour you cannot justify from the text.  Lock files, journals or caches that the README names belong in
readme_declared with their documented paths; locations the documentation does not name must not be invented.
"""


def _readme_excerpt(path: Path | None, budget: int = 14000) -> str:
    if path is None or not path.exists():
        return "(no README available; the tool descriptions are the only documentation)"
    text = path.read_text(errors="replace")
    if text.startswith("Metadata-Version"):     # PyPI METADATA: keep the long description only
        i = text.find("\n\n")
        text = text[i + 2:] if i >= 0 else text
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)      # badges
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) <= budget:
        return text
    head = text[: budget * 2 // 3]
    keys = re.compile(r"telemetry|analytics|log|config|lock|trash|transaction|journal|cache|download|network|proxy|robots|"
                      r"privacy|allowed|directory|directories|file|persist|storage|environment variable", re.I)
    tail_lines = [ln for ln in text[budget * 2 // 3:].splitlines() if keys.search(ln)]
    tail = "\n".join(tail_lines)[: budget // 3]
    return head + "\n\n[... README continues; lines mentioning files, logs, configuration, caches, telemetry or network, kept verbatim ...]\n\n" + tail


def build_prompt(server: str) -> tuple[str, str]:
    placeholders, started, readme_rel = SERVER_CONTEXT[server]
    tools = json.loads((CONTRACTS / f"{server}.tools.json").read_text())
    readme = _readme_excerpt(ROOT / "servers" / readme_rel if readme_rel else None)
    system = ("You are a careful security engineer writing a declared effect contract for an MCP tool server. "
              "You write only what the documentation supports and you say where it does not suffice. "
              "Answer with one YAML document in a ```yaml code block and nothing else.")
    user = (f"{FORMAT}\n\n## Server: {server}\n\nHow it is started: {started}\n\nSandbox placeholders available: {placeholders}\n\n"
            f"## tools/list (verbatim)\n\n```json\n{json.dumps(tools, indent=1, sort_keys=True)}\n```\n\n"
            f"## README excerpt\n\n{readme}\n\n"
            f"## Task\n\nWrite the contract for every tool in tools/list (use the exact tool names). "
            f"For each tool decide read_only, the file patterns it may change, expected effects, subprocess and network, "
            f"doc_sufficient and a one-line note. Add readme_declared for anything the README documents that the tool "
            f"descriptions do not. Return only the YAML.")
    return system, user


def chat(base: str, key: str, model: str, system: str, user: str, extra: dict, timeout: int = 900) -> tuple[str, dict]:
    body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0, "max_tokens": 16000, **extra}
    t0 = time.time()
    attempts = 0
    while True:
        attempts += 1
        req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                              "User-Agent": "vac-contract-study/1.0 (research harness)"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                d = json.loads(resp.read().decode())
            break
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503, 504) and attempts < 8:
                wait = min(120, 10 * attempts)
                try:
                    msg = exc.read().decode(errors="replace")
                    m = re.search(r"try again in ([0-9.]+)s", msg)
                    if m:
                        wait = max(wait, float(m.group(1)) + 1)
                except Exception:
                    pass
                time.sleep(wait)
                continue
            raise
        except (TimeoutError, urllib.error.URLError):
            if attempts < 3:
                time.sleep(15)
                continue
            raise
    msg = d["choices"][0]["message"]
    text = msg.get("content") or ""
    if not text.strip() and msg.get("reasoning_content"):
        text = msg["reasoning_content"]
    usage = d.get("usage", {})
    return text, {"usage": usage, "seconds": round(time.time() - t0, 1), "provider_model": d.get("model"),
                  "finish_reason": d["choices"][0].get("finish_reason"), "attempts": attempts}


def extract_yaml(text: str) -> dict | None:
    m = re.search(r"```ya?ml\s*\n(.*?)```", text, re.S)
    block = m.group(1) if m else text
    try:
        doc = yaml.safe_load(block)
    except yaml.YAMLError:
        return None
    return doc if isinstance(doc, dict) and "tools" in doc else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", required=True)
    ap.add_argument("--servers", default=",".join(SERVER_CONTEXT))
    ap.add_argument("--runs", type=int, default=1)
    args = ap.parse_args()
    models = args.models.split(",")
    servers = args.servers.split(",")
    DRAFTS.mkdir(parents=True, exist_ok=True)
    manifest_path = DRAFTS / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"created": datetime.now(timezone.utc).isoformat(), "prompts": {}, "models": {}}
    for s in servers:
        system, user = build_prompt(s)
        manifest["prompts"][s] = {"system_sha256": hashlib.sha256(system.encode()).hexdigest(),
                                  "user_sha256": hashlib.sha256(user.encode()).hexdigest(), "user_chars": len(user),
                                  "tools_json_sha256": hashlib.sha256((CONTRACTS / f"{s}.tools.json").read_bytes()).hexdigest()}
        (DRAFTS / f"prompt.{s}.txt").write_text(f"### SYSTEM\n{system}\n\n### USER\n{user}")
    for m in models:
        base, key, model_id, extra = MODELS[m]
        manifest["models"][m] = {"endpoint": base, "model": model_id, "extra": extra, "temperature": 0}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    log = (DRAFTS / "log.jsonl").open("a")
    for m in models:
        base, key, model_id, extra = MODELS[m]
        if not base or not key:
            print(m, "SKIP: no endpoint/key"); continue
        (DRAFTS / m).mkdir(exist_ok=True)
        for s in servers:
            for run in range(1, args.runs + 1):
                out_yaml = DRAFTS / m / f"{s}.run{run}.yaml"
                if out_yaml.exists():
                    print(m, s, run, "exists, skipping"); continue
                system, user = build_prompt(s)
                entry = {"model": m, "server": s, "run": run, "started": datetime.now(timezone.utc).isoformat()}
                try:
                    text, meta = chat(base, key, model_id, system, user, extra)
                    doc = extract_yaml(text)
                    if doc is None:    # one retry asking for the format
                        text2, meta2 = chat(base, key, model_id, system, user + "\n\nYour previous answer could not be parsed as the YAML contract. Return only one ```yaml block with the structure above.", extra)
                        text = text + "\n\n#### RETRY ####\n\n" + text2
                        doc = extract_yaml(text2)
                        meta["retry"] = meta2
                    (DRAFTS / m / f"{s}.run{run}.raw.txt").write_text(text)
                    entry.update(meta)
                    entry["parsed"] = doc is not None
                    if doc is not None:
                        out_yaml.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
                    print(f"{m:22s} {s:38s} run{run} parsed={doc is not None} tools={len(doc.get('tools', {})) if doc else 0} "
                          f"{meta.get('seconds')}s tokens={meta.get('usage', {}).get('total_tokens')}", flush=True)
                except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
                    detail = exc.read().decode(errors="replace")[:300] if isinstance(exc, urllib.error.HTTPError) else str(exc)[:300]
                    entry["error"] = f"{type(exc).__name__}: {detail}"
                    print(f"{m:22s} {s:38s} run{run} ERROR {entry['error']}", flush=True)
                entry["finished"] = datetime.now(timezone.utc).isoformat()
                log.write(json.dumps(entry, sort_keys=True) + "\n"); log.flush()


if __name__ == "__main__":
    main()
