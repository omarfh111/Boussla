import pytest

from boussla.contracts import Actor, BousslaError, ErrorCode, Role
from boussla.security import POLICY, ActorRegistry, authorize

CASE = "CASE-BRICKS-001"


@pytest.fixture
def reg():
    return ActorRegistry.demo()


def err(fn):
    with pytest.raises(BousslaError) as e:
        fn()
    return e.value.code


def test_company_reads_own_case(reg):
    a = Actor(actor_id="DEMO-COMPANY-BAT", role=Role.COMPANY, company_id="DEMO-BAT")
    assert authorize(reg, a, "get_case", "DEMO-BAT", CASE).actor_id == a.actor_id


def test_wrong_company_forbidden(reg):
    a = Actor(actor_id="DEMO-COMPANY-OTHER", role=Role.COMPANY, company_id="DEMO-OTHER")
    assert err(lambda: authorize(reg, a, "get_case", "DEMO-BAT", CASE)) is ErrorCode.CROSS_COMPANY


def test_forged_role_or_company_rejected(reg):
    forged_role = Actor(actor_id="DEMO-COMPANY-BAT", role=Role.OFFICER, assigned_case_ids=(CASE,))
    forged_co = Actor(actor_id="DEMO-COMPANY-OTHER", role=Role.COMPANY, company_id="DEMO-BAT")
    unknown = Actor(actor_id="X", role=Role.OFFICER)
    for a in (forged_role, forged_co, unknown):
        assert err(lambda: authorize(reg, a, "get_case", "DEMO-BAT", CASE)) is ErrorCode.FORBIDDEN


def test_forged_assignment_ignored(reg):
    a = Actor(actor_id="DEMO-OFFICER", role=Role.OFFICER, assigned_case_ids=("CASE-OTHER",))
    assert err(lambda: authorize(reg, a, "get_case", "DEMO-OTHER", "CASE-OTHER")) is ErrorCode.FORBIDDEN


def test_company_cannot_approve_own_evidence(reg):
    a = reg.actors["DEMO-COMPANY-BAT"]
    for action in ("accept_evidence", "reject_evidence", "publish_clarification", "list_queue", "export_dossier"):
        assert err(lambda: authorize(reg, a, action, "DEMO-BAT", CASE)) is ErrorCode.FORBIDDEN


def test_unknown_action_denied(reg):
    assert err(lambda: authorize(reg, reg.actors["DEMO-OFFICER"], "drop_tables")) is ErrorCode.FORBIDDEN


def test_policy_covers_every_service_method():
    from boussla.contracts import BousslaService
    methods = {m for m in dir(BousslaService) if not m.startswith("_")}
    assert methods <= set(POLICY)
