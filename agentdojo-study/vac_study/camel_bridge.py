"""CaMeL-native workspace policy extension, preserving its capability checks.

Original upstream: google-research/camel-prompt-injection, commit f083b6b.
This module is an additive policy VETO, never a replacement for CaMeL's
data-flow / dependency checks. Re-run with CaMeL's isolated Python environment.
"""
from __future__ import annotations
from collections.abc import Mapping, Iterable
from typing import Any

from camel.interpreter.value import CaMeLValue
from camel.security_policy import Allowed, Denied
from camel.pipeline_elements.security_policies.workspace import WorkspaceSecurityPolicyEngine

from vac_study.mechanism_lab import VersionSpace, features


class VACQualifiedWorkspacePolicy(WorkspaceSecurityPolicyEngine):
    """Additional contract gate after the unchanged CaMeL base policy."""

    def __init__(self, env, learned_model: VersionSpace,
                 tool_revision: str, certified_revision: str):
        super().__init__(env)
        self.learned_model=learned_model
        self.tool_revision=tool_revision
        self.certified_revision=certified_revision
        self.vac_audit=[]

    def check_policy(self,
                     tool_name: str,
                     kwargs: Mapping[str, CaMeLValue],
                     dependencies: Iterable[CaMeLValue]):
        base=super().check_policy(tool_name,kwargs,dependencies)
        if isinstance(base, Denied):
            self.vac_audit.append((tool_name,"camel_denied",base.reason))
            return base

        if tool_name != "append_to_file":
            self.vac_audit.append((tool_name,"camel_allowed","unchanged"))
            return base

        current_revision = self.tool_revision() if callable(self.tool_revision) else self.tool_revision
        if current_revision != self.certified_revision:
            self.vac_audit.append((tool_name,"vac_review","tool_revision_mismatch"))
            return Denied("VACReview: effect contract revision mismatch")

        try:
            file_id=kwargs["file_id"].raw
            content=kwargs["content"].raw
            if not isinstance(file_id,str) or not isinstance(content,str):
                raise ValueError("untyped input")
            target=self._env.cloud_drive.files[file_id]
            verdict=self.learned_model.verdict(features(target,content))
        except (ValueError,AttributeError,KeyError,TypeError):
            verdict="review"

        self.vac_audit.append((tool_name,"vac_"+verdict,"effect_contract"))
        if verdict!="allow":
            return Denied("VACReview: unqualified or dangerous effect: "+verdict)
        return base


def trusted_string(value: str) -> CaMeLValue:
    """Literal known to the privileged CaMeL interpreter / trusted user."""
    from camel.interpreter.value import CaMeLStr
    from camel.capabilities import Capabilities
    return CaMeLStr.from_raw(value,Capabilities.default(),())
