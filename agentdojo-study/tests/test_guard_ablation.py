"""Guard ablation: each removed guard must expose the violation it is there to stop."""
from vac_study.ablation import (MajorityVersionSpace, camel_precedence_ablation, revision_pinning_ablation,
                                unanimity_ablation, unseen_token_ablation, verdict)
from vac_study.mechanism_lab import VersionSpace


def test_majority_differs_from_unanimity_only_when_survivors_disagree():
    space = VersionSpace()
    # three survivors over features (0, 1); on bits (1, 1) (cell 3) table 0b1000 predicts an effect, the others do not
    space.hypotheses = [(0, 1, 0b1000), (0, 1, 0b0000), (0, 1, 0b0000)]
    bits = (1, 1) + (0,) * 10
    assert space.verdict(bits) == "review"
    assert MajorityVersionSpace(space).verdict(bits) == "allow"
    space.hypotheses = []
    assert MajorityVersionSpace(space).verdict(bits) == "review"


def test_verdict_labels():
    assert verdict(0, 3) == "load-bearing"
    assert verdict(0, 0, 10, 5) == "load-bearing (utility)"
    assert verdict(0, 0).startswith("decorative")


def test_unseen_token_review_is_load_bearing_on_family_8():
    r = unseen_token_ablation(seeds=(11,))
    assert r["baseline_with_review"]["harm_allowed"] == 0
    assert r["ablated_without_review"]["harm_allowed"] > 0


def test_revision_pinning_blocks_a_stale_contract():
    r = revision_pinning_ablation(pairs=((0, 4),), seeds=(11,))
    row = r["rows"][0]
    assert row["revision_differs"]
    total = row["pinned"]["safe_total"] + row["pinned"]["harm_total"]
    assert row["pinned"]["reviewed"] == total and row["pinned"]["harm_allowed"] == 0
    assert row["unpinned"]["harm_allowed"] > 0


def test_unanimity_matters_only_while_hypotheses_remain_ambiguous():
    r = unanimity_ablation(families=(0, 5), seeds=(11,), budgets=(8, 32))
    assert r["8"]["ablated_majority"]["harm_allowed"] >= r["8"]["baseline_unanimity"]["harm_allowed"]
    assert r["32"]["baseline_unanimity"]["harm_allowed"] == 0 and r["32"]["ablated_majority"]["harm_allowed"] == 0


def test_camel_precedence_cannot_be_overridden_by_a_learned_allow():
    r = camel_precedence_ablation()
    assert r["baseline_denied_by_camel"] > 0
    assert r["ablated_allowed_by_learned_verdict"] > 0
