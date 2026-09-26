"""Hermetic test environment for every lane's tests.

Each test runs as if there were no local ``.env``: provider keys are set to
empty strings (python-dotenv never overrides an existing variable), providers
and tracing are off, and all runtime paths point into the test's tmp dir so no
test writes to the real ``runtime/`` or calls a live API. Tests that need a
provider opt in explicitly with ``monkeypatch.setenv``.
"""
import pytest

from boussla.config import get_settings

CLOSED_ENDPOINT = "http://127.0.0.1:9/provider-disabled-in-tests"
KEYS = ("OPENAI_API_KEY", "TYPESAFE_API_KEY", "LANGSMITH_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY",
        "QDRANT_URL", "QDRANT_API_KEY")


@pytest.fixture(autouse=True)
def hermetic_env(tmp_path_factory, monkeypatch):
    runtime = tmp_path_factory.mktemp("runtime")
    for key in KEYS:
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("LLM_PROVIDER", "manual")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("JEV_ENABLED", "false")
    # The 12-enterprise portfolio is opt-in per test (it changes queue contents).
    monkeypatch.setenv("BOUSSLA_PORTFOLIO", "false")
    monkeypatch.delenv("BOUSSLA_SERVICE", raising=False)
    for key, name in (("CASE_DB_PATH", "cases.sqlite"), ("CHECKPOINT_DB_PATH", "checkpoints.sqlite"),
                      ("UPLOAD_DIR", "uploads"), ("EVENT_LOG_PATH", "events.jsonl")):
        monkeypatch.setenv(key, str(runtime / name))
    # Hard-coded provider endpoints ignore OPENAI_BASE_URL; point them at a closed local
    # port so a test that opts into a (fake) key can never reach a real provider.
    # (Jev needs TYPESAFE_API_KEY and JEV_ENABLED, both disabled above; its tests assert its URL.)
    for module in ("boussla.adapters.model_extraction", "boussla.context.interpreter",
                   "boussla.retrieval.grounded_rag", "boussla.investigator.selector"):
        try:
            monkeypatch.setattr(f"{module}.ENDPOINT", CLOSED_ENDPOINT)
        except (ImportError, AttributeError):
            pass
    get_settings.cache_clear()
    _clear_reference_cache()
    yield
    get_settings.cache_clear()
    _clear_reference_cache()


def _clear_reference_cache():
    """The public-reference retriever is cached per process; tests must not share it."""
    try:
        from boussla.retrieval.corpus import _cached_retriever
    except ImportError:
        return
    _cached_retriever.cache_clear()
