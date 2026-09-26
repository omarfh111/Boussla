"""Runtime settings — lane A. Secrets stay server-side and are never logged.

Values come from the environment, optionally loaded from a local, git-ignored
``.env`` (see ``.env.example``). ``Settings`` deliberately has no ``__repr__``
that could print keys; use ``describe()`` for a redacted summary.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_ROOT = REPO_ROOT / "docs" / "build_lock" / "fixtures"


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    return default if raw is None else raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return default if raw in (None, "") else int(raw)


def use_os_trust_store() -> None:
    """Verify TLS against the OS certificate store (needed behind TLS-inspecting AV/proxies).

    Opt out with ``BOUSSLA_OS_TRUSTSTORE=false``. Never disables verification.
    """
    if not _flag("BOUSSLA_OS_TRUSTSTORE", True):
        return
    try:
        import truststore
    except ImportError:
        return
    truststore.inject_into_ssl()


@dataclass(frozen=True, repr=False)
class Settings:
    app_mode: str = "local_synthetic_demo"
    case_db_path: Path = REPO_ROOT / "runtime" / "cases.sqlite"
    checkpoint_db_path: Path = REPO_ROOT / "runtime" / "checkpoints.sqlite"
    upload_dir: Path = REPO_ROOT / "runtime" / "uploads"
    event_log_path: Path = REPO_ROOT / "runtime" / "events.jsonl"
    llm_provider: str = "manual"
    openai_chat_model: str | None = None
    general_model_timeout_seconds: int = 30
    jev_enabled: bool = False
    jev_model: str = "jev-1.13.0"
    langsmith_tracing: bool = False
    langsmith_project: str = "boussla-synthetic-demo"
    max_upload_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 5
    max_question_rounds: int = 2
    portfolio_enabled: bool = True
    """Load lane B's 12-enterprise synthetic portfolio into the case store at startup."""
    portfolio_state_path: Path = REPO_ROOT / "runtime" / "portfolio.json"
    _secrets: dict[str, str] = field(default_factory=dict, compare=False)

    def secret(self, name: str) -> str | None:
        return self._secrets.get(name) or None

    def describe(self) -> dict[str, str]:
        """Redacted summary safe for logs/diagnostics."""
        return {
            "app_mode": self.app_mode,
            "llm_provider": self.llm_provider,
            "openai_chat_model": self.openai_chat_model or "",
            "openai_key": "set" if self.secret("OPENAI_API_KEY") else "missing",
            "jev_enabled": str(self.jev_enabled),
            "typesafe_key": "set" if self.secret("TYPESAFE_API_KEY") else "missing",
            "langsmith_tracing": str(self.langsmith_tracing),
            "langsmith_key": "set" if self.secret("LANGSMITH_API_KEY") else "missing",
        }

    def __repr__(self) -> str:  # never expose secrets
        return f"Settings({self.describe()})"


def _resolve(path: str | None, default: Path) -> Path:
    if not path:
        return default
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    try:
        from dotenv import load_dotenv
        load_dotenv(REPO_ROOT / ".env", override=False)
    except ImportError:
        pass
    # LangSmith must hide raw inputs/outputs before any client is created.
    os.environ.setdefault("LANGSMITH_HIDE_INPUTS", "true")
    os.environ.setdefault("LANGSMITH_HIDE_OUTPUTS", "true")
    secrets = {k: os.environ.get(k, "") for k in ("OPENAI_API_KEY", "LANGSMITH_API_KEY", "TYPESAFE_API_KEY")}
    has_openai = bool(secrets["OPENAI_API_KEY"])
    return Settings(
        app_mode=os.environ.get("APP_MODE", "local_synthetic_demo"),
        case_db_path=_resolve(os.environ.get("CASE_DB_PATH"), REPO_ROOT / "runtime" / "cases.sqlite"),
        checkpoint_db_path=_resolve(os.environ.get("CHECKPOINT_DB_PATH"), REPO_ROOT / "runtime" / "checkpoints.sqlite"),
        upload_dir=_resolve(os.environ.get("UPLOAD_DIR"), REPO_ROOT / "runtime" / "uploads"),
        event_log_path=_resolve(os.environ.get("EVENT_LOG_PATH"), REPO_ROOT / "runtime" / "events.jsonl"),
        llm_provider=os.environ.get("LLM_PROVIDER") or ("openai" if has_openai else "manual"),
        openai_chat_model=os.environ.get("OPENAI_CHAT_MODEL") or None,
        general_model_timeout_seconds=_int("GENERAL_MODEL_TIMEOUT_SECONDS", 30),
        # Jev routing runs when a TypeSafe key is set, unless JEV_ENABLED=false.
        jev_enabled=_flag("JEV_ENABLED", True) and bool(secrets["TYPESAFE_API_KEY"]),
        jev_model=os.environ.get("JEV_MODEL") or "jev-1.13.0",
        langsmith_tracing=_flag("LANGSMITH_TRACING", False) and bool(secrets["LANGSMITH_API_KEY"]),
        langsmith_project=os.environ.get("LANGSMITH_PROJECT", "boussla-synthetic-demo"),
        max_upload_bytes=_int("MAX_UPLOAD_BYTES", 10 * 1024 * 1024),
        max_pdf_pages=_int("MAX_PDF_PAGES", 5),
        max_question_rounds=_int("MAX_QUESTION_ROUNDS", 2),
        portfolio_enabled=_flag("BOUSSLA_PORTFOLIO", True),
        portfolio_state_path=_resolve(os.environ.get("PORTFOLIO_STATE_PATH"),
                                      _resolve(os.environ.get("CASE_DB_PATH"), REPO_ROOT / "runtime" / "cases.sqlite")
                                      .parent / "portfolio.json"),
        _secrets=secrets,
    )
