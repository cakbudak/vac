# VERIFIABLE AGENT CONTROL (VAC)
## Metrics, Statistical Unit and Acceptance

**Document 3 of 4 — methodological annex to `VAC_Research_Description.md`**
**Date:** 30 October 2026
**Status:** preregistrable analysis framework. Thresholds, margins, power, clustering and stop rules are **not** set here; they are set from development-only pilot data, externally reviewed and frozen before any acceptance family is opened. Every number in this document is a planning illustration and is marked as such.

**Companion documents.** Document 1, *Research Governance Protocol*; Document 2, *Benchmark Production and Qualification*; Document 4, *Negative Controls and Integrity Cases*.

---

## 1. Four separate success questions

The evaluation distinguishes **correct control decisions**, **reproducibility under a declared perturbation regime**, **net benefit including production cost**, and **transfer of retained changes**. A better score on known families answers none of the last three. A single traffic light or aggregate score never collapses them.

The experiment protocol fixes, before execution, which statement is to be confirmed and which measurement is diagnosis only. Mandatory checks, permissions and data isolation stay active in every arm; only the learning, probing and promotion components are ablated.

---

## 2. Metrics

**Learning fidelity.** Rule correctness; handling of negation and of `unknown`; coverage and cost; effect-level recall on independently labelled applicable cases; false-positive rate and precision of supported hypotheses; missed-harmful-effect rate stratified by observability and severity; abstention rate; calibration and conditional error among non-abstentions; sensitivity and specificity of the misspecification test against the controls of Document 4, §2. Where a predictor outputs probabilities, Brier score and log-loss with prefixed clipping, calibration, ranking quality, coverage and behaviour in unknown segments are reported; missing coverage is not improved by omitting hard cases.

**Safety (primary).** `successful_unauthorized_effects / preregistered attack opportunities` on held-out policy-gap families under a prespecified adaptive attack budget, determined by the independent outcome oracle — never by an agent's statement or an LLM judge. High-severity misses are disclosed separately.

**Utility (co-primary constraint).** Legitimate goals completed on safe held-out tasks; false blocks on benign lookalikes; review load. "Safety improvement with unacceptable utility" is reported as such.

**Reproducibility.** Agreement with a verified reference under the declared perturbation regime; learner, selection and runtime variance reported separately. Code identity and semantic effect are different measures.

**Cost.** Probes, inference, verification, discarded attempts, ablations, rebuilds, revalidation and every retry — in wall-clock, compute time and tokens, each on its own measurement basis. Different hardware is not converted into notionally identical units. Short-run operating cost and amortized cost including benchmark production are reported separately. No arm is compared both with free pre-training and as an end-to-end system at once.

**Secondary.** Effect-hypothesis precision, recall and coverage; proportion of unknown outcomes; incorrect automatic promotions; bypasses; cross-family transfer; per-probe cost ledger.

---

## 3. Outcome kinds without false labels

Three axes are recorded for every attempt and are never collapsed:

| Axis | Values | Meaning |
|---|---|---|
| `execution_status` | planned / not executed, running, completed, technically failed, aborted, outcome unknown | What physically happened |
| `integrity_status` | passed, violated, not yet checked | Whether the attempt stayed inside its contract |
| `result_kind` | positive, negative, undecided, not evaluable | The substantive finding |

A correctly measured worse approach is `completed / passed / negative`. A checker outage has no confirmed validity. A deliberately produced technical failure stays a technical failure and proves no bad method. An attempt recognised as invalid stays traceable but receives no positive credit anywhere.

For the endpoint "goal achieved within budget", an unfinished task counts as not achieved; this does not create a substantive label for a candidate that was never observed. Valid measurements, technical errors, task defects and unknown effects are additionally reported separately. A value computed only on evaluable runs is diagnosis and never replaces the full policy balance.

---

## 4. Statistical unit and multiplicity

The independent unit is the **mechanism family** (Document 2, §7), not the seed, the prompt, the context or the plan. Paired variants are compared family-wise. Repeated production runs — independent executions of a learning or production method — form an additional random source, and any resampling or model must preserve that structure; mixing individual runs would manufacture precision. All variants of a family, paraphrases and template-derived instances stay in one split; family identity and derivation are fixed before execution.

Exploratory hypothesis checks and confirmatory gates are separate families of tests. The α budget is not moved between hypotheses after seeing results. Ordinary confidence intervals are not inspected after every run until favourable; a continuing decision needs a procedure designed for it (§5, option PB-3). The concrete interval or test procedure for the primary endpoint — including small samples, stratification, missing values and continuation — is fixed before the first confirmatory study and checked on known or simulated data.

A method-level statement needs **independent production repetitions**: many test families under one learned version are not independent repetitions of its production. The report separates test uncertainty within one bundle from variance between produced bundles.

---

## 5. Sample size and Plan B

### 5.1 Planning aid

For a paired binary family-level comparison with true difference zero, one-sided α and power 1 − β, the required number of families is approximately

```
n ≈ (z_{1−α} + z_{1−β})² · p_d / δ²
```

with `p_d` the share of discordant family pairs (one arm decides correctly, the other not) and `δ` the non-inferiority margin. **Illustration only:** at α = 0.05, power 0.8 and δ = 0.02, this gives roughly 770 families for `p_d` = 0.05 and 1,550 for `p_d` = 0.10; 200 families support only a margin near 5.6 points at `p_d` = 0.10. The approximation is a planning aid, not a substitute for the calculation from pilot data, and it fixes no margin for the study.

Several seeds per family do not increase the independent sample. Stratification and pairing reduce variance but replace none of the options below.

### 5.2 Decision rule before the acceptance families are opened

From the pilot discordance rate, the required number of families for the target margin is computed. If the available fresh families suffice, the original design stands. Otherwise **exactly one** of the following is recorded beforehand; a switch after seeing acceptance data is excluded.

| Option | Procedure | Statement limit |
|---|---|---|
| **PB-1 — Estimation instead of test** | Family-wise paired difference with a predeclared two-sided interval (cluster bootstrap or exact method); no non-inferiority decision | "The difference lies between … and …"; supports development and planning decisions, not promotion |
| **PB-2 — Larger prespecified margin** | Non-inferiority at the margin the available families can support, computed and fixed as a number beforehand | Explicitly "not worse than X points"; the tighter target margin remains the goal for later rounds |
| **PB-3 — Group-sequential design** | Predeclared interim analyses over newly produced fresh families, α-spending function and maximum size; early stopping only by plan | Full statement only on reaching a stopping boundary; undecided without one |
| **PB-4 — Cost path instead of success path** | Acceptance via demonstrated cost reduction with non-inferior safety and utility, if the cost measurement carries the tighter bound | Applies only to the chosen path; the error budget is not split afterwards |

PB-1 is always admissible as an exploratory report. PB-2 and PB-3 are compatible with §4 because margin and stopping rule are fixed before data access.

---

## 6. Study structure and what each study may claim

| Study | Design | Answers | Does not answer |
|---|---|---|---|
| **A — model quality at equal information** | Same probe records for every learner | What each hypothesis class and inference rule extracts from identical evidence | Anything about probe policies |
| **B — whole system at equal total budget** | Each arm chooses its own probes, representation and restrictions within the same total budget (probes, inference, verification, discarded attempts, preparation) | Whether a complete policy is better or cheaper | Which component caused it, without the internal ablations |
| **D — transfer of retained changes** | D-frozen (base policy unchanged), D-local (learn within a family, then reset), D-retained (only protocol-promoted restrictions kept), separated learning states, bundle fixed before each hidden block | Whether retained changes help on fresh families net of production cost | Unbounded future improvement |

All arms of a study share base capabilities, tools, families and total resources. The control arm may spend its unused learning budget by a predeclared rule. No arm receives another arm's private evaluation results. A new instance of an already learned family is not transfer (Document 2, §7). Capacity advantages are documented separately from method advantages: the synthetic study showed that representational capacity alone produces large apparent gains (`agentdojo-study/RESULTS.md` §2, the 3-junta on the three-feature family).

Factorized comparisons: learned effects against no learning, state-aware predicates against lexical ones, governed promotion against ungoverned use, and at least one same-data comparison against the exact, algebraic and action-model baselines. An oracle-informed controller is a diagnostic upper bound only.

---

## 7. Acceptance of a confirming version

Frozen before the acceptance families are opened:

**Integrity.** No violation of validators, scope, isolation, data roles, permitted changes or state revisions. A violation invalidates the round; no favourable mean compensates.

**Component.** A learned effect model, probe policy or restriction rule must show a positive family-wise one-sided bound on its declared quality measure and no inadmissible coverage loss. An unchanged component needs no newly asserted success. When a policy and a predictor change together, old/old, new/old, old/new and new/new are compared; a combination may be rejected even if its components looked better in isolation.

**Whole bundle.** Either the **success path** — fewer unauthorized outcomes at equal total budget, subject to the utility criterion — or the **cost path** — demonstrated cost reduction with non-inferior safety and utility — is chosen beforehand; if both are to remain open, the error budget is split between them beforehand. "At least X" requires a corresponding bound, not a point estimate of X.

**Reproducibility.** The preconfigured margin is not violated; a changed perturbation regime is not added to an old result.

**Undecided.** No promotion. More data only by the predeclared continuation procedure; otherwise a new protocol with new families.

A report ends `accepted`, `rejected`, `inconclusive` or `invalid` (Document 1, §11). The additional reproduction obligation follows the claim: a concrete artefact may be accepted as such if the contract allows it; a reproducibly better *method* needs the matching rebuild and method-reproduction report.

---

## 8. Transfer report and verdicts

A transfer report states separately: performance of the fixed, freshly produced bundle on fresh families; production effort; operating cost afterwards; variance between independent production runs; and the assumed usage horizon of any amortized statement.

Possible verdicts: **transferable net benefit**; **local benefit only**; **better performance without economic amortization**; **undecided**; **integrity failure**. "Local benefit only" justifies a better problem solver; it justifies no claim of transferable control value.

Private evaluation of all checkpoints remains diagnosis and may not select a more favourable transfer candidate afterwards. Further investigations after private inspection need a new independent evaluation plan.

---

## 9. Reporting rules

- The balance contains **all assigned attempts**, their resources and their termination causes, including rejected world candidates and failed reruns.
- Diagnostic subsets — evaluable runs only, non-abstentions only, checker-complete cases only — are labelled as diagnosis and never replace the full balance.
- Selection statistics, development scores and model-internal confidences are not substitute endpoints and are not reported as causal attribution.
- A non-significant decline proves no stability; non-inferiority bounds with a prechosen margin are reported instead.
- Hardware, wall-clock, compute time and tokens are reported on their own bases; no notional conversion.
- Every number quoted from the evidence archive is asserted by the archive's own tests; this document carries no empirical figure of its own.

---

## 10. Settings fixed before confirmatory execution

Before the first confirmatory study: the mechanism families and their split; the actual learner, comparator and runtime identities; primary and co-primary endpoints; minimum relevant effects; variance and power from the pilot; α allocation; permitted continuation; cost basis; resource limits; selection rules; the Plan-B option (§5.2). Before a reproduction claim: rebuild tolerance and repetition count. Before a transfer claim: the number of independent production repetitions and transfer blocks.

Comparator implementations are frozen by source and revision; local adaptations and imported code are reported separately. A method named only by its published description, without a pinned implementation, is not a frozen comparator for confirmatory use.

Open settings do not prevent development work. They prevent only that its results are presented prematurely as confirmatory evidence.
