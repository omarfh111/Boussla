"""Narrow side-effect-free context consistency API for later Lane A wiring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

from boussla.adapters.model_extraction import DEFAULT_MODEL
from boussla.config import get_settings
from boussla.contracts import Mode
from boussla.context.consistency import ContextConsistencyResult, ContextReasonCode, evaluate_consistency
from boussla.context.duration import DEMO_SHORT_HORIZON_MAX_DAYS
from boussla.context.interpreter import OpenAIContextInterpreter
from boussla.context.models import ContextInput, ContextInterpretation, HorizonBucket
from boussla.context.questions import recommend_question_ids


class ContextInterpreter(Protocol):
    def interpret(self, context: ContextInput) -> ContextInterpretation: ...


@dataclass(frozen=True)
class ContextAssessment:
    interpretation: ContextInterpretation
    consistency: ContextConsistencyResult
    recommended_question_ids: tuple[str, ...]
    mode: Mode

    @property
    def duration_days(self) -> int | None:
        return self.consistency.duration_days

    @property
    def calculated_horizon(self) -> HorizonBucket:
        return self.consistency.calculated_horizon

    @property
    def reason_codes(self) -> tuple[ContextReasonCode, ...]:
        return self.consistency.reason_codes


class ContextConsistencyAssistant:
    def __init__(
        self, interpreter: ContextInterpreter, *, short_max_days: int = DEMO_SHORT_HORIZON_MAX_DAYS,
    ) -> None:
        self.interpreter = interpreter
        self.short_max_days = short_max_days

    def assess(
        self, context: ContextInput, *, answered_question_ids: Iterable[str] = (),
    ) -> ContextAssessment:
        interpretation = self.interpreter.interpret(context)
        consistency = evaluate_consistency(
            context, interpretation, short_max_days=self.short_max_days,
        )
        return ContextAssessment(
            interpretation=interpretation, consistency=consistency,
            recommended_question_ids=recommend_question_ids(
                consistency.reason_codes, answered_ids=answered_question_ids,
            ),
            mode=interpretation.mode,
        )


def context_consistency_assistant() -> ContextConsistencyAssistant:
    settings = get_settings()
    key = settings.secret("OPENAI_API_KEY") if settings.llm_provider == "openai" else None
    interpreter = OpenAIContextInterpreter(
        api_key=key, model=settings.openai_chat_model or DEFAULT_MODEL,
        timeout=settings.general_model_timeout_seconds,
    )
    return ContextConsistencyAssistant(interpreter)
