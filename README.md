# Verifiable Agent Control (VAC)

**Research package** · Cengizhan Akbudak (Vienna, Austria) · with Hamna Qaseem

Autonomous agents act through tools whose descriptions can omit what the tools do to files, processes, the network and their own state. **VAC builds verifiable effect contracts that connect what a tool declares, what isolated execution reveals, and what a controller may authorize before dispatch**, and it measures the cost of those decisions in held legitimate calls.

The package brings together instrumented studies of real MCP servers, state-aware controllers evaluated with verdicts recorded before execution, an enforcing guard that runs as an MCP proxy in front of unmodified servers, contract-authoring and static-analysis comparisons, a controlled AgentDojo/CaMeL study, the raw receipts and the verifiers that regenerate every reported number from them.

## Results

| Finding | Evidence |
|---|---|
| Real MCP behaviour mapped | **13 servers** (7 official reference servers, 4 variants of the MSB benchmark server, 2 widely installed third-party servers), **3 seeds, 1,683 graded calls**, file, process and network effects observed in a private network namespace |
| Cross-machine reproduction | **12 of 13** servers reproduce call for call on a second machine; Desktop Commander's asynchronous telemetry varies in count, not in kind |
| Declaration-to-effect gaps | an undeclared subprocess on every Desktop Commander call, DNS lookups of an undocumented telemetry host on 81 calls, `.git/index` rewritten by tools annotated read-only, journal and trash files that only obsidian-mcp's README declares, an attack parameter visible only in the served definition |
| State-aware pre-call decisions | a predicate that reads `.git/index` before the call flags **12 of 12** index rewrites over 85 read-only calls of the controller run and **17 of 17** over 220 read-only calls of ten new seeds, with no review of a call that did not rewrite |
| Feature selection | a depth-2 tree selected on two seeds flags **17 of 17** rewrites on the ten new seeds with 3 additional reviews; a per-tool baseline flags 12 of 17 with 68 |
| Enforcement on a live server | the guard as an MCP stdio proxy in front of the unmodified git server: **480 calls, 415 forwarded under an attested revision, 65 held**; no held call reached the server, no read-only call rewrote the index |
| Call-scoped network declarations | applied to the recorded receipts, they flag **81 of 81** calls that reached the undocumented telemetry host, including 8 that the tool-wide declaration excused |
| Contract authorship | contracts drafted by seven language models from the same documentation agree with the human contracts on read-only intent for 92–98 % of tools and differ on 13–46 % of call-level grades; execution is what qualifies them |
| Lexical learner on real servers | the frozen 2-junta learner of the synthetic study reviews 42–81 % of legitimate held-out calls on the file, database and note servers and cannot express the state-conditional rewrite — the measurement the state-aware design answers |
| Evidence integrity | every label, summary and report regenerated from its receipts by `VERIFY.sh`; **21 tests**; a hash manifest over every file |

## Research program

**WP1 — Conformance map:** at least 60 locally runnable MCP servers, documentation against observed effects, existing static and dynamic tools run beside the harness as comparators.

**WP2 — State-aware qualification:** pre-call state and history predicates for the state-conditional residue of the map, selected before the traffic they are scored on, against budget-matched baselines, with the review-resolution policy of the enforcing proxy as a measured parameter.

**WP3 — Independent confirmation:** the frozen controller on sealed hidden-effect tools produced by a second person, live agent executions and an independent outcome grader.

**Core invariant:** VAC narrows an existing security boundary and never widens it. Unknown effects and changed revisions are held for review.

## Read the research

1. [Research description](VAC_Research_Description.md) — problem, results, hypotheses, methods and closest work.
2. [Evidence](EVIDENCE.md) — every measurement and where it is regenerated.
3. [Scope](LIMITATIONS.md) — what the observation channels and samples cover, and the work package that extends each.
4. [Reproduction](REPRODUCE.md) — offline verification and the live runs.

The package is one evidence chain: `real-mcp/` (harness, receipts, controller and guarded runs), `runtime/` (guard, MCP proxy, state policy, network scoping, ledger), `research/` (feature selection, network scoping on receipts), `contract-study/` (contract authoring), `static-scan/` (static analysis), `agentdojo-study/` (controlled mechanisms and CaMeL), `evidence/` (verification), `governance/` (research protocol) and `disclosure/` (maintainer notices).

## Reproduce

Follow [REPRODUCE.md](REPRODUCE.md) for the pinned dependency. From the package root:

```bash
bash VERIFY.sh
```

**Licenses:** Apache-2.0 for code; CC BY 4.0 for original text and data. Upstream dependencies are installed separately.
