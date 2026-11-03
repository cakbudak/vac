"""Regenerate the extended-study evidence and compare byte-for-byte.

Covers the extended study, the scripted attack study, the family-level summary and the
three deterministic second-release studies (guard ablation, induced vocabulary, tool-trust
lifecycle).  None of them contacts a model.
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentdojo.task_suite import get_suites
get_suites("v1.2.2")  # upstream import-order requirement
from vac_study.extended_study import study, ALL_FAMILIES
from vac_study.extended_adversary import study_attack
from vac_study.stats import summarize
from vac_study.ablation import study as ablation_study
from vac_study.induced_vocabulary import study as induced_study
from vac_study.lifecycle_study import study as lifecycle_study

ROOT = Path(__file__).resolve().parents[1]


def extended():
    result = study()
    sweep = study(families=ALL_FAMILIES, seeds=(11, 22, 33), budgets=(8, 16, 64))
    result["budget_sweep_rows"] = sweep["rows"]
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--write", action="store_true", help="replace the recorded evidence")
    a = p.parse_args()
    plan = (("extended_study.json", extended), ("extended_attack_study.json", study_attack),
            ("guard_ablation.json", ablation_study), ("induced_vocabulary_study.json", induced_study),
            ("lifecycle_study.json", lifecycle_study))
    produced = {}
    for name, producer in plan:
        path = ROOT / "results" / name
        produced[name] = producer()
        actual = json.dumps(produced[name], indent=2, sort_keys=True) + "\n"
        if a.write:
            path.write_text(actual); print("WRITTEN", name)
        else:
            assert actual == path.read_text(), name + " changed"
            print("BYTE_IDENTICAL", name)
    summary = json.dumps(summarize(produced["extended_study.json"], produced["extended_attack_study.json"]),
                         indent=2, sort_keys=True) + "\n"
    path = ROOT / "results" / "family_level_summary.json"
    if a.write:
        path.write_text(summary); print("WRITTEN family_level_summary.json")
    else:
        assert summary == path.read_text(), "family_level_summary.json changed"
        print("BYTE_IDENTICAL family_level_summary.json")
    print("All extended studies reproduced.")


if __name__ == "__main__":
    main()
