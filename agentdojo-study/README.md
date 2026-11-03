# VAC — learned, governed tool-effect contracts on the AgentDojo runtime

**Verifiable Agent Control (VAC)** · the synthetic study of the VAC research package
(`../VAC_Research_Description.md` §2.7) · Cengizhan Akbudak, Vienna, Austria, with Hamna Qaseem
(collaborator: blind contract production and qualification, sealed benchmark families)

A documented tool can have an undocumented, state-conditional side effect — a static measurement
across 10,240 public MCP servers finds substantial description/implementation mismatches in about
one in eight (Li et al. 2026). This package measures, on the
real AgentDojo tool runtime, whether a controller can learn a **revision-pinned effect
contract** for such a tool from a bounded number of isolated executions, whether that contract
stops the hidden effect on actions the controller has never seen while preserving legitimate
writes, which of its guards are load-bearing, what it costs to govern the tool once an effect is
witnessed, and where it fails. It runs the unchanged CaMeL interpreter with and
without the learned contract on every family with two hosted models, and it attacks the
controller with scripted searches and with language models.

## What is in the package

| Path | Content |
|---|---|
| `RESULTS.md` | **generated** from `results/` by `python -m vac_study.report`; every number is reproducible or verifiable by state |
| `METHOD.md`, `LIMITATIONS.md`, `EVALUATION_DISCIPLINE.md`, `DATA_DICTIONARY.md` | instrument, arms, statistics; scope; the study rules; the evidence files |
| `vac_study/mechanism_lab.py` | hidden-effect tool wrapper, worlds, grader, 2-junta learner, the 7 arms of the hand-written-family study |
| `vac_study/extended_study.py` | 18 families, 12 arms, budget sweep |
| `vac_study/adversary.py`, `vac_study/extended_adversary.py`, `vac_study/llm_adversary.py` | bounded scripted attackers; the LLM-driven attacker with manifests |
| `vac_study/ablation.py` | guard ablation (unanimity, revision pinning, unseen-token review, CaMeL precedence) |
| `vac_study/induced_vocabulary.py` | label-free induced feature vocabulary and the learner on top of it |
| `vac_study/lifecycle.py`, `vac_study/lifecycle_study.py` | tool-trust lifecycle: effect ledger, ratification and brake, governed contracts, decision order; its measured cost |
| `vac_study/camel_bridge.py`, `vac_study/live_camel_study.py`, `vac_study/verify_live.py` | the CaMeL policy veto; the live-model harness with pre-I/O manifests; verification of live and attacker records by state |
| `vac_study/stats.py`, `vac_study/report.py`, `vac_study/verify*.py` | family-level statistics; RESULTS.md generator; evidence verifiers |
| `vac_study/effects.py`, `vac_study/runner.py` | probe receipts and implementation-revision digests; the reference arms on the unmodified official AgentDojo task |
| `tests/` | 52 regression tests plus `camel_policy_smoke.py` (no model) and `fake_privileged_llm_server.py` (deterministic stub for dry runs) |
| `results/` | all evidence (see `DATA_DICTIONARY.md`); `results/live/` holds the live matrices, the attacker episodes and their manifests |
| `scripts/` | environment setup, pinned CaMeL fetch, byte-for-byte reproduction of every deterministic study, checksums |

Upstream code is **not** vendored: AgentDojo 0.1.35 comes from PyPI and CaMeL
(google-research/camel-prompt-injection, Apache-2.0) is fetched at commit `f083b6b` by
`scripts/fetch_camel.sh`. Neither is modified.

## Reproduce

```bash
bash scripts/setup_env.sh        # venv, agentdojo 0.1.35, numpy, scikit-learn, pytest, CaMeL @ f083b6b
bash REPRODUCE.sh                # tests, verifiers, byte-for-byte regeneration of all deterministic evidence
```

`REPRODUCE.sh` runs in about seven minutes on one CPU core and needs no model, no API key and no
network beyond the two installs. It regenerates every deterministic file (main study, attacks,
statistics, guard ablation, induced vocabulary, lifecycle) and verifies live and attacker
records against their manifests and final state. Model output is not byte-deterministic, so the live studies are re-run rather than
replayed:

```bash
# any OpenAI-compatible endpoint (OPENAI_API_KEY / OPENAI_BASE_URL); writes <out>.manifest.json before the first call
.venv/bin/python -m vac_study.live_camel_study --families 0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17 \
    --seeds 11,22,33 --model <model-id> --out results/live/camel_live_<model>.jsonl
.venv/bin/python -m vac_study.llm_adversary --seeds 11 --model <model-id> --out results/live/llm_attack_<model>.jsonl
.venv/bin/python -m vac_study.verify_live results/live/*.jsonl

# dry run of the harness with a deterministic stub (tests wiring, not a model):
.venv/bin/python tests/fake_privileged_llm_server.py --port 8765 &
.venv/bin/python -m vac_study.live_camel_study --base-url http://127.0.0.1:8765/v1 --model stub \
    --model-kind deterministic_stub --out results/live/harness_dry_run.jsonl
```

## Headline numbers (all in `RESULTS.md`, asserted by `vac_study/verify_release.py`)

* **Main study.** 16 in-class families × 3 seeds, 32 isolated probes per instance: the learned
  contract allows **3,133 of 3,133** legitimate writes and **0 of 1,475** hidden-effect actions on
  held-out files; the tool-name allowlist and the unchanged CaMeL workspace policy allow all
  1,475; blanket review allows 0 legitimate writes; an equal-probe feature-vector lookup allows
  820; an abstaining decision-tree ensemble allows 2,246 (and 65 unsafe actions at 8 probes).
  Zero unsafe allowances inside the hypothesis class follows from realizability and unanimity;
  the comparisons that are true by construction are marked as such.
* **Misspecification.** 36 of 93 hidden effects pass the two-feature learner when the trigger is
  a token never seen in training, more probes do not repair it, scripted and LLM attackers
  exploit it within 8 attempts; an unseen-token review restores 0/93 at 36 reviews. A
  three-feature rule costs the two-feature learner 74 % of its utility; a 3-junta class recovers
  it (258/273) with 0 unsafe.
* **Guard ablation.** Majority vote instead of unanimity: 200/1,475 unsafe at 8 probes, 0 at 16
  and 32. No revision pinning: a stale contract allows 441/584 hidden effects on a changed
  implementation. No unseen-token review: 36/93. No CaMeL precedence: 4/4 denied writes
  re-allowed. Three guards load-bearing, one load-bearing only while ambiguity remains.
* **Induced vocabulary.** With predicates generated label-free from the candidate strings instead
  of the twelve hand-written features (27 predicates instead of 12), the same learner allows
  3,133/3,133 legitimate and 0/1,475 unsafe on in-class families; the unseen-token rule is
  expressible in neither vocabulary, and on the three-feature family the larger vocabulary keeps
  wrong hypotheses alive that the small one refuted (6/15 unsafe instead of 0/15).
* **Live matrix.** Unmodified CaMeL with `nvidia/nemotron-3-ultra-550b-a55b` and
  `openai/gpt-oss-120b`, 18 families × 3 seeds × 3 arms each (900 records, 0 execution errors)
  under pre-I/O manifests. The two models give identical outcome tables: CaMeL alone carried out
  the hidden effect in all 53 harmful episodes; CaMeL + VAC in 0 of 53, every one blocked before
  dispatch, while writing 91 of 94 benign requests (the 3 held for review are all the
  misspecified three-feature family; blanket review wrote 0 of 94); the unseen-token exploit of
  family 8 passed CaMeL + VAC in 3 of 3, as predicted.
* **LLM attackers.** `openai/gpt-oss-120b` and `qwen/qwen3.6-27b`, budget 8, all 18 families,
  144 episodes: 31 of 32 successes against the allowlist on in-class families, 0 of 96 against
  the learned contracts; on the unseen-token family 2 of 2 against the plain contract and 0 of 2
  with the unseen-token review.
* **Tool-trust lifecycle.** 17 of 18 families reach the brake after three independent probe
  worlds; without a contract the braked tool allows 0/3,637 legitimate actions; a promoted
  contract with a recorded override restores 3,436/3,637 and re-exposes exactly the misspecified
  family's 36 unsafe allowances; a changed implementation sends all 5,220 actions to review.

`LIMITATIONS.md` states the study's scope. The real-server work is in `../real-mcp/`; the sealed
benchmark built from documented real mismatches by a second person is WP3.

## License

Apache-2.0 for code (`LICENSE`); CC BY 4.0 for text and synthetic data.
