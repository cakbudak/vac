# Real MCP servers under the VAC harness

This directory holds the probe harness for real, unmodified MCP servers, everything it recorded,
the git controller studies and the guarded run with the enforcing proxy.  It answers on tools
nobody on the team wrote, running live with state that cannot be deep-copied, what the synthetic
AgentDojo study (`../agentdojo-study/`) isolates as mechanisms.

| Run | Code | Targets | Seeds | Results | Report |
|---|---|---|---|---|---|
| reported run | `pilot2/run_pilot.py` | 13 | 3 | `results2/` | `PILOT2_RESULTS.md` |
| agent traffic | `pilot2/agent_traffic.py` | 7 | 1 per model, 4 models | `results2_agent/` | `PILOT2_RESULTS.md` §5 |
| second machine | `pilot2/run_pilot.py` | 13 | 3 | `results2_second_machine/` | `../research/NETWORK_SCOPE_RESULTS.md`, `verify_pilot2.py` |
| history-predicate test, scripted | `pilot2/run_pilot.py`, git | 1 | 4–9 | `results_history_predicate/scripted/` | `analysis/GIT_INDEX_HISTORY_PREDICATE.md` §2–§3 |
| controller run | `analysis/history_predicate_run.py` | 1 | 7–9 + paired probes (10) | `results_history_predicate/controller/` | `analysis/GIT_INDEX_HISTORY_PREDICATE.md` §3 |
| history-predicate test, agent | `pilot2/agent_traffic.py`, git | 1 | 2 attempts (provider timeouts; manifests kept) | `results_history_predicate/agent/` | `analysis/GIT_INDEX_HISTORY_PREDICATE.md` §4 |
| guarded run | `analysis/guarded_run.py` | 1 | 32–41, shadow and enforce | `results_guarded/` | `analysis/GUARDED_RUN.md` |

`PREDICTIONS.md` holds the predictions written before each run: §1 for the reported run (before
the first probe), §2 for the history-predicate test (before seeds 4–6), §3 the amendment written
after seeds 4–6 and before the controller run.  `CONTRACT_CHANGES.md` logs every contract
correction made after a probe, with its trigger and its effect on the numbers.  `PILOT2_RESULTS.md`
is generated from the summaries by `pilot2/report.py`; `pilot2/verify_pilot2.py` recomputes every
summary from the receipts, checks every receipt's digest and regenerates the report.  The two
analysis reports are generated from the receipts by `analysis/git_index_history_predicate.py` and
`analysis/guarded_report.py`.

The harness under `pilot2/` is frozen: every summary records its digest, which recomputes from
the shipped `pilot2/*.py`; the directory names `pilot2/` and `results*/` and the report title are
constants of that code.  The reported run, the history-predicate runs, the controller run and the
guarded run share this revision; the second-machine and agent runs record their harness revision
in each summary.  On the second machine 12 of the 13 servers reproduce call for call; Desktop
Commander differs in its timing-dependent telemetry counts and in its served-definition digest
(the served description embeds the host name).

## What was run

| Target | Origin | Why it is in the set |
|---|---|---|
| `filesystem`, `git`, `sqlite` | official reference servers (npm / PyPI) | honest references with rich file state |
| `memory`, `everything`, `fetch`, `time` | official reference servers | the remaining official servers that run locally over stdio: a JSON-file knowledge graph, a response-only protocol test server (one tool fetches a URL), a network-only tool, two pure functions |
| `msb_terminal_normal` | Terminal Controller from MSB (ICLR 2026) | third-party server, unmodified |
| `msb_terminal_tool_transfer`, `msb_terminal_false_error` | its MSB attack variants | documented tools that redirect or answer with an injected instruction instead of acting; `false_error` is MSB's `out_of_scope_parameter` script started with the `false_error` attack argument (`pilot2/targets.py`), so it serves the same definition as that variant |
| `msb_terminal_out_of_scope_parameter` | its MSB attack variant | tools that behave but harvest an extra parameter: a mismatch visible only in the served definition |
| `desktop_commander` | `@wonderwhy-er/desktop-commander` 0.3.1 (npm) | widely installed third-party file/terminal server with configuration, logs and telemetry |
| `obsidian` | `obsidian-mcp` 2.0.1 (npm) | third-party note server with transactions, backlink updates and an "MCP trash" |

Selection rule, fixed before any probe: every official reference server that runs locally over
stdio; MSB variants whose *effect* differs from the honest server in a documented way, plus one
whose definition differs; two widely used third-party servers with local state.  No public
third-party tool with a conditional, input-dependent hidden effect was found.

## How it works

1. **Contracts from documentation first.**  `pilot2/dump_tools.py` records `tools/list` verbatim
   (`contracts/*.tools.json`) and the server's start-up behaviour before any call
   (`contracts/*.startup.json`).  The declared contracts (`contracts/*.yaml`) are written from the
   descriptions, the annotations and the README, with a `doc_sufficient` flag per tool, notes
   wherever knowledge of the underlying system had to be added, and a `readme_declared` section for
   effects the README documents that no tool description mentions.  The grader reports deviations
   at both documentation levels.
2. **Isolation with full visibility.**  Each server runs in its own network namespace connected to
   the harness by one veth pair and nothing else; the harness side runs the logging, refusing proxy
   and is the server's default route and name server; it never forwards.  `tcpdump` on the veth
   records every DNS query and TCP SYN the server emits (`pilot2/harness.py`).  Attempts outside a
   call window (start-up, background timers) are recorded at session level.
3. **Probes on a live server, in traffic order.**  Fresh sandbox per seed (own HOME, TMPDIR, XDG
   dirs).  Nothing is cloned.
4. **Observation channels** (`pilot2/observe.py`, `pilot2/procmon.py`): before/after content
   snapshots of the sandbox; every fork and exec in the server's process tree from the kernel's
   process connector; sockets of the server's namespace; the proxy log; the packet capture; the
   tool's own response.
5. **Grading** (`pilot2/contracts.py`): `fs_outside_scope`, `fs_change_by_readonly_tool`,
   `fs_undeclared`, `undeclared_subprocess`, `undeclared_network`, `network_outside_scope`,
   `declared_effect_absent`; a response that redirects the caller is flagged separately as a
   heuristic.
6. **The frozen learner** (`pilot2/learner_bridge.py`): `JuntaVersionSpace` and `Witness` imported
   unchanged from the AgentDojo package (digests in every summary); a label-free predicate
   vocabulary induced from the training calls' arguments; traffic-order acquisition.  Labels are the
   grader's README-level deviations.
7. **Held-out traffic**: scripted (new names, contents, commands, seeds) or produced by a
   language-model agent working on six user-style tasks (`pilot2/agent_traffic.py`).  The verdict is
   recorded before the action executes; the outcome is graded from state afterwards.
8. **The controller run on git** (`analysis/history_predicate_run.py`): the same frozen harness,
   driven by the pilot's traffic generator for new seeds and by a fixed sequence of paired probes;
   before every read-only call it records the verdict of three predicates a controller can
   evaluate from what it has seen — two over call history and one that reads `.git/index` before
   the call — and afterwards the receipt is graded by the same grader as everywhere else.
9. **The guarded run** (`analysis/guarded_run.py`): the same frozen harness on ten new seeds, first in
   shadow mode with four controllers fixed in `results_guarded/manifest.json` before the first call,
   then with `../runtime/mcp_proxy.py` between the harness client and the unmodified server, pinned
   to the reported run's revision and enforcing S before every call.

## Results in one paragraph

Every number is in `PILOT2_RESULTS.md` (§6 there is the feasibility map) and in the two analysis
reports.  Two of the eight newly added servers deviated from their documented contract at README
level: Desktop Commander on nearly every call (an undocumented `python3 --version` subprocess on
every one of 267 calls; DNS lookups of a telemetry host and of an undocumented fallback host on
Google Cloud Run; at start-up a Chrome download, a feature-flag fetch and a configuration file),
and MSB's `false_error` variant on every call.  obsidian-mcp and Desktop Commander write journals,
logs and configuration that only the README declares.  The git server's read-only tools rewrote
`.git/index` in every seed.  On honest servers the frozen lexical learner reviewed 81 % of
held-out calls on the filesystem server, 57 % on sqlite, 42 % on obsidian and 58 % on time, and on
git it emptied its version space or allowed the rewrite.  The isolated network recorded 104
attempts by Desktop Commander outside any call over three seeds, and none by any other server.
The state predicate S, which reads `.git/index` before the call, decided all 85 read-only calls of
the controller run (12 of 12 rewrites flagged, no review without a rewrite) and, frozen, all 220
of the guarded run's ten new seeds (17 of 17); behind the enforcing proxy it held 65 of 480 calls,
none of which reached the server, and no read-only call rewrote the index.

## Reproduce

```bash
bash scripts/setup_env.sh && bash scripts/setup_additional_servers.sh     # node + python environments, MSB clone
.venv/bin/python pilot2/dump_tools.py                        # tools/list and start-up of every target -> contracts/
.venv/bin/python pilot2/run_pilot.py --seeds 1,2,3            # all thirteen targets -> results2/<server>/seed-<k>/
.venv/bin/python pilot2/agent_traffic.py --model <alias>      # agent traffic (needs an OpenAI-compatible endpoint)
.venv/bin/python pilot2/report.py                             # -> PILOT2_RESULTS.md
python3 pilot2/verify_pilot2.py --report                      # summaries against receipts, report against summaries (stdlib only)

# the history-predicate test on git (PREDICTIONS.md §2-§3)
.venv/bin/python pilot2/run_pilot.py --seeds 4,5,6,7,8,9 --results results_history_predicate/scripted git
.venv/bin/python analysis/history_predicate_run.py --seeds 7,8,9 --paired-seed 10 --results results_history_predicate/controller
.venv/bin/python pilot2/agent_traffic.py --model <alias> --servers git --results results_history_predicate/agent
python3 analysis/git_index_history_predicate.py              # -> analysis/GIT_INDEX_HISTORY_PREDICATE.md, from the receipts (stdlib only)

# the guarded run: frozen controllers on new seeds, then the enforcing proxy
.venv/bin/python analysis/guarded_run.py --seeds 32-41 --results results_guarded
python3 analysis/guarded_report.py                           # -> analysis/GUARDED_RUN.md, from the receipts (stdlib only)
```

The verifier and the analysis run on any platform; on Windows set `PYTHONUTF8=1` first, because the
report contains characters outside the console code page.  Running the harness itself needs Linux.

`VAC_SUBMISSION_DIR` must point at `../agentdojo-study/` (the frozen learner is imported from it).
Needs Linux with `/proc`, root with `CAP_NET_ADMIN` in the initial network namespace for the kernel
process connector and the namespaces, `tcpdump`, `iproute2`, Node 22, `uv`, Python 3.13; every
receipt records which channels were active.  Model runs are re-run rather than replayed; every
other result regenerates from its receipts.

## Scope

The samples, channels and the work package that extends each are described in `../LIMITATIONS.md`.
