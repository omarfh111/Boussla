"""Tests for the append-only SQLite case store."""
import threading

import pytest

from boussla.contracts import ActionReceipt, BousslaError, ErrorCode, Question
from boussla.store import CaseStore

CASE = "CASE-T"


def q(qid, text):
    return Question(question_id=qid, text_fr=text)


@pytest.fixture
def store(tmp_path):
    s = CaseStore(tmp_path / "cases.sqlite", tmp_path / "uploads")
    with s.write(CASE) as tx:
        tx.create_case("CO-1", "seed")
        tx.put("question", "Q1", q("Q1", "v1"))
        tx.commit_version("seed")
    return s


def test_seed_is_version_one(store):
    assert store.case_meta(CASE) == {"case_id": CASE, "company_id": "CO-1", "version": 1}
    assert [x.text_fr for x in store.facts(CASE, "question", Question)] == ["v1"]


def test_supersede_retire_and_as_of_reads(store):
    with store.write(CASE) as tx:
        tx.require_version(1)
        tx.put("question", "Q1", q("Q1", "v2"))
        tx.put("question", "Q2", q("Q2", "new"))
        tx.commit_version("edit")
    with store.write(CASE) as tx:
        tx.retire("question", "Q2")
        tx.commit_version("retire")
    assert [x.text_fr for x in store.facts(CASE, "question", Question)] == ["v2"]
    assert [x.text_fr for x in store.facts(CASE, "question", Question, version=2)] == ["v2", "new"]
    assert [x.text_fr for x in store.facts(CASE, "question", Question, version=1)] == ["v1"]
    revs = store.revisions(CASE)
    assert [r.version for r in revs] == [1, 2, 3] and revs[2].parent_version == 2
    assert len({r.fact_hash for r in revs}) == 3


def test_error_rolls_back_everything(store):
    with pytest.raises(RuntimeError):
        with store.write(CASE) as tx:
            tx.put("question", "Q1", q("Q1", "bad"))
            tx.event("X", "A", "should vanish")
            tx.commit_version("bad")
            raise RuntimeError("boom")
    assert store.case_meta(CASE)["version"] == 1
    assert store.facts(CASE, "question", Question)[0].text_fr == "v1"
    assert store.events(CASE) == []
    assert store.audit_records(CASE) == []


def test_stale_version_rejected(store):
    with pytest.raises(BousslaError) as e:
        with store.write(CASE) as tx:
            tx.require_version(0)
    assert e.value.code is ErrorCode.STALE_REVISION


def test_receipts_replay_and_conflict(store):
    receipt = ActionReceipt(idempotency_key="k", action="act", case_id=CASE, actor_id="A",
                            input_hash="h1", resulting_version=1, result_hash="r")
    with store.write(CASE) as tx:
        assert tx.find_receipt("act", "k", "h1") is None
        tx.save_receipt(receipt, q("Q9", "result"))
    with store.write(CASE) as tx:
        assert Question.model_validate_json(tx.find_receipt("act", "k", "h1")).text_fr == "result"
        with pytest.raises(BousslaError) as e:
            tx.find_receipt("act", "k", "h2")
        assert e.value.code is ErrorCode.IDEMPOTENCY_CONFLICT
    with pytest.raises(BousslaError) as e:
        with store.write(CASE) as tx:
            tx.save_receipt(receipt, q("Q9", "again"))
    assert e.value.code is ErrorCode.DUPLICATE_ACCEPTANCE


def test_concurrent_writers_serialize(store):
    errors, done = [], []

    def worker():
        try:
            with store.write(CASE) as tx:
                tx.require_version(1)
                tx.put("question", "Q1", q("Q1", "race"))
                tx.commit_version("race")
            done.append(1)
        except BousslaError as exc:
            errors.append(exc.code)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(done) == 1 and errors == [ErrorCode.STALE_REVISION] * 3
    assert store.case_meta(CASE)["version"] == 2


def test_originals_content_addressed(store):
    d1, p1 = store.save_original(b"%PDF-1", ".pdf")
    d2, p2 = store.save_original(b"%PDF-1", ".pdf")
    assert d1 == d2 and p1 == p2


def test_duplicate_case_rejected(store):
    with pytest.raises(BousslaError):
        with store.write(CASE) as tx:
            tx.create_case("CO-1", "again")


def test_audit_event_is_atomic_and_preserves_unknown_scores(store):
    with store.write(CASE) as tx:
        tx.put("question", "Q1", q("Q1", "new"))
        tx.commit_version("updated question")
        tx.event("ANSWERS", "COMPANY-1", "Question answered", ("Q1",))
    record = store.audit_records(CASE)[0]
    assert record["event_id"] == store.events(CASE)[0].event_id
    assert record["actor_id"] == "COMPANY-1"
    assert record["reason"] == "Question answered"
    assert record["evidence_ids"] == ["Q1"]
    assert record["before"] is None and record["after"] is None
    assert record["rules_version"] is None


def test_existing_database_adds_audit_table_without_rewriting_events(tmp_path):
    import sqlite3
    db = tmp_path / "legacy.sqlite"
    store = CaseStore(db, tmp_path / "uploads")
    with store.write(CASE) as tx:
        tx.create_case("CO-1", "seed")
        tx.commit_version("seed")
    with sqlite3.connect(db) as conn:
        conn.execute("INSERT INTO events (case_id, kind, actor_id, at, case_version, summary, fact_ids) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (CASE, "LEGACY", "A", "2026-01-01T00:00:00+00:00", 1, "before audit", "[]"))
        conn.execute("DROP TABLE audit_records")
        conn.execute("UPDATE schema_meta SET value='1' WHERE key='schema_version'")
    migrated = CaseStore(db, tmp_path / "uploads")
    assert len(migrated.events(CASE)) == 1
    assert migrated.audit_records(CASE) == []
    with migrated.write(CASE) as tx:
        tx.event("NEW", "A", "after audit")
    assert len(migrated.audit_records(CASE)) == 1
    with sqlite3.connect(db) as conn:
        assert conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0] == "2"
