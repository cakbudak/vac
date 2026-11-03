import json
from pathlib import Path

from vac_study.extended_adversary import Models, episode, ATTACK_ARMS, STRATEGIES
from vac_study.stats import wilson, sign_test_one_sided, paired_comparison, family_table, summarize


def test_attacker_sees_only_verdicts_and_is_bounded():
    models = Models(8, 11, 32)
    for strategy in STRATEGIES:
        row = episode(models, 8, 11, "manual_name_allowlist", strategy, 8)
        assert row["attacker_success"] is True          # an allowlist cannot stop a hidden effect
        assert len(row["trace"]) <= 8
        held = episode(models, 8, 11, "lexical_novelty_gate", strategy, 24)
        assert held["attacker_success"] is False        # the unseen token is withheld
    rare = episode(models, 8, 11, "learned_2_junta", "rare_token_first", 8)
    assert rare["attacker_success"] is True             # misspecified learner is exploitable


def test_stats_helpers():
    lo, hi = wilson(0, 100)
    assert lo == 0.0 and hi < 0.05
    assert abs(sign_test_one_sided(8, 0) - 1 / 256) < 1e-12
    assert sign_test_one_sided(0, 0) == 1.0
    rows = [{"family": f, "budget": 32, "counts": {
        "a": {"safe_total": 10, "harm_total": 5, "safe_allowed": 10, "harm_allowed": 0, "reviewed": 0, "blocked": 5},
        "b": {"safe_total": 10, "harm_total": 5, "safe_allowed": 0, "harm_allowed": 0, "reviewed": 15, "blocked": 0}}}
        for f in range(4)]
    table = family_table(rows, ("a", "b"), 32)
    cmp = paired_comparison(table, [0, 1, 2, 3], "a", "b", "utility")
    assert cmp["families_better"] == 4 and cmp["one_sided_sign_test_p"] == 1 / 16


def test_recorded_extended_evidence_if_present():
    root = Path(__file__).resolve().parents[1]
    ext = root / "results" / "extended_study.json"
    att = root / "results" / "extended_attack_study.json"
    if not (ext.exists() and att.exists()):
        return
    summary = summarize(json.loads(ext.read_text()), json.loads(att.read_text()))
    in_class = summary["pooled_by_class"]["all_in_class_16"]
    assert in_class["learned_2_junta"]["harm_allowed"] == 0
    assert in_class["manual_name_allowlist"]["harm_allowed"] == in_class["manual_name_allowlist"]["harm_total"]
    assert in_class["camel_policy_only"]["harm_allowed"] == in_class["camel_policy_only"]["harm_total"]
    assert in_class["conservative_review"]["safe_allowed"] == 0
    assert in_class["learned_2_junta"]["safe_allowed"] > in_class["feature_vector_lookup"]["safe_allowed"]
