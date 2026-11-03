#!/usr/bin/env bash
# Offline verification of the VAC research package: tests, every verifier, every generated report.
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
echo "== Guard, MCP proxy, state policy, network scoping and ledger tests =="
"$PY" -m unittest discover -s runtime/tests -v
echo "== Regrade every receipt against the shipped contracts =="
"$PY" evidence/verify_grading.py
echo "== Recompute the scripted and agent summaries and the pilot report =="
"$PY" real-mcp/pilot2/verify_pilot2.py --report
echo "== Recompute the git controller report =="
"$PY" real-mcp/analysis/git_index_history_predicate.py > /dev/null
echo "== Recompute the guarded run (frozen controllers on new seeds, enforcing proxy) =="
"$PY" real-mcp/analysis/guarded_report.py
echo "== Recompute the state-feature selection =="
"$PY" research/state_eval.py > /dev/null
echo "== Recompute call-scoped network declarations =="
"$PY" research/network_scope_eval.py > /dev/null
echo "== Recompute the contract-authoring and static-scan comparisons =="
"$PY" contract-study/evaluate.py > /dev/null
"$PY" static-scan/compare.py > /dev/null
echo "== Assert the synthetic study's numbers =="
(cd agentdojo-study && "$PY" vac_study/verify_release.py)
echo "== Check the complete file manifest =="
"$PY" evidence/check_manifest.py
echo "PASS: offline VAC verification"
