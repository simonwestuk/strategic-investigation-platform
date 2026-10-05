from dataclasses import dataclass

from sip.domain.models import Investigation, RiskLevel


@dataclass(frozen=True)
class GovernanceAssessment:
    risk: RiskLevel
    requires_human_review: bool
    reason: str


def assess_investigation(investigation: Investigation) -> GovernanceAssessment:
    """Initial explicit policy layer. Replace/extend with configurable policy rules later."""
    sensitive = any(s.sensitivity.value in {"confidential", "restricted"} for s in investigation.sources)
    consequential = bool(investigation.decision_options)

    if sensitive and consequential:
        return GovernanceAssessment(RiskLevel.HIGH, True, "Sensitive evidence informs consequential options.")
    if consequential:
        return GovernanceAssessment(RiskLevel.MEDIUM, True, "Strategic options require a human decision.")
    if sensitive:
        return GovernanceAssessment(RiskLevel.MEDIUM, True, "Sensitive evidence requires review before release.")
    return GovernanceAssessment(RiskLevel.LOW, False, "Autonomous research may continue.")
