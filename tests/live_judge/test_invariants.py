"""Real isolated backend invariants. No network or default demo DB."""
import pytest
from scripts.live_judge.run import run_one


@pytest.mark.parametrize("number", [n for n in range(1, 40) if n not in {8, 28, 37}])
def test_offline_invariant(number):
    result = run_one(f"JUDGE-{number:03d}")
    assert result["outcome"] in {"PASS", "SAFE_REJECTION", "SAFE_FALLBACK", "MANUAL_REQUIRED"}, result


@pytest.mark.parametrize("number", range(40, 47))
def test_pending_is_never_pass(number):
    result = run_one(f"JUDGE-{number:03d}")
    assert result["outcome"] == "NOT_RUN"
    assert result["details"]["status"] == "PENDING"
