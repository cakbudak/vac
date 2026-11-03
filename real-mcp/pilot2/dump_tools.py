"""Step 1 of the second slice: record each target server's tools/list verbatim, plus the
start-up behaviour the harness sees before any tool is called (files created, network
attempts).  This is the "documentation" the declared contracts are written from.  No
tool is called here; contracts must exist before the first probe.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from targets import TARGETS  # noqa: E402
from harness import open_session, cleanup_stale_namespaces  # noqa: E402
from observe import snapshot, diff  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "contracts"


async def dump(name: str):
    spec = TARGETS[name]
    sandbox = spec.make_sandbox(0)
    before = snapshot([str(sandbox.root)], (str(sandbox.pidfile), str(sandbox.root / "server.stderr.log"), str(sandbox.root / "net.capture.txt")))
    async with open_session(spec, sandbox) as live:
        tools = await live.session.list_tools()
        await asyncio.sleep(1.0)
        startup_net = list(live.background_net) + [dict(a, phase="startup_late") for a in (live.net.drain() if live.net else [])]
    after = snapshot([str(sandbox.root)], (str(sandbox.pidfile), str(sandbox.root / "server.stderr.log"), str(sandbox.root / "net.capture.txt")))
    rows = [{"name": t.name, "description": t.description,
             "inputSchema": getattr(t, "input_schema", None) or getattr(t, "inputSchema", None),
             "annotations": (t.annotations.model_dump() if getattr(t, "annotations", None) else None)}
            for t in tools.tools]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.tools.json").write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    startup = {"fs": diff(before, after), "net": startup_net}
    (OUT / f"{name}.startup.json").write_text(json.dumps(startup, indent=2, sort_keys=True, default=str) + "\n")
    print(name, len(rows), "tools:", ", ".join(r["name"] for r in rows))
    print("   start-up fs:", {k: len(v) for k, v in startup["fs"].items()}, "net attempts:", len(startup_net),
          sorted({a.get("qname") or a.get("dst") or a.get("host") for a in startup_net})[:8])


async def main(names):
    cleanup_stale_namespaces()
    for n in names:
        try:
            await dump(n)
        except Exception as exc:  # report, continue with the next server
            print(n, "FAILED:", type(exc).__name__, str(exc)[:300])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or list(TARGETS)))
