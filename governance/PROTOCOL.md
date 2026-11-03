# VERIFIABLE AGENT CONTROL (VAC)
## Research Governance Protocol

**Document 1 of 4 — methodological annex to `VAC_Research_Description.md`**
**Date:** 30 October 2026
**Status:** prospective, binding for every arm, comparator and negative control of the VAC study. This document states rules; it reports no results and makes no empirical claim.

**Companion documents.** Document 2, *Benchmark Production and Qualification*; Document 3, *Metrics, Statistics and Acceptance*; Document 4, *Negative Controls and Integrity Cases*. The four documents are self-contained: the funded work depends on no private specification, code or infrastructure. They were written for the synthetic AgentDojo study; `governance/README.md` states which of their rules govern every work package of the funded work and which apply to the sealed benchmark (WP3) only.

---

## 1. Purpose and scope

VAC asks whether learning the effects of unfamiliar tool actions from bounded observations reduces independently measured unauthorized outcomes under a fixed safety objective, beyond what strong existing controls achieve at equal information. The answer is only worth having if the measurement cannot be gamed — by the learner, by the investigator, or by the benchmark. This protocol fixes how evidence is produced, who may see what, which statements may be derived from which checks, and when a result counts.

The rules are domain-neutral. They apply unchanged to the VAC learner, to every external comparator (static mediator, trusted monitor, information-flow and temporal controllers, safe action-model learners, counterexample-guided rule learners, algebraic and exact learners, statistical baselines) and to every negative control. A comparator that is given an easier protocol than the VAC arm produces no admissible comparison.

Nothing here is claimed as a scientific contribution. The protocol is the instrument's operating discipline, published so that it can be reused and challenged.

---

## 2. Roles and authority

Roles are **authorization roles**, not necessarily distinct people or distinct model products. One person may hold several; one model type may serve several. What may not be shared is access: the rights of one role do not transfer to another by holding both, and correlated errors of a shared model are themselves a qualification question (Document 2, §6).

| Role | Holds | May not |
|---|---|---|
| **Learner** (untrusted) | Scoped view of traces and isolated probes; its own hypotheses, effect models and candidate restrictive rules | Read oracle labels, amend objectives, expand permissions, set or remove data labels, approve anything |
| **Verifier** | Declared model, invariant, non-expansion obligations, decidable fragment, solver | Certify completeness of real effects; approve on `unknown`, `timeout`, `verification_error` or `not_checked` |
| **Policy owner** | Authority to promote a version-pinned restrictive rule for *new* runs | Promote on an undecided result; change a running run's identity |
| **Mediator** | Version-pinned configuration; dispatch of actions; effect receipts | Hold privileged host credentials for the agent; treat a timeout as non-execution |
| **Independent outcome oracle** | True transitions and sealed outcome labels | Be read by the learner; be replaced by an agent's statement or an LLM judge |
| **Benchmark producer** | Design and materialization of mechanism worlds (Document 2) | Qualify its own worlds; pass private references to the learner |
| **Independent qualifier** | Qualification contract, control solutions, fail variants | Tune a world to a candidate; set `qualified` from a generator's self-grade |
| **Builder** | Clean environment and exactly the permitted inputs of a recipe | Receive acceptance or audit assets; hold verifier rights |
| **Investigator** | Development data and released feedback; protocol authorship before freezing | Open acceptance detail before the bundle is fixed; move the α budget after seeing results |
| **External reviewer** | Frozen protocol, acceptance criteria, analysis plan; audit view at the scheduled opening | Carry audit-derived hints into the next development round (§5.2) |

The learner can propose; it can never authorize. The verifier can prove a statement about a declared model; it can never prove that the model is complete. The policy owner can promote; it can never make a failed or missing check into a pass.

---

## 3. Four separate verification questions

| Verification | Question | May **not** be inferred from it |
|---|---|---|
| **Function** | Does the artefact — a learned effect model, a promoted restriction, a benchmark family — pass the defined checks? | That the way it was produced was permitted or reproducible |
| **Integrity** | Were changes, data, models and execution kept within the declared contract: roles, scopes, isolation, data roles, revisions? | That the artefact is better |
| **Reproduction** | Does the claimed artefact or result re-emerge from the submitted recipe in a clean environment? | That the method transfers to other families |
| **Transfer** | Do retained changes help on fresh mechanism families against a frozen control? | Unbounded future improvement |

The four answers are recorded as four independent status axes (§11) and are never derived from one another. A functional pass with an integrity violation is recorded as an **invalid attempt**, not as a result. A method that is interesting but outside the claim contract (§12) may be reported as a separate approach; it does not count as success of the original claim.

---

## 4. Zones and information flow

### 4.1 Four zones

**Research / learner zone.** The task, public development data, admitted baselines, a bounded workspace and released tools. No private tests, no verifier secrets, no host credentials. Network access only by explicit contract; for the synthetic study, none by default.

**Builder zone.** Reproduces a submitted method from the declared development inputs. Receives no acceptance or audit assets and none of the verifier's rights. Hands artefacts over under control.

**Untrusted candidate zone.** Executes a learned effect model, a proposed restriction or an agent action under limited rights. Sees only the inputs required for that execution — never the private corpus or its reference labels.

**Verifier control zone.** Holds private test definitions, reference outcomes, scoring logic and release keys. Drives tests through a narrow input/output contract and computes scores independently of the candidate process.

A candidate may need to see one test input to answer it. That confers no right to enumerate the private corpus, read test code, write results out, or request repeated private queries. These interface and leakage boundaries are part of the threat model.

### 4.2 Why a read-only mount is not a boundary

When candidate code runs in the same privileged process as private tests, a read-only test directory is not enough. Process rights, visible files, environment variables, import and hook paths, output channels and network connections are all part of the boundary. The isolation chosen for a study is demonstrated by negative tests (Document 4, §3), not by a container name or a configuration flag. The protocol claims no defence against unknown kernel or runtime faults; residual risks are documented and limit what may be released.

The candidate process receives a freshly assembled allow-list environment: only declared file paths and only the network connections the contract permits. Provider and host secrets, private test paths, user configuration and confidential process variables are not inherited. A subprocess or a separate package environment by itself proves no isolation.

Untrusted artefacts are never loaded through a deserialization path that can execute submitted code inside the verifier. The permitted artefact and loading contract is fixed and tested before use.

### 4.3 Information flow at the action boundary

Zones bound *who* sees private assets. They do not bound *where* content flows that an agent may legitimately read in its own zone. An agent can pass protected content through an individually permitted action to a recipient who could not read the source. This is the disclosure scenario VAC studies, and it is treated as a first-class control, not as an edge case:

- Read paths attach **provenance/restriction labels** to data at the access layer. The model can neither set nor remove a label; a label or a claim of "public" in model output is ineffective.
- Every action to be released is checked against the labels of **all** data that flowed into the run up to that action and against the target or recipient scope, before a receipt is issued. The decision is one of `flow_allowed`, `flow_blocked` or `needs_authorization`, recorded with the contributing labels, and never reinterpreted afterwards.
- Derived content — summaries, translations, reformulations, encodings, parameters, file names, metadata — inherits the labels of its sources until an **authorized role declassifies** it, with a record, scope and validity period; declassification is revocable and cannot be triggered by the agent.
- A source without a label receives the strictest restriction of its scope, never "public"; the missing label is itself a finding.
- The first implementation conservatively attributes to an action every label read in the run before it was proposed. Finer attribution to partial content is a research question and may not reduce coverage without the reduction being measured and reported.
- The flow state survives interruption, resumption and any context compaction; a summary removes no labels.
- Covert channels outside the action content — timing, resource use — are out of scope and recorded as residual risk.

A string search for known secrets replaces neither the zone boundary nor the flow check. Where flow control is disabled or not implemented, no flow protection is claimed and no interface may switch it on unchecked.

### 4.4 Protection of results and derivatives

The learner and the investigator receive only the projection the protocol permits: for an acceptance round, the released decision or an abridged report. Private individual cases, reference answers, exact failure triggers and recommendations derived from them stay in protected views. Debriefs, reviewer sessions, log exports, dashboards and search indexes follow the same boundary.

When an authorized new development is to use private findings, its evaluation plan is set up afresh and independently; the consumed data set is then no longer fresh evidence.

---

## 5. Evidence classes and data roles

A **data role** states origin; a **usage right** states permitted purpose. Both are kept separately, and a text field claiming a role is not a right.

| Origin / role | Visible in the learning context? | Usable for learning, probe selection or rule synthesis? | Condition |
|---|---|---|---|
| `development_input` / `development_feedback` | Yes, within the assigned scope | Yes, where released for it | Origin rights, split and family preserved |
| `operational_observation` | Through an authorized view | Not automatically; only after an eligibility check | Rights, source role, data contract |
| `acceptance_result` | Only the released decision or an abridged projection | No detail tuning on the consumed acceptance families | Fresh families for a new round; the decision counts as consumed feedback |
| `acceptance_detail` | No, in the research or learner context | No | Sealed verifier / reviewer view |
| `audit_detail` | No until the scheduled opening; then review only | No, in the running programme | An audit is a report, not a later training split |
| `derived_restricted` | Only with equivalent origin rights | No while the source restriction holds | Summaries, embeddings, statistics and caches inherit the restriction |
| `hypothetical` / `synthetic_prediction` | As a labelled hypothesis | Never as an observed outcome | Never recorded as an execution observation |

### 5.1 Combination and unlocking

Combining sources yields the **intersection** of their permitted purposes, not the union. Unlocking requires an explicitly authorized rule and is not a learning operator. The rule covers memory compression, caches, semantic search and exported reports.

### 5.2 A forbidden migration

An audit shows that a particular input triggers a failure. A reviewer writes "watch for input X". That sentence remains audit-derived and may not enter the next development run as a neutral hint. What is permitted is the recorded fact that the audit failed, followed by a new, independent development and verification plan.

### 5.3 Authorize retrieval first

Any retrieval into a learner or investigator context is filtered by purpose and evidence policy before content is returned. Where a shared index is used, access control must hold for hit texts, ranks, metadata and cached responses. The simpler and preferred solution is separate released projections, not a later instruction to the model to ignore forbidden hits.

---

## 6. Feedback levels

| Level | What it scores | Separation |
|---|---|---|
| **Public checks** | Give feedback during a development episode | Released development data |
| **Hidden task end-check** | The result selected *beforehand* for that episode | Independent; opened only after the selection is fixed |
| **Version acceptance** | A bundle fixed beforehand, on fresh mechanism families | Separate role, separate data role, frozen criteria (Document 3, §7) |
| **Locked audit** | The closing check at a milestone | Opened on schedule only; never a training split |

These levels are separated by verification stage, data role and authorized adapter; a candidate cannot swap them through a free parameter. **Every private opening is logged and makes the affected cases unavailable as fresh evidence.** Public and private scores must have the same declared meaning and direction; because their tasks may differ in difficulty, the baseline is measured in both conditions and improvements are compared relative to it.

Development tests hidden during an episode may become released development feedback after the episode ends, if that was defined beforehand. Acceptance and audit labels are strictly different and remain excluded from learning.

---

## 7. A failed check is not a pass

Every mandatory check returns an explicit status: `passed`, `rejected` (technical or substantive), or `not_checked` (timeout, service failure, missing dependency). No heuristic, model judgement or favourable score replaces a missing format, integrity or substantive check. A broken checking tool creates neither a fabricated negative label nor a pass.

The metric's name, direction, unit, computation, source and treatment of missing values are fixed before any selection signal (for probes, candidates or rules) is computed. The adapter reads a verifiable structured result, never free-form candidate output or a model's interpretation of it. A model may explain and flag suspected deviations; it may not redefine the metric's direction or the check's result afterwards.

Measurement, selection signal and acceptance judgement remain separate fields with separate sources. An unusual score may trigger an additional check; an ordinary or low score does not exempt an attempt from integrity controls — access rules, permitted changes and data roles apply to **every** attempt.

A bounded re-check of the same unchanged candidate may be scheduled; if the check still cannot be performed, the candidate stays unchecked and not releasable. A human exception path, where provided, is documented separately and is never presented as an automatic pass.

---

## 8. Identity and immutability

**Bundle revision.** Every run pins one immutable bundle: effect vocabulary, learner version, scope contract, policy and verifier revisions, comparator set, mediator configuration, tool definitions and permission scopes, benchmark family revisions, resource budget, seeds. References name concrete revisions, never "latest". States and observations may change within a run; its rules may not. A missing capability or evidence item ends the run or starts a *new* run with a fitting bundle; there is no silent mode switch mid-run. A declared and qualified fallback may be part of a composed policy; its actual use stays separately visible and bypasses no required check.

**Behaviour digest.** The transitive, revision-bound, execution-relevant configuration — but **not** its own evidence (calibration, qualification, acceptance status). Otherwise the bundle would contain the evidence and the evidence the bundle. Evidence names the behaviour digest it is about. A report-only correction may not relabel old evidence onto a different behaviour. Redundant references to the same dependency must resolve to the same revision; a contradiction is a validation error.

**Evaluation identity.** The measurement configuration — oracle revision, scoring rule, projection, adapter and library versions, invariant revision — has its own digest. A result or its qualification is never part of its own digest. An evaluation that influences selection, repetition, stopping or the available budget *inside* a run is part of the behaviour digest; a purely offline report without feedback is not. The decisive criterion is the actual information and control flow, not the label on a dashboard.

**Runtime identity.** Where any component is a language model or a provider-hosted service, model and weight identity, tokenizer and template, quantization, adapters, engine version, relevant kernel and batch settings, generation options and hardware class are recorded. A provider that does not disclose a precise identity receives a correspondingly limited evidence scope; missing fields are not guessed. The same alias or endpoint is never a proof of identity.

**Content digests** are computed from a declared canonical serialization; the digest field, transport metadata and later display values are not part of their own input. Hash algorithm and canonicalization revision belong to the identity definition.

---

## 9. Prediction before observation, and the predictor contract

### 9.1 Binding order

fix the candidate → store the prediction → store the selection → execute → store the observation → form the prediction–observation pair.

A score produced after seeing the outcome may be labelled *diagnostic*; it never replaces the original pair. Unexecuted candidates have no observation. An aborted stream, infrastructure error or unknown timeout receives a completion status and is not a fabricated negative label. Post-hoc scoring of old candidates is permitted as a separately labelled offline analysis and may not be presented as a prediction that existed at the time.

### 9.2 Completion is several axes

Transport completion, complete response, provider end, external effect, substantive outcome and cost closure are different axes and are recorded separately. Effect receipts distinguish `attempted`, `dispatched`, `committed`, `observed`, `failed` and `unknown`. A timeout after dispatch is not evidence that the action did not occur; recovery reconciles execution identifiers before any retry. An unknown substantive outcome is not a fabricated training label and does not disappear from the cost account.

### 9.3 Three reliability states

| State | Precondition | Behaviour |
|---|---|---|
| `reliable` | Predeclared quality and coverage requirements met in the applicable segment | The prediction may be used as configured |
| `unreliable` | Sufficient evidence of a relevant violation of the requirements | The declared baseline is used; an update may be requested by protocol |
| `insufficient` | Too little data, missing mandatory features, or outside the confirmed range | The declared baseline is used; no positive reliability claim |

A probability of success is not an uncertainty measure. Calibration and coverage are checked separately. The fallback is part of the fixed bundle and does not change the active predictor version mid-run.

**VAC's effect learner is an instance of this contract.** Its prediction is the final state after a plan; its baseline is review; its state is `reliable` only when all surviving hypotheses agree **and** the declared scope contract covers the case, and `insufficient` otherwise. Realizability makes the reliable state exact. Misspecification is the case in which the state is asserted reliable while the predictor is wrong; the misspecification test is the mechanism meant to move such cases to `unreliable` before the exposure window, and it is evaluated against the controls of Document 4, §2.

### 9.4 Selection bias and the randomized audit sample

A predictor sees most often the candidates it favours; blind spots can stay hidden. In isolated exploratory operation a budgeted randomized sample is therefore observed **independently of the predictor's ranking** and kept separate from action-selection-biased observations, with its cost recorded. For each decision the rule, candidate set, randomization and selection probability are stored where exactly determinable; an unknown propensity is not guessed. The study prefers direct randomized comparisons over complicated post-hoc correction.

### 9.5 Controlled predictor update

An update to the effect predictor is a **new predictor version** under a frozen update protocol: minimum data per segment, permitted data roles, quality triggers, budget and acceptance procedure. A single error or a high subjective uncertainty does not trigger an update. A successful fit means only `fitted`; component check, pair check with the policy that uses it, and, where claimed, rebuild follow separately (§11, Document 3 §7). When a policy and a predictor change together, old/old, new/old, old/new and new/new are compared; a combination may be rejected even if each component looked better alone.

---

## 10. Recipe-based reproduction

A generated artefact needs a readable, executable recipe: source, entry point, pinned dependencies, data and model references, configuration, seeds, expected outputs, resource limits. Where source code is itself the product, its documented build and run path suffices; no second recipe is invented.

The builder starts from a clean state with exactly the permitted inputs and produces a new artefact that passes the same integrity and substantive checks. The recipe has no access to private evaluation assets even if the original candidate later scored well on them. The clean environment does not inherit agent caches, installed libraries, user configuration or background processes; a missing dependency yields a clear incomplete result, not an improvised installation under verifier rights.

**Deterministic reproduction** requires identical relevant artefacts or a declared canonical equality; timestamps and non-functional metadata are ignored only if that was fixed beforehand. **Stochastic reproduction** fixes independent seeds, repetition count, admissible performance and cost deviation and the evaluation procedure beforehand; a single lucky rebuild proves no stable method improvement.

Recipe structure check, actual rebuild and statistical method reproduction are three findings. "Recipe present" is never displayed as "reproduced". The evidence archive's `reproduce` command is the deterministic case and establishes software reproducibility only.

Transfer of a fixed bundle for hidden evaluation uses a server-side content list with digests. Self-declared hashes do not prove admissibility; they identify what was actually checked. Paths must lie inside the permitted area; symlinks, traversal, later modification and implicit workspace dependencies are checked separately. A change by a supporting reviewer creates a new candidate with its own identity and its own checks; neither the previous results nor the previous seal carry over.

---

## 11. Four status axes and evidence invalidation

### 11.1 Axes

| Axis | Values | Question |
|---|---|---|
| **Artefact acceptance** | `proposed`, `component_evaluated`, `pair_evaluated`, `accepted`, `rejected`, `inconclusive`, `invalid` | What has been checked about this candidate? |
| **Method reproduction** | `recipe_present`, `rebuild_passed`, `rebuild_failed`, `method_reproduced`, `insufficient` | Which reproducibility statement is established? |
| **Version activation** | `inactive`, `active`, `retired`, `rolled_back`, `suspended` | Is this bundle used for new runs? |
| **Transfer** | `local_only`, `transfer_evaluated`, `transfer_supported`, `transfer_inconclusive` | Which transferable effect was examined? |

`accepted` is not `method_reproduced`; `fitted` is not `active`; an active isolated research version is not released for external effects. `invalid` denotes a violated protocol or integrity failure, not merely poor performance. Rejected and invalid artefacts stay traceable but inactive. A favourable development score or a high selection priority can set none of these axes.

### 11.2 What a change invalidates

| Change | At least re-examined | Kept historically |
|---|---|---|
| Effect vocabulary, hypothesis language, representational capacity | Comparability of all arms, matched-capacity claims, abstention contracts, misspecification exposure | Old results under the old vocabulary, named as such |
| Learner version, probe policy, restriction synthesis rule | Component quality, pair check with the policy, coverage, affected downstream contexts | Original predictions remain unchanged |
| Scope contract or completeness claim | Every reliability state that depended on it; every "0 unsafe" figure | Nothing transfers: a scope claim is the safety property |
| Policy revision, verifier, invariant, decidable fragment | Non-expansion obligations, model-relative checks, promoted rules | Old proofs under the old model only |
| Oracle, scoring rule, success criterion | New comparison contract, new comparability, possibly new baseline | Old scores only under the old measure |
| Benchmark family revision, taxonomy, split assignment | World qualification, family and split binding, exposure history | Findings under the old world remain validly named |
| Mediator, tool definitions, permission scopes, execution environment | Bypass and leak canaries, receipts, TOCTOU tests, cost basis | Old measurements on their old platform |
| Comparator implementation or source revision | Frozen method comparison; local adaptation and imported code separated | A verifiably unchanged artefact stays the same |
| Report presentation only | Correct references and rights | All behaviour evidence, where behaviour is verifiably unchanged |

The table demands a dependency check, not a blanket repetition of every study after every text correction. Unaffected evidence may continue to be referenced; the reason it is unaffected must be stated.

Invalidated evidence is **closed** and new evidence begun — never continued with old sums. A combination candidate inherits no `accepted` or calibration status from its references. A change by any role creates a new candidate revision.

### 11.3 Atomic activation and running runs

Activation of an accepted change is one consistent operation that checks current rights, scope, the unchanged bundle, the validity of the acceptance and the **expected** current binding revision. On conflict the operation fails; it does not silently promote onto the newer state, whose incumbent may have changed. Two promotions against the same active revision cannot both succeed. A read followed by an unconditional write does not meet this contract.

Activation applies to new runs only. Running runs keep their pinned bundle. A critical finding can block future starts and end running runs; it does not rewrite their identity. Rollback returns the active binding to a previously valid version that is **still admissible** for the current scope; a formerly valid bundle is not automatically admissible today. Rollback does not undo external effects, which the synthetic programme excludes and which later domains must handle with their own adapters. "Pause learning", "stop new runs", "abort a running job" and "roll back the active version" are different operations with different authority and records.

### 11.4 Monitoring without mixing evidence

Operational reports show results per bundle, segment and measurement basis. Sequential statistics are closed and restarted on a relevant behaviour change; old predictor errors are not relabelled as current predictions. An alarm indicates possible degradation, not its cause, and acknowledging it restores no violated assumption. Sentinel measurements remain separate from the locked audit; once a monitor influences development decisions, its feedback is part of the development history and new confirmatory acceptance uses fresh families.

---

## 12. Claim contract

Before any comparison, an **effect-learning claim** binds:

- the **object** being improved — an effect model, a probe policy, a restriction synthesis rule, a benchmark generator; different objects have different statement limits;
- the **baseline** and the **permitted substitutions**;
- the **target quantity**, the **population** (which mechanism families), the **resources** and the **statement limit**.

| Object | Example | Required statement limit |
|---|---|---|
| Learned effect model | A scoped effect table for one action family | Passes the checks defined for that family; no claim about unmodelled effects |
| Probe policy | A different intervention design at equal budget | Better in the studied population; the combination with the learner checked separately |
| Restriction synthesis rule | A rule that turns policy-gap witnesses into restrictive candidates | Non-expansion within the declared fragment; utility criterion met; no deployment authority |
| Benchmark generator | A producer of harder, qualifiable families | Quality and coverage of produced families checked separately, not checker agreement |
| Method | A learning or probe-selection strategy | Independent production repetitions and fresh families; one lucky candidate is not enough |

An algorithmic substitute may be admissible in an efficiency claim and out of contract in a learning claim. The verifier checks the claim's terms, not only a green score. A model review may flag deviations for human inspection but cannot change the terms afterwards.

---

## 13. Pre-registration of each experiment

Every experiment, exploratory or confirmatory, writes **before execution**: hypothesis, change, expected distinguishing observation, comparison basis and measurement rule. After execution it records the actually executed configuration, data and bundle identities, measurements, costs, deviations, interpretation and the next decision. The interpretation separates *observed* from *conjectured*.

Negative and undecided findings are kept and are retrievable so that a later attempt does not repeat an already examined idea without reason. A changed model, a different domain or a deliberate replication can justify repetition; the reason is recorded.

For any hidden evaluation, the candidate to be evaluated is fixed from permitted development information **before** the private result is opened. The privately best historical candidate remains a diagnosis and may not be selected afterwards (§6; Document 3 §8). A plan is not rewritten afterwards to fit what was produced; an artefact outside the plan is not legitimized by amending the plan.

---

## 14. Autonomy levels

| Level | Permitted behaviour | Not yet permitted |
|---|---|---|
| Technical probe | Explicitly chosen contacts, synthetic inputs, controlled negative cases | Productive data access; any claimed learning benefit |
| Isolated execution | Bounded tasks and verified pilot artefacts | Unrestricted shell or production work |
| Bounded research | Several approved experiments; new candidates; no self-release | Changing rights, verifiers, data roles or top-level budgets |
| Verified version adoption | Authorized activation of accepted candidates for new runs | Retroactive identity change of running runs |
| Bounded production | Only after a separate scope and operations decision with a suitable domain adapter | General autonomy from a single benchmark |

The VAC study works at the first three levels. An implemented learning path and an empirically demonstrated learning gain are different results; a negative or undecided finding closes a work package properly and leaves the corresponding option disabled.

---

## 15. What this protocol requires to be demonstrated

The protocol is satisfied by real tests, not by this text. Before any performance claim: a valid control solution passes in a clean environment; a wrong solution fails substantively; a manipulating candidate fails on integrity; a declared reproducible effect model can be rebuilt from its recipe without the learner's workspace; private evaluation stays outside every learning projection; the integrity cases of Document 4 each show their expected rejection with runtime evidence. An environment that fails isolation, oracle independence or leakage checks is not eligible for learner-performance claims.
