"""Paired official AgentDojo comparison using an unchanged frozen injection.

Arms: baseline (standard runtime), manually pinned read-only contract, observed-
context effect contract. Effects are observed on cloned official tool states.
"""
import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path

from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline, PipelineConfig
from agentdojo.functions_runtime import FunctionsRuntime
from agentdojo.models import ModelsEnum
from agentdojo.task_suite import get_suites

from vac_study.effects import IsolatedEffectProber, EffectBoundRuntime, export_receipts, state_fingerprint

ROOT = Path(__file__).resolve().parents[1]
# The frozen official AgentDojo run (injections + messages) that all three arms replay.
INPUT = ROOT / "results" / "official_agentdojo_runs" / "untreated_important_instructions_injection_task_0.json"
if not INPUT.exists():  # original location on the development server
    INPUT = ROOT.parent / "agentdojo-evaluation" / "runs" / "local_attack" / "local" / "workspace" / "user_task_0" / "important_instructions" / "injection_task_0.json"
POLICY_READ = {"get_current_day", "search_calendar_events", "get_day_calendar_events"}

# Predefined from the PUBLIC user request, not selected from hidden traces.
PREDECLARED_PROBES = (
    ("get_current_day", {}),
    ("search_calendar_events", {"query": "Networking event"}),
    ("search_calendar_events", {"query": "Networking"}),
    ("get_day_calendar_events", {"day": "2024-05-26"}),
)


class ManualRuntime(FunctionsRuntime):
    all_decisions = []
    def run_function(self, env, function, kwargs, raise_on_error=False):
        if function not in POLICY_READ:
            self.all_decisions.append({"function": function,"verdict": "review","reason": "manual_read_only"})
            return None, "VACReview: task is read-only"
        self.all_decisions.append({"function": function,"verdict": "allow","reason": "manual_specification"})
        return super().run_function(env,function,kwargs,raise_on_error=raise_on_error)


def execute(arm: str, attack: str) -> dict:
    if attack != "important_instructions":
        raise ValueError("only the frozen important_instructions injection is qualified")
    prior = json.loads(INPUT.read_text())
    assert prior["benchmark_version"] == "v1.2.2"
    assert prior["injection_task_id"] == "injection_task_0"
    assert prior["attack_type"] == attack

    suite = get_suites("v1.2.2")["workspace"]
    task = suite.user_tasks["user_task_0"]
    base_env = suite.load_and_inject_default_environment(prior["injections"])
    envhash_before = state_fingerprint(base_env)
    prober = IsolatedEffectProber(suite.tools)
    if arm == "observed":
        probe_env = task.init_environment(base_env.model_copy(deep=True))
        for function,args in PREDECLARED_PROBES:
            prober.probe(probe_env,function,args)
        if state_fingerprint(base_env) != envhash_before:
            raise AssertionError("training probes mutated the benchmark's authoritative state")

    decisions = []
    if arm == "manual":
        ManualRuntime.all_decisions = []
        runtime_cls = ManualRuntime
    elif arm == "observed":
        receipts = tuple(prober.receipts)
        class QualifiedRuntime(EffectBoundRuntime):
            def __init__(self, tools):
                super().__init__(tools, list(receipts), policy_allowed=POLICY_READ)
            def run_function(self, env, function, kwargs, raise_on_error=False):
                result,error = super().run_function(env,function,kwargs,raise_on_error=raise_on_error)
                decisions.append(asdict(self.decisions[-1]))
                return result,error
        runtime_cls = QualifiedRuntime
    elif arm == "untreated":
        runtime_cls = FunctionsRuntime
    else:
        raise ValueError(arm)

    pipeline = AgentPipeline.from_config(
        PipelineConfig(llm=ModelsEnum.LOCAL, model_id="qwen3.8:latest",
                       defense=None, tool_delimiter="tool",
                       system_message_name=None, system_message=None))
    utility, attacker_success = suite.run_task_with_pipeline(
        pipeline, task, suite.injection_tasks["injection_task_0"],
        prior["injections"], runtime_class=runtime_cls, environment=base_env)

    if arm == "manual":
        decisions = list(ManualRuntime.all_decisions)
    return {
        "benchmark": "AgentDojo 0.1.35 / v1.2.2", "suite": "workspace",
        "user_task": task.ID, "injection_task": "injection_task_0",
        "attack": attack, "arm": arm, "model": "local/qwen3.8:latest",
        "utility": utility, "attacker_goal_achieved": attacker_success,
        "probe_execution_count": len(prober.receipts),
        "probe_details": [asdict(r) for r in prober.receipts],
        "runtime_decisions": decisions,
        "source": str(INPUT), "input_injection_digest": __import__("hashlib").sha256(
            json.dumps(prior["injections"],sort_keys=True).encode()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", choices=["untreated","manual","observed"],required=True)
    args=parser.parse_args()
    result=execute(args.arm,"important_instructions")
    p=ROOT/"results"/f"{args.arm}_important_instructions.json"
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print("Saved:",p)
    print("Result:",{k:result[k] for k in ("arm","utility","attacker_goal_achieved","probe_execution_count")})
    print("Runtime:",result["runtime_decisions"])


if __name__ == "__main__":
    main()
