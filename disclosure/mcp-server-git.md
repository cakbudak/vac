# Note to the maintainers of mcp-server-git

Observed on `mcp-server-git==2026.10.28` (30 October – 1 November 2026, twenty runs of the server
on two machines): `git_status`, `git_diff_unstaged` and `git_diff`, all annotated
`readOnlyHint: true`, rewrote `.git/index` on some calls — git's stat-cache refresh when the
index's cached stat data is stale.  The condition is exact in our runs: after `git_reset` (which
runs `git read-tree` and leaves index entries without stat data), the first of these three tools
to run rewrites the index; `git_add` and `git_commit` in between do not remove the condition,
`git_checkout` does.  Benign and ordinary git behaviour, but it contradicts the annotation as a
controller reads it: a tool documented read-only changed a file in the repository.  Either
`readOnlyHint` should be understood as "does not change the working tree or the commit graph"
(worth saying in the description), or the index refresh should be mentioned.  `git_log`,
`git_show`, `git_diff_staged` and `git_branch` did not refresh the index in our runs, including
directly after a `git_reset`.
