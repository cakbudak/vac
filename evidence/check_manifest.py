"""Verify the complete delivered package without importing third-party dependencies."""
from __future__ import annotations
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "SHA256SUMS.txt"
IGNORE_NAMES = {".DS_Store"}
IGNORE_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".venv", "node_modules", "Claude outputs"}


def included_files():
    for p in sorted(ROOT.rglob("*")):
        if p.is_file() and p != MANIFEST and not set(p.relative_to(ROOT).parts).intersection(IGNORE_DIRS) and p.name not in IGNORE_NAMES and p.suffix != ".pyc":
            yield p


def verify():
    if not MANIFEST.exists():
        raise RuntimeError("missing manifest")
    declared = {}
    for line in MANIFEST.read_text().splitlines():
        h, name = line.split("  ", 1)
        if name.startswith("./"):
            name = name[2:]
        if name in declared:
            raise ValueError(f"duplicate path: {name}")
        declared[name] = h
    actual = {}
    for p in included_files():
        name = p.relative_to(ROOT).as_posix()
        actual[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    missing = sorted(declared.keys() - actual.keys())
    extra = sorted(actual.keys() - declared.keys())
    bad = sorted(name for name in declared.keys() & actual.keys() if declared[name] != actual[name])
    print(f"manifest entries={len(declared)} actual files={len(actual)}; missing={len(missing)} extra={len(extra)} wrong hashes={len(bad)}")
    for category, group in (("missing", missing), ("extra", extra), ("wrong_hash", bad)):
        if group:
            print(category, group[:20])
    return 0 if not (missing or extra or bad) else 1


if __name__ == "__main__":
    raise SystemExit(verify())
