import json

import pytest

from boussla import observability
from boussla.config import Settings
from boussla.contracts import BousslaError, ErrorCode


@pytest.fixture
def log(tmp_path, monkeypatch):
    path = tmp_path / "events.jsonl"
    monkeypatch.setattr(observability, "get_settings", lambda: Settings(event_log_path=path))
    return path


def records(path):
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]


def test_redaction_whitelist_only():
    red = observability.redact({"node": "checks", "purpose_text": "secret", "synthetic_mf": "DEMO-MF-BAT",
                                "amount": 4760000, "api_key": "sk-x", "mode": "LIVE"})
    assert red == {"node": "checks", "mode": "LIVE"}


def test_trace_excludes_raw_identifiers(log):
    with observability.traced("planner", case_id="CASE-BRICKS-001", purpose_text="Brique", model_id="m") as meta:
        meta["question_count"] = 2
        meta["raw_doc"] = "FAC-DEMO-001 DEMO-MF-BAT"
    text = log.read_text(encoding="utf-8")
    assert "CASE-BRICKS-001" not in text and "FAC-DEMO" not in text and "Brique" not in text
    rec = records(log)[0]
    assert rec["status"] == "OK" and rec["question_count"] == 2 and rec["case_ref"] == observability.case_ref("CASE-BRICKS-001")


def test_errors_reraised_with_sanitized_code(log):
    with pytest.raises(BousslaError):
        with observability.traced("accept", case_id="C"):
            raise BousslaError(ErrorCode.STALE_REVISION, "Le dossier DEMO-MF-BAT a changé")
    rec = records(log)[0]
    assert rec["status"] == "ERROR" and rec["error_code"] == "STALE_REVISION" and "DEMO-MF" not in json.dumps(rec)


def test_local_log_failure_is_nonfatal(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setattr(observability, "get_settings", lambda: Settings(event_log_path=blocker / "sub" / "e.jsonl"))
    with observability.traced("checks"):
        pass  # must not raise
