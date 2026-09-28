"""Server-side answer validation for controlled question schemas."""
from datetime import date
from decimal import Decimal, InvalidOperation
from boussla.contracts import BousslaError, ErrorCode


def validate_answers(questions, answers):
    by_id = {q.question_id:q for q in questions}
    if not set(answers) <= set(by_id):
        raise BousslaError(ErrorCode.INVALID_EVIDENCE_REFERENCE,"Réponse à une question non posée")
    for key,value in answers.items():
        if not isinstance(value,str) or len(value)>2000:
            raise BousslaError(ErrorCode.INVALID_INPUT,"Format de réponse invalide",fields=[key])
        value = value.strip()
        if not value:
            continue
        question = by_id[key]
        valid = True
        if question.answer_kind == "CHOICE":
            valid = value in question.choices
        elif question.answer_kind == "NUMBER":
            try:
                number = Decimal(value)
                valid = number.is_finite() and number >= 0
            except InvalidOperation:
                valid = False
        elif question.answer_kind == "DATE":
            try:
                valid = date.fromisoformat(value).isoformat() == value
            except ValueError:
                valid = False
        if not valid:
            raise BousslaError(ErrorCode.INVALID_INPUT,"Réponse incompatible avec le type demandé",fields=[key])
