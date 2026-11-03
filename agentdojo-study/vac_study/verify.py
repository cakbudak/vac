"""Validate the persisted paired AgentDojo study and probe ledger."""
import json
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
EXPECTED=["untreated","manual","observed"]

def main():
    records=[]
    for arm in EXPECTED:
        p=BASE/"results"/f"{arm}_important_instructions.json"
        d=json.loads(p.read_text())
        assert d["arm"] == arm
        assert d["suite"] == "workspace"
        assert d["user_task"] == "user_task_0"
        assert d["injection_task"] == "injection_task_0"
        assert d["benchmark"] == "AgentDojo 0.1.35 / v1.2.2"
        assert d["attack"] == "important_instructions"
        assert d["model"] == "local/qwen3.8:latest"
        assert type(d["utility"]) is bool and type(d["attacker_goal_achieved"]) is bool
        assert d["probe_execution_count"] == len(d["probe_details"])
        if arm != "observed":
            assert d["probe_execution_count"] == 0
        else:
            assert d["probe_execution_count"] == 4
            for receipt in d["probe_details"]:
                assert len(receipt["before"])==64
                assert len(receipt["after"])==64
                assert len(receipt["implementation_revision"])==64
                assert receipt["changed"] == (receipt["before"] != receipt["after"])
                assert receipt["error"] is None
        records.append(d)
    assert len({d["input_injection_digest"] for d in records})==1
    print("VERIFIED: 3 same-injection AgentDojo arms, correct tool-effect probes")
    for r in records:
        print(f'  {r["arm"]:>9}: utility={r["utility"]}, attacker_success={r["attacker_goal_achieved"]}, probes={r["probe_execution_count"]}')

if __name__=="__main__":
    main()
