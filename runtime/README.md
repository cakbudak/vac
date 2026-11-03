# Enforcing runtime

The decision step of VAC: what runs between a client and a tool and decides each call before it is dispatched.

- `guard.py` — `authorize`, `dispatch`, `dispatch_async`. The client's existing boundary decides first and is never widened; the revision attestation (installation, served definition, contract) must match the pin; the effect verdict computed from pre-call state must be `allow`. Anything else is `review` or `block`, and such a call is never invoked. Reviews are resolved by the parent policy.
- `mcp_proxy.py` — the guard as an MCP stdio proxy in front of an unmodified server. It reads the served definition from the server's own `tools/list`, attests installation and contract, records each decision in the ledger before the request leaves, answers held calls itself with an MCP error result, and moves every later call to review if the served definition changes within the session.
- `state_policy.py` — pre-call state policies; `git-index-state` is the predicate S of the git controller study (`real-mcp/analysis/`).
- `network_scope.py` — per-invocation network declarations: `read_file` with `isUrl: true` may reach only its own URL's host; README-documented background hosts form a separate class.
- `decision_ledger.py` — hash-chained decisions, fsynced before dispatch; `verify` detects any edited, inserted or removed record and `head()` gives the chain head for an external witness.
- `pins/git.json` — the installation, served-definition and contract digests of the reported git run.

`tests/` holds 21 tests: the guard's boundary, revision and dispatch rules, a tool whose hidden write must not happen on review, the proxy end to end over stdio against a recording server (allowed call forwarded once after its ledger record, held call never received, pin mismatch, definition drift within a session, existing boundary), the state policy on crafted `.git/index` files, network scoping and the ledger.

On the live git server the proxy held 65 of 480 calls on ten new seeds with no held call reaching the server and no read-only call rewriting the index (`real-mcp/analysis/GUARDED_RUN.md`).
