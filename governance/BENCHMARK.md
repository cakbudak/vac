# VERIFIABLE AGENT CONTROL (VAC)
## Benchmark Production and Qualification

**Document 2 of 4 — methodological annex to `VAC_Research_Description.md`**
**Date:** 30 October 2026
**Status:** prospective production and qualification contract for the mechanism families the VAC study is measured on. No family produced under this contract exists yet; the synthetic AgentDojo study's worlds (`agentdojo-study/`) are development material only.

**Companion documents.** Document 1, *Research Governance Protocol* (roles, zones, data roles, status axes); Document 3, *Metrics, Statistics and Acceptance* (how qualified families enter the statistics); Document 4, *Negative Controls and Integrity Cases* (the production-integrity cases this document must pass).

---

## 1. Purpose

A study of effect learning is only as good as the worlds it is measured on. The synthetic AgentDojo study showed what a badly designed benchmark does: a world with fixed causal arity, two effect branches, full observability and free isolated probes is solved by a generic exact learner and cannot discriminate between methods. The funded work therefore treats benchmark production as a **measurement-instrument problem** with its own contract, roles, qualification and integrity cases — not as a by-product of writing a generator.

A **benchmark world** is a reproducible test and work state: a hidden mechanism, a learner-visible view, permitted actions and probes, a fixed safety objective, exact checks and sealed references. It is not a predictive world model, and nothing about it is "the real tool"; the claim limits of Document 3 follow from that.

The statistical unit is the **mechanism family** (Document 3, §4). This document fixes what a family is, how one is produced, when it may be used, and what "fresh" means.

---

## 2. Domain brief before generation

A production brief is written and bound **before** any world is generated. It states:

- which capability is under study (for example: discovery of a state-conditional side effect; multi-step disclosure; a permission change reachable only through a composition of permitted actions);
- which sources and generator recipes may be used;
- which world components are mutable and which are fixed across the family;
- which information is accessible to the learner (observability stratum: full, unregistered-but-observable, partial, delayed, noisy, indistinguishable) and which probes are permitted (none, prior traces, fixed isolated budget, constrained adaptive budget);
- the fixed safety objective and the attack opportunities it defines;
- which outcomes are expected and what counts as a **valid alternative** (the benign lookalike that must be allowed);
- the family classification, the qualification role, the resource budget, the provenance to be recorded and the data role the family will later hold (development, acceptance, audit).

A brief may deliberately contain incomplete information and study how a method handles it. It may not silently rely on a fact known only to the verifier for the task to be solvable. Synthetic data carry traceable provenance and rights; the label "synthetic" does not lift restrictions on any source data used to produce them.

---

## 3. Components of a complete world revision

| Component | Content for VAC | Qualification duty |
|---|---|---|
| **Hidden mechanism** | Per action: the true effect function over the full state (including any unregistered or unobservable relation), its causal support, conditional branches, partial-commit behaviour; per family: the generator recipe and seed | Fresh materialization reproduces it exactly; the learner never reads it |
| **Learner view** | Registered features, observation channel (clean, noisy, delayed, partial), permitted probe interface and budget, tool descriptions (accurate, incomplete or misleading, as declared) | Exactly what the brief declares; no hidden extra channel and no host privilege |
| **Actions and plans** | Action schemas with typed arguments, plan lengths, legitimate goals, attack opportunities | No capability the description does not declare; every attack opportunity reachable through permitted actions |
| **Fixed objective** | Invariant `I(s)`, authorization predicate under the base policy, prohibited disclosures, state changes and authority crossings | Fixed before learning; owned by the objective store, not by the producer |
| **Scope contract** | Which inputs are declared causally relevant, which completeness claim is made, whether the contract is supplied, withheld or deliberately false | Declared per world; a false contract is a negative control, never an accident |
| **Exact checks** | Oracle transition function, outcome labelling rule, invariant check, utility criterion for legitimate goals | The control solution passes; each predefined fail variant fails |
| **Private references** | Oracle labels, control solutions, fail variants, qualification traces | Outside the learner's zone, its memory and its exports |
| **Provenance** | Recipe, versions, seed, parent families, taxonomy revision, cost of production | No fictitious complete data sets; no missing snapshot recipe |

A simple family does not need every component. Scope follows the claim; unnecessary services and data do not raise the quality of an experiment.

---

## 4. Production sequence

1. **Design candidates.** Task, world and criteria may be proposed together, within the producer's own scope and budget. A model may propose designs, variants and fail cases.
2. **Materialize.** The builder for worlds creates the actual initial state from the recipe. A missing dependency is a production failure, not a world.
3. **Qualify independently.** The independent qualifier applies a qualification contract bound beforehand (§5). A generator's own judgement cannot set `qualified`.
4. **Seal the revision.** Task, world, criteria, permitted views and family assignment are identified together under one digest; private details live in separate projections.
5. **Instantiate and solve.** The learner receives only its task and its released world; the revision stays unchanged for the attempt.
6. **Reconcile.** Substantive outcome, external effect, resources, reset and cleanup are recorded separately. Later corrections are new revisions.

Manual curation skips step 1's generation, not the qualification of what is actually needed. The sequence creates no second runtime: materialization and execution are ordinary jobs of the evaluation runner.

---

## 5. Qualification of a measurement instrument

### 5.1 Visible solvability

For every mandatory requirement an admissible path must exist from the learner's view: observation channel, probe interface, budget and inputs fit the task. A control solution must demonstrate it, or an equivalent independent check must carry it. "Should be solvable" is not a proof.

Where recognising missing information is the goal — the identifiability stratum, the indistinguishable pair, the withheld scope contract — the **correct admission of ignorance is the success** and is described as such. A method is not penalised for abstaining because a private checker knows the full answer.

### 5.2 Criteria fit and counter-probes

Qualification checks at least one correct control solution, the relevant admissible alternatives and targeted fail variants. For VAC the admissible alternative is the **benign lookalike**: an action or plan that resembles a harmful one but violates no objective and must be allowed; broad denials count against utility. Where a task has substantively only one correct result, different admissible solution paths or equivalent representations suffice as counter-probes.

Fail variants include at least: an effect of the wrong magnitude or on the wrong relation; an omitted sub-requirement; a forbidden side change reached through permitted steps; a plausible answer with an unsupported claim (for example a model asserted `reliable` outside its scope); an attack that passes a known comparator. The expected findings are fixed **before** the qualification run. A model may propose variants but does not set their reference verdict.

### 5.3 Defects versus poor answers

A contradiction, an unclear requirement or an incomplete environment is a **task defect**. A poor learner answer is a hint, not a proof of defect. A separately authorized role evaluates the suspicion without touching acceptance data that has already been opened. A defect produces a new revision; it never produces a retroactively valid score.

### 5.4 Three independent quality questions

| Level | Question | Not to be confused with |
|---|---|---|
| Task and criteria quality | Is the task solvable and does its measure target the right goal? | The generator's own grade |
| Checker quality (where a non-exact checker is used) | Does a concrete evaluator apply the criteria reliably? | The quality of the criteria themselves |
| System benefit | Does using these families improve learning or control? | Agreement of a checker with references |

In VAC the primary endpoint is measured by an exact oracle; no LLM judge and no agent statement may stand in for it. Where a non-exact checker is used for a secondary measure, it is qualified separately against independently fixed reference verdicts, with perturbation controls (candidate order, presentation, irrelevant verbosity) and manipulation cases, and its authority reaches only "this checker rated this material so". None of the three levels is released from another.

---

## 6. Roles and private information

Production, qualification, learner execution and acceptance are distinct **authorization roles**, not necessarily distinct model products (Document 1, §2). The same model type may serve in separate contexts; its correlated errors and possible self-preference remain subjects of qualification.

Whoever produces or reads private references — oracle labels, control solutions, fail variants — may not pass them to the learner through shared sessions, summaries, caches, memory, logs, names or search indexes. Private materialization happens outside the learner workspace. Deleting a once-visible file does not restore secrecy, and a different role name creates no retroactive independence.

Qualification may include controlled learner runs. These count as **exposure** of that family; their results and sessions are not carried into the development knowledge of the policy that is later evaluated on it. "Never publicly used" is not "never seen". Exposure is recorded with its purpose. A family seen during the development of a comparator, a checker, a generator or a misspecification test is exposed for that purpose and is not an untouched confirmation.

Rejected world candidates stay in the production log and the cost account; production cost is part of the amortized statement in Document 3, §8.

---

## 7. Instances, families and transfer

A new seed, different values or renamed features produce a **new instance**, not a new family. Family assignment considers shared mechanism structure, generator recipe, causal support pattern, effect class, shared sources and criteria templates. A taxonomy revision is recorded and traceable; it does not move already consumed cases into a fresh split.

| Transfer scope | Example | Admissible statement |
|---|---|---|
| New instance | Another seed of a known mechanism structure | Generalization within this known family |
| New combination | Known sub-mechanisms in a withheld composition | Compositional transfer in exactly this factorization |
| New family | A withheld mechanism structure | Cross-family transfer within the declared scope |
| New domain | A different tool semantics, interface or effect mechanism | A separate domain study; not derived from family variation |

Development, acceptance and audit roles are assigned before the respective use. A generative method does not create an unlimited supply of independent families by repetition; dependency structure and possible collisions are part of the statistical planning (Document 3, §4).

---

## 8. Development distribution and curriculum

An initial curriculum is a **fixed selection rule** over released development families. It may consider difficulty, observability stratum, effect mechanism or required capability, as long as those attributes are defined beforehand. No trained curriculum model is required.

A later adaptation may react to released development feedback. It creates a new method and data revision with selection reasons, distribution and budget. Families that have become easy may be kept as regression material; the synthetic study's existing mechanism families serve exactly that purpose. The independent **acceptance distribution is never adapted** to the strengths of the current candidate.

Improvements of a production method are compared with the same learner base, matching reference families and full production cost. Number of families, combinatorial variety and checker scores are not substitute metrics for usability and transfer.

---

## 9. Reset, reconcile and cleanup

Every comparison arm starts from the agreed fresh world. Comparable initial states are evidenced by snapshot and state digests and a reset record; fresh directory names alone are not enough. Caches and services that can influence behaviour are explicitly covered by the reset or resource contract.

Authoritative world states, effect ledgers and receipts live in the evidence store; worker files are temporary materializations. An aborted process does not remove effects that have already occurred. On an unclear outcome the instance is **reconciled first**, then a new instance is created or the attempt is ended with a reason.

World lifecycle states: `requested`, `provisioning`, `ready`, `leased`, `running`, `reconciling`, `closed`, `failed`, `outcome_unknown`. A missing cleanup record is not a free resource allowance; `outcome_unknown` is not `closed`.

---

## 10. Record contracts

| Record | Minimum content | Invariant |
|---|---|---|
| **WorldDefinition** | task reference, generator recipe, initial state digest, learner projection, verifier projection, exact checks, tool and probe profile, objective revision, scope-contract declaration, observability stratum, family lineage, dependencies, resource limits | Immutable candidate content; private references only in the authorized view; a qualification report is not part of its own subject digest |
| **QualificationReport** | subject world digest, qualification protocol, solvability result, criteria-fit result, environment result, admissible-alternative references, fail-variant references, reviewer references, permitted role (development / acceptance / audit), limitations | Independent bound finding; qualifies no learner and no policy |
| **WorldInstance** | world definition, run reference, lease, initial snapshot digest, provisioning receipt, runtime references, current state, effect ledger, cleanup record, lifecycle status | One execution sees only its instance; a reset evidences a new initial state, not the undoing of unknown real effects |
| **FamilyLineage** | family id, taxonomy revision, generator recipe, parent families, shared mechanism factors, shared sources, split assignment, exposure history | Names and seeds are instance attributes; family independence is not derived from textual difference |
| **CurriculumRevision** | eligible development families, selection rule, difficulty definition, distribution constraints, adaptation triggers, budget, effective-from | Only released development families; no automatic change of the acceptance population |

Qualification states: `proposed`, `under_review`, `qualified`, `defective`, `inconclusive`, `retired`. `qualified` names its purpose and applies only to the checked world, task and criteria revisions; it is no general truth. Protected families are separated from the sessions that produced them and from those sessions' memory paths. The learner receives no control solution as a hidden hint.

---

## 11. Acceptance of the production path

The production path is accepted when a small development family has been **actually produced and independently qualified** — with its control solution, benign lookalike, fail variants, provenance and a successful reset-and-resume run — and when a deliberately defective candidate is correctly rejected by the same path. Both directions are required: accepting valid worlds and rejecting defective ones.

Production quality and later learning benefit are separate questions. If automatic production shows no benefit over curated worlds, the curated path remains valid. A new domain is qualified as a new binding, not by copying a positive status.
