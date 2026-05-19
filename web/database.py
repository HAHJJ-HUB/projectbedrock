"""SQLite-backed case file management."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path("./web/cases.db")


@contextmanager
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS cases (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            case_number TEXT    UNIQUE NOT NULL,
            name        TEXT    NOT NULL,
            subject_type TEXT   DEFAULT 'topic',
            description TEXT,
            status      TEXT    DEFAULT 'active',
            priority    TEXT    DEFAULT 'medium',
            tags        TEXT    DEFAULT '[]',
            created_at  TEXT    NOT NULL,
            updated_at  TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id     INTEGER NOT NULL,
            content     TEXT    NOT NULL,
            source      TEXT    DEFAULT 'manual',
            agent       TEXT,
            created_at  TEXT    NOT NULL,
            FOREIGN KEY (case_id) REFERENCES cases(id)
        );

        CREATE TABLE IF NOT EXISTS research_runs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id         INTEGER NOT NULL,
            status          TEXT    DEFAULT 'queued',
            scope           TEXT,
            sources_found   INTEGER DEFAULT 0,
            findings_count  INTEGER DEFAULT 0,
            started_at      TEXT    NOT NULL,
            completed_at    TEXT,
            error           TEXT,
            FOREIGN KEY (case_id) REFERENCES cases(id)
        );
        """)


def _next_case_number() -> str:
    with db() as con:
        row = con.execute("SELECT COUNT(*) as n FROM cases").fetchone()
        n = (row["n"] or 0) + 1
        return f"CASE-{n:04d}"


def create_case(
    name: str,
    subject_type: str = "topic",
    description: str = "",
    priority: str = "medium",
    tags: list[str] | None = None,
) -> dict:
    now = datetime.utcnow().isoformat()
    case_number = _next_case_number()
    with db() as con:
        cur = con.execute(
            """INSERT INTO cases
               (case_number, name, subject_type, description, priority, tags, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (case_number, name, subject_type, description, priority,
             json.dumps(tags or []), now, now),
        )
        return get_case(cur.lastrowid)


def get_case(case_id: int) -> dict | None:
    with db() as con:
        row = con.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["tags"] = json.loads(d["tags"] or "[]")
        return d


def list_cases(status: str = "") -> list[dict]:
    with db() as con:
        if status:
            rows = con.execute(
                "SELECT * FROM cases WHERE status=? ORDER BY updated_at DESC", (status,)
            ).fetchall()
        else:
            rows = con.execute("SELECT * FROM cases ORDER BY updated_at DESC").fetchall()
    result = []
    for row in rows:
        d = dict(row)
        d["tags"] = json.loads(d["tags"] or "[]")
        result.append(d)
    return result


def update_case_status(case_id: int, status: str) -> None:
    now = datetime.utcnow().isoformat()
    with db() as con:
        con.execute(
            "UPDATE cases SET status=?, updated_at=? WHERE id=?",
            (status, now, case_id),
        )


def add_note(
    case_id: int,
    content: str,
    source: str = "manual",
    agent: str | None = None,
) -> dict:
    now = datetime.utcnow().isoformat()
    with db() as con:
        cur = con.execute(
            "INSERT INTO notes (case_id, content, source, agent, created_at) VALUES (?,?,?,?,?)",
            (case_id, content, source, agent, now),
        )
        con.execute(
            "UPDATE cases SET updated_at=? WHERE id=?", (now, case_id)
        )
        row = con.execute("SELECT * FROM notes WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(row)


def get_notes(case_id: int) -> list[dict]:
    with db() as con:
        rows = con.execute(
            "SELECT * FROM notes WHERE case_id=? ORDER BY created_at ASC",
            (case_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def create_run(case_id: int, scope: str = "") -> dict:
    now = datetime.utcnow().isoformat()
    with db() as con:
        cur = con.execute(
            """INSERT INTO research_runs
               (case_id, status, scope, started_at) VALUES (?,?,?,?)""",
            (case_id, "running", scope, now),
        )
        row = con.execute(
            "SELECT * FROM research_runs WHERE id=?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)


def update_run(
    run_id: int,
    status: str,
    sources_found: int = 0,
    findings_count: int = 0,
    error: str = "",
) -> None:
    now = datetime.utcnow().isoformat()
    with db() as con:
        con.execute(
            """UPDATE research_runs
               SET status=?, sources_found=?, findings_count=?, completed_at=?, error=?
               WHERE id=?""",
            (status, sources_found, findings_count, now, error, run_id),
        )


def get_runs(case_id: int) -> list[dict]:
    with db() as con:
        rows = con.execute(
            "SELECT * FROM research_runs WHERE case_id=? ORDER BY started_at DESC",
            (case_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_run(run_id: int) -> dict | None:
    with db() as con:
        row = con.execute(
            "SELECT * FROM research_runs WHERE id=?", (run_id,)
        ).fetchone()
    return dict(row) if row else None


def case_stats(case_id: int) -> dict:
    with db() as con:
        note_count = con.execute(
            "SELECT COUNT(*) as n FROM notes WHERE case_id=?", (case_id,)
        ).fetchone()["n"]
        run_count = con.execute(
            "SELECT COUNT(*) as n FROM research_runs WHERE case_id=?", (case_id,)
        ).fetchone()["n"]
        sources = con.execute(
            "SELECT COALESCE(SUM(sources_found),0) as n FROM research_runs WHERE case_id=? AND status='complete'",
            (case_id,),
        ).fetchone()["n"]
    return {"notes": note_count, "runs": run_count, "sources": sources}
