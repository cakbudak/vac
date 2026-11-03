# Note to the maintainers of mcp-server-git

Observed on `mcp-server-git==2026.10.28` (30 October – 1 November 2026, twenty runs of the server
on two machines; confirmed on 3 November 2026 on ten further seeds on a third machine): `git_status`,
`git_diff_unstaged` and `git_diff`, all annotated `readOnlyHint: true`, rewrote `.git/index` on some
calls — git's stat-cache refresh when the index's cached stat data is stale.  The condition is exact
in our runs: after `git_reset` (which runs `git read-tree` and leaves index entries without stat
data), the first of these three tools to run rewrites the index; `git_add` and `git_commit` in
between do not remove the condition, `git_checkout` does.  Benign and ordinary git behaviour, but it
contradicts the annotation as a controller reads it: a tool documented read-only changed a file in
the repository.  Either `readOnlyHint` should be understood as "does not change the working tree or
the commit graph" (worth saying in the description), or the index refresh should be mentioned.
`git_log`, `git_show`, `git_diff_staged` and `git_branch` did not refresh the index in our runs,
including directly after a `git_reset`.

**Reproduction with git alone** (git 2.43), in any repository with committed files:

```bash
git read-tree --index-output=.git/tmpidx HEAD && mv .git/tmpidx .git/index   # what git_reset runs
sha1sum .git/index; git status > /dev/null; sha1sum .git/index                # the index changes
git status > /dev/null; sha1sum .git/index                                    # unchanged
```

**Receipts** at https://github.com/cakbudak/vac (one JSON line per tool call):

- Paired probes: `real-mcp/results_history_predicate/controller/git/seed-10/receipts.jsonl` —
  line 2 `git_reset` (`git read-tree --index-output=… HEAD` in `children`); line 3 `git_status`
  rewrites `.git/index` (`index_state_before`: 6 of 6 entries without stat data); line 4 a second
  `git_status` does not; lines 7–12 `git_add` and `git_commit` in between; lines 14–16
  `git_checkout` in between; line 20 `git_diff`; lines 22–33 `git_diff_staged`, `git_log`,
  `git_show`, `git_branch`.  Summarised in `real-mcp/analysis/GIT_INDEX_HISTORY_PREDICATE.md`.
- Scripted and agent traffic: `real-mcp/results2/git/seed-1/receipts_heldout.jsonl` line 8;
  `real-mcp/results2_agent/git/<model>/seed-1/receipts_agent.jsonl`.
- Third machine: `real-mcp/results_guarded/shadow/git/`, report `real-mcp/analysis/GUARDED_RUN.md`.
- Annotations as served: `real-mcp/contracts/git.tools.json`.
