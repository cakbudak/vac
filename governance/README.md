# Operating discipline — one page

The four documents in this directory (*Research Governance Protocol*, *Benchmark Production and
Qualification*, *Metrics, Statistics and Acceptance*, *Negative Controls and Integrity Cases*) are
the detailed operating rules, first applied in the synthetic AgentDojo study.  This page states
which of their rules govern every research work package (WP1–WP3 are §4.7–§4.9 of
`VAC_Research_Description.md`), which apply to the sealed benchmark, and how the pilot applied
them.

## Rules that govern every work package

1. **Prediction before observation.** Predictions are written and dated before a run
   (`real-mcp/PREDICTIONS.md`: §1 before the first probe, §2 before the history-predicate test, §3
   before its controller run); contracts are written from documentation before any probe; every
   later correction is logged with its trigger and its effect on the numbers
   (`real-mcp/CONTRACT_CHANGES.md`). A correction may narrow a contract toward the documentation,
   never widen it beyond it. (Document 1, §9 and §13.)
2. **Verdict before execution.** A controller's decision on a held-out or agent call is recorded
   before the call runs and graded from state afterwards; the model's own account of what it did is
   never consulted. (Document 1, §9.1.)
3. **Receipts, digests, verifier.** Every call leaves a receipt with its own digest; every summary
   carries the digests of the installation, the served definition, the contract and the harness
   revision; a verifier recomputes every reported number from the receipts
   (`VERIFY.sh`). From WP1
   on, one frozen harness revision per run. (Document 1, §8 and §10.)
4. **Every attempt counts.** Aborted runs, provider failures and discarded attempts are listed with
   their reason, never dropped (the aborted-run line in `PILOT2_RESULTS.md` §5; the re-done agent runs in
   `real-mcp/CONTRACT_CHANGES.md`; the two agent attempts that produced no call,
   `real-mcp/analysis/GIT_INDEX_HISTORY_PREDICATE.md` §4).
   (Document 3, §3 and §9.)
5. **Roles that must not coincide.** The harness author does not write the blind half of the
   contracts, does not produce the sealed families and does not touch a frozen harness. One person
   may hold several roles; rights do not transfer between them. (Document 1, §2.)
6. **Claims marked by construction.** A comparison whose outcome follows from the design (a
   baseline that cannot see the effect; realizability plus unanimity) is reported and labelled as
   such, never as a finding. (Document 3, §6; practised in `agentdojo-study/RESULTS.md`.)
7. **Negative controls that carry over.** No-op state-change control (NC-05), metadata decoy
   (NC-06), benign lookalike (NC-07), tool-revision shift (NC-08) and capacity-only comparison
   (NC-12) apply to the conformance work as written. (Document 4, §2.)
8. **Pre-registration deposited.** Selection rule, contract protocol, endpoints and analysis are
   fixed, tagged in the repository and registered publicly before the first probe of WP1; the gate
   is passed if the run happened as pre-registered, not if the result is favourable.

## Rules that apply to WP3 only

Mechanism families as the statistical unit, the production brief, independent qualification,
sealing, exposure history, the family-level power calculation and Plan-B options (Documents 2
and 3), and the integrity cases on benchmark production (Document 4, §4) describe the sealed
hidden-effect benchmark. They do not describe the conformance map, whose unit is the server and
whose statistics are descriptive rates with bootstrap intervals over servers.

## How the pilot applied them

Predictions before observation (`PREDICTIONS.md` §1–§3); contracts before probes with a logged
correction list (`CONTRACT_CHANGES.md`); verdicts before execution in the held-out, agent and
controller phases, and in the guarded run with the controllers fixed in its manifest before the
first call (`real-mcp/analysis/`); receipts with digests and verifiers that recompute every reported
number; aborted runs listed with their reason; the thirteen servers run again on a second machine.
The history-predicate test shows what a pre-registration is for: its first predicate was refuted
once, the refutation was recorded, and the amended predictions were written before the next run.
WP1 adds a human second contract writer and one frozen harness revision for every run, and labels
conformance and harm separately (research description §4.2).
