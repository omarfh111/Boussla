from datetime import date

import pytest

from boussla.contracts import Audience
from boussla.retrieval.corpus import load_public_references, public_reference_retriever


def test_reviewed_official_corpus_has_inspected_provenance():
    records = load_public_references()

    assert 5 <= len(records) <= 15
    assert len({record.rule_id for record in records}) == len(records)
    assert all(record.source_url.startswith("https://www.finances.gov.tn/") for record in records)
    assert all(record.source_hash == "9fbdad1650772ef219382159665ab51c286c15fab60ed3a16d681d5cb350885e" for record in records)
    assert all(record.jurisdiction == "TN" and record.language == "fr" for record in records)
    assert all(record.review_status == "REVIEWED" for record in records)
    assert all(record.source_date is None and record.effective_from is None for record in records)


def test_public_corpus_is_officer_candidate_only_until_effective_dates_are_verified():
    retriever = public_reference_retriever()

    officer = retriever.search("facture taxe", as_of=date(2026, 9, 26), jurisdiction="TN", audience=Audience.OFFICER)
    company = retriever.search("facture taxe", as_of=date(2026, 9, 26), jurisdiction="TN", audience=Audience.COMPANY)

    assert officer and all(item.review_status == "REVIEWED" for item in officer)
    assert company == []


def test_missing_and_empty_corpus_return_no_passages(tmp_path):
    missing = public_reference_retriever(tmp_path / "missing.json")
    empty_path = tmp_path / "empty.json"
    empty_path.write_text("[]", encoding="utf-8")
    empty = public_reference_retriever(empty_path)

    assert missing.status == empty.status == "NOT_SUPPLIED"
    assert missing.search("facture", as_of=date(2026, 1, 1), jurisdiction="TN", audience=Audience.OFFICER) == []
    assert empty.search("facture", as_of=date(2026, 1, 1), jurisdiction="TN", audience=Audience.OFFICER) == []


def test_loader_rejects_unofficial_or_incomplete_record(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('[{"rule_id":"x","source_url":"https://blog.invalid/law"}]', encoding="utf-8")

    with pytest.raises(ValueError):
        load_public_references(path)
