"""SQLite storage for research jobs + completed reports.

Two tables:
    jobs           — one row per research_start call (metadata + status)
    reports_fts    — FTS5 index over completed report markdown for search

The DB lives at $MCP_DB_PATH (default: ./data/jobs.db).
Autocreated on first use.
"""

import os
import sqlite3
import sys
import threading
import time
from pathlib import Path

DB_PATH = os.environ.get("MCP_DB_PATH", str(Path(__file__).parent / "data" / "jobs.db"))

_lock = threading.RLock()
_conn: sqlite3.Connection | None = None


def _ensure_parent():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _ensure_parent()
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False, isolation_level=None)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
        _init_schema(_conn)
    return _conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            interaction_id          TEXT PRIMARY KEY,
            tier                    TEXT NOT NULL,
            agent                   TEXT NOT NULL,
            prompt                  TEXT NOT NULL,
            prompt_preview          TEXT NOT NULL,
            started_at              REAL NOT NULL,
            completed_at            REAL,
            status                  TEXT NOT NULL DEFAULT 'in_progress',
            markdown                TEXT,
            usage_json              TEXT,
            error                   TEXT,
            previous_interaction_id TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_started_at ON jobs(started_at DESC);

        CREATE VIRTUAL TABLE IF NOT EXISTS reports_fts USING fts5(
            interaction_id,
            prompt,
            markdown,
            tokenize='porter unicode61'
        );
    """)
    # NOTE: idx_jobs_prev is created AFTER the migration below, because the
    # previous_interaction_id column may not exist on pre-existing DBs at this
    # point. Creating the index inside executescript above would abort the
    # whole script before the ALTER TABLE could fire.
    # Migrations — idempotent, try-then-ignore-duplicate pattern.
    # Every added column goes in this list. Running the ALTER is always safe:
    # if the column exists, SQLite raises "duplicate column" which we swallow.
    _PENDING_COLUMNS = [
        ("previous_interaction_id", "TEXT"),
    ]
    for col_name, col_type in _PENDING_COLUMNS:
        try:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}")
            print(f"[storage] migration: added jobs.{col_name}", file=sys.stderr)
        except sqlite3.OperationalError as exc:
            if "duplicate column" in str(exc).lower():
                continue  # Already migrated, fine
            raise
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_prev ON jobs(previous_interaction_id)")


def record_start(
    interaction_id: str,
    tier: str,
    agent: str,
    prompt: str,
    previous_interaction_id: str | None = None,
) -> None:
    with _lock:
        conn = _connect()
        preview = prompt[:200] + ("..." if len(prompt) > 200 else "")
        conn.execute(
            """INSERT OR REPLACE INTO jobs
               (interaction_id, tier, agent, prompt, prompt_preview, started_at, status,
                previous_interaction_id)
               VALUES (?, ?, ?, ?, ?, ?, 'in_progress', ?)""",
            (interaction_id, tier, agent, prompt, preview, time.time(), previous_interaction_id),
        )


def get_chain(interaction_id: str, max_depth: int = 20) -> list[dict]:
    """Walk the previous_interaction_id chain backwards to the root."""
    with _lock:
        conn = _connect()
        chain: list[dict] = []
        current = interaction_id
        for _ in range(max_depth):
            row = conn.execute(
                """SELECT interaction_id, tier, prompt_preview, started_at, status,
                          previous_interaction_id
                   FROM jobs WHERE interaction_id = ?""",
                (current,),
            ).fetchone()
            if row is None:
                break
            chain.append(dict(row))
            current = row["previous_interaction_id"]
            if current is None:
                break
        return chain


def record_completion(
    interaction_id: str,
    markdown: str,
    usage_json: str | None = None,
) -> None:
    with _lock:
        conn = _connect()
        conn.execute(
            """UPDATE jobs
               SET status='completed', completed_at=?, markdown=?, usage_json=?
               WHERE interaction_id=?""",
            (time.time(), markdown, usage_json, interaction_id),
        )
        # Upsert FTS entry for this job
        row = conn.execute(
            "SELECT prompt FROM jobs WHERE interaction_id=?", (interaction_id,)
        ).fetchone()
        if row:
            conn.execute("DELETE FROM reports_fts WHERE interaction_id=?", (interaction_id,))
            conn.execute(
                "INSERT INTO reports_fts(interaction_id, prompt, markdown) VALUES (?,?,?)",
                (interaction_id, row["prompt"], markdown),
            )


def record_failure(interaction_id: str, status: str, error: str | None) -> None:
    with _lock:
        conn = _connect()
        conn.execute(
            """UPDATE jobs SET status=?, completed_at=?, error=? WHERE interaction_id=?""",
            (status, time.time(), error, interaction_id),
        )


def get_job(interaction_id: str) -> dict | None:
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT * FROM jobs WHERE interaction_id=?", (interaction_id,)
        ).fetchone()
        return dict(row) if row else None


def list_jobs(
    limit: int = 50,
    status_filter: str | None = None,
) -> list[dict]:
    with _lock:
        conn = _connect()
        if status_filter:
            rows = conn.execute(
                "SELECT interaction_id, tier, agent, prompt_preview, started_at, "
                "completed_at, status FROM jobs WHERE status=? "
                "ORDER BY started_at DESC LIMIT ?",
                (status_filter, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT interaction_id, tier, agent, prompt_preview, started_at, "
                "completed_at, status FROM jobs "
                "ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


def search_reports(query: str, limit: int = 10) -> list[dict]:
    """Full-text search over completed reports. Returns snippets."""
    with _lock:
        conn = _connect()
        # FTS5 MATCH syntax; escape any problematic chars by quoting the query
        escaped = query.replace('"', '""')
        rows = conn.execute(
            """SELECT f.interaction_id,
                      snippet(reports_fts, 2, '[', ']', '…', 20) AS snippet,
                      j.prompt_preview,
                      j.tier,
                      j.completed_at,
                      f.rank
               FROM reports_fts f
               LEFT JOIN jobs j ON j.interaction_id = f.interaction_id
               WHERE reports_fts MATCH ?
               ORDER BY f.rank
               LIMIT ?""",
            (f'"{escaped}"', limit),
        ).fetchall()
        return [dict(r) for r in rows]


def job_count() -> dict[str, int]:
    with _lock:
        conn = _connect()
        total = conn.execute("SELECT COUNT(*) AS c FROM jobs").fetchone()["c"]
        by_status: dict[str, int] = {}
        for row in conn.execute("SELECT status, COUNT(*) AS c FROM jobs GROUP BY status"):
            by_status[row["status"]] = row["c"]
        return {"total": total, "by_status": by_status}


def get_usage_json(interaction_id: str) -> str | None:
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT usage_json FROM jobs WHERE interaction_id=?",
            (interaction_id,),
        ).fetchone()
        return row["usage_json"] if row else None


def list_jobs_with_usage(since_epoch: float | None = None, tier: str | None = None) -> list[dict]:
    """Return completed jobs with their usage_json, optionally filtered by
    started_at >= since_epoch and/or tier."""
    with _lock:
        conn = _connect()
        q = (
            "SELECT interaction_id, tier, agent, started_at, completed_at, "
            "status, usage_json FROM jobs WHERE usage_json IS NOT NULL"
        )
        args: list = []
        if since_epoch is not None:
            q += " AND started_at >= ?"
            args.append(since_epoch)
        if tier:
            q += " AND tier = ?"
            args.append(tier)
        q += " ORDER BY started_at DESC"
        return [dict(r) for r in conn.execute(q, args).fetchall()]
