# Scope of the evidence

What the samples and observation channels cover, and the work package (§4.7–§4.9 of `VAC_Research_Description.md`) that extends each. The controlled AgentDojo study describes its own scope in `agentdojo-study/LIMITATIONS.md`.

1. **Sample.** Thirteen servers chosen by a rule fixed before the first probe: every official reference server that runs locally over stdio, the MSB benchmark server with three attack variants, and two widely installed third-party servers. Two MSB variants are the same installed script started with different attack arguments and share installation and served-definition digests (§3 H3). Eleven servers are deterministic under the traffic, so their seeds replicate; git and Desktop Commander vary between seeds. WP1 applies the same rule to at least sixty servers.

2. **Contract writers.** The human contracts were written from documentation before any probe, and every later correction is logged with its trigger (`real-mcp/CONTRACT_CHANGES.md`). The contract study adds seven model-written contracts per server. WP1 adds a second human writer, blind to the harness, for a random half of the servers.

3. **Observation channels.** Before/after snapshots of the sandbox, every fork and exec from the kernel's process connector, sockets of the server's namespace, DNS and connection attempts by name on a dead-end network, and the tool's response. Files created and removed within one call, in-memory state and protocol messages are read from the code by the static scans (`static-scan/`), which complement the harness on the behaviours execution cannot reach.

4. **Trigger classes.** The deviations public servers show under scripted and agent traffic are unconditional, state-conditional, timing-dependent or definition-level; input-conditional triggers keyed to tokens the probes never send are the subject of the sealed benchmark (WP3), produced by a second person from documented real mismatches.

5. **Agent traffic.** Four models, one run each, six user-style tasks per server, 7–36 calls per server and model; model identity is the hosted provider's report, recorded per run. Review rates on agent traffic are reported per model.

6. **The git controller.** S, P2 and the selected tree concern one official server and one benign effect, git's stat-cache refresh. Each predicate was written from receipts of earlier runs and scored only on runs made after it was fixed; S and the tree were then frozen and evaluated on ten new seeds. WP2 runs the same procedure on the state-conditional residue of the conformance map, with predicates chosen before the traffic they are scored on.

7. **Review cost.** Every review in the git results holds a legitimate call: S reviews 17 of 220 read-only calls in shadow mode, and under enforcement without a reviewer 65, because a held refresh leaves the index stale for the next reader. Harm and legitimate-call cost are reported separately throughout; the resolution of a review is a parameter WP2 measures.

8. **Pinning and attestation.** The enforcing proxy attests installation, contract and served definition and holds every call on a mismatch. Desktop Commander's served description embeds the host name, so its pin is per machine; WP1 specifies the pinning policy per server. The decision ledger is hash-chained and fsynced before dispatch; in WP3 its chain heads go to an external witness.
