"""Enforcing MCP stdio proxy: the VAC guard in front of an unmodified server.

    python3 -m runtime.mcp_proxy --pin runtime/pins/git.json --policy git-index-state \
        --ledger decisions.jsonl --installation-path <installed package> --installation-base <servers dir> \
        --contract real-mcp/contracts/git.yaml -- mcp-server-git -r <repo>

The client talks to the proxy exactly as to the server.  The proxy reads the served
definition from the server's own `tools/list` and attests the installation and the contract
it was started with.  Every `tools/call` is decided by `runtime.guard.authorize` before it is
forwarded: the client's existing boundary first, then the revision attestation against the
pin, then the effect policy evaluated on pre-call state.  The decision is fsynced to the
hash-chained ledger before the request leaves the proxy.  A call that is not allowed is
answered by the proxy with an MCP error result and never reaches the server.  A served
definition that changes during the session moves every later call to review.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from runtime.decision_ledger import Ledger  # noqa: E402
from runtime.guard import Evidence, Revision, authorize  # noqa: E402
from runtime.state_policy import POLICIES  # noqa: E402

PRIVATE_ID = "vac-proxy-tools-list"


def served_definition_digest(tools: list[dict]) -> str:
    """Digest of a served `tools/list`, canonical across client libraries (wire camelCase or model dump)."""
    rows = []
    for t in tools:
        a = t.get("annotations")
        if a is not None:
            a = {"title": a.get("title"),
                 "read_only_hint": a.get("readOnlyHint", a.get("read_only_hint")),
                 "destructive_hint": a.get("destructiveHint", a.get("destructive_hint")),
                 "idempotent_hint": a.get("idempotentHint", a.get("idempotent_hint")),
                 "open_world_hint": a.get("openWorldHint", a.get("open_world_hint"))}
        rows.append({"name": t.get("name"), "description": t.get("description"),
                     "inputSchema": t.get("inputSchema", t.get("input_schema")), "annotations": a})
    return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


def installation_digest(paths: list[str], base: str | None) -> str:
    """Relative paths plus content hashes of the installed implementation (as in the pilot harness)."""
    h = hashlib.sha256()
    for p in sorted(paths):
        pp = Path(p)
        files = sorted(x for x in pp.rglob("*") if x.is_file() and "__pycache__" not in x.parts) if pp.is_dir() else [pp]
        for f in files:
            try:
                rel = str(f.relative_to(base)) if base else f.name
            except ValueError:
                rel = f.name
            h.update(rel.encode()); h.update(b"\0")
            h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()


def contract_digest(path: str) -> str:
    import yaml  # PyYAML, pinned in requirements-verify.txt
    raw = yaml.safe_load(Path(path).read_text())
    return hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()


class Proxy:
    def __init__(self, args: argparse.Namespace) -> None:
        pin = json.loads(Path(args.pin).read_text())
        self.pinned = Revision(pin["installation"], pin["served_definition"], pin["contract"])
        self.installation = installation_digest(args.installation_path, args.installation_base) if args.installation_path else ""
        self.contract = contract_digest(args.contract) if args.contract else ""
        self.served: str | None = None
        self.served_first: str | None = None
        self.policy = POLICIES[args.policy]
        self.allowed_tools = set(args.allow_tool) if args.allow_tool else None
        self.ledger = Ledger(args.ledger)
        self.log = Path(args.log) if args.log else None
        self.server_argv = args.server
        self.out_lock = asyncio.Lock()
        self.served_ready = asyncio.Event()
        self.initialized = False

    # ------------------------------------------------------------------ io
    async def write_client(self, msg: dict) -> None:
        async with self.out_lock:
            sys.stdout.buffer.write((json.dumps(msg, separators=(",", ":")) + "\n").encode())
            sys.stdout.buffer.flush()

    async def write_server(self, msg: dict | bytes) -> None:
        data = msg if isinstance(msg, bytes) else (json.dumps(msg, separators=(",", ":")) + "\n").encode()
        self.proc.stdin.write(data)
        await self.proc.stdin.drain()

    def note(self, record: dict) -> None:
        if self.log is not None:
            with self.log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, sort_keys=True, default=str) + "\n")

    # ------------------------------------------------------------ decisions
    def observe_served(self, tools: list[dict]) -> None:
        d = served_definition_digest(tools)
        if self.served_first is None:
            self.served_first = d
        # drift within a session invalidates the attestation for the rest of it
        self.served = d if d == self.served_first else "drift:" + d
        self.served_ready.set()

    def decide(self, tool: str, arguments: dict[str, Any]):
        verdict, state = self.policy(tool, arguments)
        observed = Revision(self.installation, self.served or "", self.contract)
        decision = authorize(tool=tool, arguments=arguments,
                             base_allows=lambda t, a: self.allowed_tools is None or t in self.allowed_tools,
                             pinned=self.pinned, evidence=Evidence(verdict, observed))
        return decision, verdict, state, observed

    async def on_client(self, line: bytes) -> None:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            await self.write_server(line)
            return
        if msg.get("method") == "notifications/initialized" and not self.initialized:
            self.initialized = True
            await self.write_server(line)
            await self.write_server({"jsonrpc": "2.0", "id": PRIVATE_ID, "method": "tools/list", "params": {}})
            return
        if msg.get("method") != "tools/call" or "id" not in msg:
            await self.write_server(line)
            return
        if self.initialized:
            await self.served_ready.wait()
        params = msg.get("params") or {}
        tool, arguments = params.get("name", ""), params.get("arguments") or {}
        decision, verdict, state, observed = self.decide(tool, arguments)
        chain = self.ledger.append(decision, tool, arguments)          # fsynced before anything leaves
        self.note({"sequence": self.ledger.count - 1, "chain": chain, "tool": tool, "decision": decision.kind,
                   "reason": decision.reason, "effect_verdict": verdict, "state_before": state,
                   "revision_observed": observed.__dict__, "forwarded": decision.kind == "allow"})
        if decision.kind == "allow":
            await self.write_server(line)
            return
        await self.write_client({"jsonrpc": "2.0", "id": msg["id"], "result": {
            "content": [{"type": "text", "text": f"VAC guard: call held ({decision.kind}): {decision.reason}"}],
            "isError": True, "_meta": {"vac": {"decision": decision.kind, "reason": decision.reason, "ledger": chain}}}})

    async def on_server(self, line: bytes) -> None:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            async with self.out_lock:
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
            return
        tools = (msg.get("result") or {}).get("tools") if isinstance(msg.get("result"), dict) else None
        if msg.get("id") == PRIVATE_ID:
            self.observe_served(tools or [])
            return
        if tools is not None:
            self.observe_served(tools)
        await self.write_client(msg)

    # ----------------------------------------------------------------- run
    async def run(self) -> int:
        self.proc = await asyncio.create_subprocess_exec(*self.server_argv, stdin=asyncio.subprocess.PIPE,
                                                         stdout=asyncio.subprocess.PIPE)
        loop = asyncio.get_running_loop()
        reader = asyncio.StreamReader(limit=1 << 24)
        await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)

        async def client_side():
            while line := await reader.readline():
                await self.on_client(line)
            self.proc.stdin.close()

        async def server_side():
            while line := await self.proc.stdout.readline():
                await self.on_server(line)

        await asyncio.gather(client_side(), server_side())
        return await self.proc.wait()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pin", required=True, help="JSON with installation, served_definition and contract digests")
    ap.add_argument("--policy", default="git-index-state", choices=sorted(POLICIES))
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--log", help="JSONL with each decision's state and attestation")
    ap.add_argument("--installation-path", action="append", default=[])
    ap.add_argument("--installation-base")
    ap.add_argument("--contract")
    ap.add_argument("--allow-tool", action="append", help="the client's existing boundary (default: every served tool)")
    ap.add_argument("server", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    if args.server and args.server[0] == "--":
        args.server = args.server[1:]
    if not args.server:
        ap.error("server command missing after --")
    return asyncio.run(Proxy(args).run())


if __name__ == "__main__":
    sys.exit(main())
