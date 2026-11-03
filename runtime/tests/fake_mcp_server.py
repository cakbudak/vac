"""Minimal stdio MCP server for the proxy tests: records every tools/call it receives.

FAKE_TOOLS   JSON list of tool-list versions; the n-th tools/list returns version n (last one repeats)
FAKE_LOG     JSONL written for every tools/call that reaches the server
FAKE_LEDGER  the proxy's ledger; its line count at the moment the call arrives is logged
"""
import json
import os
import sys
from pathlib import Path

versions = json.loads(Path(os.environ["FAKE_TOOLS"]).read_text())
listed = 0


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    msg = json.loads(line)
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": mid, "result": {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                                                        "serverInfo": {"name": "fake", "version": "0"}}})
    elif method == "tools/list":
        send({"jsonrpc": "2.0", "id": mid, "result": {"tools": versions[min(listed, len(versions) - 1)]}})
        listed += 1
    elif method == "tools/call":
        ledger = Path(os.environ["FAKE_LEDGER"])
        with open(os.environ["FAKE_LOG"], "a") as f:
            f.write(json.dumps({"tool": msg["params"]["name"],
                                "ledger_lines": len(ledger.read_text().splitlines()) if ledger.exists() else 0}) + "\n")
        send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": "ok"}], "isError": False}})
    elif mid is not None:
        send({"jsonrpc": "2.0", "id": mid, "result": {}})
