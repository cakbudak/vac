# Scope of the synthetic study

The study isolates mechanisms on AgentDojo's workspace runtime. Each point states what the construction fixes and where the research program extends it.

1. **Vocabulary and hypothesis class.** The main study gives every learner the twelve features the hidden rules are written over, so for the 16 in-class families the true rule lies inside the hypothesis class and zero unsafe allowances follow from realizability plus unanimity; comparisons that are true by construction are marked in `RESULTS.md`. The induced-vocabulary study replaces the features by predicates generated from the candidate strings without labels and reaches the same safety and utility in class; on the three-feature family the larger vocabulary keeps wrong hypotheses alive (6 of 15 unsafe instead of 0 of 15). Predicate induction from state differences on tools written by someone else is WP2.

2. **Misspecification.** The unseen-token family is never refuted in training, because the refuting input never occurs there; scripted and LLM attackers exploit it within eight attempts. The unseen-token review is a lexical check that catches this construction (0 of 93 unsafe at 36 reviews). On real servers the state-conditional residue is handled by pre-call state predicates (`../real-mcp/analysis/`).

3. **Probes and effects.** Probes are executions on a deep-copied environment: deterministic, resettable and counted. One tool, `append_to_file`, carries one hidden effect per family, written by the authors. The real-server harness (`../real-mcp/`) probes live, non-resettable state, and the sealed benchmark of WP3 is produced by a second person from documented real mismatches.

4. **Attackers.** Two hosted models attack the four control arms on all 18 families with the scripted attacker's information plus observed effects, choosing among the 96 candidates with a budget of eight attempts. WP3 adds attackers that craft inputs.

5. **Live models.** The unmodified CaMeL pipeline ran on all 18 families × 3 seeds × 3 arms with `nvidia/nemotron-3-ultra-550b-a55b` and `gpt-oss-120b`, with provider-reported model identifiers in every record. The models write the tool call and the controller's decisions are deterministic, so the matrix tests that the veto holds inside the real pipeline. The official `workspace/user_task_0` run is an integration check.

6. **Roles and families.** Producer, learner, attacker and grader are separated by data flow in one process; sixteen in-class families come from one two-feature grammar, eight hand-written. Independent production and sealing of families by a second person is the first organisational step of the research program.

7. **Method and integration.** The active version space is a textbook method; the study measures the value of a contract that generalizes against lookups, blanket review, an abstaining statistical learner, the unchanged CaMeL policy and a name allowlist. VAC enters CaMeL as a pre-dispatch veto for one tool; on real servers the same veto runs as an MCP proxy (`../runtime/mcp_proxy.py`). The tool-trust lifecycle runs on the real runtime with a recorded acknowledgement in place of a human operator; operator behaviour under brake, override and review is measured in WP3.
