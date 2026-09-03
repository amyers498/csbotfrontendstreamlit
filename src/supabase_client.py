"""
Supabase client helper for Crypto and Stock Trading Bot 2026.
Handles resilient authentication, data querying, and Pandas transformations.
"""

import os
from typing import Optional, Tuple, Any, List
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

# Load local .env file
load_dotenv()

# Attempt to import supabase; handle missing dependency gracefully
try:
    from supabase import create_client, Client
    SUPABASE_INSTALLED = True
except ImportError:
    SUPABASE_INSTALLED = False
    Client = None


def sanitize_credential(val: Any) -> Optional[str]:
    """Sanitize credential by removing surrounding whitespace, quotes, and newlines."""
    if val is None:
        return None
    s = str(val).strip()
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1].strip()
    return s if s else None


def get_all_supabase_credentials() -> Tuple[Optional[str], list]:
    """
    Search for Supabase URL and all available candidate API keys across
    Streamlit secrets and environment variables.
    """
    url_keys = [
        "SUPABASE_URL",
        "NEXT_PUBLIC_SUPABASE_URL",
        "VITE_SUPABASE_URL",
        "PUBLIC_SUPABASE_URL",
    ]
    # Priority: Publishable / Anon keys first (these authenticate to PostgREST API), then Service Role / Secret keys
    key_keys = [
        "SUPABASE_PUBLISHABLE_KEY",
        "SUPABASE_ANON_KEY",
        "SUPABASE_KEY",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_SECRET_KEY",
    ]

    supabase_url = None
    candidate_keys = []

    # 1. Check Streamlit secrets first (if in Streamlit environment)
    try:
        if hasattr(st, "secrets"):
            for k in url_keys:
                if k in st.secrets:
                    val = sanitize_credential(st.secrets[k])
                    if val:
                        supabase_url = val
                        break
            for k in key_keys:
                if k in st.secrets:
                    val = sanitize_credential(st.secrets[k])
                    if val and val not in candidate_keys:
                        candidate_keys.append(val)
    except Exception:
        pass

    # 2. Check environment variables
    if not supabase_url:
        for k in url_keys:
            val = sanitize_credential(os.getenv(k))
            if val:
                supabase_url = val
                break

    for k in key_keys:
        val = sanitize_credential(os.getenv(k))
        if val and val not in candidate_keys:
            candidate_keys.append(val)

    return supabase_url, candidate_keys


def get_supabase_credentials() -> Tuple[Optional[str], Optional[str]]:
    """Return primary Supabase URL and best candidate key."""
    url, keys = get_all_supabase_credentials()
    return url, (keys[0] if keys else None)


@st.cache_resource(show_spinner=False)
def init_supabase_client() -> Tuple[Optional[Client], Optional[str]]:
    """
    Initialize and return the Supabase client instance.
    Automatically tests candidate keys to guarantee valid PostgREST authentication.
    Returns (client, error_message).
    """
    if not SUPABASE_INSTALLED:
        return None, "The 'supabase' package is not installed. Please run: pip install -r requirements.txt"

    url, candidate_keys = get_all_supabase_credentials()

    if not url or not candidate_keys:
        return None, (
            "Supabase credentials not detected. Please ensure your .env file or Streamlit Secrets contains:\n"
            "SUPABASE_URL = \"https://<your-project>.supabase.co\"\n"
            "SUPABASE_PUBLISHABLE_KEY = \"<your-publishable-or-anon-key>\""
        )

    last_error = None
    working_client = None

    # Try each candidate key until one authenticates successfully
    for key in candidate_keys:
        try:
            client = create_client(url, key)
            # Healthcheck test query
            client.table("trades").select("id").limit(1).execute()
            return client, None
        except Exception as e:
            err_str = str(e)
            last_error = err_str
            # If 401 Unregistered API key, try the next candidate key in list
            if "401" in err_str or "Unregistered API key" in err_str:
                continue
            # If other non-auth error (e.g. empty table or schema notice), connection itself is valid
            return client, None

    return None, f"Failed to authenticate with Supabase: {last_error}"


def safe_to_datetime(series: pd.Series) -> pd.Series:
    """
    Safely convert timestamp series to datetimes with ISO8601 parsing,
    handling microseconds, offsets, and mixed formats across Pandas versions.
    """
    if series is None or series.empty:
        return series
    try:
        return pd.to_datetime(series, format="ISO8601", errors="coerce")
    except Exception:
        try:
            return pd.to_datetime(series, format="mixed", errors="coerce")
        except Exception:
            return pd.to_datetime(series, errors="coerce")


def fetch_account_snapshots(client: Client, limit: int = 500) -> pd.DataFrame:
    """
    Fetch historical account snapshots sorted by timestamp ASC for the equity curve.
    """
    if client is None:
        return pd.DataFrame()

    try:
        response = (
            client.table("account_snapshots")
            .select("*")
            .order("timestamp", desc=False)
            .limit(limit)
            .execute()
        )
        data = response.data
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        if "timestamp" in df.columns:
            df["timestamp"] = safe_to_datetime(df["timestamp"])
        if "created_at" in df.columns:
            df["created_at"] = safe_to_datetime(df["created_at"])
        
        # Numeric conversions
        num_cols = [
            "settled_cash",
            "portfolio_value",
            "buying_power",
            "intraday_allocated",
            "swing_allocated",
            "crypto_allocated",
        ]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        return df
    except Exception as e:
        st.warning(f"Could not load account snapshots: {e}")
        return pd.DataFrame()


def fetch_trades(
    client: Client,
    status: Optional[str] = None,
    asset_class: Optional[str] = None,
    limit: int = 1000
) -> pd.DataFrame:
    """
    Fetch trades from public.trades with optional filters.
    """
    if client is None:
        return pd.DataFrame()

    try:
        query = client.table("trades").select("*").order("entry_time", desc=True)

        if status:
            query = query.eq("status", status.upper())
        if asset_class and asset_class.lower() != "all":
            query = query.ilike("asset_class", asset_class)

        response = query.limit(limit).execute()
        data = response.data
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        
        # Datetime conversions
        for dt_col in ["entry_time", "exit_time", "created_at"]:
            if dt_col in df.columns:
                df[dt_col] = safe_to_datetime(df[dt_col])

        # Numeric conversions
        numeric_cols = [
            "qty",
            "notional",
            "entry_price",
            "exit_price",
            "fees",
            "realized_pnl",
            "pnl_percent",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        # Target & Risk management columns (preserve None if not set)
        risk_cols = [
            "take_profit_price",
            "stop_loss_price",
            "estimated_tp_pnl",
            "estimated_tp_pct",
            "estimated_sl_pnl",
            "estimated_sl_pct",
            "risk_reward_ratio",
        ]
        for col in risk_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df
    except Exception as e:
        st.warning(f"Could not load trades: {e}")
        return pd.DataFrame()


def fetch_trade_events(
    client: Client,
    symbol: Optional[str] = None,
    limit: int = 200
) -> pd.DataFrame:
    """
    Fetch recent trade audit events from public.trade_events.
    """
    if client is None:
        return pd.DataFrame()

    try:
        query = client.table("trade_events").select("*").order("timestamp", desc=True)

        if symbol:
            query = query.eq("symbol", symbol.upper())

        response = query.limit(limit).execute()
        data = response.data
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        if "timestamp" in df.columns:
            df["timestamp"] = safe_to_datetime(df["timestamp"])

        return df
    except Exception as e:
        st.warning(f"Could not load trade events: {e}")
        return pd.DataFrame()


OPEN_ORDER_STATUSES = {
    "new",
    "accepted",
    "pending_new",
    "partially_filled",
    "open",
    "held",
    "pending_replace",
    "pending_cancel",
}


def fetch_orders(
    client: Client,
    limit: int = 500
) -> pd.DataFrame:
    """
    Fetch order submissions and lifecycle states from public.orders.
    """
    if client is None:
        return pd.DataFrame()

    try:
        query = client.table("orders").select("*").order("submitted_at", desc=True)
        response = query.limit(limit).execute()
        data = response.data
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)

        # Datetime conversions
        for dt_col in ["submitted_at", "filled_at", "created_at"]:
            if dt_col in df.columns:
                df[dt_col] = safe_to_datetime(df[dt_col])

        # Numeric conversions
        num_cols = [
            "qty",
            "notional",
            "limit_price",
            "stop_price",
            "filled_qty",
            "filled_avg_price",
        ]
        for col in num_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

        return df
    except Exception as e:
        # Table might not exist yet or have no records
        return pd.DataFrame()


