"""The frozen learner from the VAC package, applied to real tool calls.

What is frozen: `JuntaVersionSpace` (exact k-junta version space, unanimity
verdicts) and `Witness`, imported unchanged from the submitted package; their
source digests are recorded in every result file.  What is new and therefore
NOT frozen: the feature adapter below, which induces a label-free predicate
vocabulary from the strings of arbitrary tool arguments (the package's
generators only knew (file, content) pairs), and the fact that probes are
consumed in traffic order on a live server instead of chosen on cloned state.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

SUBMISSION = Path(os.environ.get(
    "VAC_SUBMISSION_DIR",
    "/tmp/claude-0/-home-claude/b91f55e5-636d-5559-a2c4-ab2035313ac7/scratchpad/submission/VAC_AgentDojo_Study_Submission_2026-10-30"))
sys.path.insert(0, str(SUBMISSION))
from vac_study.extended_study import JuntaVersionSpace  # noqa: E402  (frozen)
from vac_study.mechanism_lab import Witness  # noqa: E402  (frozen)

FROZEN_FILES = ("vac_study/extended_study.py", "vac_study/mechanism_lab.py", "vac_study/induced_vocabulary.py")
TOKEN = re.compile(r"[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)*")


def frozen_digests() -> dict[str, str]:
    return {f: hashlib.sha256((SUBMISSION / f).read_bytes()).hexdigest() for f in FROZEN_FILES}


def _strings(args: dict) -> dict[str, str]:
    """Flatten the call's arguments to named strings (lists joined, numbers stringified)."""
    out = {}
    for k, v in sorted(args.items()):
        if isinstance(v, list):
            out[k] = " ".join(str(x) if not isinstance(x, dict) else " ".join(str(y) for y in x.values()) for x in v)
        elif isinstance(v, dict):
            out[k] = " ".join(str(y) for y in v.values())
        else:
            out[k] = str(v)
    return out


def generate_predicates(pool: list[tuple[str, dict]]):
    """pool: list of (tool, args).  Mirrors the package's generator families
    (tokens, first character, length thresholds, character classes, punctuation,
    suffixes) over every argument, plus the tool name and a few path facts."""
    preds = []
    tools = sorted({t for t, _ in pool})
    for t in tools:
        preds.append((f"tool:{t}", lambda tool, s, x=t: tool == x))
    keys = sorted({k for _, a in pool for k in _strings(a)})
    for key in keys:
        vals = [_strings(a).get(key, "") for _, a in pool]
        preds.append((f"has_arg:{key}", lambda tool, s, k=key: k in s))
        for tok in sorted({x for v in vals for x in TOKEN.findall(v)}):
            preds.append((f"{key}.token_cs:{tok}", lambda tool, s, k=key, x=tok: x in TOKEN.findall(s.get(k, ""))))
        for tok in sorted({x.lower() for v in vals for x in TOKEN.findall(v)}):
            preds.append((f"{key}.token_ci:{tok}", lambda tool, s, k=key, x=tok: x in [y.lower() for y in TOKEN.findall(s.get(k, ""))]))
        for ch in sorted({v[:1] for v in vals if v}):
            preds.append((f"{key}.first:{ch}", lambda tool, s, k=key, x=ch: s.get(k, "").startswith(x)))
        for L in sorted({len(v) for v in vals})[1:]:
            preds.append((f"{key}.len_ge:{L}", lambda tool, s, k=key, n=L: len(s.get(k, "")) >= n))
        preds.append((f"{key}.has_upper", lambda tool, s, k=key: any(c.isupper() for c in s.get(k, ""))))
        preds.append((f"{key}.has_digit", lambda tool, s, k=key: any(c.isdigit() for c in s.get(k, ""))))
        for ch in sorted({c for v in vals for c in v if not c.isalnum() and not c.isspace()}):
            preds.append((f"{key}.has_char:{ch}", lambda tool, s, k=key, x=ch: x in s.get(k, "")))
        for ext in sorted({v.rsplit(".", 1)[-1] for v in vals if "." in v.rsplit("/", 1)[-1]}):
            preds.append((f"{key}.suffix:{ext}", lambda tool, s, k=key, e=ext: s.get(k, "").endswith("." + e)))
        for d in sorted({v.count("/") for v in vals})[1:]:
            preds.append((f"{key}.depth_ge:{d}", lambda tool, s, k=key, n=d: s.get(k, "").count("/") >= n))
    return preds


class InducedVocabulary:
    """Label-free induction on the pool; identical or complementary truth vectors merged."""

    def __init__(self, pool: list[tuple[str, dict]]):
        raw = generate_predicates(pool)
        self.generated = len(raw)
        self.names, self.predicates, self.aliases = [], [], {}
        seen: dict[tuple, str] = {}
        for name, fn in raw:
            vec = tuple(int(bool(fn(t, _strings(a)))) for t, a in pool)
            if len(set(vec)) < 2:
                continue
            canon = vec if vec[0] == 0 else tuple(1 - v for v in vec)
            if canon in seen:
                self.aliases.setdefault(seen[canon], []).append(name)
                continue
            seen[canon] = name
            self.names.append(name)
            self.predicates.append(fn)

    @property
    def size(self) -> int:
        return len(self.names)

    def bits(self, tool: str, args: dict) -> tuple[int, ...]:
        s = _strings(args)
        return tuple(int(bool(p(tool, s))) for p in self.predicates)


class Learner:
    """Frozen JuntaVersionSpace over an induced vocabulary; traffic-order acquisition."""

    def __init__(self, vocab: InducedVocabulary, k: int):
        self.vocab, self.k = vocab, k
        self.space = JuntaVersionSpace(vocab.size, k)
        self.observed = 0

    def observe(self, tool: str, args: dict, deviation: bool, tool_error: bool):
        bits = self.vocab.bits(tool, args)
        w = Witness(bits, bool(deviation), bool(tool_error), "")
        self.space.observe(w)          # the frozen class ignores tool errors itself
        if not tool_error:
            self.observed += 1

    def verdict(self, tool: str, args: dict) -> str:
        return self.space.verdict(self.vocab.bits(tool, args))

    @property
    def hypotheses_remaining(self) -> int:
        return self.space.hypotheses_remaining
