"""
Local SQLite database helper for Crypto and Stock Trading Bot 2026.
Provides an offline fallback at data/trades.db when Supabase is unreachable.
"""

import os
import sqlite3
from typing import Optional, Dict, Any, List
import pandas as pd


DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DB_PATH = os.path.join(DB_DIR, "trades.db")


def get_sqlite_connection() -> sqlite3.Connection:
    """Get or initialize SQLite database connection."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_sqlite_schema(conn)
    return conn


def init_sqlite_schema(conn: sqlite3.Connection) -> None:
    """Ensure all required tables exist in local SQLite database."""
    cursor = conn.cursor()

    # 1. Trades table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_order_id TEXT UNIQUE,
        symbol TEXT NOT NULL,
        asset_class TEXT NOT NULL,
        strategy_tag TEXT NOT NULL,
        side TEXT NOT NULL,
        qty REAL NOT NULL,
        notional REAL,
        entry_price REAL NOT NULL,
        exit_price REAL,
        entry_time TEXT NOT NULL,
        exit_time TEXT,
        status TEXT NOT NULL DEFAULT 'OPEN',
        fees REAL DEFAULT 0.0,
        realized_pnl REAL DEFAULT 0.0,
        pnl_percent REAL DEFAULT 0.0,
        stop_loss_order_id TEXT,
        take_profit_order_id TEXT,
        take_profit_price REAL,
        stop_loss_price REAL,
        estimated_tp_pnl REAL,
        estimated_tp_pct REAL,
        estimated_sl_pnl REAL,
        estimated_sl_pct REAL,
        risk_reward_ratio REAL,
        notes TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Account Snapshots table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS account_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        settled_cash REAL NOT NULL,
        portfolio_value REAL NOT NULL,
        buying_power REAL NOT NULL,
        intraday_allocated REAL DEFAULT 0.0,
        swing_allocated REAL DEFAULT 0.0,
        crypto_allocated REAL DEFAULT 0.0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 3. Orders table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alpaca_order_id TEXT UNIQUE NOT NULL,
        client_order_id TEXT,
        symbol TEXT NOT NULL,
        side TEXT NOT NULL,
        order_type TEXT NOT NULL,
        time_in_force TEXT NOT NULL,
        qty REAL,
        notional REAL,
        limit_price REAL,
        stop_price REAL,
        status TEXT NOT NULL,
        submitted_at TEXT NOT NULL,
        filled_at TEXT,
        filled_qty REAL DEFAULT 0.0,
        filled_avg_price REAL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 4. Trade Events table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trade_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        event_type TEXT NOT NULL,
        symbol TEXT,
        client_order_id TEXT,
        details TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()


def sync_supabase_to_sqlite(
    conn: sqlite3.Connection,
    trades_df: pd.DataFrame,
    snapshots_df: pd.DataFrame,
    orders_df: pd.DataFrame,
    events_df: pd.DataFrame
) -> None:
    """
    Mirror fresh data fetched from Supabase into local SQLite for offline redundancy.
    """
    try:
        if not trades_df.empty:
            df_to_save = trades_df.copy()
            for c in ["entry_time", "exit_time", "created_at"]:
                if c in df_to_save.columns:
                    df_to_save[c] = df_to_save[c].astype(str)
            df_to_save.to_sql("trades", conn, if_exists="replace", index=False)

        if not snapshots_df.empty:
            df_to_save = snapshots_df.copy()
            for c in ["timestamp", "created_at"]:
                if c in df_to_save.columns:
                    df_to_save[c] = df_to_save[c].astype(str)
            df_to_save.to_sql("account_snapshots", conn, if_exists="replace", index=False)

        if not orders_df.empty:
            df_to_save = orders_df.copy()
            for c in ["submitted_at", "filled_at", "created_at"]:
                if c in df_to_save.columns:
                    df_to_save[c] = df_to_save[c].astype(str)
            df_to_save.to_sql("orders", conn, if_exists="replace", index=False)

        if not events_df.empty:
            df_to_save = events_df.copy()
            for c in ["timestamp", "created_at"]:
                if c in df_to_save.columns:
                    df_to_save[c] = df_to_save[c].astype(str)
            if "details" in df_to_save.columns:
                df_to_save["details"] = df_to_save["details"].apply(
                    lambda x: str(x) if isinstance(x, (dict, list)) else str(x) if pd.notnull(x) else ""
                )
            df_to_save.to_sql("trade_events", conn, if_exists="replace", index=False)
            
        conn.commit()
    except Exception as e:
        # Non-blocking mirror error
        pass


def fetch_sqlite_trades(conn: sqlite3.Connection) -> pd.DataFrame:
    """Fetch all trades from local SQLite."""
    try:
        df = pd.read_sql_query("SELECT * FROM trades ORDER BY entry_time DESC", conn)
        for c in ["entry_time", "exit_time", "created_at"]:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def fetch_sqlite_snapshots(conn: sqlite3.Connection) -> pd.DataFrame:
    """Fetch account snapshots from local SQLite."""
    try:
        df = pd.read_sql_query("SELECT * FROM account_snapshots ORDER BY timestamp ASC", conn)
        for c in ["timestamp", "created_at"]:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def fetch_sqlite_orders(conn: sqlite3.Connection) -> pd.DataFrame:
    """Fetch orders from local SQLite."""
    try:
        df = pd.read_sql_query("SELECT * FROM orders ORDER BY submitted_at DESC", conn)
        for c in ["submitted_at", "filled_at", "created_at"]:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()


def fetch_sqlite_events(conn: sqlite3.Connection) -> pd.DataFrame:
    """Fetch trade events from local SQLite."""
    try:
        df = pd.read_sql_query("SELECT * FROM trade_events ORDER BY timestamp DESC", conn)
        for c in ["timestamp", "created_at"]:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce")
        return df
    except Exception:
        return pd.DataFrame()

