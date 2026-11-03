"""Observation-backed tool effect contracts for the REAL AgentDojo FunctionsRuntime.

One sample is a witnessed transition, not proof that a tool can never mutate.
Contracts are bound to the Python implementation digest and to exact argument
shapes. Holdout calls are checked by a separate pre-dispatch adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from typing import Any, Mapping
import inspect
import json

from agentdojo.functions_runtime import FunctionsRuntime

def canonical(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)

def digest(obj: Any) -> str:
    return sha256(canonical(obj).encode()).hexdigest()

def implementation_revision(func) -> str:
    """Bind code, tool contract AND captured configuration (e.g. hidden branch).

    A source-only digest would miss a changed closure using identical source.
    """
    if func is None or not hasattr(func, "run"):
        return "UNAVAILABLE"
    try:
        src = inspect.getsource(func.run)
    except (OSError, TypeError):
        return "UNAVAILABLE"
    captures=[]
    for cell in getattr(func.run, "__closure__", None) or ():
        try:
            v=cell.cell_contents
        except ValueError:
            return "UNAVAILABLE"
        if isinstance(v,(str,int,float,bool,type(None))):
            captures.append({"literal":v})
        elif hasattr(v,"run") and callable(getattr(v,"run",None)):
            try:
                source_of_wrapped=inspect.getsource(v.run)
            except (OSError,TypeError):
                return "UNAVAILABLE"
            captures.append({"wrapped_tool":getattr(v,"name",None),
                             "wrapped_source":source_of_wrapped})
        elif callable(v):
            try: source_of_callable=inspect.getsource(v)
            except (OSError,TypeError): return "UNAVAILABLE"
            captures.append({"callable":getattr(v,"__qualname__",None),
                             "source":source_of_callable})
        else:
            return "UNAVAILABLE"
    return digest({"module":func.run.__module__,"name":func.run.__qualname__,
                   "source":src,"captures":captures,
                   "description":getattr(func,"description",None),
                   "dependencies":sorted(getattr(func,"dependencies",{}))})

def state_fingerprint(env) -> str:
    return digest(env.model_dump(mode="json"))

@dataclass(frozen=True)
class ProbeReceipt:
    function: str
    implementation_revision: str
    argument_digest: str
    before: str
    after: str
    changed: bool
    error: str | None

class IsolatedEffectProber:
    def __init__(self, tools):
        self.tools = list(tools)
        self.runtime = FunctionsRuntime(self.tools)
        self.receipts: list[ProbeReceipt] = []

    def probe(self, base_env, function: str, kwargs: Mapping[str, Any]) -> ProbeReceipt:
        if function not in self.runtime.functions:
            raise ValueError("unknown tool")
        clone = base_env.model_copy(deep=True)
        before = state_fingerprint(clone)
        _, error = self.runtime.run_function(clone, function, dict(kwargs))
        after = state_fingerprint(clone)
        receipt = ProbeReceipt(
            function, implementation_revision(self.runtime.functions[function]),
            digest(dict(kwargs)), before, after, before != after, error,
        )
        self.receipts.append(receipt)
        if state_fingerprint(base_env) != before:
            raise AssertionError("probe modified source environment")
        return receipt

@dataclass(frozen=True)
class Decision:
    tool: str
    verdict: str
    reason: str
    revision: str

class EffectBoundRuntime(FunctionsRuntime):
    """Exact-input, observed-only control. A read-only policy is an external input."""
    def __init__(self, tools, receipts: list[ProbeReceipt], *, policy_allowed: set[str]):
        super().__init__(tools)
        self.by_sample = {(r.function, r.argument_digest): r for r in receipts}
        self.policy_allowed = frozenset(policy_allowed)
        self.decisions: list[Decision] = []

    def run_function(self, env, function: str, kwargs: Mapping[str, Any], raise_on_error=False):
        tool = self.functions.get(function)
        revision = implementation_revision(tool) if tool is not None else "unknown"
        if tool is None or revision == "UNAVAILABLE":
            return self._review(function, revision, "unregistered_or_unpinned")
        if function not in self.policy_allowed:
            return self._review(function, revision, "base_policy")
        receipt = self.by_sample.get((function, digest(dict(kwargs))))
        if receipt is None:
            return self._review(function, revision, "unobserved_argument_context")
        if receipt.implementation_revision != revision:
            return self._review(function, revision, "stale_tool_revision")
        if receipt.error is not None:
            return self._review(function, revision, "probe_failure")
        if receipt.changed:
            return self._review(function, revision, "observed_state_mutation")
        result, error = super().run_function(env, function, kwargs, raise_on_error=raise_on_error)
        self.decisions.append(Decision(function,"executed" if not error else "outcome_unknown",
                                       "matched_isolated_observation",revision))
        return result, error

    def _review(self, function, revision, reason):
        self.decisions.append(Decision(function,"review",reason,revision))
        return None, "VACReview: " + reason


def export_receipts(prober: IsolatedEffectProber, path):
    from pathlib import Path
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps([asdict(x) for x in prober.receipts], indent=2, sort_keys=True)+"\n")
