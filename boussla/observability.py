"""Redacted observability — lane A.

- Local JSONL node records (``runtime/events.jsonl``) are the authoritative
  run trace; the case store's events table is the authoritative case history.
- LangSmith is optional (``LANGSMITH_TRACING=true`` + key). Inputs/outputs are
  hidden (``LANGSMITH_HIDE_INPUTS/OUTPUTS=true`` set before any client) and only
  WHITELISTED metadata is attached: no raw documents, names, tax IDs, amounts,
  free text, credentials or exception messages.
- Tracing failure is non-fatal. Exceptions raised by the traced code itself are
  always re-raised unchanged (including LangGraph interrupts).

Traceability aid, not tamper-proof legal evidence.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from boussla.config import get_settings

ALLOWED_KEYS = frozenset({
    "node", "mode", "status", "duration_ms", "case_ref", "case_version", "audience", "error_code",
    "error_type", "model_id", "prompt_version", "question_count", "finding_count", "round",
    "input_tokens", "output_tokens", "checks_version",
})
_lock = threading.Lock()


def case_ref(case_id: str) -> str:
    """Opaque, stable reference so traces never carry the case identifier itself."""
    return hashlib.sha256(f"boussla:{case_id}".encode()).hexdigest()[:12]


def redact(metadata: dict) -> dict:
    out = {}
    for key, value in metadata.items():
        if key not in ALLOWED_KEYS:
            continue
        if isinstance(value, (bool, int, float)) or value is None:
            out[key] = value
        else:
            out[key] = str(value)[:80]
    return out


def _write_local(record: dict, path: Path) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with _lock, path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass  # local trace failure must not block the case


@contextmanager
def _langsmith_span(name: str, metadata: dict) -> Iterator[None]:
    """Optional LangSmith span with empty inputs and whitelisted metadata only.
    On failure the trace receives the exception TYPE only, never its message."""
    settings = get_settings()
    span = None
    if settings.langsmith_tracing:
        try:
            from langsmith import trace
            span = trace(name=name, run_type="chain", inputs={}, metadata=metadata,
                         project_name=settings.langsmith_project)
            span.__enter__()
        except Exception:  # noqa: BLE001 - tracing unavailable: continue untraced
            span = None
    failure: BaseException | None = None
    try:
        yield
    except BaseException as exc:
        failure = exc
        raise
    finally:
        if span is not None:
            try:
                if failure is None:
                    span.__exit__(None, None, None)
                else:
                    safe = RuntimeError(type(failure).__name__)
                    span.__exit__(RuntimeError, safe, None)
            except Exception:  # noqa: BLE001 - trace outage never blocks the case
                pass


@contextmanager
def traced(node: str, case_id: str | None = None, **metadata) -> Iterator[dict]:
    """Trace one bounded node. Yields a dict the node may update with whitelisted
    result metadata (e.g. ``mode``, ``question_count``)."""
    settings = get_settings()
    extra: dict = {}
    base = {"node": node, **({"case_ref": case_ref(case_id)} if case_id else {}), **metadata}
    start = time.perf_counter()
    status = "OK"
    try:
        with _langsmith_span(f"boussla.{node}", redact(base)):
            yield extra
    except BaseException as exc:
        status = "INTERRUPT" if type(exc).__name__ == "GraphInterrupt" else "ERROR"
        extra.setdefault("error_type", type(exc).__name__)
        code = getattr(exc, "code", None)
        if code is not None:
            extra.setdefault("error_code", getattr(code, "value", str(code)))
        raise
    finally:
        record = redact({**base, **extra, "status": status,
                         "duration_ms": round((time.perf_counter() - start) * 1000, 1)})
        record["at"] = datetime.now(timezone.utc).isoformat()
        _write_local(record, settings.event_log_path)
