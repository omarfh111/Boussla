"""Small, officer-only investigation DTOs; no canonical case objects or writes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re

from boussla.contracts import ClarificationStatus, FindingFamily, FindingStatus, Mode


_CODE = re.compile(r"^(?!.*\d{5,})[A-Z][A-Z0-9_-]{0,63}$")


def _codes(values: tuple[str, ...]) -> None:
    if len(values) > 30 or any(not isinstance(v, str) or not _CODE.fullmatch(v) for v in values):
        raise ValueError("expected bounded opaque codes, not free text")


class ObservationKind(str, Enum):
    FACT = "FACT"
    DECLARATION = "DECLARATION"
    MODEL_INTERPRETATION = "MODEL_INTERPRETATION"
    HYPOTHESIS = "HYPOTHESIS"
    HYPOTHETICAL_SCENARIO = "HYPOTHETICAL_SCENARIO"


class HypothesisSupport(str, Enum):
    SUPPORTED = "SUPPORTED"
    PLAUSIBLE = "PLAUSIBLE"
    WEAK = "WEAK"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True)
class FindingDigest:
    family: FindingFamily
    reason_code: str
    status: FindingStatus
    evidence_refs: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    coverage_code: str = "UNKNOWN"

    def __post_init__(self) -> None:
        _codes((self.reason_code, *self.evidence_refs, *self.missing_evidence,
                self.coverage_code))


@dataclass(frozen=True)
class ContextDigest:
    declared_purpose_code: str = "UNKNOWN"
    declared_horizon_code: str = "UNKNOWN"
    interpreted_horizon_code: str = "UNKNOWN"
    consistency_code: str = "INSUFFICIENT"
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _codes((self.declared_purpose_code, self.declared_horizon_code,
                self.interpreted_horizon_code, self.consistency_code, *self.reason_codes))


@dataclass(frozen=True)
class EvidenceFeature:
    hypothesis_id: str
    supporting_refs: tuple[str, ...] = ()
    contradicting_refs: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _codes((self.hypothesis_id, *self.supporting_refs, *self.contradicting_refs,
                *self.missing_evidence))


@dataclass(frozen=True)
class ClarificationDigest:
    status: ClarificationStatus = ClarificationStatus.NOT_REQUESTED
    answered_question_ids: tuple[str, ...] = ()
    answer_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _codes((*self.answered_question_ids, *self.answer_codes))


@dataclass(frozen=True)
class ScenarioDigest:
    scenario_code: str
    outcome_code: str
    hypothetical_review_index: int | None = None

    def __post_init__(self) -> None:
        _codes((self.scenario_code, self.outcome_code))
        if self.hypothetical_review_index is not None and not 0 <= self.hypothetical_review_index <= 100:
            raise ValueError("scenario index must be supplied by deterministic code")


@dataclass(frozen=True)
class InvestigatorInput:
    findings: tuple[FindingDigest, ...] = ()
    evidence_features: tuple[EvidenceFeature, ...] = ()
    context: ContextDigest | None = None
    history_signal_codes: tuple[str, ...] = ()
    transaction_summary_codes: tuple[str, ...] = ()
    clarification: ClarificationDigest = ClarificationDigest()
    reference_rule_ids: tuple[str, ...] = ()
    scenarios: tuple[ScenarioDigest, ...] = ()

    def __post_init__(self) -> None:
        if (len(self.findings) > 12 or len(self.evidence_features) > 10
                or len(self.scenarios) > 5):
            raise ValueError("investigation input exceeds bounds")
        _codes((*self.history_signal_codes, *self.transaction_summary_codes,
                *self.reference_rule_ids))
        from boussla.investigator.catalogue import HYPOTHESIS_CATALOGUE
        if any(f.hypothesis_id not in HYPOTHESIS_CATALOGUE for f in self.evidence_features):
            raise ValueError("unknown hypothesis feature")
        known_refs = {ref for finding in self.findings for ref in finding.evidence_refs}
        if any(ref not in known_refs for feature in self.evidence_features
               for ref in (*feature.supporting_refs, *feature.contradicting_refs)):
            raise ValueError("hypothesis cites evidence outside the scoped findings")


@dataclass(frozen=True)
class Observation:
    kind: ObservationKind
    text_fr: str
    source_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class InvestigatorHypothesis:
    hypothesis_id: str
    status: HypothesisSupport
    supporting_refs: tuple[str, ...]
    contradicting_refs: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    why_it_matters_fr: str


@dataclass(frozen=True)
class InvestigatorBrief:
    summary_fr: str
    key_observations: tuple[Observation, ...]
    top_hypotheses: tuple[InvestigatorHypothesis, ...]
    missing_information: tuple[str, ...]
    suggested_question_ids: tuple[str, ...]
    what_changed_since_previous_revision: tuple[str, ...]
    reference_rule_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    mode: Mode


@dataclass(frozen=True)
class InvestigatorResult:
    brief: InvestigatorBrief | None
    mode: Mode
