"""Enforcing pre-dispatch boundary of VAC.

The client's existing boundary decides first and is never widened.  The revision
attestation (installation, served definition, contract) must match the pin, and the
effect verdict computed from pre-call state must be `allow`; anything else is a
`review` or a `block`, and such a call is never invoked.  Used in-process through
`dispatch`/`dispatch_async` and in front of an MCP server by `runtime/mcp_proxy.py`.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal, TypeVar

DecisionKind = Literal["allow", "review", "block"]
T = TypeVar("T")


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


@dataclass(frozen=True)
class Revision:
    installation: str
    served_definition: str
    contract: str

    def complete(self) -> bool:
        return all(isinstance(v, str) and len(v) == 64
                   and all(c in "0123456789abcdef" for c in v.lower())
                   for v in (self.installation, self.served_definition, self.contract))


@dataclass(frozen=True)
class Decision:
    kind: DecisionKind
    reason: str


class DispatchDenied(RuntimeError):
    def __init__(self, decision: Decision) -> None:
        super().__init__(f"{decision.kind}: {decision.reason}")
        self.decision = decision


@dataclass(frozen=True)
class Evidence:
    # Decision computed from pre-call state. None means unqualified.
    effect_verdict: DecisionKind | None
    revision: Revision


def authorize(
    *, tool: str, arguments: dict[str, Any], base_allows: Callable[[str, dict[str, Any]], bool],
    pinned: Revision, evidence: Evidence,
) -> Decision:
    # Hard boundary always takes precedence, including over reviews and overrides.
    if not base_allows(tool, arguments):
        return Decision("block", "existing security boundary denies")
    if not pinned.complete() or not evidence.revision.complete():
        return Decision("review", "missing or invalid revision attestation")
    if evidence.revision != pinned:
        return Decision("review", "contract or tool revision changed")
    verdict = evidence.effect_verdict
    if verdict == "block":
        return Decision("block", "effect contract denies")
    if verdict == "review":
        return Decision("review", "effect contract abstains")
    if verdict != "allow":
        return Decision("review", "unknown effect verdict")
    return Decision("allow", "boundary and attested effect contract agree")


def dispatch(
    *, tool: str, arguments: dict[str, Any], base_allows: Callable[[str, dict[str, Any]], bool],
    pinned: Revision, evidence: Evidence, invoke: Callable[[str, dict[str, Any]], T],
    record_before_dispatch: Callable[[Decision, str, dict[str, Any]], Any] | None = None,
) -> tuple[Decision, T]:
    decision = authorize(tool=tool, arguments=arguments, base_allows=base_allows,
                         pinned=pinned, evidence=evidence)
    if record_before_dispatch is not None:
        record_before_dispatch(decision, tool, arguments)
    if decision.kind != "allow":
        raise DispatchDenied(decision)
    return decision, invoke(tool, arguments)


async def dispatch_async(
    *, tool: str, arguments: dict[str, Any], base_allows: Callable[[str, dict[str, Any]], bool],
    pinned: Revision, evidence: Evidence, invoke: Callable[[str, dict[str, Any]], Awaitable[T]],
    record_before_dispatch: Callable[[Decision, str, dict[str, Any]], Any] | None = None,
) -> tuple[Decision, T]:
    decision = authorize(tool=tool, arguments=arguments, base_allows=base_allows,
                         pinned=pinned, evidence=evidence)
    if record_before_dispatch is not None:
        record_before_dispatch(decision, tool, arguments)
    if decision.kind != "allow":
        raise DispatchDenied(decision)
    return decision, await invoke(tool, arguments)
