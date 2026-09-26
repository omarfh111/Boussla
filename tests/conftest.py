"""Hermetic test environment for every lane's tests.

Each test runs as if there were no local ``.env``: provider keys are set to
empty strings (python-dotenv never overrides an existing variable), providers
and tracing are off, and all runtime paths point into the test's tmp dir so no
test writes to the real ``runtime/`` or calls a live API. Tests that need a
provider opt in explicitly with ``monkeypatch.setenv``.
"""
import pytest

from boussla.config import get_settings

KEYS = ("OPENAI_API_KEY", "TYPESAFE_API_KEY", "LANGSMITH_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")


@pytest.fixture(autouse=True)
def hermetic_env(tmp_path_factory, monkeypatch):
    runtime = tmp_path_factory.mktemp("runtime")
    for key in KEYS:
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("LLM_PROVIDER", "manual")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("JEV_ENABLED", "false")
    monkeypatch.delenv("BOUSSLA_SERVICE", raising=False)
    for key, name in (("CASE_DB_PATH", "cases.sqlite"), ("CHECKPOINT_DB_PATH", "checkpoints.sqlite"),
                      ("UPLOAD_DIR", "uploads"), ("EVENT_LOG_PATH", "events.jsonl")):
        monkeypatch.setenv(key, str(runtime / name))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
