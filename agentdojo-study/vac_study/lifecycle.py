"""Tool-trust lifecycle: what happens operationally once a hidden effect is observed.

A learned contract answers "which actions of this tool are safe?".  It does not
answer the prior question "should this tool revision be used at all?".  This
module makes that decision explicit and deterministic, following the pattern of
dead-end ratification in an earlier open-source agent runtime by the author
(prior work, not a deliverable):

* **Ratification and brake.**  Every observed undeclared effect of a tool
  revision is an append-only `ObservedEffect` citing the probe or run that
  produced it.  The trust state of a (tool, revision) is *derived* by counting
  distinct independent contexts: one context -> `proposed`, two -> `confirmed`,
  three or more -> `canonical`, and a canonical revision is refused before
  dispatch, with citations.  Only declared effect classes ratify; an effect of
  an unknown class does not count towards the brake and is reported instead, so
  that a mis-classified observation cannot engage the brake by itself.
* **Contracts are governed exceptions.**  A learned contract enters as a
  quarantined `ContractCandidate`.  Deterministic qualification checks that it is
  pinned to the current revision, consistent with every held-out witness (no
  "allow" on a witnessed effect), and non-expanding (it never allows what the
  base policy denies).  Only an explicit human acknowledgement of the exact
  candidate fingerprint promotes it; a changed revision invalidates it.
* **Decision order.**  base policy denial > brake (unless a promoted contract
  carries an explicit, recorded `override_brake` decision) > promoted contract >
  review.  "Keep using the tool inside its learned-safe region" is therefore a
  deliberate, attributable exception with measurable cost, never the default.

Nothing here is a model.  All state is append-only and the derived states are
recomputed from the ledger, so a controller cannot argue its way past the brake.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from hashlib import sha256
import json

EFFECT_CLASSES = ("read_share", "write_share", "foreign_modification", "foreign_deletion")
THRESHOLDS = ((3, "canonical"), (2, "confirmed"), (1, "proposed"))


def _digest(obj) -> str:
    return sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


@dataclass(frozen=True)
class ObservedEffect:
    tool: str
    revision: str
    context_id: str          # independent probe world or run; repeats in one context count once
    effect_class: str
    receipt_digest: str      # the probe receipt or run record that witnessed the effect


@dataclass
class ContractCandidate:
    tool: str
    certified_revision: str
    verdicts: dict            # feature-vector tuple (as string) -> allow / block / review
    probes: int
    fingerprint: str = field(init=False)
    status: str = "quarantined"
    qualification: dict | None = None
    promotion: dict | None = None

    def __post_init__(self):
        self.fingerprint = _digest({"tool": self.tool, "revision": self.certified_revision,
                                    "verdicts": self.verdicts, "probes": self.probes})


class ToolTrustLedger:
    def __init__(self):
        self.effects: list[ObservedEffect] = []
        self.unclassified: list[ObservedEffect] = []
        self.candidates: list[ContractCandidate] = []

    # --- ratification -------------------------------------------------------
    def observe(self, effect: ObservedEffect):
        if effect.effect_class not in EFFECT_CLASSES:
            self.unclassified.append(effect)   # reported, never counted
            return
        self.effects.append(effect)

    def ratification_state(self, tool: str, revision: str) -> dict:
        contexts = sorted({e.context_id for e in self.effects if e.tool == tool and e.revision == revision})
        state = "clean"
        for n, name in THRESHOLDS:
            if len(contexts) >= n:
                state = name
                break
        citations = sorted({e.receipt_digest for e in self.effects if e.tool == tool and e.revision == revision})
        return {"tool": tool, "revision": revision, "independent_contexts": len(contexts),
                "contexts": contexts, "state": state, "citations": citations}

    def check_brake(self, tool: str, revision: str) -> dict:
        s = self.ratification_state(tool, revision)
        return {"engaged": s["state"] == "canonical", **s}

    # --- governed contracts -------------------------------------------------
    def quarantine(self, candidate: ContractCandidate) -> ContractCandidate:
        self.candidates.append(candidate)
        return candidate

    @staticmethod
    def qualify(candidate: ContractCandidate, current_revision: str, holdout_witnesses, base_policy_allows) -> dict:
        """Deterministic, no model.  `holdout_witnesses`: iterable of (bits, effect_observed).
        `base_policy_allows(bits)`: the host policy's own decision for that action."""
        gates = {
            "revision_pinned": candidate.certified_revision == current_revision,
            "no_allow_on_witnessed_effect": all(
                candidate.verdicts.get(str(tuple(bits))) != "allow" for bits, effect in holdout_witnesses if effect),
            "non_expanding": all(
                not (candidate.verdicts.get(str(tuple(bits))) == "allow" and not base_policy_allows(bits))
                for bits, _ in holdout_witnesses),
            "has_paid_probes": candidate.probes > 0,
        }
        candidate.qualification = {"gates": gates, "passed": all(gates.values())}
        candidate.status = "qualified" if candidate.qualification["passed"] else "rejected"
        return candidate.qualification

    @staticmethod
    def promote(candidate: ContractCandidate, actor: str, acknowledged_fingerprint: str, reason: str,
                override_brake: bool = False) -> bool:
        """A human decision over the exact fingerprint.  `override_brake` records the
        explicit choice to keep using a braked revision inside the contract's allowed
        region; without it a canonical brake still refuses every action."""
        if candidate.status != "qualified" or acknowledged_fingerprint != candidate.fingerprint:
            return False
        candidate.status = "promoted"
        candidate.promotion = {"actor": actor, "fingerprint": acknowledged_fingerprint, "reason": reason,
                               "override_brake": bool(override_brake)}
        return True

    def active_contract(self, tool: str, revision: str) -> ContractCandidate | None:
        for c in self.candidates:
            if c.status == "promoted" and c.tool == tool and c.certified_revision == revision:
                return c
        return None

    # --- the decision -------------------------------------------------------
    def decide(self, tool: str, revision: str, bits, base_policy_allows) -> dict:
        if not base_policy_allows(bits):
            return {"verdict": "deny", "reason": "base_policy"}
        brake = self.check_brake(tool, revision)
        contract = self.active_contract(tool, revision)
        if brake["engaged"] and not (contract and contract.promotion and contract.promotion.get("override_brake")):
            return {"verdict": "refuse", "reason": "brake_engaged", "citations": brake["citations"]}
        if contract is None:
            return {"verdict": "review", "reason": "no_promoted_contract_for_revision"}
        return {"verdict": contract.verdicts.get(str(tuple(bits)), "review"), "reason": "promoted_contract",
                "fingerprint": contract.fingerprint}

    def export(self) -> dict:
        return {"effects": [asdict(e) for e in self.effects], "unclassified": [asdict(e) for e in self.unclassified],
                "candidates": [asdict(c) for c in self.candidates]}
