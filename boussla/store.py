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

SCHEMA_VERSION = 1
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
CREATE INDEX IF NOT EXISTS facts_by_kind ON facts(case_id, kind, valid_from);
CREATE INDEX IF NOT EXISTS events_by_case ON events(case_id, seq);
"""


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
            conn.execute("INSERT OR IGNORE INTO schema_meta VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))

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

    def retire(self, kind: str, fact_id: str) -> None:
        self.conn.execute("INSERT INTO facts VALUES (?, ?, ?, ?, 1, NULL)",
                          (self.case_id, kind, fact_id, self.begin_version()))

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
    def event(self, kind: str, actor_id: str, summary: str, fact_ids: tuple[str, ...] = (),
              version: int | None = None, at: datetime | None = None) -> None:
        v = version if version is not None else (self._new_version or self.current_version())
        self.conn.execute("INSERT INTO events (case_id, kind, actor_id, at, case_version, summary, fact_ids) "
                          "VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (self.case_id, kind, actor_id, (at or utcnow()).isoformat(), v, summary,
                           json.dumps(list(fact_ids))))

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
