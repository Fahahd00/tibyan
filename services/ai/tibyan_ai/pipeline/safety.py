"""Safety gate: the last stage before anything is shown to the user.

Decides between ANSWER / ABSTENTION based on verification results. Pre-retrieval decisions
(ESCALATION for personal and high-risk cases, CLARIFICATION) are taken earlier in the orchestrator.
"""

from __future__ import annotations

from dataclasses import dataclass

from .generation import Draft
from .verification import VerifiedClaim


@dataclass
class GateDecision:
    outcome: str  # answer | abstention
    reason_code: str | None
    kept: list[VerifiedClaim]
    removed: list[VerifiedClaim]
    should_regenerate: bool = False


def gate(draft: Draft, verified: list[VerifiedClaim], *, can_regenerate: bool) -> GateDecision:
    if draft.conflict:
        return GateDecision("abstention", "unresolved_conflict", [], verified)
    if draft.insufficient or not verified:
        return GateDecision("abstention", "weak_evidence", [], verified)

    summary = next((v for v in verified if v.role == "summary"), None)
    kept = [v for v in verified if v.supported]
    removed = [v for v in verified if not v.supported]

    if summary is None or not summary.supported:
        if can_regenerate:
            return GateDecision("abstention", "verification_failed", kept, removed, should_regenerate=True)
        return GateDecision("abstention", "verification_failed", [], verified)

    # A claim the judge marked as contradicting its own evidence means the draft is unreliable as a whole.
    if any(v.entailment == "contradicted" for v in verified):
        if can_regenerate:
            return GateDecision("abstention", "verification_failed", kept, removed, should_regenerate=True)
        return GateDecision("abstention", "verification_failed", [], verified)

    return GateDecision("answer", None, kept, removed)
