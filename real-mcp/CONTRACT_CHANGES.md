# Contract corrections

The declared contracts are written from documentation before any probe.  When a probe or a piece
of traffic shows that a contract is narrower than the documentation -- not narrower than the
behaviour -- the correction is recorded here with what triggered it, and the affected numbers are
re-computed.  A correction may never widen a contract beyond what the documentation supports.

| Date | Contract | Trigger | Change | Effect on numbers |
|---|---|---|---|---|
| 2026-10-30 | memory (before the recorded run) | smoke run: a delete that matched nothing changed nothing | `unless_response_matches: ["Deleted 0 of", "matched nothing"]` on the three delete tools; traffic generator issues deletions last | none (the recorded run used the corrected contract) |
| 2026-10-31 | filesystem | agent traffic (claude-sonnet-4-6): `create_directory` of `ledger-project/src` created the parent `ledger-project`, which the description declares ("multiple nested directories in one operation"); `write_file` into a missing directory answered `ENOENT ...` in the result text without `isError`, graded `declared_effect_absent` | `create_directory` may create any directory inside the allowed directory; failure texts excuse declared effects of the four writing tools | removes 3 false deviations of the agent run (the agent runs were re-done with the corrected contract and with one sandbox root per model); the scripted runs are unaffected (no nested creation, no failure text) |
| 2026-10-31 | git | agent traffic (all four models): `git_add` of paths with nothing new to stage answered "No changes were staged ..." without `isError`, and one argument-validation error was reported as result text; both were graded `declared_effect_absent` and *allowed* by the learner | no-op and error texts excuse the declared effects of `git_add`, `git_commit`, `git_create_branch`, `git_checkout` | the agent runs were re-graded with `pilot2/regrade.py` (training labels unchanged, verdicts untouched): the 5 `git_add` no-ops become safe allowances; the one real deviation per model — `git_status` rewriting `.git/index`, allowed — stands; the scripted runs are unaffected |
