"""
Unified Data Manager for Crypto and Stock Trading Bot 2026.
Orchestrates primary Supabase querying with automatic fallback to local SQLite (data/trades.db).
"""

from typing import Tuple, Optional
import pandas as pd
import streamlit as st

from src.supabase_client import (
    init_supabase_client,
    fetch_account_snapshots as sb_fetch_snapshots,
    fetch_trades as sb_fetch_trades,
    fetch_orders as sb_fetch_orders,
    fetch_trade_events as sb_fetch_events,
)
from src.sqlite_client import (
    get_sqlite_connection,
    sync_supabase_to_sqlite,
    fetch_sqlite_trades,
    fetch_sqlite_snapshots,
    fetch_sqlite_orders,
    fetch_sqlite_events,
)


@st.cache_data(ttl=10)
def load_dashboard_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str, bool, Optional[str]]:
    """
    Fetch all trading data. Tries Supabase cloud first; falls back seamlessly to SQLite.
    Returns:
        trades_df, snapshots_df, orders_df, events_df, source_label, is_fallback, status_message
    """
    sb_client, sb_err = init_supabase_client()

    # 1. Primary: Supabase
    if sb_client is not None:
        try:
            trades_df = sb_fetch_trades(sb_client)
            snapshots_df = sb_fetch_snapshots(sb_client)
            orders_df = sb_fetch_orders(sb_client)
            events_df = sb_fetch_events(sb_client)

            # Mirror to SQLite in background for redundancy
            try:
                conn = get_sqlite_connection()
                sync_supabase_to_sqlite(conn, trades_df, snapshots_df, orders_df, events_df)
                conn.close()
            except Exception:
                pass

            return trades_df, snapshots_df, orders_df, events_df, "Supabase Cloud", False, None
        except Exception as e:
            sb_err = str(e)

    # 2. Fallback: Local SQLite
    try:
        conn = get_sqlite_connection()
        trades_df = fetch_sqlite_trades(conn)
        snapshots_df = fetch_sqlite_snapshots(conn)
        orders_df = fetch_sqlite_orders(conn)
        events_df = fetch_sqlite_events(conn)
        conn.close()

        msg = f"Supabase offline ({sb_err}). Serving from local SQLite cache (data/trades.db)." if sb_err else "Serving from local SQLite cache."
        return trades_df, snapshots_df, orders_df, events_df, "Local SQLite (data/trades.db)", True, msg
    except Exception as sq_err:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "Offline / Error", True, f"Both Supabase ({sb_err}) and SQLite ({sq_err}) failed."

