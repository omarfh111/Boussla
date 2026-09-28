"""Authoritative SQLite case store — lane A.

Design (ARCHITECTURE.md §E/§F):
- Facts are append-only. Each row is ``(case_id, kind, fact_id, valid_from)``
  plus JSON; a later row with the same key supersedes it from that version
  on, and a tombstone retires it. Nothing is updated or deleted, so any past
  version can be reconstructed.
- ``cases.current_version`` is the only mutable column; it is advanced inside
  the same ``BEGIN IMMEDIATE`` transaction as the facts, the revision row, the
  events and the action receipt.
- Parameterized SQL only. No model call may run while a ``WriteTx`` is open.
- Original uploads are content-addressed files, never overwritten.

Local traceability store, not tamper-proof legal evidence.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, TypeVar

from pydantic import BaseModel

from boussla.contracts import (
    ActionReceipt, BousslaError, CaseEvent, CaseRevision, ErrorCode, ScoreSnapshot,
)

M = TypeVar("M", bound=BaseModel)

SCHEMA_VERSION = 3
SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    current_version INTEGER NOT NULL CHECK (current_version >= 1),
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS case_versions (
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    version INTEGER NOT NULL,
    parent_version INTEGER,
    fact_hash TEXT NOT NULL,
    reason TEXT NOT NULL,
    accepted_evidence_ids TEXT NOT NULL,
    score_json TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (case_id, version)
);
CREATE TABLE IF NOT EXISTS facts (
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    kind TEXT NOT NULL,
    fact_id TEXT NOT NULL,
    valid_from INTEGER NOT NULL,
    retired INTEGER NOT NULL DEFAULT 0 CHECK (retired IN (0, 1)),
    body TEXT,
    PRIMARY KEY (case_id, kind, fact_id, valid_from)
);
CREATE TABLE IF NOT EXISTS action_receipts (
    case_id TEXT NOT NULL,
    action TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    resulting_version INTEGER NOT NULL,
    result_hash TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (case_id, action, idempotency_key)
);
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    at TEXT NOT NULL,
    case_version INTEGER NOT NULL,
    summary TEXT NOT NULL,
    fact_ids TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_records (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id TEXT NOT NULL,
    event_seq INTEGER NOT NULL UNIQUE,
    actor_id TEXT NOT NULL,
    at TEXT NOT NULL,
    case_version INTEGER NOT NULL,
    action TEXT NOT NULL,
    reason TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT,
    evidence_ids TEXT NOT NULL,
    rules_version TEXT,
    engine_version TEXT
);
CREATE TABLE IF NOT EXISTS notification_reads (
    case_id TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    notification_id TEXT NOT NULL,
    read_at TEXT NOT NULL,
    PRIMARY KEY (case_id, actor_id, notification_id)
);
CREATE TABLE IF NOT EXISTS artifacts (
    case_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    artifact_id TEXT NOT NULL,
    case_version INTEGER NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (case_id, kind, artifact_id)
);
CREATE INDEX IF NOT EXISTS facts_by_kind ON facts(case_id, kind, valid_from);
CREATE INDEX IF NOT EXISTS events_by_case ON events(case_id, seq);
CREATE INDEX IF NOT EXISTS audit_by_case ON audit_records(case_id, seq);
"""


class ReceiptNote(BaseModel):
    """Minimal stored outcome for actions whose caller re-reads the case view."""

    note: str
    fact_ids: tuple[str, ...] = ()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def stable_hash(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def _body(model: BaseModel | dict) -> str:
    data = model.model_dump(mode="json") if isinstance(model, BaseModel) else model
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


class CaseStore:
    def __init__(self, db_path: Path | str, upload_dir: Path | str) -> None:
        self.db_path = str(db_path)
        self.upload_dir = Path(upload_dir)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._memory_conn: sqlite3.Connection | None = None
        with self._connect() as conn:
            conn.executescript(SCHEMA)
            conn.execute("INSERT INTO schema_meta VALUES ('schema_version', ?) "
                         "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA_VERSION),))

    # ----------------------------------------------------------- connections
    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        if self.db_path == ":memory:":
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
                self._memory_conn.execute("PRAGMA foreign_keys=ON")
            yield self._memory_conn
            return
        conn = sqlite3.connect(self.db_path, isolation_level=None, timeout=10)
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA journal_mode=WAL")
            yield conn
        finally:
            conn.close()

    @contextmanager
    def write(self, case_id: str) -> Iterator["WriteTx"]:
        """Serialized write transaction. Commit on success, roll back on any error."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield WriteTx(conn, case_id)
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise

    # --------------------------------------------------------------- reads
    def case_exists(self, case_id: str) -> bool:
        with self._connect() as conn:
            return conn.execute("SELECT 1 FROM cases WHERE case_id=?", (case_id,)).fetchone() is not None

    def case_meta(self, case_id: str) -> dict:
        with self._connect() as conn:
            row = conn.execute("SELECT company_id, current_version FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            raise BousslaError(ErrorCode.NOT_FOUND, "Dossier inconnu")
        return {"case_id": case_id, "company_id": row[0], "version": row[1]}

    def case_incarnation(self, case_id: str) -> str:
        """Creation timestamp of this case row. A case deleted and re-created (demo
        reset) gets a new incarnation, so derived workflow threads never collide."""
        with self._connect() as conn:
            row = conn.execute("SELECT created_at FROM cases WHERE case_id=?", (case_id,)).fetchone()
        if row is None:
            raise BousslaError(ErrorCode.NOT_FOUND, "Dossier inconnu")
        return row[0]

    def list_cases(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT case_id, company_id, current_version FROM cases ORDER BY case_id").fetchall()
        return [{"case_id": r[0], "company_id": r[1], "version": r[2]} for r in rows]

    def facts(self, case_id: str, kind: str, model: type[M], version: int | None = None) -> list[M]:
        """Current (or as-of ``version``) facts of one kind, ordered by fact_id."""
        return [model.model_validate_json(b) for b in self._fact_bodies(case_id, kind, None, version)]

    def fact(self, case_id: str, kind: str, fact_id: str, model: type[M], version: int | None = None) -> M | None:
        bodies = self._fact_bodies(case_id, kind, fact_id, version)
        return model.model_validate_json(bodies[0]) if bodies else None

    def _fact_bodies(self, case_id: str, kind: str, fact_id: str | None, version: int | None) -> list[str]:
        if version is None:
            version = self.case_meta(case_id)["version"]
        sql = """
            SELECT f.body FROM facts f
            JOIN (SELECT fact_id, MAX(valid_from) AS vf FROM facts
                  WHERE case_id=? AND kind=? AND valid_from<=? {extra} GROUP BY fact_id) latest
              ON f.fact_id = latest.fact_id AND f.valid_from = latest.vf
            WHERE f.case_id=? AND f.kind=? AND f.retired=0
            ORDER BY f.fact_id
        """
        params: list = [case_id, kind, version]
        extra = ""
        if fact_id is not None:
            extra = "AND fact_id=?"
            params.append(fact_id)
        params += [case_id, kind]
        with self._connect() as conn:
            return [r[0] for r in conn.execute(sql.format(extra=extra), params).fetchall()]

    def revisions(self, case_id: str) -> list[CaseRevision]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT version, parent_version, fact_hash, reason, accepted_evidence_ids, score_json, created_at "
                "FROM case_versions WHERE case_id=? ORDER BY version", (case_id,)).fetchall()
        return [CaseRevision(case_id=case_id, version=r[0], parent_version=r[1], fact_hash=r[2], reason=r[3],
                             accepted_evidence_ids=tuple(json.loads(r[4])),
                             score_snapshot=ScoreSnapshot.model_validate_json(r[5]) if r[5] else None,
                             created_at=r[6]) for r in rows]

    def events(self, case_id: str) -> list[CaseEvent]:
        with self._connect() as conn:
            rows = conn.execute("SELECT seq, kind, actor_id, at, case_version, summary, fact_ids FROM events "
                                "WHERE case_id=? ORDER BY seq", (case_id,)).fetchall()
        return [CaseEvent(event_id=f"EV-{r[0]:05d}", case_id=case_id, kind=r[1], actor_id=r[2], at=r[3],
                          case_version=r[4], summary=r[5], fact_ids=tuple(json.loads(r[6]))) for r in rows]

    def notification_reads(self, case_id: str, actor_id: str) -> dict[str, str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT notification_id, read_at FROM notification_reads WHERE case_id=? AND actor_id=?",
                (case_id, actor_id)).fetchall()
        return dict(rows)

    def mark_notification_read(self, case_id: str, actor_id: str, notification_id: str,
                               at: datetime) -> str:
        """An actor receipt; it does not alter case facts or version."""
        with self._connect() as conn:
            conn.execute("INSERT INTO notification_reads VALUES (?, ?, ?, ?) "
                         "ON CONFLICT(case_id, actor_id, notification_id) DO NOTHING",
                         (case_id, actor_id, notification_id, at.isoformat()))
            row = conn.execute(
                "SELECT read_at FROM notification_reads WHERE case_id=? AND actor_id=? AND notification_id=?",
                (case_id, actor_id, notification_id)).fetchone()
        return row[0]

    def audit_records(self, case_id: str) -> list[dict]:
        """Officer-only service consumes durable, transaction-coupled audit rows."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT seq, event_seq, actor_id, at, case_version, action, reason, "
                "before_json, after_json, evidence_ids, rules_version, engine_version "
                "FROM audit_records WHERE case_id=? ORDER BY seq", (case_id,)).fetchall()
        return [{"audit_id": f"AUD-{r[0]:05d}", "event_id": f"EV-{r[1]:05d}",
                 "case_id": case_id, "actor_id": r[2], "at": r[3],
                 "case_version": r[4], "action": r[5], "reason": r[6],
                 "before": json.loads(r[7]) if r[7] else None,
                 "after": json.loads(r[8]) if r[8] else None,
                 "evidence_ids": json.loads(r[9]), "rules_version": r[10],
                 "engine_version": r[11],
                 "fact_changes": (json.loads(r[8]).get("fact_changes", []) if r[8] else [])} for r in rows]

    def delete_case(self, case_id: str) -> None:
        """Remove one case entirely (synthetic demo administration only; callers enforce
        DEMO_OPERATOR authority and portfolio membership). Uploaded originals are
        content-addressed and shared, so they are left in place."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                for table in ("facts", "case_versions", "action_receipts", "audit_records", "events", "notification_reads", "artifacts", "cases"):
                    conn.execute(f"DELETE FROM {table} WHERE case_id=?", (case_id,))  # noqa: S608 - fixed names
                conn.execute("COMMIT")
            except BaseException:
                conn.execute("ROLLBACK")
                raise

    # ------------------------------------------------------------ artifacts
    def put_artifact(self, case_id: str, kind: str, artifact_id: str, case_version: int, model: BaseModel) -> None:
        """Version-bound working artifact (e.g. an unpublished draft). Not a case fact:
        it never changes the case version and is only valid for ``case_version``."""
        with self._connect() as conn:
            conn.execute("INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?)",
                         (case_id, kind, artifact_id, case_version, _body(model), utcnow().isoformat()))

    def artifact(self, case_id: str, kind: str, artifact_id: str, model: type[M]) -> tuple[int, M] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT case_version, body FROM artifacts WHERE case_id=? AND kind=? AND artifact_id=?",
                               (case_id, kind, artifact_id)).fetchone()
        return (row[0], model.model_validate_json(row[1])) if row else None

    # ------------------------------------------------------------ originals
    def save_original(self, content: bytes, suffix: str) -> tuple[str, str]:
        """Store bytes content-addressed. Returns (sha256, relative-safe path)."""
        digest = hashlib.sha256(content).hexdigest()
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        path = self.upload_dir / f"{digest}{suffix}"
        if not path.exists():
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(content)
            tmp.replace(path)
        return digest, str(path)


class WriteTx:
    """Operations valid only inside ``CaseStore.write``."""

    def __init__(self, conn: sqlite3.Connection, case_id: str) -> None:
        self.conn = conn
        self.case_id = case_id
        self._new_version: int | None = None
        self._written_facts: set[tuple[str, str]] = set()

    # -------------------------------------------------------------- case row
    def create_case(self, company_id: str, reason: str, at: datetime | None = None) -> int:
        at_s = (at or utcnow()).isoformat()
        try:
            self.conn.execute("INSERT INTO cases VALUES (?, ?, 1, ?)", (self.case_id, company_id, at_s))
        except sqlite3.IntegrityError as exc:
            raise BousslaError(ErrorCode.INVALID_STATE, "Dossier déjà existant") from exc
        self._new_version = 1
        return 1

    def current_version(self) -> int:
        row = self.conn.execute("SELECT current_version FROM cases WHERE case_id=?", (self.case_id,)).fetchone()
        if row is None:
            raise BousslaError(ErrorCode.NOT_FOUND, "Dossier inconnu")
        return row[0]

    def company_id(self) -> str:
        row = self.conn.execute("SELECT company_id FROM cases WHERE case_id=?", (self.case_id,)).fetchone()
        if row is None:
            raise BousslaError(ErrorCode.NOT_FOUND, "Dossier inconnu")
        return row[0]

    def require_version(self, expected_version: int) -> int:
        current = self.current_version()
        if expected_version != current:
            raise BousslaError(ErrorCode.STALE_REVISION, "Le dossier a changé ; rechargez-le",
                               expected=expected_version, current=current)
        return current

    def begin_version(self) -> int:
        """Reserve version N+1 for the facts written in this transaction."""
        if self._new_version is None:
            self._new_version = self.current_version() + 1
        return self._new_version

    # --------------------------------------------------------------- facts
    def put(self, kind: str, fact_id: str, model: BaseModel | dict) -> None:
        self.conn.execute("INSERT INTO facts VALUES (?, ?, ?, ?, 0, ?)",
                          (self.case_id, kind, fact_id, self.begin_version(), _body(model)))
        self._written_facts.add((kind, fact_id))

    def retire(self, kind: str, fact_id: str) -> None:
        self.conn.execute("INSERT INTO facts VALUES (?, ?, ?, ?, 1, NULL)",
                          (self.case_id, kind, fact_id, self.begin_version()))
        self._written_facts.add((kind, fact_id))

    def _current_fact_hash(self, version: int) -> str:
        rows = self.conn.execute("""
            SELECT f.kind, f.fact_id, f.body FROM facts f
            JOIN (SELECT kind, fact_id, MAX(valid_from) AS vf FROM facts
                  WHERE case_id=? AND valid_from<=? GROUP BY kind, fact_id) l
              ON f.kind=l.kind AND f.fact_id=l.fact_id AND f.valid_from=l.vf
            WHERE f.case_id=? AND f.retired=0 ORDER BY f.kind, f.fact_id
        """, (self.case_id, version, self.case_id)).fetchall()
        return stable_hash(rows)

    def commit_version(self, reason: str, accepted_evidence_ids: tuple[str, ...] = (),
                       score: ScoreSnapshot | None = None, at: datetime | None = None) -> int:
        """Record the revision row and advance ``current_version``."""
        version = self.begin_version()
        parent = version - 1 if version > 1 else None
        self.conn.execute(
            "INSERT INTO case_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (self.case_id, version, parent, self._current_fact_hash(version), reason,
             json.dumps(list(accepted_evidence_ids)), score.model_dump_json() if score else None,
             (at or utcnow()).isoformat()))
        cur = self.conn.execute("UPDATE cases SET current_version=? WHERE case_id=? AND current_version=?",
                                (version, self.case_id, parent or version))
        if parent is not None and cur.rowcount != 1:
            raise BousslaError(ErrorCode.STALE_REVISION, "Version concurrente détectée")
        return version

    # -------------------------------------------------------------- events
    @staticmethod
    def _score_audit(score_json: str | None) -> dict | None:
        if not score_json:
            return None
        score = json.loads(score_json)
        return {"review_index": score.get("review_index"),
                "cause_contributions": {c["cause_id"]: c["current_contribution"]
                                        for c in score.get("cause_progress", []) if c.get("cause_id")},
                "calculated_at": score.get("calculated_at")}

    @staticmethod
    def _audit_safe(value):
        if isinstance(value, dict):
            return {key: WriteTx._audit_safe(item) for key, item in value.items()
                    if key not in {"local_path", "_secrets"}}
        if isinstance(value, list):
            return [WriteTx._audit_safe(item) for item in value]
        return value

    def _fact_at(self, kind: str, fact_id: str, version: int) -> dict | None:
        if version < 1:
            return None
        row = self.conn.execute(
            "SELECT retired, body FROM facts WHERE case_id=? AND kind=? AND fact_id=? "
            "AND valid_from<=? ORDER BY valid_from DESC LIMIT 1",
            (self.case_id, kind, fact_id, version)).fetchone()
        if not row or row[0] or not row[1]:
            return None
        value = self._audit_safe(json.loads(row[1]))
        if kind == "document_text":
            return {"document_id": value.get("document_id"), "status": value.get("status"),
                    "page_count": len(value.get("pages", [])), "limitations": value.get("limitations", []),
                    "text_sha256": hashlib.sha256(row[1].encode()).hexdigest()}
        return value

    def event(self, kind: str, actor_id: str, summary: str, fact_ids: tuple[str, ...] = (),
              version: int | None = None, at: datetime | None = None,
              before_score: ScoreSnapshot | None = None,
              after_score: ScoreSnapshot | None = None) -> None:
        """Write event and audit together; missing snapshots remain explicitly unknown."""
        v = version if version is not None else (self._new_version or self.current_version())
        at_s = (at or utcnow()).isoformat()
        event = self.conn.execute("INSERT INTO events (case_id, kind, actor_id, at, case_version, summary, fact_ids) "
                                  "VALUES (?, ?, ?, ?, ?, ?, ?)",
                                  (self.case_id, kind, actor_id, at_s, v, summary,
                                   json.dumps(list(fact_ids))))
        revision = self.conn.execute(
            "SELECT parent_version, score_json FROM case_versions WHERE case_id=? AND version=?",
            (self.case_id, v)).fetchone()
        parent_json = None
        if revision and revision[0] is not None:
            parent = self.conn.execute(
                "SELECT score_json FROM case_versions WHERE case_id=? AND version=?",
                (self.case_id, revision[0])).fetchone()
            parent_json = parent[0] if parent else None
        before = self._score_audit(before_score.model_dump_json() if before_score else parent_json)
        after = self._score_audit(after_score.model_dump_json() if after_score else (revision[1] if revision else None))
        if revision and self._new_version == v and self._written_facts:
            changes = [{"kind": fact_kind, "fact_id": fact_id,
                        "before": self._fact_at(fact_kind, fact_id, v - 1),
                        "after": self._fact_at(fact_kind, fact_id, v)}
                       for fact_kind, fact_id in sorted(self._written_facts)]
            after = {**(after or {}), "fact_changes": changes}
        source = after_score or before_score
        if source is None and revision and revision[1]:
            source = ScoreSnapshot.model_validate_json(revision[1])
        if source is None and parent_json:
            source = ScoreSnapshot.model_validate_json(parent_json)
        self.conn.execute(
            "INSERT INTO audit_records (case_id, event_seq, actor_id, at, case_version, action, reason, "
            "before_json, after_json, evidence_ids, rules_version, engine_version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (self.case_id, event.lastrowid, actor_id, at_s, v, kind, summary,
             json.dumps(before, ensure_ascii=False) if before is not None else None,
             json.dumps(after, ensure_ascii=False) if after is not None else None,
             json.dumps(list(fact_ids)), source.rules_version if source else None,
             source.engine_version if source else None))

    # ------------------------------------------------------------ receipts
    def find_receipt(self, action: str, idempotency_key: str, input_hash: str) -> str | None:
        """Stored result JSON for an identical retry; IDEMPOTENCY_CONFLICT if the key was reused."""
        row = self.conn.execute(
            "SELECT input_hash, result_json FROM action_receipts WHERE case_id=? AND action=? AND idempotency_key=?",
            (self.case_id, action, idempotency_key)).fetchone()
        if row is None:
            return None
        if row[0] != input_hash:
            raise BousslaError(ErrorCode.IDEMPOTENCY_CONFLICT, "Clé réutilisée avec un contenu différent")
        return row[1]

    def save_receipt(self, receipt: ActionReceipt, result: BaseModel) -> None:
        """Persist the receipt with the full result for exact replay. The primary
        key also guards two concurrent retries: the loser gets DUPLICATE_ACCEPTANCE."""
        if receipt.case_id != self.case_id:
            raise BousslaError(ErrorCode.CROSS_COMPANY, "Reçu d'un autre dossier")
        try:
            self.conn.execute("INSERT INTO action_receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                              (self.case_id, receipt.action, receipt.idempotency_key, receipt.actor_id,
                               receipt.input_hash, receipt.resulting_version, receipt.result_hash,
                               result.model_dump_json(), utcnow().isoformat()))
        except sqlite3.IntegrityError as exc:
            raise BousslaError(ErrorCode.DUPLICATE_ACCEPTANCE, "Action déjà enregistrée") from exc
