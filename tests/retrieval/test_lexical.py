from datetime import date

from boussla.contracts import Audience, Mode
from boussla.retrieval.lexical import LexicalReferenceRetriever, ReferenceRecord


def record(*, rule_id="TEST-R1", jurisdiction="TN", review_status="REVIEWED", effective_from=date(2025, 1, 1)):
    return ReferenceRecord(
        rule_id=rule_id,
        source_url="https://example.invalid/official-test-source",
        source_hash="a" * 64,
        document_title="TEST ONLY: synthetic reference",
        source_date=date(2025, 1, 1),
        page=2,
        article="TEST-1",
        language="fr",
        jurisdiction=jurisdiction,
        effective_from=effective_from,
        effective_to=None,
        review_status=review_status,
        text="Affectation des briques au projet indiqué.",
    )


def test_no_supplied_corpus_returns_explicit_not_supplied():
    retriever = LexicalReferenceRetriever(())

    assert retriever.status == "NOT_SUPPLIED"
    assert retriever.backend_mode == "LEXICAL"
    assert retriever.search("briques", as_of=date(2026, 1, 1), jurisdiction="TN", audience=Audience.OFFICER) == []


def test_scoped_lexical_search_returns_candidate_only():
    retriever = LexicalReferenceRetriever((record(),))

    results = retriever.search("briques projet", as_of=date(2026, 1, 1), jurisdiction="TN", audience=Audience.COMPANY)

    assert [item.rule_id for item in results] == ["TEST-R1"]
    assert results[0].mode is Mode.TEMPLATE
    assert results[0].review_status == "REVIEWED"


def test_wrong_jurisdiction_future_and_unreviewed_are_filtered_for_company():
    retriever = LexicalReferenceRetriever((
        record(rule_id="OTHER", jurisdiction="FR"),
        record(rule_id="FUTURE", effective_from=date(2027, 1, 1)),
        record(rule_id="UNREVIEWED", review_status="UNREVIEWED"),
    ))

    company = retriever.search("briques", as_of=date(2026, 1, 1), jurisdiction="TN", audience=Audience.COMPANY)
    officer = retriever.search("briques", as_of=date(2026, 1, 1), jurisdiction="TN", audience=Audience.OFFICER)

    assert company == []
    assert [item.rule_id for item in officer] == ["UNREVIEWED"]


def test_company_audience_string_cannot_bypass_review_filter():
    retriever = LexicalReferenceRetriever((record(review_status="UNREVIEWED"),))

    assert retriever.search("briques", as_of=date(2026, 1, 1), jurisdiction="TN", audience="COMPANY") == []
