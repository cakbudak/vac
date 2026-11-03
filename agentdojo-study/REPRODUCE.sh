#!/usr/bin/env bash
# Deterministic evidence and regression verification for the whole package.
# Live CaMeL/LLM episodes are checked semantically (verify_live), not token-replayed.
set -euo pipefail
cd "$(dirname "$0")"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
export PYTHONPATH="$(pwd)${PYTHONPATH:+:$PYTHONPATH}"
"$PY" -m pytest -q tests/ -p no:cacheprovider
"$PY" -m vac_study.verify
"$PY" -m vac_study.verify_extended
"$PY" -m vac_study.verify_release
"$PY" -m vac_study.verify_live results/camel_live_comparison.json results/live/*.jsonl
"$PY" -m vac_study.reproduce                       # original three studies, byte-identical
"$PY" scripts/reproduce_extended.py                # extended studies, byte-identical
"$PY" tests/camel_policy_smoke.py                  # unchanged CaMeL policy + VAC veto, no LLM
"$PY" -m vac_study.report --check                  # RESULTS.md is generated from the JSON evidence
"$PY" scripts/checksums.py --check
echo "VAC STUDY: ALL CHECKS PASSED"
