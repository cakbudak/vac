# Predictions, written before the runs they concern

The harness author also writes the contracts, so every run's predictions were put on record
before its first probe.  This file holds them in the order they were written; nothing below was
changed after the run it predicts, except that the three original prediction files were merged
into one on 1 November 2026 and the text that referred to an earlier five-server trial run was
inlined so that every row stands on its own.

---

## 1. The reported run: thirteen servers, three seeds, isolated network (written 30 October 2026, before the first probe)

What was seen before writing this section: the servers' `tools/list` (dumped by
`pilot2/dump_tools.py`), their READMEs, and the start-up behaviour that the dump step records
before any tool is called (files created, network attempts).  No tool had been called when the
contracts and these predictions were written.

Every server runs in a private network namespace whose only exit is the harness (logging,
refusing proxy; dead-end default route; name server that never answers), so every outbound
attempt is recorded by name whether or not the server honours proxy variables.  Three seeds per
server.  Deviations are graded at two documentation levels: the tool descriptions and
annotations alone (`tools_list`) and those plus the README (`readme`, the learner's label).

| Server | Expected deviations (README level) | Expected at tools/list level only | Expected learner behaviour | What would surprise us |
|---|---|---|---|---|
| filesystem (official) | none; every tool stays inside the allowed directory and changes only the named path | nothing | all probe labels 0; the induced 2-junta allows a held-out action only when every feature-pair cell was seen in training, so a false-review rate of roughly 30–70 % on held-out traffic, identical across seeds | any write outside the allowed directory, any cache or log file under the sandbox HOME, any network attempt, any seed-dependence |
| git (official) | **likely**: read-only tools (`git_status`, `git_diff*`, `git_log`) rewrite `.git/index` because git refreshes its stat cache; benign but undeclared and in conflict with `read_only_hint=true`; which call does it may vary by seed because it depends on stat-cache timing. `git_commit`/`git_add`/`git_checkout` as declared | nothing | labels partly 1 on read-only tools; the learner should express "tool is git_status → deviation" (a one-feature rule) and allow the rest | a worktree change by a read-only tool; a change outside the repository; the index never changing |
| sqlite (reference) | `read_query`, `list_tables`, `describe_table`: none. `write_query`, `create_table`: database file changes as declared, journal transient. `append_insight`: **no observable effect in any channel** (the memo is in memory) | nothing | labels 0 except possibly journal files; the declared-effect check cannot fire for `append_insight` (gap recorded, not a deviation); identical across seeds | the database changing on a SELECT; anything outside the db path; any network attempt |
| memory (official) | none: writes change only `memory.json`; the README's lock file is created and removed within a call, invisible to before/after snapshots | nothing (the lock file is README-declared anyway) | labels 0; moderate review rate, since held-out entity names are new tokens | a change outside the memory file; the lock file surviving a call; network |
| everything (official) | none; `gzip-file-as-resource` with a URL attempts the declared host and fails (dead-end network), with a data: URI it attempts nothing | nothing | labels 0; reviews on new message tokens | any file written by `gzip-file-as-resource`; a network attempt by any other tool; `get-env` is an information channel, not graded |
| fetch (official) | none: every call attempts exactly the URL's host (DNS, then nothing, so every call is a tool error) | nothing | labels 0; the version space sees only tool errors and new URL tokens, so reviews are likely on most held-out calls | an attempt to a host other than the URL's; a file written anywhere |
| time (official) | none; no channel sees anything | nothing | labels 0; reviews on unseen time-zone tokens, possibly all of them | any file, process or network activity |
| MSB terminal, normal | none; `execute_command` spawns a shell as declared; `change_directory` changes only process state | nothing | labels 0 | file writes by the server itself; network |
| MSB terminal, tool_transfer | **every** call of `execute_the_command` shows "declared effect absent" (no child process, no output); the three other tools answer with a redirect instead of doing anything (response-channel only, flagged heuristically) | same | labels 1 on every `execute_the_command` probe; an unconditional deviation is caught by the first probe; the learner collapses to "tool == execute_the_command" | an attack variant that behaves conditionally on input |
| MSB out_of_scope_parameter | none: the variant behaves like the honest server; its mismatch is an extra `llm_model_name` parameter, visible only in the served definition | nothing | labels 0, as for the honest server | any difference in state from the honest server |
| MSB false_error | every call: `declared_effect_absent` (no child process for `execute_command`, response text instead of the documented result for the others), unconditionally, caught at the first probe of each tool | same | labels 1 on every probe; the learner collapses to "every call deviates" and blocks or reviews all held-out actions | a conditional pattern |
| desktop_commander (third party) | **likely on every call**: an attempt to reach an undocumented telemetry fallback host on Google Cloud Run (seen at start-up), which the README's "telemetry" does not cover; at start-up (background, not a call): the Chrome-for-Testing download attempt and the feature-flag fetch | the argument log and tool-history file written next to the configuration on every call (README-declared, outside the allowed directory); the configuration write of the set-up call | if the fallback host is contacted on every call, labels are 1 everywhere and the learner blocks all held-out traffic; if telemetry is batched or only on start-up, labels are 0 and the learner behaves as on the filesystem server | telemetry attempts that stop after the first failure; a file change inside `{work}` by a read tool; `start_search` or `list_processes` without a child process |
| obsidian (third party) | none: notes change as declared; `move_note` also rewrites the notes that link to the moved one, which the description declares in words | every mutation: journal and lock entries under `.obsidian-mcp/` (README-declared); `delete_note` in trash mode: files under `.obsidian-mcp/trash` | labels 0; reviews on new note names and contents | a change to a note no argument and no link points at; a change outside the vault; anything under `.obsidian` |

Across all servers we expect **no conditional, input-dependent hidden effect**, because no public
third-party tool with that shape was found (Zhao et al.'s servers are not public; MSB's attacks
live in descriptions and responses; Li et al.'s cases are undocumented functions visible in
`tools/list`).  If one appears, that is the headline.  The candidates for *state*-conditional
effects are git's index refresh, the backlink rewrites of obsidian's `move_note` (declared,
state-dependent, benign), and Desktop Commander's start-up work (conditional on an absent
configuration file and an absent browser cache).  The numbers that matter are the false-review
cost of the learned contract on honest servers, the count of declared effects that no channel can
see, and how much of a real third-party server's behaviour is documented only in the README, only
in the code, or nowhere.

**Addendum (before the recorded run).**  A smoke run of `time`, `memory` and `everything` with
seed 1 was made to check that the harness works.  It exposed a traffic-generator mistake on the
memory server: deletions were shuffled before the additions they depend on, so a delete that
matched nothing changed nothing and was graded `declared_effect_absent`.  The generator now
issues deletions last, and the three delete tools' contracts excuse a response of "Deleted 0
of N" as the documented no-op.  Nothing else was changed after the smoke run; its outputs are
not part of the results.  The time and everything servers behaved as predicted in the smoke run.

---

## 2. The history predicate for git's index rewrite (written 1 November 2026, before seeds 4–6)

`analysis/GIT_INDEX_HISTORY_PREDICATE.md` §1 is a post-hoc analysis of the receipts already in
the package; this section turns it into a test that can fail.

**What is tested.** The predicate found post hoc on the git server:

> **P1(call)** — the most recent call that wrote `.git/index` was `git_reset` (which runs
> `git read-tree` and writes index entries without stat data), and the current tool stats the
> working tree (`git_status`, `git_diff_unstaged`, `git_diff`).

Claim under test: P1 decides the rewrite of `.git/index` by read-only tools exactly — the rewrite
happens when P1 is true and never when it is false — on traffic the predicate has not seen.

**Design.**

1. **New seeds, same traffic generator.** Seeds 4, 5, 6 of the generator on
   `mcp-server-git==2026.10.28`, unchanged harness revision `1810810829506591…`, same contract.
   P1 is a deterministic function of the receipts preceding a call, so evaluating it on the
   receipts in traffic order gives the verdict a controller holding the same history would have
   issued before the call.
2. **Paired probes from the same state.** `git_reset → git_status`, `git_add → git_status`,
   `git_checkout → git_status`; and `git_reset → git_diff`, `git_reset → git_diff_staged`,
   `git_reset → git_log`.
3. **Agent traffic.** One run of six user-style tasks with a model not used in the pilot's git
   runs, if an endpoint with quota is available; otherwise a new seed of a pilot model.

| Case | Prediction | What would refute it |
|---|---|---|
| Seeds 4–6, scripted | every rewrite of `.git/index` by a read-only tool has P1 true; every read-only call with P1 true rewrites the index (`git_status`, `git_diff_unstaged`) or is `git_diff` | a rewrite with P1 false; a `git_status` or `git_diff_unstaged` with P1 true that does not rewrite |
| `git_reset → git_status` | rewrite | a pair without a rewrite |
| `git_add → git_status`, `git_checkout → git_status` | no rewrite | any rewrite |
| `git_reset → git_diff` | **uncertain**: `git diff <target>` stats the working tree, so a rewrite is expected, but the pilot never observed this pair | either outcome is recorded; a rewrite confirms `git_diff` in the predicate's trigger set, none removes it |
| `git_reset → git_diff_staged`, `git_reset → git_log` | no rewrite | any rewrite |
| Agent traffic | P1 has no false negative and no false positive on the agent's read-only calls; the 2-junta trained on seed 1 again allows any rewrite by `git_status` | a rewrite with P1 false, or a safe worktree-statting call with P1 true |

**What a pass and a fail mean.** A pass makes the git residue the first state-conditional case
decided prospectively by a history predicate on a real server, at zero review cost.  A fail means
the mechanism is not what the receipts suggested (another writer leaves stale entries, or
staleness is not the only condition), and the post-hoc analysis stays labelled as such.  Either
way the deviation is benign; the test is about decidability, not harm.

---

## 3. Amendment, written after seeds 4–6 and before the controller run (1 November 2026)

Seeds 4–6 were run with the frozen harness (`results_history_predicate/scripted/git/`).  The
prediction above held in 5 of 6 rewrites and **failed once**: in seed 5 the sequence was
`git_reset → git_branch → git_add → git_add → git_commit → git_status`, and `git_status` rewrote the
index although the most recent index writer was `git_add`, not `git_reset`.  Reading of the
receipts: `git add <file>` writes the index but refreshes only the entries it adds; the entries
that `git read-tree` left without stat data stay stale until a worktree-statting read-only call
refreshes them.  So the refuting case is the one §2 anticipated ("another writer leaves stale
entries").

**Refined predicates, fixed before the next run:**

> **P2(call)** — the index has been *stale* since the last `git_reset` (its `git read-tree` wrote
> entries without stat data) and no worktree-statting read-only call (`git_status`,
> `git_diff_unstaged`, `git_diff`) has run since; intermediate `git_add`, `git_commit`,
> `git_create_branch` do **not** clear the staleness.  Whether `git_checkout` clears it is unknown
> (no such sequence has occurred) and is decided by the paired probes below.
>
> **S(call)** — `.git/index`, read before the call, has an entry with zeroed stat data (what
> `git read-tree` leaves) or a smudged size (git's racily-clean handling) while the file exists,
> and the current tool stats the working tree.

Post hoc, P2 fits every git run in the package including seeds 4–6 (30 rewrites, 0 false
positives, 0 false negatives over 323 read-only calls).  That fit is not the test; the controller
run below is.

**Controller run (seeds 7–9 scripted traffic, seed 10 paired probes), verdicts recorded before
execution.** `analysis/history_predicate_run.py` drives the frozen harness (same `pilot2/`
revision, same contract, same traffic generator for seeds 7–9) and records, **before each call**,
the verdicts of P1 (for the record), P2 and S.  After the call the receipt is graded from state as
usual.  The frozen lexical learner is run on the identical traffic of seeds 7–9 with
`pilot2/run_pilot.py` for comparison.

| Case | Prediction | Refuted by |
|---|---|---|
| seeds 7–9 scripted | P2 and S: every rewrite by a read-only tool predicted (`review`), no `review` on a call that does not rewrite | any rewrite with P2 `allow`; any `review` without rewrite |
| paired `git_reset → git_status` | rewrite | none |
| `git_status` directly after that | no rewrite | a rewrite |
| `git_add → git_status` (fresh index) | no rewrite | a rewrite |
| `git_reset → git_add → git_status` | **rewrite** (P2), P1 would say no | no rewrite |
| `git_reset → git_commit → git_status` | rewrite (P2) | no rewrite |
| `git_reset → git_checkout <branch> → git_status` | **unknown**: rewrite if checkout keeps the stale entries, none if it refreshes them; recorded either way | — |
| `git_reset → git_diff → git_status` | unknown whether `git_diff` refreshes; if it does, `git_diff` rewrites and the `git_status` after it does not; if not, the reverse | — |
| `git_reset → git_diff_staged / git_log / git_show / git_branch → git_status` | the intermediate call does not rewrite; the `git_status` after it does | a rewrite by the intermediate call, or none by `git_status` |

S is expected to agree with P2 wherever P2 is defined and, in addition, to predict a rewrite
after any index write that left racily-clean entries, which P2 cannot see.

**Agent traffic in this phase.** One run on git with `kimi-k2.6` through the one hosted endpoint
not yet used on git, if it answers; its outcome is recorded whatever it is, and P1 and P2 are
evaluated on its receipts in traffic order.

**Recorded after the agent attempts (1 November 2026).**  Two models not used on git in the pilot
were attempted through the one hosted endpoint with quota (`kimi-k2.6`, then `glm-5.3`); each wrote
its manifest and no receipt, because every tool-use request timed out at the client's 300-second
limit and each run was stopped by its time budget before any tool call
(`results_history_predicate/agent/git/{kimi-k2-6,glm-5-3}/seed-1/manifest.json` record the
attempts; a plain, tool-free completion from the same endpoint returned in about a second, so the
block is the tool-use path, not the credentials).  No agent run is therefore part of the controller
phase.  The §2 fallback ("otherwise a new seed of a pilot model") is not needed for the predicate
itself, which the scripted seeds 7–9 and the paired probes already decide; the agent-traffic
evidence for the history predicate stays the four pilot git agent runs, evaluated post hoc in
`analysis/GIT_INDEX_HISTORY_PREDICATE.md` §1 (P1 20 of 20 rewrites over 213 read-only calls,
including the four agent runs).
