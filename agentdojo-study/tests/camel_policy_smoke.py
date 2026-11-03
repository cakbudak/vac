"""Run the ORIGINAL CaMeL workspace policy with an additional VAC learned-effect veto.

Not an LLM-driven CaMeL benchmark: this tests the actual CaMeL policy seam and
the official AgentDojo tool dispatch, with a separate mechanism world.
"""
from agentdojo.task_suite import get_suites
get_suites("v1.2.2")  # Avoid a circular import in the upstream policy artifact.
from agentdojo.functions_runtime import FunctionsRuntime
from camel.security_policy import Allowed, Denied
from camel.pipeline_elements.security_policies.workspace import WorkspaceSecurityPolicyEngine
from camel.capabilities import Capabilities, sources
from camel.interpreter.value import CaMeLStr

from vac_study.mechanism_lab import (
    active_probe_plan, independent_grade, new_world, run_real_probe, tool_suite,
)
from vac_study.camel_bridge import VACQualifiedWorkspacePolicy, trusted_string
from vac_study.effects import implementation_revision


def main():
    kind=0
    seed=11
    tools=tool_suite(kind)
    runtime=FunctionsRuntime(tools)
    train,examples=new_world(seed,kind,0)
    target,heldout=new_world(seed,kind,1)
    model,observations=active_probe_plan(runtime,train,examples,32,seed*17+kind)
    base=WorkspaceSecurityPolicyEngine(target)
    tool=next(t for t in tools if t.name=="append_to_file")
    qualified_revision=implementation_revision(tool)
    assert qualified_revision != "UNAVAILABLE"
    policy=VACQualifiedWorkspacePolicy(target,model,
        tool_revision=lambda: implementation_revision(tool),certified_revision=qualified_revision)
    outcomes={"allowed_benign":0,"blocked_hidden_side_effect":0,
              "base_denied":0,"stale_denied":0}
    for action in heldout:
        args={"file_id":trusted_string(action.file_id),
              "content":trusted_string(action.content)}
        basic=base.check_policy("append_to_file",args,())
        strict=policy.check_policy("append_to_file",args,())
        outcome=run_real_probe(runtime,target,action)
        assert isinstance(basic,Allowed), "unexpected base CaMeL rejection"
        if outcome.observed_unauthorized_effect:
            assert isinstance(strict,Denied)
            outcomes["blocked_hidden_side_effect"]+=1
        else:
            assert isinstance(strict,Allowed)
            outcomes["allowed_benign"]+=1

    # The unchanged CaMeL policy has independent authority; VAC cannot
    # override it even when its own effect model predicts no harmful effect.
    from camel.capabilities import sources
    malicious_capabilities=Capabilities(
        frozenset({sources.SourceEnum.User}),frozenset({"nobody@example.org"}))
    file_id=next(a.file_id for a in heldout if target.cloud_drive.files[a.file_id].shared_with)
    args={"file_id":trusted_string(file_id),
          "content":CaMeLStr.from_raw("private content",malicious_capabilities,())}
    assert isinstance(base.check_policy("append_to_file",args,()),Denied)
    assert isinstance(policy.check_policy("append_to_file",args,()),Denied)
    assert policy.vac_audit[-1][1]=="camel_denied"
    outcomes["base_denied"]=1

    stale=VACQualifiedWorkspacePolicy(target,model,lambda: implementation_revision(tool),"stale-digest")
    safe=next(a for a in heldout if not run_real_probe(runtime,target,a).observed_unauthorized_effect)
    args={"file_id":trusted_string(safe.file_id),"content":trusted_string(safe.content)}
    assert isinstance(stale.check_policy("append_to_file",args,()),Denied)
    outcomes["stale_denied"]=1

    print("CaMeL + VAC policy bridge PASS:",outcomes,
          "independent_probe_count",len(observations))


if __name__=="__main__":
    main()
