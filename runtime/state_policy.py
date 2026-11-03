"""Pre-call state policies for the enforcing guard.

`git_index_state` is the state predicate S of the git controller study
(`real-mcp/analysis/history_predicate_run.py`), packaged for the guard: before a
worktree-statting read-only call it reads `.git/index` and answers `review` when an
entry carries zeroed stat data (what `git read-tree` leaves) or a smudged size, i.e.
when the call is about to rewrite the index although the tool is annotated read-only.
Every other call gets `allow` from this policy; the declared contract covers it.
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import Any, Mapping

WORKTREE_READERS = frozenset({"git_status", "git_diff_unstaged", "git_diff"})


def read_index(repo: Path) -> dict:
    """Entries of `.git/index` (versions 2 and 3) with their stat data."""
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
    entries, off = [], 12
    for _ in range(count):
        ctime_s, _cn, mtime_s, mtime_n, _dev, _ino, _mode, _uid, _gid, size = struct.unpack(">10I", data[off:off + 40])
        flags = struct.unpack(">H", data[off + 60:off + 62])[0]
        hdr = 62 + (2 if version == 3 and flags & 0x4000 else 0)
        name_len = flags & 0x0FFF
        name = data[off + hdr:off + hdr + name_len].decode("utf-8", "replace")
        entry_len = hdr + name_len
        entry_len += 8 - (entry_len % 8)
        off += entry_len
        entries.append({"path": name, "ctime": ctime_s, "mtime": mtime_s, "mtime_ns": mtime_n, "size": size})
    return {"version": version, "index_mtime": int(p.stat().st_mtime), "entries": entries}


def index_state(repo: Path) -> dict:
    idx = read_index(repo)
    if "error" in idx:
        return {"stale": None, "reason": idx["error"], "zero_stat": None, "smudged": None, "racy": None}
    zero = [e["path"] for e in idx["entries"] if e["ctime"] == 0 and e["mtime"] == 0]
    smudged, racy = [], []
    for e in idx["entries"]:
        try:
            st = (repo / e["path"]).stat()
        except FileNotFoundError:
            continue
        if e["size"] == 0 and st.st_size > 0:
            smudged.append(e["path"])
        if e["mtime"] >= idx["index_mtime"] and e["mtime"] != 0:
            racy.append(e["path"])
    stale = bool(zero or smudged)
    return {"stale": stale, "reason": "zeroed stat data" if zero else "smudged size" if smudged else "fresh",
            "zero_stat": len(zero), "smudged": len(smudged), "racy": len(racy), "entries": len(idx["entries"])}


def git_index_state(tool: str, arguments: Mapping[str, Any]) -> tuple[str, dict]:
    """(effect verdict, state read before the call) for one git tool call."""
    if tool not in WORKTREE_READERS:
        return "allow", {}
    repo = arguments.get("repo_path")
    if not isinstance(repo, str) or not repo:
        return "review", {"reason": "no repo_path"}
    state = index_state(Path(repo))
    if state["stale"] is None:
        return "review", state
    return ("review" if state["stale"] else "allow"), state


POLICIES = {"git-index-state": git_index_state}
