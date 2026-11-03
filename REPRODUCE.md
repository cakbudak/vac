# Reproduction

## Offline verification

Python 3.11 or newer and the pinned PyYAML dependency. On Linux or macOS, from the package root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-verify.txt
bash VERIFY.sh
```

`VERIFY.sh` runs, from the package root:

```bash
python3 -m unittest discover -s runtime/tests -v          # guard, MCP proxy, state policy, network scoping, ledger
python3 evidence/verify_grading.py                         # every stored label regraded from its raw receipt
python3 real-mcp/pilot2/verify_pilot2.py --report          # every summary against its receipts, the pilot report against the summaries
python3 real-mcp/analysis/git_index_history_predicate.py   # git controller report from the receipts
python3 real-mcp/analysis/guarded_report.py                # guarded run report from the receipts
python3 research/state_eval.py                             # state-feature selection
python3 research/network_scope_eval.py                     # call-scoped network declarations on the recorded receipts
python3 contract-study/evaluate.py                         # contract-authoring comparison
python3 static-scan/compare.py                             # static-versus-dynamic comparison
(cd agentdojo-study && python3 vac_study/verify_release.py)  # every number of the synthetic study
python3 evidence/check_manifest.py                         # every file against SHA256SUMS.txt
```

Each generator rewrites its report from the receipts; the manifest check runs last, so any report that does not regenerate byte for byte fails it.

## Live runs on real MCP servers

Linux with network namespaces and `CAP_NET_ADMIN`, `tcpdump`, `iproute2`, Node 22, `uv` and Python 3.13. The harness under `real-mcp/pilot2/` is frozen: its digest is recorded in every summary and recomputes from the shipped files. Run untrusted servers only inside an isolation boundary such as the harness's network namespace.

```bash
cd real-mcp
export VAC_SUBMISSION_DIR="$PWD/../agentdojo-study"
bash scripts/setup_env.sh
bash scripts/setup_additional_servers.sh
.venv/bin/python pilot2/run_pilot.py --seeds 1,2,3                                   # thirteen servers -> results2/
.venv/bin/python pilot2/report.py                                                    # -> PILOT2_RESULTS.md
.venv/bin/python analysis/history_predicate_run.py --seeds 7,8,9 --paired-seed 10    # git controller run
.venv/bin/python analysis/guarded_run.py --seeds 32-41                               # frozen controllers and the enforcing proxy
python3 pilot2/verify_pilot2.py --report
```

Agent traffic (`pilot2/agent_traffic.py`) and the contract and static studies need an OpenAI-compatible model endpoint; each run writes its manifest with the provider-reported model identity before the first call.

## The enforcing proxy in front of any stdio MCP server

```bash
python3 -m runtime.mcp_proxy --pin runtime/pins/git.json --policy git-index-state \
    --ledger decisions.jsonl --log decisions-detail.jsonl \
    --installation-path <site-packages>/mcp_server_git --installation-base <servers dir> \
    --contract real-mcp/contracts/git.yaml -- mcp-server-git -r <repo>
```

The client is configured with this command in place of the server's. Calls that are not allowed are answered by the proxy with an MCP error result and never reach the server.

## Synthetic AgentDojo / CaMeL study

```bash
cd agentdojo-study
bash scripts/setup_env.sh
bash REPRODUCE.sh
```

AgentDojo 0.1.35 comes from PyPI and CaMeL is fetched at commit `f083b6b`; neither is modified. The live CaMeL matrices are re-run against a model endpoint and verified against their manifests and final state by `vac_study/verify_live.py`.

## Integrity and licensing

`SHA256SUMS.txt` covers every file except itself. Apache-2.0 for code; CC BY 4.0 for original text and data; upstream dependencies are installed separately.
