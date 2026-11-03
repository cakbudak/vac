"""Write or check SHA256SUMS.txt over every tracked file of the package."""
import argparse, hashlib, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE_DIRS = {".venv", "external", "__pycache__", ".pytest_cache", "logs", ".git", "scratch"}


def tracked():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in path.relative_to(ROOT).parts):
            continue
        rel = path.relative_to(ROOT).as_posix()
        if rel in ("SHA256SUMS.txt",) or rel.startswith("scratch_") or rel.endswith(".log") and "/" not in rel:
            continue  # transcripts written next to the package by setup/reproduce runs are not evidence
        yield rel


def digest(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true")
    p.add_argument("--check", action="store_true")
    a = p.parse_args()
    manifest = ROOT / "SHA256SUMS.txt"
    if a.write:
        manifest.write_text("".join(f"{digest(rel)}  ./{rel}\n" for rel in tracked()))
        print("wrote", manifest, "with", sum(1 for _ in tracked()), "entries")
        return
    expected = {}
    for line in manifest.read_text().splitlines():
        if line.strip():
            h, rel = line.split("  ./", 1)
            expected[rel] = h
    bad = [rel for rel, h in expected.items() if not (ROOT / rel).exists() or digest(rel) != h]
    missing = [rel for rel in tracked() if rel not in expected]
    if bad or missing:
        print("MANIFEST MISMATCH", {"changed_or_missing": bad, "untracked": missing}); sys.exit(1)
    print("PASS:", len(expected), "file hashes")


if __name__ == "__main__":
    main()
