"""Live synthetic Cloud + configured general-model smoke; identifiers only."""

from __future__ import annotations

from datetime import date
from time import perf_counter
from types import SimpleNamespace

from boussla.contracts import Audience, FindingFamily, Mode
from boussla.retrieval.grounded_rag import public_reference_assistant


def main() -> None:
    reason = "INVOICE_FIELDS_UNCONFIRMED"
    assistant = public_reference_assistant()
    finding = SimpleNamespace(family=FindingFamily.COUNTERPARTY, reason_code=reason)
    start = perf_counter()
    result = assistant.for_findings((finding,), as_of=date(2026, 9, 26), audience=Audience.OFFICER)
    latency_ms = round((perf_counter() - start) * 1000)
    print("finding_reason", reason)
    print("retrieved_rule_ids", ",".join(p.rule_id for p in result.candidate_passages))
    print("cited_rule_ids", ",".join(result.cited_rule_ids))
    print("retrieval_mode", result.retrieval_backend, result.retrieval_mode.value)
    print("provider_mode", result.generation_mode.value)
    print("latency_ms", latency_ms)
    if result.retrieval_mode is not Mode.LIVE or result.grounded_note is None:
        raise SystemExit("live bounded RAG smoke incomplete")


if __name__ == "__main__":
    main()
