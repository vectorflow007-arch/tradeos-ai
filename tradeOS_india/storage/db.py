"""
TradeOS India — SQLite database layer using aiosqlite.

Creates and manages 7 tables: trades, daily_summary, agent_logs,
llm_messages, strategies, settings, watchlist.
All operations are async. Never blocks the Qt main thread.
"""

import asyncio
from pathlib import Path
from typing import Any, Optional

import aiosqlite

from config.settings import get_settings
from utils.logger import get_logger

log = get_logger("storage.db")

# ─── Singleton connection ────────────────────────────────────────
_db: Optional[aiosqlite.Connection] = None


def _db_path() -> str:
    """Return the database file path from settings."""
    return get_settings().db_path


# ─── Schema DDL ──────────────────────────────────────────────────
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      TEXT NOT NULL,
    symbol        TEXT NOT NULL,
    exchange      TEXT NOT NULL,
    side          TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
    quantity      INTEGER NOT NULL,
    entry_price   REAL NOT NULL,
    exit_price    REAL,
    pnl           REAL,
    charges       REAL DEFAULT 0,
    net_pnl       REAL,
    product       TEXT NOT NULL,
    order_type    TEXT NOT NULL,
    status        TEXT NOT NULL,
    mode          TEXT NOT NULL CHECK(mode IN ('paper','live')),
    broker        TEXT NOT NULL DEFAULT 'fyers',
    strategy_name TEXT,
    agent_task_id TEXT,
    entry_time    TEXT NOT NULL,
    exit_time     TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS daily_summary (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT NOT NULL UNIQUE,
    total_pnl       REAL DEFAULT 0,
    realized_pnl    REAL DEFAULT 0,
    unrealized_pnl  REAL DEFAULT 0,
    win_trades      INTEGER DEFAULT 0,
    loss_trades     INTEGER DEFAULT 0,
    total_trades    INTEGER DEFAULT 0,
    win_rate        REAL DEFAULT 0,
    max_drawdown    REAL DEFAULT 0,
    turnover        REAL DEFAULT 0,
    charges         REAL DEFAULT 0,
    net_pnl         REAL DEFAULT 0,
    mode            TEXT NOT NULL DEFAULT 'paper',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS agent_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT NOT NULL,
    agent_name      TEXT NOT NULL,
    task_type       TEXT NOT NULL,
    input_summary   TEXT,
    output_summary  TEXT,
    llm_provider    TEXT,
    tokens_used     INTEGER DEFAULT 0,
    cost_inr        REAL DEFAULT 0,
    duration_ms     INTEGER DEFAULT 0,
    success         INTEGER NOT NULL DEFAULT 1,
    error_msg       TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS llm_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    agent_name      TEXT NOT NULL,
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    direction       TEXT NOT NULL CHECK(direction IN ('request','response')),
    system_prompt   TEXT,
    user_prompt     TEXT,
    response_text   TEXT,
    tokens_in       INTEGER DEFAULT 0,
    tokens_out      INTEGER DEFAULT 0,
    cost_inr        REAL DEFAULT 0,
    duration_ms     INTEGER DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS strategies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,
    code            TEXT NOT NULL,
    language        TEXT NOT NULL DEFAULT 'python',
    timeframe       TEXT DEFAULT '15m',
    symbols         TEXT,
    parameters      TEXT,
    status          TEXT DEFAULT 'saved',
    last_backtest   TEXT,
    sharpe          REAL,
    max_dd          REAL,
    win_rate        REAL,
    stability       REAL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key             TEXT PRIMARY KEY,
    value           TEXT NOT NULL,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS watchlist (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    exchange        TEXT NOT NULL,
    display_name    TEXT,
    segment         TEXT,
    lot_size        INTEGER DEFAULT 1,
    added_at        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(symbol, exchange)
);
"""


# ═════════════════════════════════════════════════════════════════
# Connection management
# ═════════════════════════════════════════════════════════════════

async def init_db() -> aiosqlite.Connection:
    """Initialize the database: create file, tables, and return connection.

    Returns:
        The active aiosqlite connection.
    """
    global _db
    if _db is not None:
        return _db

    db_path = _db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        _db = await aiosqlite.connect(db_path)
        _db.row_factory = aiosqlite.Row
        await _db.executescript(_SCHEMA_SQL)
        await _db.commit()
        log.info(f"Database initialized at {db_path}")
    except Exception as exc:
        log.error(f"Failed to initialize database: {exc}")
        raise

    return _db


async def get_db() -> aiosqlite.Connection:
    """Return the active database connection, initializing if needed."""
    global _db
    if _db is None:
        return await init_db()
    return _db


async def close_db() -> None:
    """Close the database connection."""
    global _db
    if _db is not None:
        try:
            await _db.close()
            log.info("Database connection closed")
        except Exception as exc:
            log.error(f"Error closing database: {exc}")
        finally:
            _db = None


# ═════════════════════════════════════════════════════════════════
# Trades
# ═════════════════════════════════════════════════════════════════

async def insert_trade(trade: dict[str, Any]) -> int:
    """Insert a new trade record.

    Args:
        trade: Dict with trade fields matching the trades table schema.

    Returns:
        The inserted row ID, or -1 on error.
    """
    try:
        db = await get_db()
        columns = [
            "order_id", "symbol", "exchange", "side", "quantity",
            "entry_price", "exit_price", "pnl", "charges", "net_pnl",
            "product", "order_type", "status", "mode", "broker",
            "strategy_name", "agent_task_id", "entry_time", "exit_time",
        ]
        present = [c for c in columns if c in trade]
        placeholders = ", ".join(["?"] * len(present))
        col_str = ", ".join(present)
        values = [trade[c] for c in present]

        cursor = await db.execute(
            f"INSERT INTO trades ({col_str}) VALUES ({placeholders})",
            values,
        )
        await db.commit()
        row_id = cursor.lastrowid
        log.debug(f"Trade inserted: id={row_id}, order_id={trade.get('order_id')}")
        return row_id
    except Exception as exc:
        log.error(f"Failed to insert trade: {exc}")
        return -1


async def update_trade(order_id: str, updates: dict[str, Any]) -> bool:
    """Update an existing trade by order_id.

    Args:
        order_id: The order ID to match.
        updates: Dict of column→value pairs to update.

    Returns:
        True if a row was updated.
    """
    try:
        db = await get_db()
        set_clauses = ", ".join([f"{k} = ?" for k in updates])
        values = list(updates.values()) + [order_id]

        cursor = await db.execute(
            f"UPDATE trades SET {set_clauses} WHERE order_id = ?",
            values,
        )
        await db.commit()
        return cursor.rowcount > 0
    except Exception as exc:
        log.error(f"Failed to update trade {order_id}: {exc}")
        return False


async def get_trades(
    from_date: str,
    to_date: str,
    mode: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Query trades within a date range.

    Args:
        from_date: Start date 'YYYY-MM-DD'.
        to_date: End date 'YYYY-MM-DD'.
        mode: Optional filter — 'paper' or 'live'.

    Returns:
        List of trade dicts.
    """
    try:
        db = await get_db()
        query = (
            "SELECT * FROM trades WHERE entry_time >= ? AND entry_time <= ?"
        )
        params: list[Any] = [from_date, to_date + " 23:59:59"]

        if mode:
            query += " AND mode = ?"
            params.append(mode)

        query += " ORDER BY entry_time DESC"

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        log.error(f"Failed to get trades: {exc}")
        return []


# ═════════════════════════════════════════════════════════════════
# Daily summary
# ═════════════════════════════════════════════════════════════════

async def get_daily_summary(date: str) -> Optional[dict[str, Any]]:
    """Get daily summary for a specific date.

    Args:
        date: Date string 'YYYY-MM-DD'.

    Returns:
        Summary dict or None if not found.
    """
    try:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM daily_summary WHERE date = ?", (date,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    except Exception as exc:
        log.error(f"Failed to get daily summary: {exc}")
        return None


async def upsert_daily_summary(date: str, data: dict[str, Any]) -> bool:
    """Insert or update daily summary for a date.

    Args:
        date: Date string 'YYYY-MM-DD'.
        data: Dict of summary fields to set.

    Returns:
        True on success.
    """
    try:
        db = await get_db()
        existing = await get_daily_summary(date)

        if existing:
            set_clauses = ", ".join([f"{k} = ?" for k in data])
            values = list(data.values()) + [date]
            await db.execute(
                f"UPDATE daily_summary SET {set_clauses} WHERE date = ?",
                values,
            )
        else:
            data["date"] = date
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            await db.execute(
                f"INSERT INTO daily_summary ({columns}) VALUES ({placeholders})",
                list(data.values()),
            )

        await db.commit()
        return True
    except Exception as exc:
        log.error(f"Failed to upsert daily summary: {exc}")
        return False


# ═════════════════════════════════════════════════════════════════
# Agent logs
# ═════════════════════════════════════════════════════════════════

async def insert_agent_log(log_entry: dict[str, Any]) -> int:
    """Insert an agent activity log entry.

    Args:
        log_entry: Dict with agent_logs table fields.

    Returns:
        Inserted row ID, or -1 on error.
    """
    try:
        db = await get_db()
        columns = [
            "task_id", "agent_name", "task_type", "input_summary",
            "output_summary", "llm_provider", "tokens_used", "cost_inr",
            "duration_ms", "success", "error_msg",
        ]
        present = [c for c in columns if c in log_entry]
        placeholders = ", ".join(["?"] * len(present))
        col_str = ", ".join(present)
        values = [log_entry[c] for c in present]

        cursor = await db.execute(
            f"INSERT INTO agent_logs ({col_str}) VALUES ({placeholders})",
            values,
        )
        await db.commit()
        return cursor.lastrowid
    except Exception as exc:
        log.error(f"Failed to insert agent log: {exc}")
        return -1


# ═════════════════════════════════════════════════════════════════
# LLM messages
# ═════════════════════════════════════════════════════════════════

async def insert_llm_message(msg: dict[str, Any]) -> int:
    """Insert an LLM request/response message.

    Args:
        msg: Dict with llm_messages table fields.

    Returns:
        Inserted row ID, or -1 on error.
    """
    try:
        db = await get_db()
        columns = [
            "session_id", "agent_name", "provider", "model", "direction",
            "system_prompt", "user_prompt", "response_text",
            "tokens_in", "tokens_out", "cost_inr", "duration_ms",
        ]
        present = [c for c in columns if c in msg]
        placeholders = ", ".join(["?"] * len(present))
        col_str = ", ".join(present)
        values = [msg[c] for c in present]

        cursor = await db.execute(
            f"INSERT INTO llm_messages ({col_str}) VALUES ({placeholders})",
            values,
        )
        await db.commit()
        return cursor.lastrowid
    except Exception as exc:
        log.error(f"Failed to insert LLM message: {exc}")
        return -1


async def get_llm_messages(session_id: str) -> list[dict[str, Any]]:
    """Get all LLM messages for a session.

    Args:
        session_id: Session identifier.

    Returns:
        List of message dicts ordered by creation time.
    """
    try:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM llm_messages WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        log.error(f"Failed to get LLM messages: {exc}")
        return []


# ═════════════════════════════════════════════════════════════════
# Strategies
# ═════════════════════════════════════════════════════════════════

async def get_strategies() -> list[dict[str, Any]]:
    """Get all saved strategies.

    Returns:
        List of strategy dicts ordered by updated_at desc.
    """
    try:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM strategies ORDER BY updated_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        log.error(f"Failed to get strategies: {exc}")
        return []


async def upsert_strategy(strategy: dict[str, Any]) -> bool:
    """Insert or update a strategy by name.

    Args:
        strategy: Dict with strategy fields. Must include 'name' and 'code'.

    Returns:
        True on success.
    """
    try:
        db = await get_db()
        name = strategy["name"]

        cursor = await db.execute(
            "SELECT id FROM strategies WHERE name = ?", (name,)
        )
        existing = await cursor.fetchone()

        if existing:
            updatable = {
                k: v for k, v in strategy.items() if k not in ("id", "name", "created_at")
            }
            updatable["updated_at"] = "datetime('now')"
            set_parts = []
            values = []
            for k, v in updatable.items():
                if v == "datetime('now')":
                    set_parts.append(f"{k} = datetime('now')")
                else:
                    set_parts.append(f"{k} = ?")
                    values.append(v)
            values.append(name)
            await db.execute(
                f"UPDATE strategies SET {', '.join(set_parts)} WHERE name = ?",
                values,
            )
        else:
            columns = [
                "name", "description", "code", "language", "timeframe",
                "symbols", "parameters", "status",
            ]
            present = [c for c in columns if c in strategy]
            placeholders = ", ".join(["?"] * len(present))
            col_str = ", ".join(present)
            values = [strategy[c] for c in present]

            await db.execute(
                f"INSERT INTO strategies ({col_str}) VALUES ({placeholders})",
                values,
            )

        await db.commit()
        return True
    except Exception as exc:
        log.error(f"Failed to upsert strategy: {exc}")
        return False


# ═════════════════════════════════════════════════════════════════
# Settings (key-value store)
# ═════════════════════════════════════════════════════════════════

async def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get a setting value by key.

    Args:
        key: Setting key.
        default: Default value if not found.

    Returns:
        Setting value string or default.
    """
    try:
        db = await get_db()
        cursor = await db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        )
        row = await cursor.fetchone()
        return row["value"] if row else default
    except Exception as exc:
        log.error(f"Failed to get setting '{key}': {exc}")
        return default


async def set_setting(key: str, value: str) -> bool:
    """Set a setting value (insert or update).

    Args:
        key: Setting key.
        value: Setting value.

    Returns:
        True on success.
    """
    try:
        db = await get_db()
        await db.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = datetime('now')",
            (key, value),
        )
        await db.commit()
        return True
    except Exception as exc:
        log.error(f"Failed to set setting '{key}': {exc}")
        return False


# ═════════════════════════════════════════════════════════════════
# Watchlist
# ═════════════════════════════════════════════════════════════════

async def get_watchlist() -> list[dict[str, Any]]:
    """Get all watchlist entries.

    Returns:
        List of watchlist item dicts.
    """
    try:
        db = await get_db()
        cursor = await db.execute(
            "SELECT * FROM watchlist ORDER BY added_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:
        log.error(f"Failed to get watchlist: {exc}")
        return []


async def add_to_watchlist(
    symbol: str,
    exchange: str,
    display_name: Optional[str] = None,
    segment: Optional[str] = None,
    lot_size: int = 1,
) -> bool:
    """Add a symbol to the watchlist.

    Args:
        symbol: Trading symbol.
        exchange: Exchange code (NSE, BSE, etc.).
        display_name: Optional display name.
        segment: Optional segment.
        lot_size: Lot size, default 1.

    Returns:
        True on success, False if already exists or error.
    """
    try:
        db = await get_db()
        await db.execute(
            "INSERT OR IGNORE INTO watchlist "
            "(symbol, exchange, display_name, segment, lot_size) "
            "VALUES (?, ?, ?, ?, ?)",
            (symbol, exchange, display_name, segment, lot_size),
        )
        await db.commit()
        return True
    except Exception as exc:
        log.error(f"Failed to add to watchlist: {exc}")
        return False


async def remove_from_watchlist(symbol: str, exchange: str) -> bool:
    """Remove a symbol from the watchlist.

    Args:
        symbol: Trading symbol.
        exchange: Exchange code.

    Returns:
        True if a row was deleted.
    """
    try:
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM watchlist WHERE symbol = ? AND exchange = ?",
            (symbol, exchange),
        )
        await db.commit()
        return cursor.rowcount > 0
    except Exception as exc:
        log.error(f"Failed to remove from watchlist: {exc}")
        return False


__all__ = [
    "init_db",
    "get_db",
    "close_db",
    "insert_trade",
    "update_trade",
    "get_trades",
    "get_daily_summary",
    "upsert_daily_summary",
    "insert_agent_log",
    "insert_llm_message",
    "get_llm_messages",
    "get_strategies",
    "upsert_strategy",
    "get_setting",
    "set_setting",
    "get_watchlist",
    "add_to_watchlist",
    "remove_from_watchlist",
]
