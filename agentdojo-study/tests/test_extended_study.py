"""Regression tests for the extended study (fast subset; full runs are evidence)."""
import inspect

from agentdojo.functions_runtime import FunctionsRuntime

from vac_study.extended_study import (
    ALL_FAMILIES, GENERATED, JuntaVersionSpace, FeatureVectorLookup, ConsensusTrees, CaMeLPolicyOnly,
    _table_depends_on_both, describe_family, evaluate_instance, extended_tool_suite, features24,
    junta_active_plan, sampled_rule,
)
from vac_study.mechanism_lab import NAMES, VersionSpace, active_probe_plan, new_world, run_real_probe


def test_numpy_two_junta_space_matches_original_learner_everywhere():
    runtime = FunctionsRuntime(extended_tool_suite(3))
    train_env, train = new_world(22, 3, 0)
    test_env, test = new_world(22, 3, 1)
    original, observations = active_probe_plan(runtime, train_env, train, 32, 22 * 17 + 3)
    mirror = JuntaVersionSpace(len(NAMES), 2)
    for w in observations:
        mirror.observe(w)
    assert mirror.hypotheses_remaining == len(original.hypotheses)
    for action in test:
        assert mirror.verdict(action.bits) == original.verdict(action.bits)


def test_generated_rules_depend_on_both_inputs_and_are_distinct():
    rules = {sampled_rule(k) for k in GENERATED}
    assert len(rules) == len(GENERATED)
    for i, j, table in rules:
        assert i < j and _table_depends_on_both(table)
    assert not _table_depends_on_both(0b1010)   # depends on the first input only
    assert not _table_depends_on_both(0b1111)   # constant


def test_generated_family_has_a_real_hidden_effect_in_agentdojo_state():
    kind = GENERATED[0]
    runtime = FunctionsRuntime(extended_tool_suite(kind))
    env, actions = new_world(11, kind, 0)
    witnesses = [run_real_probe(runtime, env, a) for a in actions[:40]]
    assert any(w.observed_unauthorized_effect for w in witnesses)
    assert any(not w.observed_unauthorized_effect for w in witnesses)


def test_feature_vector_lookup_never_extrapolates():
    runtime = FunctionsRuntime(extended_tool_suite(0))
    train_env, train = new_world(11, 0, 0)
    _, observations = active_probe_plan(runtime, train_env, train, 32, 11 * 17)
    lookup = FeatureVectorLookup(observations)
    seen = {tuple(w.features) for w in observations}
    unseen = next(a for a in new_world(11, 0, 1)[1] if tuple(a.bits) not in seen)
    assert lookup.verdict(unseen.bits) == "review"


def test_consensus_trees_abstain_on_disagreement_or_decide():
    runtime = FunctionsRuntime(extended_tool_suite(1))
    train_env, train = new_world(11, 1, 0)
    _, observations = active_probe_plan(runtime, train_env, train, 32, 11 * 17 + 1)
    trees = ConsensusTrees(observations, 5)
    verdicts = {trees.verdict(a.bits) for a in new_world(11, 1, 1)[1]}
    assert verdicts <= {"allow", "block", "review"}


def test_camel_policy_alone_allows_trusted_user_appends():
    env, actions = new_world(11, 0, 1)
    policy = CaMeLPolicyOnly(env)
    assert all(policy.verdict(a) == "allow" for a in actions[:10])


def test_no_policy_code_reads_the_hidden_rule():
    from vac_study import extended_study as m
    for fn in (JuntaVersionSpace.verdict, JuntaVersionSpace.observe, junta_active_plan,
               FeatureVectorLookup.verdict, ConsensusTrees.verdict):
        src = inspect.getsource(fn)
        assert "hazard_rule" not in src and "sampled_rule" not in src


def test_instance_evaluation_is_internally_consistent():
    row = evaluate_instance(10, 11, 16, with_camel=False)
    for arm, c in row["counts"].items():
        assert c["safe_allowed"] <= c["safe_total"] and c["harm_allowed"] <= c["harm_total"]
        assert c["safe_allowed"] + c["harm_allowed"] + c["reviewed"] + c["blocked"] == c["safe_total"] + c["harm_total"]
    assert row["counts"]["learned_2_junta"]["harm_allowed"] == 0   # realizable family, unanimity
    assert row["counts"]["manual_name_allowlist"]["harm_allowed"] == row["counts"]["manual_name_allowlist"]["harm_total"]
    assert row["probes"]["learned_2_junta"] == 16


def test_family_descriptions_cover_all_families():
    classes = {describe_family(k)["class"] for k in ALL_FAMILIES}
    assert classes == {"hand_written_2_feature", "misspecified_unseen_token",
                       "misspecified_three_feature", "generated_2_feature"}
    assert len(features24(new_world(11, 0, 0)[0].cloud_drive.files[new_world(11, 0, 0)[1][0].file_id], "ok")) == 24
