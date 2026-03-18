"""
Database layer — SQLite via Python's built-in sqlite3.
Two tables:
  flashes  — raw items from the API (deduplicated by id)
  digests  — AI-generated 15-min summaries with Chinese title + categories
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "newsdesk.db"


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS flashes (
            id          TEXT PRIMARY KEY,
            time_utc    TEXT NOT NULL,
            time_taipei TEXT NOT NULL,
            important   INTEGER DEFAULT 0,
            hot         INTEGER DEFAULT 0,
            content_en  TEXT NOT NULL,
            impact      TEXT DEFAULT '[]',
            tags        TEXT DEFAULT '[]',
            digested    INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS digests (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at   TEXT NOT NULL,                  -- Taipei time
            period_start TEXT NOT NULL,                  -- earliest flash time in this batch
            period_end   TEXT NOT NULL,                  -- latest flash time in this batch
            flash_ids    TEXT NOT NULL,                  -- JSON array of flash ids used
            title_zh     TEXT NOT NULL,
            content_zh   TEXT NOT NULL,
            content_en   TEXT NOT NULL,
            categories   TEXT DEFAULT '[]'              -- JSON array of category strings
        );

        CREATE INDEX IF NOT EXISTS idx_flashes_time ON flashes(time_utc);
        CREATE INDEX IF NOT EXISTS idx_digests_created ON digests(created_at);
        """)


# ── flashes ──────────────────────────────────────────────────────────

def insert_flash(row: dict) -> bool:
    """Insert a flash. Returns True if inserted (new), False if duplicate."""
    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO flashes
                    (id, time_utc, time_taipei, important, hot, content_en, impact, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row["id"],
                row["time_utc"],
                row["time_taipei"],
                int(row.get("important", 0)),
                int(row.get("hot", False)),
                row["content_en"],
                json.dumps(row.get("impact", []), ensure_ascii=False),
                json.dumps(row.get("tags", []), ensure_ascii=False),
            ))
            return conn.total_changes > 0
    except Exception as e:
        print(f"[db] insert_flash error: {e}")
        return False


def get_undigested_flashes() -> list:
    """Return all flashes not yet included in a digest."""
    with get_conn() as conn:
        # Add digested column if it doesn't exist (migration for existing DBs)
        try:
            conn.execute("ALTER TABLE flashes ADD COLUMN digested INTEGER DEFAULT 0")
        except Exception:
            pass
        rows = conn.execute("""
            SELECT * FROM flashes
            WHERE digested = 0
            ORDER BY time_taipei ASC
        """).fetchall()
    return [dict(r) for r in rows]


def mark_flashes_digested(flash_ids: list):
    """Mark flashes as digested so they won't be re-summarized."""
    if not flash_ids:
        return
    placeholders = ",".join("?" * len(flash_ids))
    with get_conn() as conn:
        conn.execute(
            f"UPDATE flashes SET digested = 1 WHERE id IN ({placeholders})",
            flash_ids,
        )


# ── digests ───────────────────────────────────────────────────────────

def insert_digest(d: dict):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO digests
                (created_at, period_start, period_end, flash_ids,
                 title_zh, content_zh, content_en, categories)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            d["created_at"],
            d["period_start"],
            d["period_end"],
            json.dumps(d["flash_ids"], ensure_ascii=False),
            d["title_zh"],
            d["content_zh"],
            d["content_en"],
            json.dumps(d["categories"], ensure_ascii=False),
        ))


def get_digests(limit: int = 100, category: str = None) -> list:
    """Fetch digests for the web UI, newest first."""
    with get_conn() as conn:
        if category:
            rows = conn.execute("""
                SELECT * FROM digests
                WHERE categories LIKE ?
                ORDER BY created_at DESC, id DESC LIMIT ?
            """, (f'%"{category}"%', limit)).fetchall()
        else:
            rows = conn.execute("""
                SELECT * FROM digests
                ORDER BY created_at DESC, id DESC LIMIT ?
            """, (limit,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["categories"] = json.loads(d["categories"])
        d["flash_ids"]  = json.loads(d["flash_ids"])
        result.append(d)
    return result


def get_last_updated() -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT created_at FROM digests ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return row["created_at"] if row else "—"


def get_flashes(limit: int = 200) -> list:
    """Fetch raw flashes for display, newest first."""
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT id, time_taipei, important, hot, content_en, impact, tags
            FROM flashes
            ORDER BY time_taipei DESC LIMIT ?
        """, (limit,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["impact"] = json.loads(d["impact"])
        d["tags"]   = json.loads(d["tags"])
        result.append(d)
    return result