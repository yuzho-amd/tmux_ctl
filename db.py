"""SQLite persistence for session metadata."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "sessions.db"
DEFAULT_TITLE_RE = re.compile(r"^session-(\d+)$")
DEFAULT_CELL_WIDTH = 320
DEFAULT_CELL_HEIGHT = 240
MIN_CELL_WIDTH = 260
MIN_CELL_HEIGHT = 160
MAX_CELL_WIDTH = 960
MAX_CELL_HEIGHT = 720


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                default_title TEXT NOT NULL DEFAULT '',
                tmux_session TEXT NOT NULL DEFAULT '',
                port INTEGER NOT NULL,
                sort_order INTEGER NOT NULL DEFAULT 0,
                cell_width INTEGER NOT NULL DEFAULT 320,
                cell_height INTEGER NOT NULL DEFAULT 240,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        columns = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
        if "default_title" not in columns:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN default_title TEXT NOT NULL DEFAULT ''"
            )
        if "tmux_session" not in columns:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN tmux_session TEXT NOT NULL DEFAULT ''"
            )
        if "sort_order" not in columns:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
            )
        if "cell_width" not in columns:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN cell_width INTEGER NOT NULL DEFAULT 320"
            )
        if "cell_height" not in columns:
            conn.execute(
                "ALTER TABLE sessions ADD COLUMN cell_height INTEGER NOT NULL DEFAULT 240"
            )
        conn.execute(
            """
            UPDATE sessions
            SET tmux_session = 'agent-' || id
            WHERE tmux_session = '' OR tmux_session IS NULL
            """
        )
        _backfill_sort_order(conn)
        _backfill_default_titles(conn)


def _backfill_sort_order(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT id, sort_order FROM sessions ORDER BY created_at ASC"
    ).fetchall()
    if not rows:
        return
    orders = [int(row["sort_order"] or 0) for row in rows]
    if len(set(orders)) == len(orders) and set(orders) == set(range(len(orders))):
        return
    for index, row in enumerate(rows):
        conn.execute(
            "UPDATE sessions SET sort_order = ? WHERE id = ?",
            (index, row["id"]),
        )


def _backfill_default_titles(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT id, title, default_title FROM sessions ORDER BY created_at ASC"
    ).fetchall()
    used: set[int] = set()
    for row in rows:
        default_title = (row["default_title"] or "").strip()
        match = DEFAULT_TITLE_RE.match(default_title)
        if match:
            used.add(int(match.group(1)))

    for row in rows:
        title = (row["title"] or "").strip()
        default_title = (row["default_title"] or "").strip()
        if not DEFAULT_TITLE_RE.match(default_title):
            n = 1
            while n in used:
                n += 1
            used.add(n)
            default_title = f"session-{n}"
        if not title:
            title = default_title
        conn.execute(
            "UPDATE sessions SET title = ?, default_title = ? WHERE id = ?",
            (title, default_title, row["id"]),
        )


def next_default_title() -> str:
    with _connect() as conn:
        rows = conn.execute("SELECT default_title, title FROM sessions").fetchall()
    max_n = 0
    for row in rows:
        for value in (row["default_title"], row["title"]):
            match = DEFAULT_TITLE_RE.match((value or "").strip())
            if match:
                max_n = max(max_n, int(match.group(1)))
    return f"session-{max_n + 1}"


def next_sort_order() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT MAX(sort_order) AS n FROM sessions").fetchone()
    if row is None or row["n"] is None:
        return 0
    return int(row["n"]) + 1


def clamp_cell_size(width: int, height: int) -> tuple[int, int]:
    width = max(MIN_CELL_WIDTH, min(MAX_CELL_WIDTH, int(width)))
    height = max(MIN_CELL_HEIGHT, min(MAX_CELL_HEIGHT, int(height)))
    return width, height


def cell_size_for(row: sqlite3.Row) -> tuple[int, int]:
    width = int(row["cell_width"] or DEFAULT_CELL_WIDTH)
    height = int(row["cell_height"] or DEFAULT_CELL_HEIGHT)
    return clamp_cell_size(width, height)


def default_tmux_session(session_id: str) -> str:
    return f"agent-{session_id}"


def tmux_session_for(row: sqlite3.Row) -> str:
    name = (row["tmux_session"] or "").strip()
    if name:
        return name
    return default_tmux_session(row["id"])


def bound_tmux_sessions() -> set[str]:
    with _connect() as conn:
        rows = conn.execute("SELECT id, tmux_session FROM sessions").fetchall()
    return {tmux_session_for(row) for row in rows}


def count_sessions_with_tmux(tmux_session: str, exclude_id: str | None = None) -> int:
    with _connect() as conn:
        if exclude_id:
            cur = conn.execute(
                """
                SELECT COUNT(*) AS n FROM sessions
                WHERE tmux_session = ? AND id != ?
                """,
                (tmux_session, exclude_id),
            )
        else:
            cur = conn.execute(
                "SELECT COUNT(*) AS n FROM sessions WHERE tmux_session = ?",
                (tmux_session,),
            )
        row = cur.fetchone()
        return int(row["n"]) if row else 0


def save_session(
    session_id: str,
    title: str,
    port: int,
    default_title: str | None = None,
    tmux_session: str | None = None,
) -> None:
    default_title = (default_title or title).strip() or next_default_title()
    title = title.strip() or default_title
    tmux_session = (tmux_session or default_tmux_session(session_id)).strip()
    sort_order = next_sort_order()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (id, title, default_title, tmux_session, port, sort_order)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, title, default_title, tmux_session, port, sort_order),
        )


def list_sessions() -> list[sqlite3.Row]:
    with _connect() as conn:
        _backfill_default_titles(conn)
        cur = conn.execute(
            """
            SELECT id, title, default_title, tmux_session, port, sort_order,
                   cell_width, cell_height, created_at
            FROM sessions
            ORDER BY sort_order ASC, created_at ASC
            """
        )
        return cur.fetchall()


def get_session(session_id: str) -> sqlite3.Row | None:
    with _connect() as conn:
        cur = conn.execute(
            """
            SELECT id, title, default_title, tmux_session, port, sort_order,
                   cell_width, cell_height, created_at
            FROM sessions WHERE id = ?
            """,
            (session_id,),
        )
        return cur.fetchone()


def count_sessions() -> int:
    with _connect() as conn:
        cur = conn.execute("SELECT COUNT(*) AS n FROM sessions")
        row = cur.fetchone()
        return int(row["n"]) if row else 0


def display_title(row: sqlite3.Row) -> str:
    title = (row["title"] or "").strip()
    if title:
        return title
    default_title = (row["default_title"] or "").strip()
    if default_title:
        return default_title
    return next_default_title()


def default_title_for(row: sqlite3.Row) -> str:
    default_title = (row["default_title"] or "").strip()
    if default_title:
        return default_title
    title = (row["title"] or "").strip()
    if title:
        return title
    return next_default_title()


def update_title(session_id: str, title: str) -> None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT default_title FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            return
        default_title = (row["default_title"] or "").strip() or next_default_title()
        cleaned = title.strip() or default_title
        conn.execute(
            "UPDATE sessions SET title = ?, default_title = ? WHERE id = ?",
            (cleaned, default_title, session_id),
        )


def update_port(session_id: str, port: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET port = ? WHERE id = ?",
            (port, session_id),
        )


def delete_session(session_id: str) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def update_cell_size(session_id: str, width: int, height: int) -> None:
    width, height = clamp_cell_size(width, height)
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET cell_width = ?, cell_height = ? WHERE id = ?",
            (width, height, session_id),
        )


def update_session_order(session_ids: list[str]) -> None:
    with _connect() as conn:
        for index, session_id in enumerate(session_ids):
            conn.execute(
                "UPDATE sessions SET sort_order = ? WHERE id = ?",
                (index, session_id),
            )
