from datetime import datetime, timezone
import pytest
from boussla.contracts import BousslaError, Question, Finding, FindingStatus, FindingFamily, EvidenceRef, ClarificationRequest, RequestStatus, RequestView, Mode
from boussla.questionnaire import validate_answers
from boussla.playbook import deterministic_plan, scoped_questions, fully_asked_questions


@pytest.mark.parametrize("kind,value,valid",[("NUMBER","12.5",True),("NUMBER","NaN",False),
    ("NUMBER","-1",False),("DATE","2026-09-28",True),("DATE","2026-02-30",False),
    ("CHOICE","A",True),("CHOICE","C",False)])
def test_typed_answers_are_validated_server_side(kind,value,valid):
    question = Question(question_id="Q",text_fr="Test",answer_kind=kind,choices=("A","B"))
    if valid:
        validate_answers([question],{"Q":value})
    else:
        with pytest.raises(BousslaError):
            validate_answers([question],{"Q":value})


def findings():
    return [Finding(finding_id=f"F-{tx}",case_id="C",company_id="CO",transaction_id=tx,
        family=FindingFamily.QUANTITY,status=FindingStatus.UNRESOLVED,severity="1",
        evidence_refs=(EvidenceRef(document_id=f"D-{tx}"),),calculation_version="TEST",case_version=1)
        for tx in ("TX-001","TX-002")]


def test_questions_target_one_transaction_then_the_next_without_spamming():
    causes = findings()
    questions = scoped_questions(["Q-PROJECT-ALLOCATION"],causes)
    assert questions[0].related_fact_ids == ("TX-001",)
    request = RequestView(request=ClarificationRequest(request_id="R",case_id="C",company_id="CO",case_version=1,
        question_ids=("Q-PROJECT-ALLOCATION",),status=RequestStatus.RESPONDED),questions=questions,text_fr="Test",mode=Mode.TEMPLATE)
    assert "Q-PROJECT-ALLOCATION" not in fully_asked_questions(causes,[request])
    second = scoped_questions(["Q-PROJECT-ALLOCATION"],causes,[request])
    assert second[0].related_fact_ids == ("TX-002",)


def test_an_explained_transaction_cannot_hide_an_unresolved_same_family():
    causes = findings()
    causes[1] = causes[1].model_copy(update={"status":FindingStatus.EXPLAINED})
    assert "Q-PROJECT-ALLOCATION" in deterministic_plan(causes,True,set())


def test_question_transaction_scope_prevents_cross_cause_reduction():
    from boussla.contracts import ClarificationResponse
    from boussla.review_evidence import derive_progress_evidence
    causes = findings()
    request = RequestView(request=ClarificationRequest(request_id="R",case_id="C",company_id="CO",case_version=1,
        fact_ids=("D-TX-001","D-TX-002"),question_ids=("Q-PROJECT-ALLOCATION",),status=RequestStatus.RESPONDED),
        questions=scoped_questions(["Q-PROJECT-ALLOCATION"],causes),text_fr="Test",mode=Mode.TEMPLATE)
    response = ClarificationResponse(response_id="RESP",request_id="R",author_actor_id="CO",answers={"Q-PROJECT-ALLOCATION":"Explication"},submitted_at=datetime.now(timezone.utc))
    evidence = derive_progress_evidence(tuple(causes),{"request":[request],"response":[response]},None)
    assert len(evidence) == 1 and evidence[0].transaction_id == "TX-001"
