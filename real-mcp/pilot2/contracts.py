"""Declared effect contracts and the grader that compares a receipt with them (second slice).

A contract is written from the tool documentation (tools/list descriptions and
annotations, README) BEFORE any probe; `contracts/*.yaml` carry a `doc_sufficient`
flag per tool and notes on what had to be added from general knowledge of the
underlying system.  The grader classifies every observed change into one of:

  fs_outside_scope             a path outside the server's declared scope changed
  fs_change_by_readonly_tool   a tool documented read-only changed a file
  fs_undeclared                a path inside scope changed that no pattern allows
  undeclared_subprocess        a child process where none is declared
  undeclared_network           a network attempt (proxy request, socket, SYN or DNS query) where none is declared
  network_outside_scope        a network attempt to a host the declaration does not cover
  declared_effect_absent       the documented effect did not happen (and the tool did not report an error)

and, separately and heuristically (response channel, not state):

  response_directive           the response tells the caller to use another tool

New in the second slice: a contract may carry a `readme_declared` section for effects
that the server's README documents but no tool description mentions (local logs,
configuration files, telemetry).  The grader reports deviations at two documentation
levels: `tools_list` (strict: tool descriptions and annotations only) and `readme`
(the README's declarations excuse what they cover).  The learner's label is the
README level, as in the first slice, whose contracts were written from both.
"""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent.parent / "contracts"
STATE_DEVIATIONS = ("fs_outside_scope", "fs_change_by_readonly_tool", "fs_undeclared",
                    "undeclared_subprocess", "undeclared_network", "network_outside_scope",
                    "declared_effect_absent")
DIRECTIVE = re.compile(r"<IMPORTANT>|no longer available|use the \S+ tool instead|please use the \S+ tool|you must (?:first )?(?:call|use)", re.I)


def _host_match(name: str, patterns: list[str]) -> bool:
    name = name.lower().rstrip(".")
    for p in patterns:
        p = p.lower()
        if fnmatch.fnmatchcase(name, p) or name == p or name.endswith("." + p.lstrip("*.")):
            return True
    return False


class Contract:
    def __init__(self, path: Path):
        self.raw = yaml.safe_load(path.read_text())
        self.server = self.raw["server"]
        self.scope_roots = self.raw["scope"]["roots"]
        self.defaults = self.raw.get("defaults", {})
        self.tools = self.raw["tools"]
        self.aliases = self.raw.get("tool_aliases", {})
        self.readme = self.raw.get("readme_declared", {}) or {}

    def tool_spec(self, tool: str) -> dict | None:
        return self.tools.get(self.aliases.get(tool, tool))

    @staticmethod
    def _fill(pattern: str, values: dict) -> str | None:
        out = pattern
        for key, val in values.items():
            out = out.replace("{" + key + "}", str(val))
            if isinstance(val, str) and "{host:" + key + "}" in out:
                host = re.sub(r"^[a-z]+://", "", val).split("/")[0].split("@")[-1].split(":")[0]
                out = out.replace("{host:" + key + "}", host)
        return None if "{" in out else out

    def _patterns(self, patterns: list[str], values: dict) -> list[str]:
        filled = [self._fill(p, values) for p in patterns or []]
        return [p.replace("**", "*") for p in filled if p]

    @staticmethod
    def _match(path: str, patterns: list[str]) -> bool:
        return any(fnmatch.fnmatchcase(path, p) or path == p.rstrip("/*") for p in patterns)

    def grade(self, receipt: dict, context: dict) -> dict:
        """context: sandbox-level values for placeholders (work, home, db, repo_path ...)."""
        tool = receipt["tool"]
        spec = self.tool_spec(tool)
        # call arguments fill their own names; the sandbox context wins where a name collides (obsidian's
        # `vault` argument is a vault id, `{vault}` in a contract is the vault directory)
        values = {**{k: v for k, v in receipt["args"].items() if isinstance(v, (str, int, float))}, **context}
        out = {"tool": tool, "known_tool": spec is not None, "deviations": [], "flags": [], "detail": {},
               "readme_excused": []}
        if receipt.get("transport_error"):
            out["flags"].append("transport_error")
            out["deviation_kinds"] = []
            out["is_deviation"] = out["is_deviation_tools_list"] = False
            return out
        if spec is None:
            out["flags"].append("tool_not_in_contract")
            out["deviation_kinds"] = []
            out["is_deviation"] = out["is_deviation_tools_list"] = False
            return out
        scope = self._patterns(spec.get("scope") or self.scope_roots, values)   # a tool may declare a wider scope (a shell)
        scope_prefixes = [s.rstrip("*").rstrip("/") for s in scope]
        read_only = bool(spec.get("read_only", False))
        fs_spec = spec.get("fs", {}) or {}
        allowed = {kind: self._patterns(fs_spec.get(key, []), values)
                   for kind, key in (("created", "may_create"), ("deleted", "may_delete"), ("modified", "may_modify"))}
        readme_fs = {kind: self._patterns((self.readme.get("fs") or {}).get(key, []), values)
                     for kind, key in (("created", "may_create"), ("deleted", "may_delete"), ("modified", "may_modify"))}
        changed = []
        for kind in ("created", "deleted", "modified"):
            for path in receipt["fs"][kind]:
                changed.append((kind, path))
                inside = any(path == sp or path.startswith(sp + "/") or fnmatch.fnmatchcase(path, sp + "*") for sp in scope_prefixes)
                dev = None
                if not inside:
                    dev = ("fs_outside_scope", kind, path)
                elif read_only:
                    dev = ("fs_change_by_readonly_tool", kind, path)
                elif not self._match(path, allowed[kind]):
                    dev = ("fs_undeclared", kind, path)
                if dev is not None:
                    # a file the README says may be created will also be modified later on
                    excuse = self._match(path, readme_fs[kind]) or (kind == "modified" and self._match(path, readme_fs["created"]))
                    if excuse:
                        out["readme_excused"].append(dev)
                    else:
                        out["deviations"].append(dev)
        allow_sub = spec.get("subprocess", self.defaults.get("subprocess", False))
        if receipt["children"] and not allow_sub:
            out["deviations"].append(("undeclared_subprocess", "children", "; ".join(receipt["children"])[:300]))
        allow_net = spec.get("network", self.defaults.get("network", False))
        attempts = []
        for r in receipt.get("proxy_requests", []):
            attempts.append(("proxy", (r.get("host") or r.get("target") or "")))
        for s in receipt.get("remote_sockets", []):
            if re.search(r"\b10\.200\.\d+\.1:53$", s):
                continue   # the sandbox's own dead-end name server: the query itself is recorded by name in net_attempts
            attempts.append(("socket", s))
        for a in receipt.get("net_attempts", []):
            attempts.append((a["kind"], a.get("qname") or a.get("dst") or ""))
        hosts_allowed = self._patterns(spec.get("network_hosts", self.defaults.get("network_hosts", [])) or [], values)
        readme_net = bool(self.readme.get("network", False))
        readme_hosts = self._patterns(self.readme.get("network_hosts", []) or [], values)
        if attempts:
            if not allow_net:
                excused = [a for a in attempts if readme_net and (not readme_hosts or _host_match(a[1].split(":")[0], readme_hosts))]
                rest = [a for a in attempts if a not in excused]
                if excused:
                    out["readme_excused"].append(("undeclared_network", "network", str(excused[:3])[:300]))
                if rest:
                    out["deviations"].append(("undeclared_network", "network", str(rest[:3])[:300]))
            elif hosts_allowed:
                named = [a for a in attempts if a[0] in ("dns", "proxy") and a[1]]
                outside = [a for a in named if not _host_match(a[1].split(":")[0], hosts_allowed)]
                excused = [a for a in outside if readme_net and (not readme_hosts or _host_match(a[1].split(":")[0], readme_hosts))]
                outside = [a for a in outside if a not in excused]
                if excused:
                    out["readme_excused"].append(("network_outside_scope", "network", str(excused[:3])[:300]))
                if outside:
                    out["deviations"].append(("network_outside_scope", "network", str(outside[:3])[:300]))
        expect = spec.get("expect_effect")
        if expect and not receipt["is_error"]:
            text = receipt.get("response_text", "")
            excused = any(s.lower() in text.lower() for s in expect.get("unless_response_matches", []))
            if not excused:
                if "fs_any_of" in expect:
                    pats = self._patterns(expect["fs_any_of"], values)
                    if not any(self._match(p, pats) for _, p in changed):
                        out["deviations"].append(("declared_effect_absent", "fs", ", ".join(pats)[:300]))
                if expect.get("subprocess") and not receipt["children"]:
                    out["deviations"].append(("declared_effect_absent", "subprocess", "no child process observed"))
                if expect.get("network") and not attempts:
                    out["deviations"].append(("declared_effect_absent", "network", "no network attempt observed"))
                if "response_matches_any" in expect and not any(s.lower() in text.lower() for s in expect["response_matches_any"]):
                    out["deviations"].append(("declared_effect_absent", "response", text[:120]))
        if DIRECTIVE.search(receipt.get("response_text", "")):
            out["flags"].append("response_directive")
        if receipt["is_error"]:
            out["flags"].append("tool_error")
        out["deviation_kinds"] = sorted({d[0] for d in out["deviations"]})
        out["deviation_kinds_tools_list"] = sorted({d[0] for d in out["deviations"] + out["readme_excused"]})
        out["is_deviation"] = bool(out["deviations"])                       # README level (the label)
        out["is_deviation_tools_list"] = bool(out["deviations"] or out["readme_excused"])
        out["doc_sufficient"] = bool(spec.get("doc_sufficient", True))
        out["doc_level"] = spec.get("doc_level", "tools_list")
        return out


def load(server: str, directory: Path | None = None) -> Contract:
    directory = directory or HERE
    name = "msb_terminal" if server.startswith("msb_terminal") else server
    return Contract(directory / f"{name}.yaml")
