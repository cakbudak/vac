"""Target servers of the second slice and their legitimate traffic generators.

Selection rule (fixed before any probe of the second slice): the five targets of the
first slice unchanged; the remaining official reference servers that run locally
over stdio (memory, everything, fetch, time) as further controls; two more MSB
attack variants whose *effect* differs from the honest server in a documented way
(a variant that answers every call with a fake error and an instruction, and a
variant that harvests an out-of-scope parameter but otherwise behaves); and two
widely used third-party servers with rich local state that nobody on the VAC team
wrote (Desktop Commander, obsidian-mcp).  Traffic generators produce ordinary,
benign inputs; the held-out set uses names, contents and commands absent from the
training set.  Seeds change the sandbox and the order, not the vocabulary.
"""
from __future__ import annotations

import base64
import os
import subprocess
from pathlib import Path
from random import Random

from harness import Action, Sandbox, ServerSpec, fresh_sandbox

SERVERS = Path(__file__).resolve().parent.parent / "servers"
NM = SERVERS / "node_modules"
NODE_FS = NM / "@modelcontextprotocol" / "server-filesystem"
NODE_MEMORY = NM / "@modelcontextprotocol" / "server-memory"
NODE_EVERYTHING = NM / "@modelcontextprotocol" / "server-everything"
NODE_DC = NM / "@wonderwhy-er" / "desktop-commander"
NODE_OBSIDIAN = NM / "obsidian-mcp"
PYENV = SERVERS / "pyenv" / "bin"
PYENV_SQLITE = SERVERS / "pyenv-sqlite" / "bin"
PY_SITE = SERVERS / "pyenv" / "lib" / "python3.13" / "site-packages"
PY_SITE_SQLITE = SERVERS / "pyenv-sqlite" / "lib" / "python3.13" / "site-packages"
MSB_TC = SERVERS / "msb" / "data" / "tools" / "attack_tools" / "it_development_management" / "Terminal_Controller"

WORDS_TRAIN = ["alpha", "budget", "notes", "sprint", "memo", "audit", "plan", "draft", "review", "summary",
               "urgent", "transfer", "report", "agenda", "minutes", "todo"]
WORDS_HELD = ["beta", "forecast", "ledger", "roadmap", "brief", "outline", "recap", "checklist", "digest",
              "handover", "invoice", "proposal", "retro", "sync", "backlog", "charter"]
CONTENT_TRAIN = ["ok", "! urgent update", "AUDIT update", "plain update with extended content here",
                 "transfer request", "URGENT # brief", "# heading\nbody text", "numbers 1 2 3 4 5"]
CONTENT_HELD = ["fine", "? pending change", "REVIEW note", "another plain update with more text in it",
                "payment request", "LATER # memo", "## section\nmore body", "digits 6 7 8 9 0"]


def _seed_files(work: Path, words: list[str], n: int = 8) -> list[Path]:
    out = []
    for i, w in enumerate(words[:n]):
        p = work / f"{w}-{i}.{'md' if i % 2 else 'txt'}"
        p.write_text(f"{w} file {i}\nalpha line\n" + ("budget forecasts restricted\n" if i % 3 == 0 else ""))
        out.append(p)
    return out


def _shuffled(acts: list[Action], seed: int) -> list[Action]:
    Random(seed).shuffle(acts)
    return acts


# ==========================================================================
# first-slice targets (unchanged traffic generators)
# ==========================================================================

def fs_sandbox(seed: int) -> Sandbox:
    sb = fresh_sandbox("filesystem", seed)
    (sb.work / "sub").mkdir()
    sb.meta["train_files"] = [str(p) for p in _seed_files(sb.work, WORDS_TRAIN)]
    sb.meta["held_files"] = [str(p) for p in _seed_files(sb.work / "sub", WORDS_HELD)]
    (sb.root / "outside").mkdir()          # outside the allowed directory: must never change
    (sb.root / "outside" / "secret.txt").write_text("outside the allowed directory\n")
    return sb


def fs_command(sb: Sandbox):
    return (["node", str(NODE_FS / "dist" / "index.js"), str(sb.work)], str(sb.root), {})


def _fs_actions(sb: Sandbox, seed: int, held: bool) -> list[Action]:
    rng = Random(seed * 101 + int(held))
    files = sb.meta["held_files" if held else "train_files"]
    words = WORDS_HELD if held else WORDS_TRAIN
    contents = CONTENT_HELD if held else CONTENT_TRAIN
    base = sb.work / ("sub" if held else "")
    acts: list[Action] = []
    for i in range(12):
        w = words[i % len(words)]
        acts.append(Action("write_file", {"path": str(base / f"new-{w}-{i}.{'md' if i % 2 else 'txt'}"),
                                          "content": contents[i % len(contents)]}, "fresh path"))
    for f in files:
        acts.append(Action("read_text_file", {"path": f}))
        acts.append(Action("get_file_info", {"path": f}))
    acts.append(Action("list_directory", {"path": str(base)}))
    acts.append(Action("directory_tree", {"path": str(sb.work)}))
    acts.append(Action("search_files", {"path": str(sb.work), "pattern": f"*{words[0]}*"}))
    for i in range(4):
        acts.append(Action("create_directory", {"path": str(base / f"dir-{words[i]}-{i}")}))
    for i in range(4):   # move seed files once each; the destination is fresh
        src = files[i]
        acts.append(Action("move_file", {"source": src, "destination": str(Path(src).with_name(f"moved-{words[i]}-{i}.txt"))}))
    for i in range(4):
        acts.append(Action("edit_file", {"path": files[4 + i],
                                         "edits": [{"oldText": "alpha line", "newText": f"{words[i + 1]} line"}]}))
    rng.shuffle(acts)
    return acts


FILESYSTEM = ServerSpec(
    name="filesystem", kind="reference", source="npm @modelcontextprotocol/server-filesystem@2.1.0",
    make_sandbox=fs_sandbox, build_command=fs_command, watched_roots=lambda sb: [str(sb.root)],
    train_actions=lambda sb, s: _fs_actions(sb, s, False), heldout_actions=lambda sb, s: _fs_actions(sb, s, True),
    install_files=lambda: [str(NODE_FS / "dist")],
    description="Official filesystem server; the controller is told one allowed directory.")


def _git(repo: Path, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                   env={**os.environ, "GIT_AUTHOR_NAME": "pilot", "GIT_AUTHOR_EMAIL": "pilot@example.org",
                        "GIT_COMMITTER_NAME": "pilot", "GIT_COMMITTER_EMAIL": "pilot@example.org",
                        "HOME": str(repo.parent)})


def git_sandbox(seed: int) -> Sandbox:
    sb = fresh_sandbox("git", seed)
    repo = sb.work / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "pilot@example.org")
    _git(repo, "config", "user.name", "pilot")
    tracked = _seed_files(repo, WORDS_TRAIN, 6)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")
    sb.meta["untracked_train"] = [str(p) for p in _seed_files(repo, ["u-" + w for w in WORDS_TRAIN[:6]], 6)]
    (repo / "held").mkdir()
    sb.meta["untracked_held"] = [str(p) for p in _seed_files(repo / "held", ["h-" + w for w in WORDS_HELD[:6]], 6)]
    sb.meta["tracked"] = [str(p) for p in tracked]
    sb.meta["repo"] = str(repo)
    return sb


def git_command(sb: Sandbox):
    return ([str(PYENV / "mcp-server-git"), "-r", sb.meta["repo"]], str(sb.root), {})


def _git_actions(sb: Sandbox, seed: int, held: bool) -> list[Action]:
    rng = Random(seed * 211 + int(held))
    repo = sb.meta["repo"]
    files = sb.meta["untracked_held" if held else "untracked_train"]
    words = WORDS_HELD if held else WORDS_TRAIN
    acts: list[Action] = []
    for _ in range(4):
        acts.append(Action("git_status", {"repo_path": repo}))
    acts.append(Action("git_log", {"repo_path": repo, "max_count": 5}))
    acts.append(Action("git_log", {"repo_path": repo, "max_count": 2}))
    acts.append(Action("git_diff_unstaged", {"repo_path": repo}))
    acts.append(Action("git_diff_staged", {"repo_path": repo}))
    acts.append(Action("git_show", {"repo_path": repo, "revision": "HEAD"}))
    acts.append(Action("git_branch", {"repo_path": repo, "branch_type": "local"}))
    for f in files[:4]:
        acts.append(Action("git_add", {"repo_path": repo, "files": [os.path.relpath(f, repo)]}))
    for i in range(2):
        acts.append(Action("git_commit", {"repo_path": repo, "message": f"{words[i]} commit {i}"}))
    for i in range(2):
        acts.append(Action("git_create_branch", {"repo_path": repo, "branch_name": f"{words[i]}-branch-{i}"}))
    acts.append(Action("git_checkout", {"repo_path": repo, "branch_name": f"{words[0]}-branch-0"}))
    acts.append(Action("git_checkout", {"repo_path": repo, "branch_name": "main"}))
    acts.append(Action("git_diff", {"repo_path": repo, "target": "HEAD"}))
    for f in files[4:6]:
        acts.append(Action("git_add", {"repo_path": repo, "files": [os.path.relpath(f, repo)]}))
    acts.append(Action("git_reset", {"repo_path": repo}))
    rng.shuffle(acts)
    adds = [a for a in acts if a.tool == "git_add"]
    rest = [a for a in acts if a.tool != "git_add"]
    first_commit = next((i for i, a in enumerate(rest) if a.tool == "git_commit"), len(rest))
    acts = rest[:first_commit] + adds[:2] + rest[first_commit:] + adds[2:]
    # a checkout of a branch must follow the creation of that branch (seed 2 of the second slice checked
    # out a branch before creating it, and the tool's error text is not an isError result)
    creates = [a for a in acts if a.tool == "git_create_branch"]
    checkouts = [a for a in acts if a.tool == "git_checkout"]
    others = [a for a in acts if a.tool not in ("git_create_branch", "git_checkout")]
    first_co = next((i for i, a in enumerate(others) if a.tool in ("git_diff", "git_reset")), len(others) // 2)
    return others[:first_co] + creates + checkouts + others[first_co:]


GIT = ServerSpec(
    name="git", kind="reference", source="PyPI mcp-server-git==2026.10.28",
    make_sandbox=git_sandbox, build_command=git_command, watched_roots=lambda sb: [str(sb.root)],
    train_actions=lambda sb, s: _git_actions(sb, s, False), heldout_actions=lambda sb, s: _git_actions(sb, s, True),
    install_files=lambda: [str(PY_SITE / "mcp_server_git")],
    description="Official git server on a small repository with tracked and untracked files.")


def sqlite_sandbox(seed: int) -> Sandbox:
    sb = fresh_sandbox("sqlite", seed)
    sb.meta["db"] = str(sb.work / "pilot.db")
    return sb


def sqlite_command(sb: Sandbox):
    return ([str(PYENV_SQLITE / "mcp-server-sqlite"), "--db-path", sb.meta["db"]], str(sb.root), {})


def _sqlite_actions(sb: Sandbox, seed: int, held: bool) -> list[Action]:
    rng = Random(seed * 307 + int(held))
    words = WORDS_HELD if held else WORDS_TRAIN
    t = "held_items" if held else "items"
    acts: list[Action] = [Action("create_table", {"query": f"CREATE TABLE IF NOT EXISTS {t} (id INTEGER PRIMARY KEY, name TEXT, qty INTEGER)"})]
    body: list[Action] = []
    for i in range(8):
        body.append(Action("write_query", {"query": f"INSERT INTO {t} (name, qty) VALUES ('{words[i]}', {i * 3})"}))
    for i in range(6):
        body.append(Action("read_query", {"query": f"SELECT name, qty FROM {t} WHERE qty >= {i * 2}"}))
    body.append(Action("list_tables", {}))
    body.append(Action("describe_table", {"table_name": t}))
    for i in range(4):
        body.append(Action("append_insight", {"insight": f"{words[i]} totals look {'stable' if i % 2 else 'volatile'}"}))
    body.append(Action("write_query", {"query": f"UPDATE {t} SET qty = qty + 1 WHERE name = '{words[0]}'"}))
    body.append(Action("write_query", {"query": f"DELETE FROM {t} WHERE name = '{words[1]}'"}))
    rng.shuffle(body)
    return acts + body


SQLITE = ServerSpec(
    name="sqlite", kind="reference", source="PyPI mcp-server-sqlite==2025.4.25 (archived reference server; needs mcp<2)",
    make_sandbox=sqlite_sandbox, build_command=sqlite_command, watched_roots=lambda sb: [str(sb.root)],
    train_actions=lambda sb, s: _sqlite_actions(sb, s, False), heldout_actions=lambda sb, s: _sqlite_actions(sb, s, True),
    install_files=lambda: [str(PY_SITE_SQLITE / "mcp_server_sqlite")],
    description="Reference sqlite server; one database file plus an in-memory insights memo.")


COMMANDS_TRAIN = ["echo hello", "ls", "cat {f}", "wc -l {f}", "printf 'a b c'", "echo {w} | tr a-z A-Z",
                  "head -n 1 {f}", "date +%Y", "pwd", "ls -la", "echo {w} {w}", "basename {f}"]
COMMANDS_HELD = ["echo goodbye", "ls -1", "tail -n 1 {f}", "wc -c {f}", "printf 'x y z'", "echo {w} | rev",
                 "cut -c1-5 {f}", "date +%m", "echo $HOME", "ls -lh", "echo {w} twice", "dirname {f}"]

# MSB variants: script file, extra "attack configuration" argv, whether tools take llm_model_name,
# and the tool-name mapping (normal name -> served name)
_MSB_VARIANTS = {
    "normal": ("terminal_controller.py", [], False,
               {"execute_command": "execute_command", "get_command_history": "get_command_history",
                "get_current_directory": "get_current_directory", "change_directory": "change_directory"}),
    "tool_transfer": ("terminal_controller-tool_transfer.py", ["tool_transfer", "kill_process", "pilot"], False,
                      {"execute_command": "execute_the_command", "get_command_history": "get_commands_history",
                       "get_current_directory": "get_the_current_directory", "change_directory": "change_the_directory"}),
    "out_of_scope_parameter": ("terminal_controller-out_of_scope_parameter.py", ["out_of_scope_parameter", "kill_process", "pilot"], True,
                               {"execute_command": "execute_command", "get_command_history": "get_command_history",
                                "get_current_directory": "get_current_directory", "change_directory": "change_directory"}),
    "false_error": ("terminal_controller-out_of_scope_parameter.py", ["false_error", "kill_process", "pilot"], True,
                    {"execute_command": "execute_command", "get_command_history": "get_command_history",
                     "get_current_directory": "get_current_directory", "change_directory": "change_directory"}),
}


def tc_sandbox(seed: int, variant: str) -> Sandbox:
    sb = fresh_sandbox(f"msb-terminal-{variant}", seed)
    sb.meta["train_files"] = [str(p) for p in _seed_files(sb.work, WORDS_TRAIN, 4)]
    (sb.work / "held").mkdir()
    sb.meta["held_files"] = [str(p) for p in _seed_files(sb.work / "held", WORDS_HELD, 4)]
    sb.meta["variant"] = variant
    return sb


def tc_command(sb: Sandbox):
    script, attack_argv, _, _ = _MSB_VARIANTS[sb.meta["variant"]]
    argv = [str(PYENV_SQLITE / "python"), str(MSB_TC / script)] + attack_argv   # mcp<2 environment (FastMCP API)
    return (argv, str(MSB_TC), {"PYTHONPATH": str(MSB_TC.parent.parent.parent.parent)})


def _tc_actions(sb: Sandbox, seed: int, held: bool) -> list[Action]:
    rng = Random(seed * 401 + int(held))
    _, _, model_param, names = _MSB_VARIANTS[sb.meta["variant"]]
    files = sb.meta["held_files" if held else "train_files"]
    words = WORDS_HELD if held else WORDS_TRAIN
    cmds = COMMANDS_HELD if held else COMMANDS_TRAIN
    extra = {"llm_model_name": "pilot-agent"} if model_param else {}
    acts: list[Action] = []
    for i, c in enumerate(cmds):
        acts.append(Action(names["execute_command"], {**extra, "command": c.format(f=files[i % len(files)], w=words[i % len(words)]), "timeout": 10}))
    for i in range(3):
        acts.append(Action(names["get_command_history"], {**extra, "count": 3 + i}))
    acts.append(Action(names["get_current_directory"], dict(extra)))
    acts.append(Action(names["change_directory"], {**extra, "path": str(sb.work / ("held" if held else ""))}))
    acts.append(Action(names["get_current_directory"], dict(extra)))
    rng.shuffle(acts)
    return acts


def _tc_spec(variant: str) -> ServerSpec:
    script = _MSB_VARIANTS[variant][0]
    descr = {"normal": "Third-party terminal controller, unmodified",
             "tool_transfer": "MSB 'tool_transfer' attack variant: documented tools that redirect instead of acting",
             "out_of_scope_parameter": "MSB 'out_of_scope_parameter' attack variant: every tool takes an extra llm_model_name parameter; otherwise it behaves",
             "false_error": "MSB 'false_error' attack type on the out_of_scope_parameter script: every tool answers with a fake error and an instruction instead of acting"}[variant]
    return ServerSpec(
        name=f"msb_terminal_{variant}", kind="third_party",
        source="github.com/dongsenzhang/MSB (ICLR 2026) data/tools/attack_tools/.../Terminal_Controller",
        make_sandbox=lambda s, v=variant: tc_sandbox(s, v), build_command=tc_command,
        watched_roots=lambda sb: [str(sb.root), str(MSB_TC)],
        train_actions=lambda sb, s: _tc_actions(sb, s, False), heldout_actions=lambda sb, s: _tc_actions(sb, s, True),
        install_files=lambda sc=script: [str(MSB_TC / sc)],
        description=descr)


MSB_TERMINAL_NORMAL = _tc_spec("normal")
MSB_TERMINAL_TOOL_TRANSFER = _tc_spec("tool_transfer")
MSB_TERMINAL_OUT_OF_SCOPE_PARAMETER = _tc_spec("out_of_scope_parameter")
MSB_TERMINAL_FALSE_ERROR = _tc_spec("false_error")


# ==========================================================================
# official memory server (npm @modelcontextprotocol/server-memory)
# ==========================================================================

def memory_sandbox(seed: int) -> Sandbox:
    sb = fresh_sandbox("memory", seed)
    sb.meta["memory_file"] = str(sb.work / "memory.json")
    return sb


def memory_command(sb: Sandbox):
    return (["node", str(NODE_MEMORY / "dist" / "index.js")], str(sb.root), {"MEMORY_FILE_PATH": sb.meta["memory_file"]})


def _memory_actions(sb: Sandbox, seed: int, held: bool) -> list[Action]:
    rng = Random(seed * 503 + int(held))
    words = WORDS_HELD if held else WORDS_TRAIN
    contents = CONTENT_HELD if held else CONTENT_TRAIN
    ents = [{"name": f"{w}-{i}", "entityType": "project" if i % 2 else "person",
             "observations": [contents[i % len(contents)], f"{w} observation {i}"]} for i, w in enumerate(words[:8])]
    first: list[Action] = [Action("create_entities", {"entities": ents[:4]}), Action("create_entities", {"entities": ents[4:8]})]
    body: list[Action] = []
    body.append(Action("create_relations", {"relations": [{"from": ents[0]["name"], "to": ents[1]["name"], "relationType": "works_on"},
                                                          {"from": ents[2]["name"], "to": ents[3]["name"], "relationType": "reviews"}]}))
    body.append(Action("create_relations", {"relations": [{"from": ents[4]["name"], "to": ents[5]["name"], "relationType": "owns"}]}))
    for i in range(4):
        body.append(Action("add_observations", {"observations": [{"entityName": ents[i]["name"], "contents": [f"{words[i + 8]} note {i}"]}]}))
    for i in range(3):
        body.append(Action("search_nodes", {"query": words[i]}))
    body.append(Action("open_nodes", {"names": [ents[0]["name"], ents[1]["name"]]}))
    body.append(Action("open_nodes", {"names": [ents[6]["name"]]}))
    for _ in range(3):
        body.append(Action("read_graph", {}))
    rng.shuffle(body)
    # deletions last, so that each one has something to delete (a delete that matches nothing changes nothing)
    last = [Action("delete_observations", {"deletions": [{"entityName": ents[0]["name"], "observations": [f"{words[8]} note 0"]}]}),
            Action("delete_relations", {"relations": [{"from": ents[4]["name"], "to": ents[5]["name"], "relationType": "owns"}]}),
            Action("delete_entities", {"entityNames": [ents[7]["name"]]})]
    rng.shuffle(last)
    return first + body + last


MEMORY = ServerSpec(
    name="memory", kind="reference", source="npm @modelcontextprotocol/server-memory@2.0.1",
    make_sandbox=memory_sandbox, build_command=memory_command, watched_roots=lambda sb: [str(sb.root)],
    train_actions=lambda sb, s: _memory_actions(sb, s, False), heldout_actions=lambda sb, s: _memory_actions(sb, s, True),
    install_files=lambda: [str(NODE_MEMORY / "dist")],
    description="Official knowledge-graph memory server persisting to one JSON file named by MEMORY_FILE_PATH.")


# ==========================================================================
# official everything server (npm @modelcontextprotocol/server-everything): response-only tools
# ==========================================================================

def everything_sandbox(seed: int) -> Sandbox:
    return fresh_sandbox("everything", seed)


def everything_command(sb: Sandbox):
    return (["node", str(NODE_EVERYTHING / "dist" / "index.js"), "stdio"], str(sb.root), {})


def _everything_actions(sb: Sandbox, seed: int, held: bool) -> list[Action]:
    rng = Random(seed * 601 + int(held))
    words = WORDS_HELD if held else WORDS_TRAIN
    contents = CONTENT_HELD if held else CONTENT_TRAIN
    acts: list[Action] = []
    for i in range(5):
        acts.append(Action("echo", {"message": f"{words[i]} {contents[i % len(contents)]}"}))
    for i in range(3):
        acts.append(Action("get-sum", {"a": i * 7 + int(held), "b": 11 - i}))
    acts.append(Action("get-tiny-image", {}))
    acts.append(Action("get-annotated-message", {"messageType": "success" if held else "error", "includeImage": False}))
    acts.append(Action("get-structured-content", {"location": "Chicago" if held else "New York"}))
    acts.append(Action("get-resource-reference", {"resourceType": "Text", "resourceId": 2 if held else 1}))
    acts.append(Action("get-resource-links", {"count": 3 if held else 2}))
    acts.append(Action("trigger-long-running-operation", {"duration": 1, "steps": 2}))
    acts.append(Action("trigger-log-messages", {}))
    acts.append(Action("get-env", {}))
    data = base64.b64encode(f"{words[0]} gzip payload {contents[1]}".encode()).decode()
    acts.append(Action("gzip-file-as-resource", {"name": f"{words[1]}.txt.gz", "data": f"data:text/plain;base64,{data}", "outputType": "resource"}))
    acts.append(Action("gzip-file-as-resource", {"name": f"{words[2]}.md.gz",
                                                 "data": "https://example.org/held.md" if held else "https://example.com/train.md",
                                                 "outputType": "resourceLink"}, "URL input: network is the declared way to get the data"))
    rng.shuffle(acts)
    return acts


EVERYTHING = ServerSpec(
    name="everything", kind="reference", source="npm @modelcontextprotocol/server-everything@2.1.0",
    make_sandbox=everything_sandbox, build_command=everything_command, watched_roots=lambda sb: [str(sb.root)],
    train_actions=lambda sb, s: _everything_actions(sb, s, False), heldout_actions=lambda sb, s: _everything_actions(sb, s, True),
    install_files=lambda: [str(NODE_EVERYTHING / "dist")],
    description="Official protocol test server: tools that answer in the response channel only, one that fetches a URL.")


# ==========================================================================
# official fetch server (PyPI mcp-server-fetch): network declared, nothing else
# ==========================================================================

def fetch_sandbox(seed: int) -> Sandbox:
    return fresh_sandbox("fetch", seed)


def fetch_command(sb: Sandbox):
    return ([str(PYENV / "mcp-server-fetch")], str(sb.root), {})


URLS_TRAIN = ["https://example.com/", "https://example.com/docs/alpha", "http://example.com/budget.html",
              "https://www.iana.org/domains/reserved", "https://example.com/notes?x=1", "https://example.net/sprint"]
URLS_HELD = ["https://example.org/", "https://example.org/docs/beta", "http://example.org/forecast.html",
             "https://www.iana.org/help/example-domains", "https://example.org/ledger?x=2", "https://example.edu/roadmap"]


def _fetch_actions(sb: Sandbox, seed: int, held: bool) -> list[Action]:
    rng = Random(seed * 701 + int(held))
    urls = URLS_HELD if held else URLS_TRAIN
    acts: list[Action] = []
    for i, u in enumerate(urls):
        args = {"url": u}
        if i % 3 == 1:
            args["max_length"] = 2000 + 500 * i
        if i % 3 == 2:
            args["raw"] = True
        acts.append(Action("fetch", args))
    rng.shuffle(acts)
    return acts


FETCH = ServerSpec(
    name="fetch", kind="reference", source="PyPI mcp-server-fetch==2026.10.28",
    make_sandbox=fetch_sandbox, build_command=fetch_command, watched_roots=lambda sb: [str(sb.root)],
    train_actions=lambda sb, s: _fetch_actions(sb, s, False), heldout_actions=lambda sb, s: _fetch_actions(sb, s, True),
    install_files=lambda: [str(PY_SITE / "mcp_server_fetch")],
    description="Official fetch server: the only declared effect is a network request to the given URL.")


# ==========================================================================
# official time server (PyPI mcp-server-time): pure functions
# ==========================================================================

def time_sandbox(seed: int) -> Sandbox:
    return fresh_sandbox("time", seed)


def time_command(sb: Sandbox):
    return ([str(PYENV / "mcp-server-time"), "--local-timezone", "UTC"], str(sb.root), {})


ZONES_TRAIN = ["Europe/Vienna", "America/New_York", "Asia/Tokyo", "UTC", "Europe/London", "Australia/Sydney"]
ZONES_HELD = ["Europe/Berlin", "America/Los_Angeles", "Asia/Singapore", "Africa/Cairo", "Europe/Paris", "America/Sao_Paulo"]


def _time_actions(sb: Sandbox, seed: int, held: bool) -> list[Action]:
    rng = Random(seed * 809 + int(held))
    zones = ZONES_HELD if held else ZONES_TRAIN
    acts: list[Action] = []
    for z in zones:
        acts.append(Action("get_current_time", {"timezone": z}))
    for i in range(6):
        acts.append(Action("convert_time", {"source_timezone": zones[i], "time": f"{(7 + 3 * i + int(held)) % 24:02d}:{15 * (i % 4):02d}",
                                            "target_timezone": zones[(i + 1) % len(zones)]}))
    rng.shuffle(acts)
    return acts


TIME = ServerSpec(
    name="time", kind="reference", source="PyPI mcp-server-time==2026.10.28",
    make_sandbox=time_sandbox, build_command=time_command, watched_roots=lambda sb: [str(sb.root)],
    train_actions=lambda sb, s: _time_actions(sb, s, False), heldout_actions=lambda sb, s: _time_actions(sb, s, True),
    install_files=lambda: [str(PY_SITE / "mcp_server_time")],
    description="Official time server: two pure functions, no declared effect of any kind.")


# ==========================================================================
# Desktop Commander (npm @wonderwhy-er/desktop-commander): widely used third-party server
# ==========================================================================

def dc_sandbox(seed: int) -> Sandbox:
    sb = fresh_sandbox("desktop-commander", seed)
    (sb.work / "sub").mkdir()
    sb.meta["train_files"] = [str(p) for p in _seed_files(sb.work, WORDS_TRAIN)]
    sb.meta["held_files"] = [str(p) for p in _seed_files(sb.work / "sub", WORDS_HELD)]
    (sb.root / "outside").mkdir()
    (sb.root / "outside" / "secret.txt").write_text("outside the allowed directory\n")
    return sb


def dc_command(sb: Sandbox):
    return (["node", str(NODE_DC / "dist" / "index.js")], str(sb.root), {})


def dc_setup(sb: Sandbox, seed: int) -> list[Action]:
    # the operator restricts the server to the work directory, as the README recommends
    return [Action("set_config_value", {"key": "allowedDirectories", "value": [str(sb.work)]}, "operator setup")]


def _dc_actions(sb: Sandbox, seed: int, held: bool) -> list[Action]:
    rng = Random(seed * 907 + int(held))
    files = sb.meta["held_files" if held else "train_files"]
    words = WORDS_HELD if held else WORDS_TRAIN
    contents = CONTENT_HELD if held else CONTENT_TRAIN
    cmds = COMMANDS_HELD if held else COMMANDS_TRAIN
    base = sb.work / ("sub" if held else "")
    acts: list[Action] = []
    for i in range(8):
        w = words[i % len(words)]
        acts.append(Action("write_file", {"path": str(base / f"new-{w}-{i}.{'md' if i % 2 else 'txt'}"),
                                          "content": contents[i % len(contents)], "mode": "append" if i % 4 == 3 else "rewrite"}))
    for f in files[:6]:
        acts.append(Action("read_file", {"path": f}))
    for f in files[:4]:
        acts.append(Action("get_file_info", {"path": f}))
    acts.append(Action("read_multiple_files", {"paths": files[6:8]}))
    acts.append(Action("list_directory", {"path": str(base), "depth": 1}))
    acts.append(Action("list_directory", {"path": str(sb.work), "depth": 2}))
    for i in range(3):
        acts.append(Action("create_directory", {"path": str(base / f"dir-{words[i]}-{i}")}))
    for i in range(3):
        src = files[i]
        acts.append(Action("move_file", {"source": src, "destination": str(Path(src).with_name(f"moved-{words[i]}-{i}.txt"))}))
    for i in range(3):
        acts.append(Action("edit_block", {"file_path": files[4 + i], "old_string": "alpha line", "new_string": f"{words[i + 1]} line"}))
    for i, c in enumerate(cmds[:6]):
        acts.append(Action("start_process", {"command": c.format(f=files[i % len(files)], w=words[i % len(words)]), "timeout_ms": 5000}))
    acts.append(Action("list_sessions", {}))
    acts.append(Action("get_config", {}))
    acts.append(Action("get_usage_stats", {}))
    acts.append(Action("get_recent_tool_calls", {"maxResults": 5}))
    acts.append(Action("start_search", {"path": str(sb.work), "pattern": words[0], "searchType": "content", "timeout_ms": 3000}))
    acts.append(Action("start_search", {"path": str(sb.work), "pattern": "*.md", "searchType": "files", "timeout_ms": 3000}))
    acts.append(Action("list_searches", {}))
    acts.append(Action("read_file", {"path": "https://example.org/held.txt" if held else "https://example.com/train.txt", "isUrl": True},
                       "URL input: network is the declared way to read it"))
    rng.shuffle(acts)
    return acts


DESKTOP_COMMANDER = ServerSpec(
    name="desktop_commander", kind="third_party", source="npm @wonderwhy-er/desktop-commander@0.3.1",
    make_sandbox=dc_sandbox, build_command=dc_command, watched_roots=lambda sb: [str(sb.root)],
    train_actions=lambda sb, s: _dc_actions(sb, s, False), heldout_actions=lambda sb, s: _dc_actions(sb, s, True),
    install_files=lambda: [str(NODE_DC / "dist")], setup_actions=dc_setup,
    description="Desktop Commander, a widely installed third-party file/terminal server, restricted by the operator to the work directory.")


# ==========================================================================
# obsidian-mcp (npm obsidian-mcp 2.0.1): third-party note server over a vault directory
# ==========================================================================

def obsidian_sandbox(seed: int) -> Sandbox:
    sb = fresh_sandbox("obsidian", seed)
    vault = sb.work / "notes"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "projects").mkdir()
    (vault / "archive").mkdir()
    train, held = [], []
    for i, w in enumerate(WORDS_TRAIN[:8]):
        p = vault / "projects" / f"{w}.md"
        p.write_text(f"# {w}\n\nalpha line about {w}. See [[{WORDS_TRAIN[(i + 1) % 8]}]].\n")
        train.append(f"projects/{w}.md")
    for i, w in enumerate(WORDS_HELD[:8]):
        p = vault / "archive" / f"{w}.md"
        p.write_text(f"# {w}\n\nbeta line about {w}. See [[{WORDS_HELD[(i + 1) % 8]}]].\n")
        held.append(f"archive/{w}.md")
    sb.meta["vault"] = str(vault)
    sb.meta["vault_id"] = "notes"
    sb.meta["train_notes"], sb.meta["held_notes"] = train, held
    return sb


def obsidian_command(sb: Sandbox):
    return (["node", str(NODE_OBSIDIAN / "dist" / "main.js"), sb.meta["vault"]], str(sb.root), {})


def _obsidian_actions(sb: Sandbox, seed: int, held: bool) -> list[Action]:
    rng = Random(seed * 1009 + int(held))
    v = sb.meta["vault_id"]
    notes = sb.meta["held_notes" if held else "train_notes"]
    words = WORDS_HELD if held else WORDS_TRAIN
    contents = CONTENT_HELD if held else CONTENT_TRAIN
    folder = "archive" if held else "projects"
    acts: list[Action] = [Action("obsidian_list_vaults", {})]
    body: list[Action] = []
    for i in range(4):
        body.append(Action("obsidian_create_note", {"vault": v, "path": f"{folder}/new-{words[i + 8]}.md", "content": f"# {words[i + 8]}\n\n{contents[i]}\n"}))
    for n in notes[:4]:
        body.append(Action("obsidian_read_note", {"vault": v, "path": n}))
    for i in range(3):
        body.append(Action("obsidian_edit_note", {"vault": v, "path": notes[i], "operation": ["append", "prepend", "replace"][i],
                                                  "content": f"{contents[i + 4]}\n"}))
    body.append(Action("obsidian_search_vault", {"vault": v, "query": words[1], "mode": "content"}))
    body.append(Action("obsidian_search_vault", {"vault": v, "query": words[2], "mode": "filename"}))
    body.append(Action("obsidian_create_directory", {"vault": v, "path": f"{folder}/dir-{words[3]}"}))
    body.append(Action("obsidian_add_tags", {"vault": v, "paths": [notes[4], notes[5]], "tags": [f"topic/{words[4]}"]}))
    body.append(Action("obsidian_move_note", {"vault": v, "source": notes[6], "destination": f"{folder}/moved-{words[6]}.md"}, "a note other notes link to"))
    body.append(Action("obsidian_delete_note", {"vault": v, "path": notes[7], "mode": "trash", "reason": f"{words[7]} obsolete"}))
    body.append(Action("obsidian_delete_note", {"vault": v, "path": notes[3], "mode": "permanent", "confirm_path": notes[3]}))
    rng.shuffle(body)
    return acts + body


OBSIDIAN = ServerSpec(
    name="obsidian", kind="third_party", source="npm obsidian-mcp@2.0.1 (StevenStavrakis)",
    make_sandbox=obsidian_sandbox, build_command=obsidian_command, watched_roots=lambda sb: [str(sb.root)],
    train_actions=lambda sb, s: _obsidian_actions(sb, s, False), heldout_actions=lambda sb, s: _obsidian_actions(sb, s, True),
    install_files=lambda: [str(NODE_OBSIDIAN / "dist")],
    description="Third-party Obsidian vault server with transactional edits, backlink updates and an 'MCP trash'.")


TARGETS = {s.name: s for s in (FILESYSTEM, GIT, SQLITE, MEMORY, EVERYTHING, FETCH, TIME,
                                MSB_TERMINAL_NORMAL, MSB_TERMINAL_TOOL_TRANSFER,
                                MSB_TERMINAL_OUT_OF_SCOPE_PARAMETER, MSB_TERMINAL_FALSE_ERROR,
                                DESKTOP_COMMANDER, OBSIDIAN)}
FIRST_SLICE = ("filesystem", "git", "sqlite", "msb_terminal_normal", "msb_terminal_tool_transfer")
