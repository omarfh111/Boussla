"""Upload idempotency and same-content duplicate behavior, using synthetic PDFs."""

import pytest

from boussla.config import FIXTURE_ROOT
from boussla.contracts import BousslaError, ErrorCode
from boussla.services import build_service


def test_identical_upload_replays_same_key_but_rejects_new_action():
    svc = build_service()
    actor = svc.registry.actors["DEMO-COMPANY-BAT"]
    case_id = "CASE-BRICKS-001"
    pdf = (FIXTURE_ROOT / "documents" / "06_second_project_allocation.pdf").read_bytes()
    version = svc.store.case_meta(case_id)["version"]

    first = svc.upload_document(actor, case_id, pdf, "synthetic.pdf", "application/pdf", version, "upload-one")
    replay = svc.upload_document(actor, case_id, pdf, "synthetic.pdf", "application/pdf", version, "upload-one")

    assert replay == first
    assert svc.store.case_meta(case_id)["version"] == version + 1
    with pytest.raises(BousslaError) as error:
        svc.upload_document(actor, case_id, pdf, "synthetic.pdf", "application/pdf", version + 1, "upload-two")
    assert error.value.code is ErrorCode.INVALID_STATE
    assert svc.store.case_meta(case_id)["version"] == version + 1
