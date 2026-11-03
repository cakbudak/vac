# Verifiable Agent Control (VAC)
## Effect contracts for tools nobody has audited — research description

**Cengizhan Akbudak** · Vienna, Austria · cengiz@cakbudak.com · github.com/cakbudak/vac

VAC asks what a controller has to know about a tool's actual effects to decide a call, how much
of that knowledge can be obtained from documentation and from isolated execution for a tool the
controller did not write, what it costs in refused legitimate calls, and where the knowledge runs
out. The research package behind this description contains an instrument that answers the question
on real Model Context Protocol (MCP) servers — a probe harness that runs an unmodified server in an
isolated network namespace and grades its file, process and network effects against a contract
written from the server's own documentation — together with a proof of concept on thirteen public
servers, a study of language models as contract authors, a static-versus-dynamic comparison on the
same servers, agent-generated traffic from four models, a state-aware controller evaluated on new
traffic and enforced by an MCP proxy in front of the unmodified server, and a synthetic study on
the AgentDojo runtime with the unmodified CaMeL interpreter. Every number quoted here is regenerated from the
recorded receipts by the package's verifiers. In one sentence: we have measured where the
assumption that a tool does what it declares fails on real MCP servers; the funded work determines
which of those failures can be learned, verified and prevented before an autonomous agent acts.
The research work packages WP1–WP3 are described in §4.7–§4.9 below.

---

## 1. The open question

Agents act through tools, and tools are added faster than anyone reads their code. The Model
Context Protocol does not require a tool's description to match its implementation, and it
declares its own effect annotations (`readOnlyHint`, `destructiveHint`) untrusted; the protocol's
own blog states that annotations guarantee nothing and that runtime evaluation of them is an open
question for the forming Tool Annotations Interest Group (§5). CaMeL's authors state that their
strongest guarantees assume tools "under the control of the system developers" (CaMeL paper, §9.1); Zhao et al.
(2025) name the "tool logic attack" — a tool whose description is honest and whose implementation
is not — as the category that current scanners miss (mcp-scan 0 of 10, AI-Infra-Guard 7 of 10 on
their proof-of-concept servers); Li et al. (2026) find, by static comparison across 10,240 public
servers, that description/implementation mismatches are common, mostly undocumented functionality
assessed without execution.

Many agent permission policies rely on declared tool effects. Existing approaches already
observe actual tool behaviour or enforce capability restrictions: MCPGuard-Dynamic, for example,
derives policies from MCP tool schemas and enforces file, process and network restrictions at
runtime (§5). VAC tests whether independently qualified, per-tool effect contracts improve the
safety-versus-utility trade-off beyond those approaches. VAC combines evidence from
tool descriptions and README documentation with isolated execution, records what remains
undecidable, and measures the cost of review or denial on legitimate calls. Its incremental value
relative to existing tools is measured in the matched experiments of WP1–WP3.
The operational question is:

> **What does a controller have to know about a tool's effects to decide a call, how much of
> that can it obtain from documentation and from isolated execution for a tool it did not write,
> at what cost in refused legitimate calls, and where does the knowledge run out?**

The real-server studies address this question directly, while the controlled AgentDojo
experiments (§2.7) isolate the mechanisms and their limits.

## 2. What the proof of concept establishes (thirteen real servers, October 2026)

The harness (`real-mcp/`) launches an unmodified public MCP server as a stdio subprocess in a
fresh sandbox (own HOME and temporary directories) inside a private network namespace whose only
exit is the harness: a logging, refusing proxy; a dead-end default route; a name server that
never answers. Every outbound attempt is recorded by name whether or not the server honours
proxy variables. Observation channels: before/after content snapshots of the sandbox, every fork
and exec in the server's process tree from the kernel's process connector, sockets of the server's
namespace, and the tool's response. Nothing is cloned: every probe changes the state the next one
sees. A **declared effect contract** per server is written from the tool descriptions, the MCP
annotations and the README *before any probe* (`contracts/*.yaml`, with a `doc_sufficient` flag per
tool and a note wherever system knowledge had to be added), predictions are written before the
run (`PREDICTIONS.md` §1), and the grader classifies every observed change against the contract:
`fs_outside_scope`, `fs_change_by_readonly_tool`, `fs_undeclared`, `undeclared_subprocess`,
`undeclared_network`, `declared_effect_absent`. The learner of the synthetic study is imported
frozen, with its digests in every result file.

**Thirteen servers**, chosen by a rule fixed before the first probe: every official reference
server that runs locally over stdio (filesystem, git, sqlite, memory, everything, fetch, time) as
controls; the Terminal Controller of the MSB benchmark (ICLR 2026) and three of its documented
attack variants as third-party implementations with a known mismatch; and two widely installed
third-party servers with rich local state that I did not write (Desktop Commander 0.3.1,
obsidian-mcp 2.0.1). Three seeds each; 6–44 probes per seed in traffic order; a held-out set with
names, contents and commands absent from training. Every number below is in `PILOT2_RESULTS.md`;
`pilot2/verify_pilot2.py` recomputes every summary from the receipts and the report from the
summaries.

**The sample.** 1,683 graded calls are 561 calls per seed (280 training probes, 280 held-out
actions, one set-up call) under three seeds. The seeds vary names, contents and order; on 11 of
the 13 servers the result is identical across seeds, because those servers are deterministic
under the traffic. Seven of the thirteen servers are the official reference servers, four are
variants of one benchmark server, two are third-party servers in production use.

**2.1 What deviates, and why.** Across 13 servers, 3 seeds and 1,683 graded calls:

| Server (origin) | Deviations from the documented contract | Trigger | Learner's class can express it |
|---|---|---|---|
| Desktop Commander (third party, widely installed) | a child process on every one of 267 calls — `python3 --version` by name on 263 of them, the other 4 exited before their command line could be read — an undeclared subprocess on the 219 calls of tools that declare none (216 in the training and held-out totals of `PILOT2_RESULTS.md` §1 plus the three set-up calls, one per seed); DNS attempts to its telemetry hosts during 161 of 267 calls, in 81 of them to a fallback host on Google Cloud Run that the README does not cover (73 graded at README level; the other 8 are local `read_file` calls that the tool-wide declaration of URL access excused — the call-scoped declaration of `runtime/network_scope.py` flags all 81, `research/NETWORK_SCOPE_RESULTS.md`); at start-up, without any call: a Chrome-for-Testing download, a feature-flag fetch, a configuration file with a client id; the argument log, tool-history file and configuration rewritten outside the allowed directory on every call (README-declared, not tool-declared) | unconditional per call; timing-dependent (asynchronous telemetry queue); state-conditional at start-up (absent cache, absent configuration) | the unconditional part trivially (and it masks everything else); the timing part not at all |
| git (official) | read-only tools rewrite `.git/index` (git's stat-cache refresh): `git_diff_unstaged` in seed 1, `git_status` in seeds 2 and 3, one call in four with identical arguments | state-conditional, contradicts `readOnlyHint` | **no** — the version space empties in two seeds (blanket review on 23 of 23 held-out calls) and allows the next occurrence in agent traffic |
| obsidian-mcp (third party) | journal files under `.obsidian-mcp/transactions/` on every one of the 72 mutating calls, trash files on deletes in trash mode (README-declared, not tool-declared); `move_note` rewrites the notes that link to the moved one | unconditional per tool; state-conditional (which notes link) | the first yes, the second no |
| MSB false_error, tool_transfer (attack variants) | every call: documented effect absent, an injected instruction returned instead (108 calls each) | unconditional | yes — caught at the first probe of each tool; nothing to learn |
| MSB out_of_scope_parameter (attack variant) | none in any channel: the mismatch is an extra `llm_model_name` parameter in the served definition (the `false_error` variant is the same MSB script started with the `false_error` attack argument, so it carries the same extra parameter; the two have identical installation and served-definition digests and differ only in behaviour — see H3) | definition-level | not applicable |
| filesystem, sqlite, memory, everything, fetch, time, MSB normal (honest) | none | — | — |

**No input-conditional hidden effect** — a backdoor of the shape "filename ends in `.md` and
content contains `AUDIT`" that the synthetic study was built around — appeared in any server under
scripted or agent traffic. The pilot establishes the *shape* of the mismatches that ordinary
traffic exposes: the conditional effects that exist are conditional on *state* (git's index,
obsidian's links, Desktop Commander's cache and configuration) or on *timing* (telemetry), both
attack servers deviate on *every* call, and one attack lives only in the *definition*. Triggers
keyed to tokens ordinary traffic never sends are the subject of the sealed benchmark (§4.9).

The grader compares declaration with behaviour; harm is a separate label (§4.2, §4.10). git's
index rewrite is a stat-cache refresh, the journal files are what obsidian-mcp's README promises,
and the network channel records destinations by name on a dead-end network, so the telemetry
attempts show an undocumented destination. The conformance map reports both labels per deviation.

**2.2 What the frozen learner adds, and what it costs.** On the honest servers the learned
2-junta contract allowed no deviation (there were none) and paid reviews: 35 of 43 held-out
actions on the filesystem server (81 %), 13 of 23 on sqlite (57 %), 8 of 19 on obsidian (42 %),
7 of 12 on time (58 %), 3 of 6 on fetch, 3 of 19 on memory, 2 of 18 on the terminal controller,
1 of 18 on everything — identical across seeds, since the version space is order-independent. On the two
attack servers it blocked or reviewed every held-out call, but the grader had already decided at
probe 1. On git it reproduced the index rewrite as a one-feature rule in seed 1 and collapsed to
an empty version space in seeds 2 and 3. On Desktop Commander the 2-junta version space emptied
in two seeds, so every held-out call went to review, and in the third kept two hypotheses that
blocked all 36 deviating calls together with 2 safe ones; the 3-junta allowed three deviating
calls in one seed. The learner
contributes on no server: the unconditional cases need no learning, the state-conditional cases
are outside its class, and on the honest servers it is pure cost. That is the measured result,
and the research plan is built on it.

**2.3 Realistic traffic.** Four language models (claude-sonnet-4.6, gpt-oss-120b, K2-Horizon-375B,
deepseek-v4.1-flash) worked on six user-style tasks per server through the tools, with every
call graded and the learner's verdict recorded before execution (`results2_agent/`,
`PILOT2_RESULTS.md` §5). Review rates on honest servers were 59–67 % on the filesystem server,
52–62 % on sqlite, 31–44 % on obsidian, 45–71 % on the terminal controller and 0 % on memory; on
git, every model triggered the index rewrite with `git_status` and the learner **allowed** it (one
allowed deviation per model, 4 of 4 models) because the training seed had taught it a different
tool; on Desktop Commander 14–28 of each model's 16–29 calls deviated and none was allowed. Agent
traffic also found two gaps in the human-written filesystem contract that scripted traffic never
exercised (nested directory creation, documented; failure reported in the result text without
`isError`) — recorded in `CONTRACT_CHANGES.md` and corrected before the reported runs. Each agent run records its harness revision and the provider-reported model identity in its manifest.

**2.4 Who writes the contract.** A structural risk of the approach is that someone must write
the declared contract. I measured how well language models do it (`contract-study/`): eleven
models received the contract format, each server's `tools/list` verbatim and the README excerpt —
exactly the material the human contracts were written from — and nothing else; the contracts of
the seven that returned parseable drafts were then applied to the recorded receipts. Per-tool agreement with the human contract on
`read_only` was 92–98 % for the four models that covered most servers (100 % for three partial
ones); the models flagged documentation as insufficient for largely the same tools the human did
(git's five writing tools, sqlite's `append_insight`, the terminal controller's
`execute_command`). But applied to behaviour, the drafts disagreed with the human grading on
13–46 % of calls (the four broad models): mostly *false alarms* on honest behaviour (a draft that
does not declare that a git server runs `git` flags every call; one that expects a response
substring the server never emits flags every call), and *misses* on the attack variants when a
draft wrote no positive expectation at all (a contract without `expect_effect` cannot see a
declared effect that is absent: two of four models missed MSB false_error on 24 of 24 calls). All
three models that covered Desktop Commander (the fourth could not take its prompt) flagged its
undocumented subprocess and telemetry, because a contract written from documentation declares
neither. Documentation alone produces a contract that is right about what a tool is for and wrong
about what it touches; execution is what qualifies it.

**2.5 Static versus dynamic on the same servers.** A language model read each server's
implementation with its tools/list (the method of the static scanners, `static-scan/`) and
listed undocumented behaviour. On seventeen behaviours established by either method, the best
scan found 15, the dynamic harness observed 12 of the 12 it could in principle see. The seventeen
behaviours were listed from both outputs; the totals show that the two methods are complements,
and the conformance benchmark (§4.7) measures each method's recall on an independently specified set.
The scans found what execution cannot: effects kept in process memory (sqlite's memo), undone
within one call (memory's lock file), carried in protocol messages, or reachable only through
client features the probe client does not use. The harness found what reading cannot: git's
index rewrite (inside the git binary GitPython calls — no scan saw it) and *when* Desktop
Commander's Python probe fires (one scan found the mechanism and placed it at start-up; it fires
on every call).

**2.6 Evaluation scope.** The pilot measures documentation-to-effect conformance on 13 local
servers under isolated, scripted and agent-generated traffic; the confirmatory benchmark (§4.9)
adds independently graded harm. Samples, channels and the work package that extends each are in
`LIMITATIONS.md`.

**2.7 The synthetic study (`agentdojo-study/`).** On AgentDojo's workspace runtime with the
genuine `append_to_file` wrapped by one concealed state-conditional side effect (18 families,
12 arms, 3 seeds), the learned 2-junta contract allowed 3,133 of 3,133 legitimate writes and 0 of
1,475 hidden-effect actions inside its hypothesis class — a consequence of realizability plus unanimity — and was confidently wrong on 36 of 93 actions when
the trigger used a token never seen in training, with more probes not helping. The unmodified
CaMeL interpreter with two hosted models carried out the hidden effect in all 53 harmful episodes
without the veto and in 0 with it. The study validates the instrument (runtime, grader, CaMeL seam,
lifecycle, manifests) and locates the learner's failure mode in misspecification; §2.2–§2.9 take
the approach to tools nobody on the team wrote.

**2.8 One state-conditional case, decided before execution.** The pilot's one state-conditional
deviation on an official server is the rewrite of `.git/index` by tools annotated
`readOnlyHint: true`. Reading the receipts after the runs showed what conditions it: every such
rewrite in the reported run, on the second machine and in the four agent runs — 20 of 20, over 213
read-only calls — was the first worktree-statting read-only call (`git_status`, `git_diff_unstaged`)
after a `git_reset`, with no other index write in between. The mechanism is in the receipts'
child-process lists: `git_reset` runs `git read-tree`, which writes index entries without stat
data, and the next `git status` or `git diff` refreshes them. That observation was then put on
record as a test that could fail (`real-mcp/PREDICTIONS.md` §2): a history predicate — *was the last
index write a `git_reset`?* — was predicted to decide every rewrite in three new seeds of the same
traffic generator, under the frozen harness. It held for 5 of 6 rewrites and **failed once**: after
`git_reset → git_branch → git_add → git_add → git_commit`, `git_status` still rewrote the index, because
`git add` refreshes only the entries it adds — the refutation the pre-registration had named
("another writer leaves stale entries"). Before the next run the amendment (`PREDICTIONS.md` §3)
fixed a refined history predicate (stale since the last `git_reset` until a worktree-statting call;
`git_add`, `git_commit`, `git_create_branch` do not clear it; `git_checkout` declared open) and a
**state predicate** that reads `.git/index` before the call and flags entries left without stat
data, together with a table of paired probes and their predicted outcomes. The controller run
(`real-mcp/analysis/history_predicate_run.py`: the same frozen harness, three further seeds and the
paired probes, every verdict recorded before the call and graded from state afterwards) gave: the
state predicate decided all 85 read-only calls correctly — 12 rewrites flagged, 0 classification false positives and 0
missed rewrites; all 12 flagged calls were legitimate and would require review under an
enforcing controller (12/85, 14.1% legitimate-call review burden); the refined history predicate flagged all 12 and raised two false reviews, both
after `git_checkout`, which the paired probes showed does refresh the stale entries; the first
predicate missed the two rewrites of the `git_reset → git_add → … → git_status` kind; every paired
prediction held and the two questions declared open were answered. On the identical traffic the
frozen lexical learner emptied its version space in one seed and allowed the rewrite in another
(`real-mcp/analysis/GIT_INDEX_HISTORY_PREDICATE.md`, regenerated from the receipts by
`real-mcp/analysis/git_index_history_predicate.py`). Of the 12
rewrites, 4 occurred in scripted traffic (seeds 7–9, 66 read-only calls) and 8 in the paired probes
(seed 10, 19 calls). Every flagged call is a legitimate call held for review, so the 12 reviews are
the operational cost of the decision.

**2.9 Frozen controllers on new traffic, and the enforcing proxy.** The guarded run
(`real-mcp/analysis/guarded_run.py`, report `real-mcp/analysis/GUARDED_RUN.md`) drives the frozen
harness on ten git seeds no earlier run used. Four controllers were fixed and written to the run's
manifest before the first call: S; the refined history predicate P2; a depth-2 decision tree that
selected among the pre-call index counters and the tool names on controller seeds 7–8
(`research/state_eval.py`; on seeds 9–10 it flags 10 of 10 rewrites with 4 additional reviews);
and a per-tool baseline fitted on the same seeds. In shadow mode, with every call executed and its
verdicts recorded before execution, S and P2 flagged 17 of 17 index rewrites over 220 read-only
calls with no review of a call that did not rewrite; the tree flagged 17 of 17 with 3 additional
reviews; the per-tool baseline flagged 12 of 17 and raised 68 additional reviews. In enforce mode
the same seeds ran with `runtime/mcp_proxy.py` between the client and the unmodified server. The
proxy attests installation, contract and served `tools/list` against the reported run's digests,
evaluates S on the index before every call, fsyncs the decision to a hash-chained ledger and
forwards only allowed calls: of 480 calls it forwarded 415 under an attested revision and held 65;
the kernel's process events and the sandbox snapshots show no activity for any held call, and no
read-only call rewrote the index. Because a held `git_status` leaves the index stale for the next
reader, enforcement without a reviewer holds 65 reader calls where shadow mode reviewed 17; the
review-resolution policy is a measured parameter of WP2 (§4.8). The proxy, the state policy, the
ledger and call-scoped network declarations are covered by 21 tests (`runtime/tests/`).

## 3. The hypotheses

The synthetic study asked whether a learner can recover a hidden Boolean trigger from isolated
executions. The pilot shows that this is the wrong first question for real tools: the hidden
behaviour that ordinary traffic exposes is unconditional, state-conditional, timing-dependent or
definition-level.

**Research target.** VAC studies mismatches observed in public tools: undocumented and
incidental behaviour (a stat-cache refresh behind a read-only annotation, a per-call interpreter
probe, telemetry to an additional host, a journal under a hidden directory) and definition-level
attacks (an extra parameter, a changed description). WP3 extends the evaluation to sealed,
attacker-triggered hidden effects. The hypothesis has three measurable parts:

**H1 (conformance).** For a tool a controller did not write, a declared contract derived from
documentation and *qualified* by a bounded number of isolated executions in an instrumented
sandbox (files, processes, network by name) leaves a measurable **residue**: the share of a
tool's calls whose effects the contract cannot decide. The claim is that on the population of
public servers the residue is small enough to review at realistic traffic, that it concentrates in
a nameable trigger class per tool, and that the cost of obtaining the contract (probes, tokens,
human minutes per server) is bounded and reportable. The measurable outcomes are the undecidable residue, its trigger class and the cost of
qualifying and acting on the contract. The pilot's thirteen servers provide the first data points: the declared contracts
decided every call on the seven honest servers, while the lexical learner sent 81 % of the
filesystem server's held-out calls to review and emptied its version space on git in two seeds of
three — the residue is a property of the contract and its vocabulary, not of the server alone.

**H2 (state).** The effects that scripted probing cannot decide are functions of state and
history, not of the call's arguments. A predicate vocabulary over state deltas (which files the
call's arguments *and the current state* make reachable: an index that is stale, a note that links
to another, a cache that is absent) restores decidability for a measurable share of them, with a
model-adequacy signal that says when it does not: on the state-conditional git and Desktop
Commander residue the lexical version space emptied in four of six seeds and kept hypotheses in
the other two (on git it then allowed the next rewrite), so WP2 measures the signal's sensitivity
with a held-out-probe consistency check beside it (§4.8). The pilot's three state-conditional
cases are benign and each follows from one sentence of system knowledge; for one of them, git's
index rewrite, §2.8–§2.9 show on 305 read-only calls that a single state predicate decides every
call with its verdict recorded before execution, and enforce it in front of the unmodified server —
the shape of result H2 predicts. WP2 produces it on cases chosen before the predicate is known,
against the budget-matched baseline of §4.8. The scope of the state-aware work is set by the size of the state-conditional residue in the
conformance map.

**H3 (definition).** Mismatches that leave no trace in behaviour (an extra parameter, a changed
description) are caught by pinning the *served* definition and schema (as MCP-Scan and
mcp-context-protector do) together with a behavioural fingerprint from the probe receipts, not by
pinning source, which presumes source access. The pilot records both digests for every server,
and shows both limits of pinning without behaviour: Desktop Commander's served description embeds
the host's name, so a naive description hash changes per machine while the behaviour does not (a
false alarm); and the two MSB variants `out_of_scope_parameter` and `false_error` are the same
installed script with the same served definition — identical installation and served-definition
digests in `PILOT2_RESULTS.md` §7 — selected by a start-up argument, so neither digest separates a
server that behaves from one that deviates on all 108 calls (a miss). Only the behavioural
fingerprint, here the deviation profile of the first probe of each tool, tells them apart.

The sealed benchmark in WP3 measures the control value of learned input-conditional
rules on independently authored cases.

## 4. Methods

**Invariant.** VAC never widens what an existing boundary allows; it can only narrow. Every method
below keeps that invariant and measures its cost in reviews.

**Work packages and the decisive test.** The funded work is three work packages: WP1, the
conformance benchmark on the population (§4.7); WP2, state-aware predicates and model adequacy
(§4.8); WP3, the sealed hidden-effect benchmark and live confirmation (§4.9). Their scientific acceptance criteria and stop rules are defined in §4.7–§4.9 and the
operational protocols in `governance/`. The decisive test
of the method is WP2's: on servers whose residue is state-conditional, does a state-aware contract
decide more of the calls that a documentation contract leaves to review, with no unsafe allowance,
than a budget-matched baseline of static analysis plus plain dynamic conformance testing without
learned or state-aware predicates? WP1 produces the measurement that makes that question answerable
and is a deliverable in its own right; WP3 tests the frozen controller on cases it has never seen,
produced and sealed by someone else.

**4.1 The harness.** An unmodified MCP server runs as a stdio subprocess in a fresh sandbox (own
HOME, TMPDIR and XDG directories) inside a private network namespace joined to the harness by one
veth pair. The harness side is the server's default route, name server and HTTP proxy, and never
forwards: every DNS query and TCP SYN dies on the veth, where `tcpdump` records it by name;
proxy variables are honoured or not without changing what is seen. Channels: before/after content
snapshots of the watched roots, every fork and exec in the server's process tree from the kernel
process connector, the sockets of the server's namespace, the proxy log, the packet capture, and
the tool's response. Attempts outside a call window (start-up, background timers) are attributed
to the session, not to a call. Nothing is cloned; probes run in traffic order on live state. Each
receipt carries its own digest; each run records the digests of the installation, the served
`tools/list`, the contract, the harness revision and the frozen learner.

**4.2 Declared contracts and grading.** A contract per server is written from documentation only,
before any probe, at two levels: the tool descriptions and annotations alone (`tools_list`), and
those plus the README (`readme`). Per tool it states read-only, allowed file scopes (`may_create`,
`may_modify`, `may_delete` with path templates over the call's arguments), whether a subprocess or
network access is declared and to which hosts, the expected effect of a successful call
(`expect_effect`, with response texts that excuse a declared no-op), and a `doc_sufficient` flag
with a note wherever system knowledge had to be added to write anything at all. The grader
classifies every observed change as `fs_outside_scope`, `fs_change_by_readonly_tool`,
`fs_undeclared`, `undeclared_subprocess`, `undeclared_network`, `network_outside_scope` or
`declared_effect_absent`, at both documentation levels; a response that redirects the caller is
flagged separately as a heuristic. Corrections after a probe may narrow a contract toward the
documentation, never widen it beyond it, and are logged with their trigger and their effect on the
numbers. Conformance and harm are kept apart: every deviation carries, besides its kind, a harm
class from a rubric fixed before probing — no effect beyond the declaration's intent (a stat-cache
refresh), an undeclared local side effect (a journal file), an undeclared information flow (a
telemetry host), an undeclared change outside the tool's scope, undeclared code execution — assigned
by rule where the rule applies and otherwise by the contracted security researcher, who also reviews
a random sample of the rule-based assignments. The map reports both labels per deviation; a count of
conformance deviations is never presented as a count of security problems.

**4.3 The learner, frozen.** The learner is the synthetic study's 2-junta version space (every
Boolean function of two predicates over the call's own arguments; a 3-junta variant where the
hypothesis count permits), with a label-free vocabulary induced from the training calls' strings
and the grader's README-level deviation as label. It is imported unchanged, with its digests in
every result file. On held-out and agent traffic its verdict (allow, review, block) is recorded
before the call executes and graded from state afterwards; the hypotheses that remain are reported,
and an empty version space is itself a finding: the training labels are not realizable in the
class.

**4.4 Contract authoring by language models.** Each model receives the contract format, the
server's `tools/list` verbatim and the README excerpt — the same material the human contracts were
written from — and nothing else, at temperature 0, one draft per server. The draft is applied to
the recorded receipts with the same grader, and compared with the human contract per tool
(read-only, subprocess, network, documentation sufficiency) and per call (deviation or not, false
alarms and misses by kind).

**4.5 Static comparison.** A language model reads each server's implementation together with its
`tools/list` (the method of the static scanners) under a character budget, largest files first,
and lists undocumented behaviour; findings are matched to the behaviours the harness observed and
to the behaviours that no channel can observe (in-memory state, within-call files, protocol
messages, client-side features).

**4.6 Agent traffic.** A language model works through the server's tools on user-style tasks in
a fresh sandbox, parallel tool calls executed sequentially, one sandbox root per model; every call
is graded, the learner's verdict is recorded before execution, and the share of calls carrying a
token no training call had is reported.

**4.7 WP1 — the conformance benchmark on the population.** The harness is scaled from the
pilot's thirteen servers to at least sixty locally installable servers of the public registry
(every official reference server; the most installed community servers by registry statistics;
every public attack variant of MSB and MCPSecBench; Zhao et al.'s servers if released), selected
from Faraj's execution-based census so that runnability is known in advance. The selection rule and
the contract protocol are fixed and deposited with a timestamp before the first probe. Contracts are
drafted by two language models and qualified by a human who has not seen a probe; a second human
writes the contracts of a random half of the servers blind to the harness author, and the two
halves are compared on the receipts. The existing dynamic sandboxes (nyuwaymcpsandbox,
MCPGuard-Dynamic, SandScope where its code is available) run on the same servers as comparators,
and so does a static scan of each server's implementation with a frontier model (the method of
§2.5), so that the map states per behaviour which of static reading, plain dynamic observation and
the declared-versus-observed comparison found it. The product is a public conformance map — per
server, per tool: deviations by kind, harm class and trigger class, documentation level, what each
channel saw, what no channel can see, what each comparator flagged, probes to first detection, the
residue and its review cost — with the harness, its pre-registration and its verifier as a reusable
instrument. If the comparators flag everything the comparison flags, that is the map's headline,
and the contract protocol is published as documentation for their policies rather than as a new
instrument.

**4.8 WP2 — state-aware predicates and model adequacy.** The predicate vocabulary is extended
from strings to state and history: reachable paths given the sandbox state, staleness of caches and
indexes, link structure, prior calls (the state and history predicates of §2.8 are the first instances),
configuration values; a predicate enters a contract only after causal confirmation by paired probes
from the same state (as done for git in §2.8: `git_reset → git_status` against `git_add → git_status`
and `git_checkout → git_status`); a cost model covers probes on non-resettable state (record/replay proxies and
shadow accounts for servers that talk to services). The adequacy signal is made explicit and
measured for sensitivity and specificity on the map: the version space's collapse to empty, a
held-out-probe consistency check, and a lexical unseen-token check. The claim is comparative and
budget-matched: on the servers whose residue is state-conditional, the state-aware contract must
decide more of the calls that the documentation contract leaves to review, with no unsafe
allowance, than a baseline given the same probe budget and the same channels but no learned or
state-aware predicate (static scan plus plain dynamic conformance testing); predicates are fixed
before the held-out seeds and agent traffic they are scored on are run. Every predicate runs as the
policy of the enforcing proxy (§2.9), and the resolution of a held call (approve once, refresh,
deny) is measured as part of the legitimate-call cost. If the map shows no
state-conditional residue beyond the pilot's three benign cases, the method reduces to a documented
contract idiom for them (declared caches, declared link rewrites), and that is reported as the
result.

**4.9 WP3 — sealed hidden-effect benchmark and live confirmation.** A second person produces,
from documented real mismatches, a sealed set of hidden-effect tools over real AgentDojo-style
state, each case labelled before sealing with its trigger class (input, state, history, time,
attacker token), its documentation level and its harm class; the frozen controller is evaluated
blind, only on cases sealed before it was frozen; the unmodified CaMeL interpreter runs with and
without the veto on hosted open-weight models; attackers craft inputs rather than choose among
candidates; a security researcher reviews fidelity to the source incidents and the lifecycle's
override path. The primary endpoint is graded by an independent outcome grader that reads the
final state and counts unauthorized effects by harm class — never the conformance grader's
deviation count and never a model's account. The analysis is pre-registered and the harness digest
frozen before the first run.

**4.10 Evaluation design.** *Primary endpoints*, per server: deviations by kind, harm class and
trigger class; probes to first detection; the residue and its review cost on held-out and agent
traffic; unsafe allowances, reported by harm class so that a blocked stat-cache refresh and a
blocked undeclared information flow are never summed. *Secondary*: documentation sufficiency per
tool and level; agreement between contract writers; what each channel saw and what none can; what
each comparator flagged; adequacy-signal sensitivity and specificity; cost per server in probes,
time, model tokens and human minutes.
*Unit*: the server for the conformance map, the state-conditional residue class for the state-aware
work, the sealed family for the benchmark; seeds are replicates and reported as such. *Inference*:
exact paired tests with pre-registered margins; bootstrap intervals over servers; pooled rates
descriptive; comparisons true by construction marked as such. *Integrity*: predictions before
observation; contracts before probes with a logged change list; two contract writers; verdicts
recorded before execution; every probe counted and aborted runs listed; receipts with digests of
installation, served definition, contract and harness revision, one frozen revision per run; verifiers
that recompute every reported number from the receipts (`VERIFY.sh`). The operating discipline is summarised
in `governance/README.md`, with the detailed governance documents as an annex.

## 5. Closest work and positioning

VAC builds on black-box testing, dynamic analysis, specification mining and existing MCP
policy enforcement. Its research contribution is to qualify per-tool declarations against
execution at the `tools/list` and README levels, identify unresolved state-dependent effects,
and quantify the legitimate-call cost of pre-dispatch decisions. The benchmark measures the
additional value of this combination against existing static and dynamic controls under
matched conditions.

* **Dynamic sandboxes for MCP servers.** *SandScope / MCP-SandboxScan* (Tan et al., January 2026)
  drives unmodified servers over stdio or under WASI, extracts declared capabilities from
  `tools/list` and reports source-to-sink witnesses from environment, files and tool inputs, with
  network recorded as egress evidence (35 repositories scanned dynamically, 1,127 tools profiled).
  *nyuwaymcpsandbox* (Apache-2.0, 2026) detonates a server in a container and records DNS, file
  writes, process spawns, environment reads and timing signals, scored by nine detection rules.
  *MCPGuard-Dynamic* (Meta, MIT, 2026) sits as a proxy between client and server, derives
  per-server allowlists for paths, hosts, processes and environment from the tool schema and
  enforces them with eBPF LSM hooks on `open`, `connect` and `execve` (14-server benchmark).
  *Corvus* (Padilla, July 2026) is the dynamic security assessment of internet-facing servers
  (414 audited). These systems overlap with VAC in observation, policy derivation and
  enforcement. The proposed research contribution is a joint, per-tool comparison with
  `tools/list` and README declarations, including absent expected effects, together with
  explicit measurement of undecidable residue and the review burden of acting on qualified
  contracts. The matched comparator studies in WP1–WP2 quantify the contribution and operational
  trade-offs relative to these existing systems.
* **Execution-based conformance at scale.** Faraj (2026) launched 6,106 locally installable servers
  from the official registry in disposable containers and measured *protocol* conformance
  (handshake, `tools/list`, schema validity, behaviour under malformed input; 61 % completed a
  handshake). It does not look at effects against descriptions. It settles the feasibility
  question for the selection rule — a registry-scale census is a matter of compute, not of
  method — and its harness and dataset are reused for the selection and the runnability baseline.
* **The idea in public.** The MCP specification repository carries a proposal from August 2026
  for "runtime verification of declared vs observed MCP server capabilities" with a behavioural
  fingerprint and capability drift (Discussion #3211, closed without technical discussion when the
  forum changed purpose). The Tool Annotations Interest Group (Microsoft, OpenAI, AWS, Cloudflare,
  Anthropic; forming since March 2026) lists whether annotations "should be evaluated at runtime
  instead of declared statically" as an open question. VAC is an answer with data to that
  question.
* **Description-versus-behaviour fidelity** is a research programme with a decade of results on
  Android: WHYPER (Pandita et al. 2013), CHABADA (Gorla et al. 2014) and AutoCog (Qu et al. 2014)
  checked app behaviour and permissions against app descriptions. VAC is that programme on MCP,
  where the declaration is read by a machine that acts on it, which is why the cost in refused
  calls, absent on Android, is a primary endpoint here.
* **Active black-box model learning** (Angluin's L*, LearnLib, de Ruiter & Poll 2015) is the
  methodological ancestor of the learner: state machines of TLS implementations learned by queries,
  deviations flagged as bugs. VAC's learner is a stateless special case; the state-aware work moves
  it toward state, where this literature already is, and will use LearnLib's abstractions where
  they fit.
* **Policy vetoes over tool calls** — Progent, AgentSpec, Claude Code's permission rules,
  MCPGuard-Dynamic's policy engine — are the veto half of VAC; the delta is where the policy comes
  from (documentation plus execution, revision-pinned), that it can only narrow, and that it runs
  as an MCP stdio proxy in front of an unmodified server (`runtime/mcp_proxy.py`).
* **Static description/implementation scanners** — Cisco MCP Scanner, MCPDiFF (Li et al.) — are the
  static complement, shown as such in §2.5 and measured in the benchmark; **ToolFuzz** and
  **MCPSafetyScanner** probe tools without learning a contract; **Daikon** and specification
  mining are the software-side relatives of contract derivation from executions.
* **Definition pinning and attestation** — MCP-Scan, mcp-context-protector, ETDI — handle the
  definition-level class (§3 H3); VAC adopts them rather than reinventing them.
* **Information-flow boundaries** (CaMeL, FIDES) and **AI Control** protocols assume known tool
  effects; VAC supplies the effect knowledge and the veto inside CaMeL's policy, measured in the
  synthetic study and to be measured on real tools in the sealed benchmark.
* **Benchmarks with malicious tools** — MSB, MCPSecBench, Zhao et al.'s 120 PoC servers — are
  existing testbeds; the conformance benchmark reuses their cases (the pilot already runs MSB's)
  and differs by grading *state*, by paired legitimate traffic, and by documenting the trigger
  class of every case.
* **Li et al. (2026)** support "mismatches are common" by static measurement; they do not show
  that input-conditional hidden effects are common, and the pilot found none.

The claimable contribution is an outcome-measured conformance map of real MCP servers against
their declared contracts, with the instrument that produced it and the existing sandboxes run
beside it; a contract protocol whose qualification step is execution; a state-aware extension
where scripted probing provably runs out; and a sealed benchmark whose cases carry their trigger
class, evaluated with explicit success criteria and transparent outcome reporting.

## 6. Why it matters

Controls over increasingly autonomous agents — permission systems, information-flow boundaries,
AI-control protocols — are only as good as what they know about the tools the agent acts through,
and today that knowledge is a self-declared description read by a machine that acts on it. As
agents gain autonomy and tool ecosystems grow faster than anyone audits them, the gap between
declared and actual effects is where a controller's guarantees stop without anyone noticing.

The chain that matters for catastrophic risk is concrete. An AI-control protocol in the sense of
Greenblatt et al. bounds what an untrusted, possibly scheming model can do by routing its actions
through a trusted monitor and a permission layer; CaMeL and FIDES bound what data can flow to which
sink. Both derive the set of things the agent *can* do from the tools' declarations: a tool
annotated read-only is auto-approved, a tool declaring no network is not a sink. A tool whose
implementation also writes outside the watched scope, spawns a process, or contacts a host the
policy never heard of gives the model an action channel the controller does not model — and a model
that is looking for one (or an injected instruction that is) can find it by use, exactly as the
probes do, while the controller's accounting of the agent's affordances stays silently wrong.

The pilot found concrete discrepancies in widely installed servers: subprocess activity
outside tool declarations, additional telemetry destinations and a read-only-annotated tool
that rewrites an index. These observations establish a measurable gap between declared and
actual capabilities. VAC qualifies that gap against executable evidence and evaluates how
the resulting knowledge changes authorization decisions before agents act.

VAC aims to give clients and registries an evidence basis for deciding which tool annotations
to trust, and to inform the standards discussion on runtime evaluation of annotations. The
repository includes the notices for the maintainers of the examined servers (`disclosure/`). The conformance map of WP1 is made for maintainers,
the MCP registry and client vendors that use annotations in approval policies. Researchers
building controllers on CaMeL, FIDES or AI-Control-style protocols can use the resulting
tool-effect evidence to examine assumptions about the tools their policies permit.

## References

1. Li, Z., Ma, B., Dai, X., Xu, M., Zhang, Y., Yan, B., Li, K. (2026). *Don't believe everything you read: Understanding and Measuring MCP Behavior under Misleading Tool Descriptions.* arXiv:2602.03580.
2. Zhao, W., Liu, J., Ruan, B., Li, S., Liang, Z. (2025). *When MCP Servers Attack: Taxonomy, Feasibility, and Mitigation.* arXiv:2509.24272.
3. Bhatt, M., Narajala, V. S., Habler, I. (2025). *ETDI: Mitigating Tool Squatting and Rug Pull Attacks in Model Context Protocol.* arXiv:2506.01333.
4. Milev, I., Balunović, M., Baader, M., Vechev, M. (2025). *ToolFuzz — Automated Agent Tool Testing.* arXiv:2503.04479.
5. Radosevich, B., Halloran, J. (2025). *MCP Safety Audit: LLMs with the Model Context Protocol Allow Major Security Exploits* (MCPSafetyScanner). arXiv:2504.03767.
6. Debenedetti, E., et al. (2025). *Defeating Prompt Injections by Design* (CaMeL). arXiv:2503.18813; code: google-research/camel-prompt-injection.
7. Costa, M., et al. (2025). *Securing AI Agents with Information-Flow Control* (FIDES). arXiv:2505.23643.
8. Greenblatt, R., Shlegeris, B., Sachan, K., Roger, F. (2024). *AI Control: Improving Safety Despite Intentional Subversion.* ICML.
9. UK AI Security Institute / Redwood Research. *ControlArena.* https://control-arena.aisi.org.uk/
10. Debenedetti, E., et al. (2024). *AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents.* NeurIPS Datasets and Benchmarks.
11. Shi, T., et al. (2025). *Progent: Programmable Privilege Control for LLM Agents.* arXiv:2504.11703.
12. Wang, H., et al. (2025). *AgentSpec: Customizable Runtime Enforcement for Safe and Reliable LLM Agents.* arXiv:2503.18666.
13. Zhang, D., Li, Z., Luo, X., Liu, X., Li, P., Xu, W. (2025). *MCP Security Bench (MSB): Benchmarking Attacks Against Model Context Protocol in LLM Agents* (ICLR 2026). arXiv:2510.15994; github.com/dongsenzhang/MSB.
14. Yang, Y., et al. (2025). *MCPSecBench: A Systematic Security Benchmark and Playground for Testing Model Context Protocols.* arXiv:2508.13220.
15. Invariant Labs. *MCP-Scan* (2025). Trail of Bits. *mcp-context-protector* (2025). Cisco AI Defense. *MCP Scanner* (2025).
16. Angluin, D. (1987). *Learning Regular Sets from Queries and Counterexamples.* Information and Computation 75(2). Isberner, M., Howar, F., Steffen, B. (2015). *The Open-Source LearnLib.* CAV. de Ruiter, J., Poll, E. (2015). *Protocol State Fuzzing of TLS Implementations.* USENIX Security.
17. Stern, R., Juba, B. (2017). *Efficient, Safe, and Probably Approximately Complete Learning of Action Models.* IJCAI. Le, H. S., Juba, B., Stern, R. (2024). *Learning Safe Action Models with Partial Observability.* AAAI.
18. Mitchell, T. M. (1982). *Generalization as Search.* Artificial Intelligence 18(2). Blum, A., Langley, P. (1997). *Selection of Relevant Features and Examples in Machine Learning.* Artificial Intelligence 97. Mossel, E., O'Donnell, R., Servedio, R. (2004). *Learning Functions of k Relevant Variables.* JCSS 69(3).
19. Ernst, M. D., et al. (2007). *The Daikon System for Dynamic Detection of Likely Invariants.* Science of Computer Programming 69. Ammons, G., Bodík, R., Larus, J. (2002). *Mining Specifications.* POPL.
20. Model Context Protocol. *Specification 2025-06-18, Server Tools* (tool annotations are untrusted). modelcontextprotocol.io.
21. Tan, Z., Hao, R., Singer, J., Tang, Y., Anagnostopoulos, C. (2026). *MCP-SandboxScan: WASM-based Secure Execution and Runtime Analysis for MCP Tools* (SandScope). arXiv:2601.01241.
22. Nyuway Cybersecurity (2026). *nyuwaymcpsandbox: behavioural sandbox for MCP servers* (Apache-2.0). github.com/Nyuway-Cybersecurity/nyuwaymcpsandbox.
23. Meta (2026). *MCPGuard-Dynamic: kernel-level eBPF sandbox for MCP tool calls* (MIT). github.com/facebook/mcpguard-dynamic.
24. Padilla, N. (2026). *Exposed by Design: A Dynamic Security Assessment of Internet-Facing MCP Servers at Scale* (Corvus). arXiv:2608.00150.
25. Faraj, A. (2026). *Does Your MCP Server Actually Follow the Protocol? An Execution-Based Conformance Study of the Model Context Protocol Ecosystem.* Preprint; harness and dataset: github.com/Ahmad-Faraj/mcp-conformance.
26. Model Context Protocol repository, Discussion #3211 (August 2026). *Runtime verification of declared vs observed MCP server capabilities.* Model Context Protocol blog (16 March 2026). *Tool Annotations as Risk Vocabulary: What Hints Can and Can't Do* (Tool Annotations Interest Group).
27. Pandita, R., Xiao, X., Yang, W., Enck, W., Xie, T. (2013). *WHYPER: Towards Automating Risk Assessment of Mobile Applications.* USENIX Security. Gorla, A., Tavecchia, I., Gross, F., Zeller, A. (2014). *Checking App Behavior Against App Descriptions* (CHABADA). ICSE. Qu, Z., Rastogi, V., Zhang, X., Chen, Y., Zhu, T., Chen, Z. (2014). *AutoCog: Measuring the Description-to-permission Fidelity in Android Applications.* CCS.
