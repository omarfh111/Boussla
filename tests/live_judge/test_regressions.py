"""RED_UNRESOLVED: these deliberately fail until owners repair production.

Do not merge as an allegedly green suite. No xfail hides these defects.
"""
import pytest
from scripts.live_judge.run import run_one


@pytest.mark.parametrize("scenario", ["JUDGE-008", "JUDGE-028", "JUDGE-037", "JUDGE-054"])
def test_reported_regression(scenario):
    result = run_one(scenario)
    assert result["outcome"] != "NOT_RUN", result["details"]
    assert not result["failures"], result["failures"]
