"""Hash-chained decision ledger, fsynced before dispatch.

Every record carries the hash of its predecessor, so `verify` detects any edited,
inserted or removed record.  `head()` is the chain head (records, hash) that is
handed to an external witness to fix the sequence up to that point.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from runtime.guard import Decision, digest


class Ledger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.last, self.count = self.verify(self.path)

    @staticmethod
    def verify(path: Path) -> tuple[str, int]:
        parent, count = "0" * 64, 0
        if not path.exists():
            return parent, count
        for line in path.read_text().splitlines():
            obj = json.loads(line)
            if obj["previous"] != parent:
                raise ValueError("broken hash chain")
            content = {k: obj[k] for k in ("previous", "sequence", "tool", "arguments_digest", "decision", "reason")}
            expected = digest(content)
            if obj["hash"] != expected or obj["sequence"] != count:
                raise ValueError("invalid decision record")
            parent, count = expected, count + 1
        return parent, count

    def head(self) -> tuple[int, str]:
        return self.count, self.last

    def append(self, decision: Decision, tool: str, arguments: dict[str, Any]) -> str:
        record = {
            "previous": self.last, "sequence": self.count, "tool": tool,
            "arguments_digest": digest(arguments),
            "decision": decision.kind, "reason": decision.reason,
        }
        record["hash"] = digest(record)
        # one writer per ledger file
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
            f.flush()
            os.fsync(f.fileno())
        self.last, self.count = record["hash"], self.count + 1
        return self.last
