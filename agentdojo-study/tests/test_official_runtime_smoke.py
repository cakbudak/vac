"""No-LLM pre-dispatch check on the official AgentDojo workspace tools and state."""
from agentdojo.task_suite import get_suites
from vac_study.runner import ManualRuntime


def test_manual_runtime_allows_read_and_rejects_send_before_dispatch():
    suite = get_suites("v1.2.2")["workspace"]
    env = suite.load_and_inject_default_environment({})
    ManualRuntime.all_decisions = []
    rt = ManualRuntime(suite.tools)
    before = env.model_dump_json()
    current_day, err = rt.run_function(env, "get_current_day", {})
    assert err is None and isinstance(current_day, str)
    _, denied = rt.run_function(env, "send_email", {
        "recipients": ["nobody@example.invalid"], "subject": "not dispatched", "body": "synthetic test",
        "attachments": None, "cc": None, "bcc": None})
    assert denied and denied.startswith("VACReview:")
    assert env.model_dump_json() == before, "blocked tool altered the official workspace state"
    assert ManualRuntime.all_decisions[-1]["function"] == "send_email"
    assert ManualRuntime.all_decisions[-1]["verdict"] == "review"
