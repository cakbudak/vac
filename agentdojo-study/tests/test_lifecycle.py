"""Tool-trust lifecycle: ratification, governed contracts, decision order."""
from vac_study.lifecycle import ContractCandidate, ObservedEffect, ToolTrustLedger
from vac_study.lifecycle_study import CHANGED_REVISION, classify_effect, family_study

ALLOW_ALL = lambda bits: True


def _effect(ctx, cls="read_share", digest=None, revision="rev-a"):
    return ObservedEffect("append_to_file", revision, ctx, cls, digest or f"receipt-{ctx}-{cls}")


def test_ratification_counts_independent_contexts_only():
    led = ToolTrustLedger()
    assert led.ratification_state("append_to_file", "rev-a")["state"] == "clean"
    led.observe(_effect("w1"))
    led.observe(_effect("w1", digest="receipt-w1-second"))        # same context twice: still one
    assert led.ratification_state("append_to_file", "rev-a")["state"] == "proposed"
    led.observe(_effect("w2"))
    assert led.ratification_state("append_to_file", "rev-a")["state"] == "confirmed"
    assert not led.check_brake("append_to_file", "rev-a")["engaged"]
    led.observe(_effect("w3"))
    brake = led.check_brake("append_to_file", "rev-a")
    assert brake["engaged"] and brake["state"] == "canonical" and len(brake["citations"]) == 4


def test_unclassified_effect_is_reported_but_never_ratifies():
    led = ToolTrustLedger()
    for ctx in ("w1", "w2", "w3"):
        led.observe(_effect(ctx, cls="something_new"))
    assert len(led.unclassified) == 3
    assert led.ratification_state("append_to_file", "rev-a")["state"] == "clean"


def test_other_revision_is_unaffected_by_the_brake():
    led = ToolTrustLedger()
    for ctx in ("w1", "w2", "w3"):
        led.observe(_effect(ctx))
    assert led.check_brake("append_to_file", "rev-a")["engaged"]
    assert not led.check_brake("append_to_file", "rev-b")["engaged"]


def test_qualification_gates():
    verdicts = {str((1, 0)): "allow", str((0, 1)): "block", str((1, 1)): "review"}
    good = ContractCandidate("append_to_file", "rev-a", verdicts, probes=8)
    q = ToolTrustLedger.qualify(good, "rev-a", [((1, 0), False), ((0, 1), True)], ALLOW_ALL)
    assert q["passed"] and good.status == "qualified"

    stale = ContractCandidate("append_to_file", "rev-a", verdicts, probes=8)
    q = ToolTrustLedger.qualify(stale, "rev-b", [], ALLOW_ALL)
    assert not q["passed"] and not q["gates"]["revision_pinned"] and stale.status == "rejected"

    contradicted = ContractCandidate("append_to_file", "rev-a", verdicts, probes=8)
    q = ToolTrustLedger.qualify(contradicted, "rev-a", [((1, 0), True)], ALLOW_ALL)
    assert not q["gates"]["no_allow_on_witnessed_effect"]

    expanding = ContractCandidate("append_to_file", "rev-a", verdicts, probes=8)
    q = ToolTrustLedger.qualify(expanding, "rev-a", [((1, 0), False)], lambda bits: False)
    assert not q["gates"]["non_expanding"]

    free = ContractCandidate("append_to_file", "rev-a", verdicts, probes=0)
    q = ToolTrustLedger.qualify(free, "rev-a", [], ALLOW_ALL)
    assert not q["gates"]["has_paid_probes"]


def test_promotion_requires_qualification_and_exact_fingerprint():
    cand = ContractCandidate("append_to_file", "rev-a", {str((1, 0)): "allow"}, probes=4)
    assert not ToolTrustLedger.promote(cand, "op", cand.fingerprint, "not qualified yet")
    ToolTrustLedger.qualify(cand, "rev-a", [], ALLOW_ALL)
    assert not ToolTrustLedger.promote(cand, "op", "deadbeef", "wrong fingerprint")
    assert cand.status == "qualified"
    assert ToolTrustLedger.promote(cand, "op", cand.fingerprint, "ok")
    assert cand.status == "promoted" and cand.promotion["override_brake"] is False


def test_decision_order_base_policy_brake_contract_review():
    led = ToolTrustLedger()
    cand = ContractCandidate("append_to_file", "rev-a", {str((1, 0)): "allow", str((0, 1)): "block"}, probes=4)
    ToolTrustLedger.qualify(cand, "rev-a", [], ALLOW_ALL)
    assert led.decide("append_to_file", "rev-a", (1, 0), ALLOW_ALL)["reason"] == "no_promoted_contract_for_revision"
    assert led.decide("append_to_file", "rev-a", (1, 0), lambda b: False)["verdict"] == "deny"
    ToolTrustLedger.promote(cand, "op", cand.fingerprint, "ok")
    led.quarantine(cand)
    assert led.decide("append_to_file", "rev-a", (1, 0), ALLOW_ALL)["verdict"] == "allow"
    assert led.decide("append_to_file", "rev-a", (0, 1), ALLOW_ALL)["verdict"] == "block"
    assert led.decide("append_to_file", "rev-a", (1, 1), ALLOW_ALL)["verdict"] == "review"   # vector outside the contract
    for ctx in ("w1", "w2", "w3"):
        led.observe(_effect(ctx))
    d = led.decide("append_to_file", "rev-a", (1, 0), ALLOW_ALL)
    assert d["verdict"] == "refuse" and d["reason"] == "brake_engaged" and d["citations"]
    cand.promotion["override_brake"] = True
    assert led.decide("append_to_file", "rev-a", (1, 0), ALLOW_ALL)["verdict"] == "allow"
    assert led.decide("append_to_file", CHANGED_REVISION, (1, 0), ALLOW_ALL)["verdict"] == "review"


def test_effect_classes_are_derived_from_state_on_the_real_runtime():
    from agentdojo.functions_runtime import FunctionsRuntime
    from vac_study.extended_study import extended_tool_suite
    from vac_study.mechanism_lab import new_world, run_real_probe
    expected = {0: "read_share", 1: "write_share", 2: "foreign_modification", 3: "foreign_deletion"}
    for kind, cls in expected.items():
        runtime = FunctionsRuntime(extended_tool_suite(kind))
        env, candidates = new_world(11, kind, 0)
        harmful = next(c for c in candidates if run_real_probe(runtime, env, c).observed_unauthorized_effect)
        clone = env.model_copy(deep=True)
        before = clone.model_copy(deep=True)
        runtime.run_function(clone, "append_to_file", {"file_id": harmful.file_id, "content": harmful.content})
        assert classify_effect(before, clone, harmful.file_id) == cls


def test_family_study_brakes_and_quantifies_each_regime():
    r = family_study(0)
    assert r["brake_engaged"] and r["final_state"] == "canonical"
    assert [t["state"] for t in r["ratification_trajectory"]] == ["proposed", "confirmed", "canonical"]
    assert r["effect_classes_witnessed"] == ["read_share"] and r["unclassified_effects"] == 0
    assert all(s["qualification"]["passed"] and s["promoted"]["with_override"] for s in r["per_seed"])
    t = r["totals"]
    assert t["brake_only"]["refused"] == t["brake_only"]["harm_total"] + t["brake_only"]["safe_total"]
    assert t["contract_without_override"]["refused"] == t["brake_only"]["refused"]
    assert t["contract_with_override"]["harm_allowed"] == 0 and t["contract_with_override"]["safe_allowed"] > 0
    assert t["stale_revision"]["reviewed"] == t["stale_revision"]["harm_total"] + t["stale_revision"]["safe_total"]
