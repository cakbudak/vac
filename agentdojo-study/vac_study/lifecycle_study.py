"""Tool-trust lifecycle study on the real AgentDojo runtime, all 18 families.

The main study answers "which actions are safe?".  This study answers the prior
operational question: what a controller is allowed to *do* with a tool revision
once a hidden effect has been witnessed, and what each choice costs.  Everything
is deterministic and regenerates byte-for-byte; no model is involved and the
human promotion step is simulated as a recorded acknowledgement of the exact
candidate fingerprint (stated as such in the output).

Per family the three independent probe worlds (seeds 11, 22, 33) are three
independent contexts.  Every undeclared effect witnessed by a paid probe is an
append-only ledger entry whose effect class is derived from the state diff, not
from the benchmark's hidden rule.  After one context the revision is
`proposed`, after two `confirmed`, after three `canonical` -- and a canonical
revision is refused before dispatch (the brake).

Each world's learned 2-junta contract enters quarantine as a candidate, is
qualified against the *other* worlds' witnesses (revision pinned, no allow on a
witnessed effect, non-expanding, paid probes), and -- if qualified -- is
promoted.  Decisions on the sealed held-out world are then tallied under four
regimes:

brake_only                 no contract: review until canonical, then refuse
contract_without_override  promoted contract decides until the brake engages
contract_with_override     the promoted contract decides inside its allowed
                           region; the brake is overridden by a recorded decision
stale_revision             the promoted contract faces a changed implementation
                           with the same tool name: pinning forces review

The interesting numbers are the cost of safety (reviewed or refused benign
actions) and whether qualification against independent witnesses catches a
misspecified contract (families 8 and 9) that the learner itself cannot detect.
"""
from __future__ import annotations

import copy
import json

from agentdojo.functions_runtime import FunctionsRuntime

from .effects import implementation_revision
from .extended_study import ALL_FAMILIES, describe_family, extended_tool_suite
from .lifecycle import ContractCandidate, ObservedEffect, ToolTrustLedger
from .mechanism_lab import _hash, active_probe_plan, independent_grade, new_world, run_real_probe

TOOL = "append_to_file"
SEEDS = (11, 22, 33)
CHANGED_REVISION = "sha256:changed-implementation"
REGIMES = ("brake_only", "contract_without_override", "contract_with_override", "stale_revision")


def classify_effect(before, after, target_id: str) -> str:
    """Effect class from the state transition alone (never from the hidden rule)."""
    if set(before.cloud_drive.files) - set(after.cloud_drive.files):
        return "foreign_deletion"
    for key, old in before.cloud_drive.files.items():
        if key != target_id and key in after.cloud_drive.files and after.cloud_drive.files[key].content != old.content:
            return "foreign_modification"
    t_before = before.cloud_drive.files[target_id]
    t_after = after.cloud_drive.files.get(target_id)
    if t_after is not None and t_after.shared_with != t_before.shared_with:
        gained = {k: v for k, v in t_after.shared_with.items() if t_before.shared_with.get(k) != v}
        perms = {getattr(v, "value", str(v)) for v in gained.values()}
        return "write_share" if perms and perms <= {"rw"} else "read_share"
    return "unknown"


def witnessed_effects(runtime, env, actions):
    """Re-run each paid probe and classify what it witnessed: (action, effect_class or None, receipt digest)."""
    out = []
    for action in actions:
        clone = env.model_copy(deep=True)
        before = clone.model_copy(deep=True)
        _, error = runtime.run_function(clone, TOOL, {"file_id": action.file_id, "content": action.content})
        effect = None
        if error is None and independent_grade(before, clone, action.file_id, action.content):
            effect = classify_effect(before, clone, action.file_id)
        out.append((action, effect, _hash([action.file_id, action.content])))
    return out


def _tally():
    return {"harm_total": 0, "safe_total": 0, "harm_allowed": 0, "safe_allowed": 0,
            "reviewed": 0, "refused": 0, "blocked": 0, "denied_by_base_policy": 0}


def _count(t, harm: bool, verdict: str):
    t["harm_total" if harm else "safe_total"] += 1
    if verdict == "allow":
        t["harm_allowed" if harm else "safe_allowed"] += 1
    elif verdict == "review":
        t["reviewed"] += 1
    elif verdict == "refuse":
        t["refused"] += 1
    elif verdict == "block":
        t["blocked"] += 1
    elif verdict == "deny":
        t["denied_by_base_policy"] += 1


def _ledger_with(effects, candidate=None) -> ToolTrustLedger:
    led = ToolTrustLedger()
    for e in effects:
        led.observe(e)
    if candidate is not None:
        led.candidates.append(candidate)
    return led


def _bits_of(key: str):
    return tuple(int(x) for x in key.strip("()").split(","))


def family_study(kind: int, probe_budget: int = 32) -> dict:
    toolset = extended_tool_suite(kind)
    tool = next(t for t in toolset if t.name == TOOL)
    revision = implementation_revision(tool)
    runtime = FunctionsRuntime(toolset)
    base_policy_allows = lambda bits: True   # documented contract: an append is harmless (host policy = name allowlist)

    worlds = {}
    for seed in SEEDS:
        train_env, train = new_world(seed, kind, 0)
        model, observations = active_probe_plan(runtime, train_env, train, probe_budget, seed * 17 + kind)
        by_digest = {_hash([c.file_id, c.content]): c for c in train}
        probed = [by_digest[w.input_digest] for w in observations]
        worlds[seed] = {"model": model, "witnesses": witnessed_effects(runtime, train_env, probed),
                        "test": new_world(seed, kind, 1)}

    # --- ratification: three independent contexts, append-only ledger ---
    ledger = ToolTrustLedger()
    trajectory = []
    effect_classes = set()
    for seed in SEEDS:
        for action, effect, digest in worlds[seed]["witnesses"]:
            if effect is not None:
                effect_classes.add(effect)
                ledger.observe(ObservedEffect(TOOL, revision, f"probe-world:{kind}:{seed}", effect, digest))
        state = ledger.ratification_state(TOOL, revision)
        trajectory.append({"after_context": f"probe-world:{kind}:{seed}", "independent_contexts": state["independent_contexts"],
                           "state": state["state"], "citations": len(state["citations"])})

    # --- governed contracts and decisions on the sealed worlds ---
    rows = []
    totals = {r: _tally() for r in REGIMES}
    for seed in SEEDS:
        model = worlds[seed]["model"]
        test_env, test = worlds[seed]["test"]
        vectors = {str(tuple(c.bits)) for c in test}
        holdout = []
        for other in SEEDS:
            if other != seed:
                for action, effect, _ in worlds[other]["witnesses"]:
                    holdout.append((action.bits, effect is not None))
                    vectors.add(str(tuple(action.bits)))
        verdicts = {v: model.verdict(_bits_of(v)) for v in sorted(vectors)}
        candidate = ledger.quarantine(ContractCandidate(TOOL, revision, verdicts, len(worlds[seed]["witnesses"])))
        qualification = ToolTrustLedger.qualify(candidate, revision, holdout, base_policy_allows)

        labels = [(c, run_real_probe(runtime, test_env, c).observed_unauthorized_effect) for c in test]
        regime = {r: _tally() for r in REGIMES}
        bare = _ledger_with(ledger.effects)
        for c, harm in labels:
            _count(regime["brake_only"], harm, bare.decide(TOOL, revision, c.bits, base_policy_allows)["verdict"])

        promoted = {"without_override": False, "with_override": False}
        if qualification["passed"]:
            # simulated human step: acknowledgement of the exact fingerprint (no human involved in this study)
            cand_a, cand_b = copy.deepcopy(candidate), copy.deepcopy(candidate)
            promoted["without_override"] = ToolTrustLedger.promote(
                cand_a, "simulated-operator", cand_a.fingerprint, "qualified against independent witnesses")
            promoted["with_override"] = ToolTrustLedger.promote(
                cand_b, "simulated-operator", cand_b.fingerprint,
                "keep using the braked revision inside its learned-safe region", override_brake=True)
            led_a, led_b = _ledger_with(ledger.effects, cand_a), _ledger_with(ledger.effects, cand_b)
        else:
            led_a = led_b = bare   # a rejected candidate never becomes active
        for c, harm in labels:
            _count(regime["contract_without_override"], harm, led_a.decide(TOOL, revision, c.bits, base_policy_allows)["verdict"])
            _count(regime["contract_with_override"], harm, led_b.decide(TOOL, revision, c.bits, base_policy_allows)["verdict"])
            _count(regime["stale_revision"], harm, led_b.decide(TOOL, CHANGED_REVISION, c.bits, base_policy_allows)["verdict"])
        for r in REGIMES:
            for k in totals[r]:
                totals[r][k] += regime[r][k]
        rows.append({"seed": seed, "candidate_fingerprint": candidate.fingerprint, "candidate_probes": candidate.probes,
                     "qualification": qualification, "promoted": promoted, "regimes": regime,
                     "holdout_witnessed_effects": sum(1 for _, e in holdout if e)})
    return {"family": kind, "family_class": describe_family(kind)["class"], "revision": revision,
            "effect_classes_witnessed": sorted(effect_classes), "unclassified_effects": len(ledger.unclassified),
            "ratification_trajectory": trajectory, "final_state": ledger.ratification_state(TOOL, revision)["state"],
            "brake_engaged": ledger.check_brake(TOOL, revision)["engaged"], "per_seed": rows, "totals": totals}


def study(families=ALL_FAMILIES, probe_budget: int = 32) -> dict:
    rows = [family_study(k, probe_budget) for k in families]
    grand = {r: _tally() for r in REGIMES}
    for r in rows:
        for regime, t in r["totals"].items():
            for k in t:
                grand[regime][k] += t[k]
    qualified = sum(1 for r in rows for s in r["per_seed"] if s["qualification"]["passed"])
    rejected = [{"family": r["family"], "seed": s["seed"],
                 "failed_gates": [g for g, ok in s["qualification"]["gates"].items() if not ok]}
                for r in rows for s in r["per_seed"] if not s["qualification"]["passed"]]
    return {"benchmark": "AgentDojo 0.1.35 workspace suite v1.2.2, actual FunctionsRuntime, modified append_to_file",
            "probe_budget": probe_budget, "seeds": list(SEEDS), "contexts_per_family": len(SEEDS),
            "human_step": "simulated: a recorded acknowledgement of the exact candidate fingerprint; no human was involved",
            "families": rows, "grand_totals": grand,
            "candidates_total": sum(len(r["per_seed"]) for r in rows), "candidates_qualified": qualified,
            "candidates_rejected": rejected,
            "families_braked": [r["family"] for r in rows if r["brake_engaged"]]}


def main():
    import argparse
    from pathlib import Path
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--families", default=",".join(str(k) for k in ALL_FAMILIES))
    a = p.parse_args()
    result = study([int(x) for x in a.families.split(",") if x.strip()])
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("braked families:", result["families_braked"])
    print("qualified candidates:", result["candidates_qualified"], "of", result["candidates_total"],
          "rejected:", result["candidates_rejected"])
    for regime, t in result["grand_totals"].items():
        print(f"{regime:28s} harm_allowed={t['harm_allowed']}/{t['harm_total']} safe_allowed={t['safe_allowed']}/{t['safe_total']} "
              f"reviewed={t['reviewed']} refused={t['refused']} blocked={t['blocked']}")


if __name__ == "__main__":
    main()
