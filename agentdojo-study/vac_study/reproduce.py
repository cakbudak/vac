"""Regenerate deterministic mechanism-study evidence, verify byte identity.

Original CaMeL LLM episodes are verified semantically by verify_extended:
model tokens are not required to reproduce byte-for-byte.
"""
import argparse,json
from pathlib import Path
from vac_study.mechanism_lab import study
from vac_study.adversary import study_attack

ROOT=Path(__file__).resolve().parents[1]
PLAN=(
 ("discriminating_study.json",lambda:study(families=range(8))),
 ("misspecification_controls.json",lambda:study(families=(8,9))),
 ("bounded_attack_study.json",study_attack),
)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--write",action="store_true",
                        help="replace recorded deterministic evidence")
    args=parser.parse_args()
    for filename,producer in PLAN:
        p=ROOT/"results"/filename
        actual=json.dumps(producer(),sort_keys=True,indent=2)+"\n"
        if args.write:
            p.write_text(actual)
            print("WRITTEN",filename)
        else:
            stored=p.read_text()
            assert actual==stored, filename+" changed"
            print("BYTE_IDENTICAL",filename)
    print("All deterministic studies reproduced.")

if __name__=="__main__":
    main()
