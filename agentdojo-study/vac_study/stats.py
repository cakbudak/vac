"""Family-level summaries and inferential checks for the extended study.

The statistical unit is the mechanism family.  Seeds within a family are
replicates of the same hidden rule and are pooled, never counted as families.
Exact tests are used because the number of families is small; the confidence
intervals on pooled rates are Wilson intervals and are reported as descriptive
coverage, not as inference over families.
"""
from __future__ import annotations

from collections import defaultdict
from math import comb, sqrt
from random import Random
import json


def wilson(successes: int, n: int, z: float = 1.959964) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def sign_test_one_sided(wins: int, losses: int) -> float:
    """P(X >= wins) for X ~ Binomial(wins+losses, 1/2); ties are dropped."""
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def family_table(rows, arms, budget: int) -> dict:
    """Pool seeds within family for one probe budget."""
    per = defaultdict(lambda: defaultdict(lambda: {"safe_total": 0, "harm_total": 0,
                                                   "safe_allowed": 0, "harm_allowed": 0,
                                                   "reviewed": 0, "blocked": 0}))
    for r in rows:
        if r["budget"] != budget:
            continue
        for arm in arms:
            c = r["counts"][arm]
            agg = per[r["family"]][arm]
            for key in agg:
                agg[key] += c[key]
    return {int(k): dict(v) for k, v in per.items()}


def rate(c, kind):
    if kind == "utility":
        return c["safe_allowed"] / c["safe_total"] if c["safe_total"] else None
    return c["harm_allowed"] / c["harm_total"] if c["harm_total"] else None


def paired_comparison(table, families, arm_a, arm_b, kind):
    """Family-wise paired comparison: how often arm_a is strictly better than arm_b."""
    better = worse = ties = 0
    diffs = []
    for fam in families:
        a = rate(table[fam][arm_a], kind)
        b = rate(table[fam][arm_b], kind)
        if a is None or b is None:
            continue
        diffs.append(a - b)
        if kind == "utility":
            better += a > b
            worse += a < b
        else:
            better += a < b
            worse += a > b
        ties += a == b
    return {"arm": arm_a, "versus": arm_b, "measure": kind, "families": len(diffs),
            "families_better": better, "families_worse": worse, "families_tied": ties,
            "one_sided_sign_test_p": sign_test_one_sided(better, worse),
            "mean_family_difference": sum(diffs) / len(diffs) if diffs else None}


def bootstrap_family_mean(table, families, arm, kind, reps=4000, seed=1):
    rng = Random(seed)
    values = [rate(table[f][arm], kind) for f in families]
    values = [v for v in values if v is not None]
    if not values:
        return None
    means = []
    for _ in range(reps):
        sample = [rng.choice(values) for _ in values]
        means.append(sum(sample) / len(sample))
    means.sort()
    return {"mean": sum(values) / len(values),
            "bootstrap_95ci": [means[int(0.025 * reps)], means[int(0.975 * reps) - 1]]}


def pooled(table, families, arm):
    tot = {"safe_total": 0, "harm_total": 0, "safe_allowed": 0, "harm_allowed": 0, "reviewed": 0, "blocked": 0}
    for f in families:
        for k in tot:
            tot[k] += table[f][arm][k]
    out = dict(tot)
    out["utility_rate"] = tot["safe_allowed"] / tot["safe_total"] if tot["safe_total"] else None
    out["utility_wilson95"] = wilson(tot["safe_allowed"], tot["safe_total"])
    out["harm_rate"] = tot["harm_allowed"] / tot["harm_total"] if tot["harm_total"] else None
    out["harm_wilson95"] = wilson(tot["harm_allowed"], tot["harm_total"])
    return out


def summarize(extended: dict, attack: dict) -> dict:
    arms = extended["arms"]
    rows = extended["rows"]
    table = family_table(rows, arms, 32)
    classes = defaultdict(list)
    for fam in extended["families"]:
        classes[fam["class"]].append(fam["kind"])
    in_class = sorted(classes["hand_written_2_feature"] + classes["generated_2_feature"])
    out = {"unit": "mechanism family (seeds pooled)", "budget": 32,
           "family_classes": {k: sorted(v) for k, v in classes.items()},
           "pooled_by_class": {}, "per_family": table, "comparisons": [], "bootstrap": {}}
    for cls, fams in classes.items():
        out["pooled_by_class"][cls] = {arm: pooled(table, fams, arm) for arm in arms}
    out["pooled_by_class"]["all_in_class_16"] = {arm: pooled(table, in_class, arm) for arm in arms}
    for arm_b, kind in (("conservative_review", "utility"), ("feature_vector_lookup", "utility"),
                        ("random_2_junta", "utility"), ("consensus_trees", "utility"),
                        ("learned_3_junta", "utility"), ("manual_name_allowlist", "harm"),
                        ("camel_policy_only", "harm"), ("consensus_trees", "harm")):
        out["comparisons"].append(paired_comparison(table, in_class, "learned_2_junta", arm_b, kind))
    for arm in ("learned_2_junta", "random_2_junta", "learned_3_junta", "learned_2_junta_24f",
                "consensus_trees", "feature_vector_lookup"):
        out["bootstrap"][arm] = {"utility_over_16_in_class_families": bootstrap_family_mean(table, in_class, arm, "utility"),
                                 "harm_over_16_in_class_families": bootstrap_family_mean(table, in_class, arm, "harm")}
    # budget sweep: pooled utility / harm per budget and arm, in-class and misspecified
    sweep = {}
    sweep_rows = rows + extended.get("budget_sweep_rows", [])
    for budget in sorted({r["budget"] for r in sweep_rows}):
        t = family_table(sweep_rows, arms, budget)
        sweep[str(budget)] = {
            "in_class": {arm: pooled(t, [f for f in in_class if f in t], arm)
                         for arm in ("learned_2_junta", "random_2_junta", "learned_3_junta",
                                     "learned_2_junta_24f", "consensus_trees", "feature_vector_lookup")},
            "misspecified": {arm: pooled(t, [f for f in classes["misspecified_unseen_token"] +
                                             classes["misspecified_three_feature"] if f in t], arm)
                             for arm in ("learned_2_junta", "random_2_junta", "learned_3_junta",
                                         "learned_2_junta_24f", "consensus_trees", "lexical_novelty_gate")},
        }
    out["budget_sweep"] = sweep
    # generalization beyond probed feature vectors (learned_2_junta, 32 probes, in-class families)
    gen = {"test_actions": 0, "unprobed_vector": 0, "unprobed_safe_total": 0, "unprobed_harm_total": 0,
           "learned_2_junta_unprobed_safe_allowed": 0, "learned_2_junta_unprobed_harm_allowed": 0}
    for r in rows:
        if r["budget"] == 32 and r["family"] in in_class and "unprobed_feature_vectors" in r:
            for k in gen:
                gen[k] += r["unprobed_feature_vectors"][k]
    gen["share_unprobed"] = gen["unprobed_vector"] / gen["test_actions"] if gen["test_actions"] else None
    out["generalization_beyond_probed_vectors"] = gen
    # attacks: successes per arm x strategy x budget x class
    att = defaultdict(lambda: {"episodes": 0, "successes": 0})
    for r in attack["rows"]:
        key = f'{r["arm"]}|{r["strategy"]}|{r["attack_budget"]}|{r["family_class"]}'
        att[key]["episodes"] += 1
        att[key]["successes"] += int(r["attacker_success"])
    out["attacks"] = dict(att)
    return out


def main():
    import argparse
    from pathlib import Path
    p = argparse.ArgumentParser()
    p.add_argument("--extended", type=Path, required=True)
    p.add_argument("--attack", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    summary = summarize(json.loads(a.extended.read_text()), json.loads(a.attack.read_text()))
    a.out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print("written", a.out)


if __name__ == "__main__":
    main()
