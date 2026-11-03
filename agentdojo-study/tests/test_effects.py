from agentdojo.task_suite import get_suites
from agentdojo.functions_runtime import FunctionsRuntime
from vac_study.effects import IsolatedEffectProber, EffectBoundRuntime, state_fingerprint


def setup():
    suite = get_suites("v1.2.2")["workspace"]
    env = suite.load_and_inject_default_environment({})
    prober = IsolatedEffectProber(suite.tools)
    return suite,env,prober

def test_clean_probe_observes_read_without_mutating_live_world():
    _,env,prober=setup()
    original=state_fingerprint(env)
    receipt=prober.probe(env,"get_current_day",{})
    assert not receipt.changed and receipt.error is None
    assert receipt.before==receipt.after==original
    assert state_fingerprint(env)==original

def test_probe_discovers_real_send_email_state_effect():
    _,env,prober=setup()
    kwargs={"recipients":["audit@example.com"],"subject":"probe","body":"probe",
            "attachments":None,"cc":None,"bcc":None}
    original=state_fingerprint(env)
    receipt=prober.probe(env,"send_email",kwargs)
    assert receipt.changed and receipt.error is None
    assert state_fingerprint(env)==original
    rt=EffectBoundRuntime(prober.tools,prober.receipts,policy_allowed={"send_email"})
    result,err=rt.run_function(env,"send_email",kwargs)
    assert err and "observed_state_mutation" in err
    assert state_fingerprint(env)==original

def test_exact_observed_read_allowed():
    suite,env,prober=setup()
    prober.probe(env,"get_current_day",{})
    rt=EffectBoundRuntime(suite.tools,prober.receipts,policy_allowed={"get_current_day"})
    value,err=rt.run_function(env,"get_current_day",{})
    assert err is None and isinstance(value,str)
    assert rt.decisions[-1].verdict=="executed"

def test_unprobed_variant_never_inherits_approval():
    suite,env,prober=setup()
    prober.probe(env,"search_calendar_events",{"query":"Networking event"})
    rt=EffectBoundRuntime(suite.tools,prober.receipts,policy_allowed={"search_calendar_events"})
    value,err=rt.run_function(env,"search_calendar_events",{"query":"another event"})
    assert value is None
    assert err and "unobserved_argument_context" in err

def test_base_policy_applies_before_observation():
    suite,env,prober=setup()
    prober.probe(env,"get_current_day",{})
    rt=EffectBoundRuntime(suite.tools,prober.receipts,policy_allowed=set())
    _,err=rt.run_function(env,"get_current_day",{})
    assert "base_policy" in err

def test_tool_revision_must_match(monkeypatch):
    suite,env,prober=setup()
    prober.probe(env,"get_current_day",{})
    rt=EffectBoundRuntime(suite.tools,prober.receipts,policy_allowed={"get_current_day"})
    from vac_study import effects
    monkeypatch.setattr(effects,"implementation_revision",lambda _: "new-revision")
    _,err=rt.run_function(env,"get_current_day",{})
    assert "stale_tool_revision" in err
