"""
Crypto and Stock Trading Bot 2026 - Streamlit Frontend Dashboard
Real-time tracking of portfolio equity, open positions, trade history, and audit events from Supabase.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from src.supabase_client import (
    init_supabase_client,
    get_supabase_credentials,
    fetch_account_snapshots,
    fetch_trades,
    fetch_trade_events,
    fetch_orders,
    OPEN_ORDER_STATUSES,
)
from src.trade_reconciliation import reconcile_trades_and_positions
from src.market_data import fetch_live_price
from src.trade_card_ui import format_trade_card_html

# -----------------------------------------------------------------------------
# Page Configuration & Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Crypto & Stock Bot 2026",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for modern dark trading terminal look
st.markdown(
    """
    <style>
    /* Metric Card Styling */
    div[data-testid="stMetric"] {
        background-color: #1a1e29;
        border: 1px solid #2d3748;
        border-radius: 8px;
        padding: 12px 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.82rem;
        color: #a0aec0;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.45rem;
        font-weight: 700;
        color: #f7fafc;
    }

    /* Status Badges */
    .badge-buy {
        background-color: rgba(16, 185, 129, 0.2);
        color: #10b981;
        border: 1px solid #10b981;
        border-radius: 4px;
        padding: 2px 8px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-sell {
        background-color: rgba(239, 68, 68, 0.2);
        color: #ef4444;
        border: 1px solid #ef4444;
        border-radius: 4px;
        padding: 2px 8px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-open {
        background-color: rgba(59, 130, 246, 0.2);
        color: #60a5fa;
        border: 1px solid #3b82f6;
        border-radius: 4px;
        padding: 2px 8px;
        font-weight: 600;
        font-size: 0.8rem;
    }

    /* Clean spacing */
    .block-container {
        padding-top: 1.8rem;
        padding-bottom: 2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# Supabase Connection
# -----------------------------------------------------------------------------
client, conn_err = init_supabase_client()
url, _ = get_supabase_credentials()

# -----------------------------------------------------------------------------
# Sidebar Configuration & Filters
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 🤖 Trading Bot 2026")
    st.caption("Crypto & Stock Algorithmic Trading")

    # Connection Status indicator
    if client:
        masked_url = url.split("//")[-1].split(".")[0] if url else "connected"
        st.success(f"🟢 Supabase Connected (`{masked_url}`)", icon="✅")
    else:
        st.error("🔴 Supabase Disconnected", icon="⚠️")
        if conn_err:
            st.info(conn_err)

    st.markdown("---")
    st.subheader("⚙️ Dashboard Controls")

    # Auto Refresh / Manual Refresh
    col_ref1, col_ref2 = st.columns([1, 1])
    with col_ref1:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # Asset Class Filter
    selected_asset = st.selectbox(
        "Asset Class",
        options=["All", "Crypto", "Stock"],
        index=0,
    )

    # Auto-refresh option (using st.rerun via timer if enabled)
    auto_refresh = st.checkbox("Auto-refresh (30s)", value=False)
    if auto_refresh:
        st.caption("Auto-refresh active")

    st.markdown("---")
    st.subheader("🛡️ Position Reconciliation")
    tracking_mode = st.radio(
        "Position Tracking Mode",
        options=["Reconciled Net Positions", "Raw Order Fills"],
        index=0,
        help="Reconciled mode automatically pairs BUY and SELL orders into completed round-trips, computes true Realized PnL, and filters out fee/crypto dust (< $1.00)."
    )
    dust_threshold = st.number_input(
        "Dust Filter ($)",
        min_value=0.01,
        max_value=10.0,
        value=1.00,
        step=0.25,
        help="Ignore remnant balances smaller than this dollar value when an asset was bought and sold."
    )

    st.markdown("---")
    st.markdown(
        """
        <small style='color: #718096;'>
        Bot Version: 2026.1<br>
        Tables: trades, trade_events, account_snapshots
        </small>
        """,
        unsafe_allow_html=True,
    )

# -----------------------------------------------------------------------------
# Data Loading
# -----------------------------------------------------------------------------
if client:
    with st.spinner("Fetching data from Supabase..."):
        snapshots_df = fetch_account_snapshots(client, limit=500)
        trades_df = fetch_trades(client, limit=1000)
        events_df = fetch_trade_events(client, limit=300)
        orders_df = fetch_orders(client, limit=500)
else:
    snapshots_df = pd.DataFrame()
    trades_df = pd.DataFrame()
    events_df = pd.DataFrame()
    orders_df = pd.DataFrame()

# Separate Working (Open) and Terminal (Closed) Orders
open_orders = pd.DataFrame()
closed_orders = pd.DataFrame()
if not orders_df.empty and "status" in orders_df.columns:
    open_orders = orders_df[orders_df["status"].str.lower().isin(OPEN_ORDER_STATUSES)]
    closed_orders = orders_df[~orders_df["status"].str.lower().isin(OPEN_ORDER_STATUSES)]

# Apply Asset Class filter to trades if selected
filtered_trades = trades_df.copy()
if not filtered_trades.empty and selected_asset != "All":
    if "asset_class" in filtered_trades.columns:
        filtered_trades = filtered_trades[
            filtered_trades["asset_class"].str.lower() == selected_asset.lower()
        ]

# Separate Open and Closed Trades
open_trades = pd.DataFrame()
closed_trades = pd.DataFrame()

if not filtered_trades.empty:
    if tracking_mode == "Reconciled Net Positions":
        open_trades, closed_trades = reconcile_trades_and_positions(
            filtered_trades, dust_threshold_usd=dust_threshold
        )
    else:
        if "status" in filtered_trades.columns:
            open_trades = filtered_trades[filtered_trades["status"].str.upper() == "OPEN"]
            closed_trades = filtered_trades[filtered_trades["status"].str.upper() != "OPEN"]

# -----------------------------------------------------------------------------
# Header & Executive KPI Metrics
# -----------------------------------------------------------------------------
st.title("📈 Crypto & Stock Trading Bot 2026")
st.markdown("Live command center for automated crypto and equity trading strategies.")

# Calculate Top-Level KPIs with Real-Time Adjustment
latest_snapshot = snapshots_df.iloc[-1] if not snapshots_df.empty else None
initial_snapshot = snapshots_df.iloc[0] if not snapshots_df.empty else None

base_portfolio_val = latest_snapshot["portfolio_value"] if latest_snapshot is not None else 0.0
base_settled_cash = latest_snapshot["settled_cash"] if latest_snapshot is not None else 0.0
base_buying_power = latest_snapshot["buying_power"] if latest_snapshot is not None else 0.0
snapshot_time = latest_snapshot["timestamp"] if latest_snapshot is not None else None

# Check for any Realized PnL from trades closed AFTER the last snapshot
pnl_since_snapshot = 0.0
post_snap_count = 0
if snapshot_time is not None and not closed_trades.empty and "exit_time" in closed_trades.columns:
    st_time = snapshot_time
    if st_time.tzinfo is None and closed_trades["exit_time"].dt.tz is not None:
        st_time = st_time.tz_localize("UTC")
    post_snap_trades = closed_trades[closed_trades["exit_time"] > st_time]
    if not post_snap_trades.empty and "realized_pnl" in post_snap_trades.columns:
        pnl_since_snapshot = float(post_snap_trades["realized_pnl"].sum())
        post_snap_count = len(post_snap_trades)

# Live Adjusted Portfolio Metrics
portfolio_val = base_portfolio_val + pnl_since_snapshot
settled_cash = base_settled_cash + pnl_since_snapshot
buying_power = base_buying_power + pnl_since_snapshot

# Calculate Overall Delta vs Initial Starting Capital
port_delta = None
if initial_snapshot is not None:
    initial_val = float(initial_snapshot["portfolio_value"])
    diff = portfolio_val - initial_val
    diff_pct = (diff / initial_val * 100) if initial_val > 0 else 0.0
    port_delta = f"{diff:+,.2f} ({diff_pct:+.2f}%) Overall"

# Realized PnL & Win Rate from closed trades
total_realized_pnl = 0.0
win_rate = 0.0
total_closed = len(closed_trades)
winning_trades = 0

if not closed_trades.empty:
    if "realized_pnl" in closed_trades.columns:
        total_realized_pnl = closed_trades["realized_pnl"].sum()
        winning_trades = (closed_trades["realized_pnl"] > 0).sum()
        win_rate = (winning_trades / total_closed * 100) if total_closed > 0 else 0.0

total_open_positions = len(open_trades)
total_open_notional = 0.0
if not open_trades.empty and "notional" in open_trades.columns:
    total_open_notional = open_trades["notional"].sum()

# Render Top KPI Row
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric(
    "Portfolio Value",
    f"${portfolio_val:,.2f}" if portfolio_val else "$0.00",
    delta=port_delta,
)
kpi2.metric(
    "Settled Cash",
    f"${settled_cash:,.2f}" if settled_cash else "$0.00",
)
kpi3.metric(
    "Buying Power",
    f"${buying_power:,.2f}" if buying_power else "$0.00",
)
kpi4.metric(
    "Total Realized PnL",
    f"${total_realized_pnl:+,.2f}",
    delta=f"{win_rate:.1f}% Win Rate ({winning_trades}/{total_closed})" if total_closed > 0 else None,
)
kpi5.metric(
    "Active Positions",
    f"{total_open_positions}",
    delta=f"${total_open_notional:,.2f} at Risk" if total_open_notional > 0 else "0 Open Exposure",
)

# Live adjustment banner if trades occurred after the snapshot
if pnl_since_snapshot != 0.0:
    st.caption(
        f"⚡ **Live Adjusted Equity**: Reflects **{pnl_since_snapshot:+,.4f}** from {post_snap_count} trade(s) "
        f"closed since the last DB snapshot ({snapshot_time.strftime('%H:%M:%S')} UTC)."
    )
elif snapshot_time is not None:
    st.caption(f"⏱️ **Account Snapshot**: Last DB record at **{snapshot_time.strftime('%H:%M:%S')} UTC**.")

st.markdown("---")

# -----------------------------------------------------------------------------
# Main Tabs Layout
# -----------------------------------------------------------------------------
tab_exec, tab_active, tab_orders, tab_history, tab_events = st.tabs([
    "📊 Executive Dashboard",
    f"⚡ Active Positions ({total_open_positions})",
    f"📝 Orders ({len(open_orders)} Open)",
    f"📜 Trade History ({total_closed})",
    f"🔍 Audit & Events ({len(events_df)})",
])

# -----------------------------------------------------------------------------
# TAB 1: EXECUTIVE DASHBOARD
# -----------------------------------------------------------------------------
with tab_exec:
    col_chart_left, col_chart_right = st.columns([2.2, 1])

    with col_chart_left:
        st.subheader("📈 Portfolio Equity Curve")
        if not snapshots_df.empty and "timestamp" in snapshots_df.columns:
            fig_equity = go.Figure()
            
            # Portfolio Value line
            fig_equity.add_trace(
                go.Scatter(
                    x=snapshots_df["timestamp"],
                    y=snapshots_df["portfolio_value"],
                    mode="lines+markers",
                    name="Portfolio Value",
                    line=dict(color="#3b82f6", width=2.5),
                    hovertemplate="%{x|%b %d %H:%M}<br>Portfolio: $%{y:,.2f}<extra></extra>",
                )
            )
            # Settled Cash line
            fig_equity.add_trace(
                go.Scatter(
                    x=snapshots_df["timestamp"],
                    y=snapshots_df["settled_cash"],
                    mode="lines",
                    name="Settled Cash",
                    line=dict(color="#10b981", width=1.5, dash="dot"),
                    hovertemplate="%{x|%b %d %H:%M}<br>Cash: $%{y:,.2f}<extra></extra>",
                )
            )
            # Buying Power line
            if "buying_power" in snapshots_df.columns:
                fig_equity.add_trace(
                    go.Scatter(
                        x=snapshots_df["timestamp"],
                        y=snapshots_df["buying_power"],
                        mode="lines",
                        name="Buying Power",
                        line=dict(color="#a855f7", width=1.2, dash="dash"),
                        hovertemplate="%{x|%b %d %H:%M}<br>Buying Power: $%{y:,.2f}<extra></extra>",
                    )
                )

            fig_equity.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=20, b=20),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                xaxis=dict(showgrid=True, gridcolor="#2d3748"),
                yaxis=dict(showgrid=True, gridcolor="#2d3748", tickprefix="$"),
                height=350,
            )
            st.plotly_chart(fig_equity, use_container_width=True)
        else:
            st.info(
                "No snapshot data recorded in `account_snapshots` yet. Once your trading bot records snapshots, "
                "the equity curve will populate automatically."
            )

    with col_chart_right:
        st.subheader("🎯 Capital Allocation")
        if latest_snapshot is not None:
            alloc_labels = ["Cash", "Crypto", "Intraday Stocks", "Swing Stocks"]
            alloc_values = [
                max(0.0, float(latest_snapshot.get("settled_cash", 0.0))),
                max(0.0, float(latest_snapshot.get("crypto_allocated", 0.0))),
                max(0.0, float(latest_snapshot.get("intraday_allocated", 0.0))),
                max(0.0, float(latest_snapshot.get("swing_allocated", 0.0))),
            ]
            
            # If all are 0, fallback to portfolio_value or display placeholder
            if sum(alloc_values) == 0 and portfolio_val > 0:
                alloc_labels = ["Cash"]
                alloc_values = [portfolio_val]

            fig_alloc = px.pie(
                names=alloc_labels,
                values=alloc_values,
                hole=0.55,
                color_discrete_sequence=["#10b981", "#f59e0b", "#3b82f6", "#8b5cf6"],
            )
            fig_alloc.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(orientation="h", yanchor="bottom", y=-0.2),
                height=350,
            )
            st.plotly_chart(fig_alloc, use_container_width=True)
        else:
            st.info("Awaiting snapshot records for capital allocation breakdown.")

    # Recent Activity Row
    st.markdown("### ⏱️ Recent Trade Activity")
    if not filtered_trades.empty:
        recent_preview = filtered_trades.head(5)[[
            "symbol", "asset_class", "side", "qty", "entry_price", "status", "entry_time", "realized_pnl"
        ]].copy()
        
        # Format columns for crisp display
        if "entry_time" in recent_preview.columns:
            recent_preview["entry_time"] = recent_preview["entry_time"].dt.strftime("%Y-%m-%d %H:%M:%S")
        if "entry_price" in recent_preview.columns:
            recent_preview["entry_price"] = recent_preview["entry_price"].map("${:,.2f}".format)
        if "realized_pnl" in recent_preview.columns:
            recent_preview["realized_pnl"] = recent_preview["realized_pnl"].map("${:+,.2f}".format)

        st.dataframe(recent_preview, use_container_width=True, hide_index=True)
    else:
        st.info("No trades found in `trades` table.")

# -----------------------------------------------------------------------------
# TAB 2: ACTIVE POSITIONS
# -----------------------------------------------------------------------------
with tab_active:
    st.subheader("⚡ Currently Open Positions")
    if tracking_mode == "Reconciled Net Positions":
        st.caption(
            f"🛡️ **Reconciled Net Tracking**: Closed round-trips (bought then sold) are automatically cleared. "
            f"Crypto fee/dust remnants below ${dust_threshold:.2f} are recognized as closed."
        )

    if not open_orders.empty:
        st.info(f"⏳ **Active Orders on Alpaca**: You currently have **{len(open_orders)} open/working order(s)** (check the **📝 Orders** tab for details).")

    if not open_trades.empty:
        # Mini metrics for open positions
        op_col1, op_col2, op_col3, op_col4 = st.columns([1, 1, 1, 1.5])
        long_count = (open_trades["side"].str.upper() == "BUY").sum() if "side" in open_trades.columns else 0
        short_count = (open_trades["side"].str.upper() == "SELL").sum() if "side" in open_trades.columns else 0
        
        op_col1.metric("Long Positions", f"{long_count}")
        op_col2.metric("Short Positions", f"{short_count}")
        op_col3.metric("Total Open Notional", f"${total_open_notional:,.2f}")
        with op_col4:
            active_view_style = st.radio(
                "Display Mode",
                ["Visual Trade Cards", "Spreadsheet Table"],
                horizontal=True,
                key="active_view_style",
            )

        if active_view_style == "Visual Trade Cards":
            st.markdown("---")
            for _, row in open_trades.iterrows():
                live_price = fetch_live_price(row["symbol"])
                card_html = format_trade_card_html(row.to_dict(), live_price=live_price, is_active=True)
                st.markdown(card_html, unsafe_allow_html=True)
        else:
            display_open = open_trades.copy()
            display_open_cols = [
                "id", "symbol", "asset_class", "side", "qty", "entry_price",
                "notional", "take_profit_price", "stop_loss_price",
                "estimated_tp_pnl", "estimated_sl_pnl", "risk_reward_ratio",
                "strategy_tag", "entry_time", "notes"
            ]
            available_open_cols = [c for c in display_open_cols if c in display_open.columns]
            
            # Display formatted table
            st.dataframe(
                display_open[available_open_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "entry_price": st.column_config.NumberColumn("Entry Price", format="$%.4f"),
                    "notional": st.column_config.NumberColumn("Notional", format="$%.2f"),
                    "qty": st.column_config.NumberColumn("Quantity", format="%.6f"),
                    "take_profit_price": st.column_config.NumberColumn("Target Price", format="$%.4f"),
                    "stop_loss_price": st.column_config.NumberColumn("Stop Price", format="$%.4f"),
                    "estimated_tp_pnl": st.column_config.NumberColumn("Target Profit ($)", format="$%.2f"),
                    "estimated_sl_pnl": st.column_config.NumberColumn("Max Risk ($)", format="$%.2f"),
                    "risk_reward_ratio": st.column_config.NumberColumn("R:R", format="1:%.1f"),
                    "entry_time": st.column_config.DatetimeColumn("Entry Time", format="YYYY-MM-DD HH:mm:ss"),
                },
            )
    else:
        st.info("No open positions at this time. The bot is currently 100% in cash or waiting for signals.")

# -----------------------------------------------------------------------------
# TAB 3: ORDERS & WORKING LIMIT/STOP ORDERS
# -----------------------------------------------------------------------------
with tab_orders:
    st.subheader("📝 Alpaca Order Book & Working Orders")
    st.caption("Live order tracking directly from `public.orders` for limit targets, stops, and execution lifecycle.")

    total_orders = len(orders_df)
    open_count = len(open_orders)
    filled_count = (orders_df["status"].str.lower() == "filled").sum() if not orders_df.empty and "status" in orders_df.columns else 0
    canceled_count = (orders_df["status"].str.lower() == "canceled").sum() if not orders_df.empty and "status" in orders_df.columns else 0

    # Summary KPI row
    ord_kpi1, ord_kpi2, ord_kpi3, ord_kpi4 = st.columns(4)
    ord_kpi1.metric("Working / Open Orders", f"{open_count}")
    ord_kpi2.metric("Filled Orders", f"{filled_count}")
    ord_kpi3.metric("Canceled Orders", f"{canceled_count}")
    ord_kpi4.metric("Total Logged Orders", f"{total_orders}")

    st.markdown("---")

    # Section 1: Working Orders
    st.markdown("### ⏳ Active / Working Orders")
    if not open_orders.empty:
        st.caption("Orders currently active on Alpaca waiting for price targets (Limit, Stop, etc.).")

        display_open_orders = open_orders.copy()
        open_cols = [
            "id", "symbol", "side", "order_type", "status", "qty", "notional",
            "limit_price", "stop_price", "filled_qty", "time_in_force",
            "submitted_at", "alpaca_order_id", "client_order_id"
        ]
        avail_open_cols = [c for c in open_cols if c in display_open_orders.columns]

        st.dataframe(
            display_open_orders[avail_open_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "side": st.column_config.TextColumn("Side"),
                "order_type": st.column_config.TextColumn("Type"),
                "status": st.column_config.TextColumn("Status"),
                "limit_price": st.column_config.NumberColumn("Limit Price", format="$%.4f"),
                "stop_price": st.column_config.NumberColumn("Stop Price", format="$%.4f"),
                "notional": st.column_config.NumberColumn("Notional", format="$%.2f"),
                "qty": st.column_config.NumberColumn("Quantity", format="%.6f"),
                "filled_qty": st.column_config.NumberColumn("Filled Qty", format="%.6f"),
                "submitted_at": st.column_config.DatetimeColumn("Submitted At", format="YYYY-MM-DD HH:mm:ss"),
            },
        )
    else:
        st.success("🟢 No working or pending orders currently open. All orders are filled, canceled, or expired.")

    st.markdown("---")

    # Section 2: All Orders History
    st.markdown("### 📋 All Order Submissions & Lifecycle History")
    if not orders_df.empty:
        # Filters for orders history
        ord_f1, ord_f2 = st.columns([1, 2])
        with ord_f1:
            all_statuses = ["All"] + sorted(orders_df["status"].dropna().unique().tolist())
            selected_status = st.selectbox("Filter Status", options=all_statuses, index=0)
        with ord_f2:
            order_sym_search = st.text_input("Search Symbol (e.g. ETH/USD)", key="order_sym_search").strip().upper()

        filtered_orders_df = orders_df.copy()
        if selected_status != "All":
            filtered_orders_df = filtered_orders_df[filtered_orders_df["status"] == selected_status]
        if order_sym_search:
            filtered_orders_df = filtered_orders_df[
                filtered_orders_df["symbol"].str.contains(order_sym_search, case=False, na=False)
            ]

        all_order_cols = [
            "id", "symbol", "side", "order_type", "status", "qty", "notional",
            "limit_price", "stop_price", "filled_qty", "filled_avg_price",
            "submitted_at", "filled_at", "time_in_force", "alpaca_order_id", "client_order_id"
        ]
        avail_all_cols = [c for c in all_order_cols if c in filtered_orders_df.columns]

        st.dataframe(
            filtered_orders_df[avail_all_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "limit_price": st.column_config.NumberColumn("Limit Price", format="$%.4f"),
                "stop_price": st.column_config.NumberColumn("Stop Price", format="$%.4f"),
                "filled_avg_price": st.column_config.NumberColumn("Fill Avg Price", format="$%.4f"),
                "notional": st.column_config.NumberColumn("Notional", format="$%.2f"),
                "qty": st.column_config.NumberColumn("Quantity", format="%.6f"),
                "filled_qty": st.column_config.NumberColumn("Filled Qty", format="%.6f"),
                "submitted_at": st.column_config.DatetimeColumn("Submitted At", format="YYYY-MM-DD HH:mm:ss"),
                "filled_at": st.column_config.DatetimeColumn("Filled At", format="YYYY-MM-DD HH:mm:ss"),
            },
        )
    else:
        st.info("No order history records found in `orders` table.")

# -----------------------------------------------------------------------------
# TAB 4: TRADE HISTORY & PERFORMANCE ANALYTICS
# -----------------------------------------------------------------------------
with tab_history:
    st.subheader("📜 Historical Closed Trades & Strategy Breakdown")
    if not closed_trades.empty:
        # Cumulative PnL Curve
        if "realized_pnl" in closed_trades.columns:
            sorted_closed = closed_trades.sort_values("exit_time", ascending=True).copy()
            sorted_closed["cumulative_pnl"] = sorted_closed["realized_pnl"].cumsum()

            fig_pnl = px.line(
                sorted_closed,
                x="exit_time" if "exit_time" in sorted_closed.columns else sorted_closed.index,
                y="cumulative_pnl",
                title="Cumulative Realized PnL ($)",
                labels={"cumulative_pnl": "Realized PnL ($)", "exit_time": "Exit Date"},
                markers=True,
            )
            fig_pnl.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(showgrid=True, gridcolor="#2d3748", tickprefix="$"),
                xaxis=dict(showgrid=True, gridcolor="#2d3748"),
                height=300,
            )
            st.plotly_chart(fig_pnl, use_container_width=True)

        # Strategy Performance Leaderboard
        st.markdown("#### 🏆 Performance by Strategy")
        if "strategy_tag" in closed_trades.columns and "realized_pnl" in closed_trades.columns:
            strat_summary = closed_trades.groupby("strategy_tag").agg(
                trades_count=("id", "count"),
                total_pnl=("realized_pnl", "sum"),
                avg_pnl_pct=("pnl_percent", "mean"),
                win_count=("realized_pnl", lambda x: (x > 0).sum()),
            ).reset_index()
            strat_summary["win_rate"] = (
                strat_summary["win_count"] / strat_summary["trades_count"] * 100
            )

            st.dataframe(
                strat_summary,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "strategy_tag": "Strategy",
                    "trades_count": "Total Trades",
                    "total_pnl": st.column_config.NumberColumn("Total Realized PnL", format="$%.2f"),
                    "avg_pnl_pct": st.column_config.NumberColumn("Avg PnL %", format="%.2f%%"),
                    "win_rate": st.column_config.NumberColumn("Win Rate", format="%.1f%%"),
                    "win_count": "Wins",
                },
            )

        # Full Closed Trades Table / Cards
        col_h1, col_h2 = st.columns([2.5, 1.5])
        with col_h1:
            st.markdown("#### 📋 All Closed Trades")
        with col_h2:
            hist_style = st.radio("History Display", ["Spreadsheet Table", "Visual Closed Cards"], horizontal=True, key="hist_style")

        if hist_style == "Visual Closed Cards":
            for _, row in closed_trades.iterrows():
                card_html = format_trade_card_html(row.to_dict(), is_active=False)
                st.markdown(card_html, unsafe_allow_html=True)
        else:
            hist_cols = [
                "id", "symbol", "asset_class", "strategy_tag", "side", "qty",
                "entry_price", "exit_price", "realized_pnl", "pnl_percent",
                "take_profit_price", "stop_loss_price", "risk_reward_ratio",
                "fees", "entry_time", "exit_time"
            ]
            available_hist_cols = [c for c in hist_cols if c in closed_trades.columns]

            st.dataframe(
                closed_trades[available_hist_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "entry_price": st.column_config.NumberColumn("Entry Price", format="$%.4f"),
                    "exit_price": st.column_config.NumberColumn("Exit Price", format="$%.4f"),
                    "realized_pnl": st.column_config.NumberColumn("Realized PnL", format="$%.2f"),
                    "pnl_percent": st.column_config.NumberColumn("PnL %", format="%.2f%%"),
                    "take_profit_price": st.column_config.NumberColumn("Target Price", format="$%.4f"),
                    "stop_loss_price": st.column_config.NumberColumn("Stop Price", format="$%.4f"),
                    "risk_reward_ratio": st.column_config.NumberColumn("R:R", format="1:%.1f"),
                    "fees": st.column_config.NumberColumn("Fees", format="$%.2f"),
                    "entry_time": st.column_config.DatetimeColumn("Entry Time", format="YYYY-MM-DD HH:mm:ss"),
                    "exit_time": st.column_config.DatetimeColumn("Exit Time", format="YYYY-MM-DD HH:mm:ss"),
                },
            )

        # Raw executions expander for auditing
        with st.expander("🔍 View Raw Individual Order Executions (from Supabase)"):
            st.caption("Individual fills as logged by the bot/broker before round-trip matching.")
            st.dataframe(filtered_trades, use_container_width=True, hide_index=True)
    else:
        st.info("No closed trades recorded yet.")

        if not filtered_trades.empty:
            with st.expander("🔍 View Raw Order Executions"):
                st.dataframe(filtered_trades, use_container_width=True, hide_index=True)

# -----------------------------------------------------------------------------
# TAB 4: AUDIT EVENTS & BOT LOGS
# -----------------------------------------------------------------------------
with tab_events:
    st.subheader("🔍 Bot Event Stream & Audit Trail")
    st.caption("Live operational logs from `trade_events` including order submissions, signal triggers, and fills.")

    if not events_df.empty:
        # Event type filter
        col_ev1, col_ev2 = st.columns([1, 2])
        with col_ev1:
            all_event_types = ["All"] + sorted(events_df["event_type"].dropna().unique().tolist())
            selected_event = st.selectbox("Filter Event Type", options=all_event_types)

        with col_ev2:
            search_symbol = st.text_input("Filter by Symbol (e.g. BTC/USD, AAPL)", "").strip().upper()

        filtered_events = events_df.copy()
        if selected_event != "All":
            filtered_events = filtered_events[filtered_events["event_type"] == selected_event]
        if search_symbol:
            filtered_events = filtered_events[
                filtered_events["symbol"].str.contains(search_symbol, case=False, na=False)
            ]

        # Display Events
        st.markdown(f"**Showing {len(filtered_events)} events:**")
        for idx, row in filtered_events.iterrows():
            ts_str = row["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if pd.notnull(row.get("timestamp")) else "N/A"
            event_type = row.get("event_type", "EVENT")
            symbol = row.get("symbol", "N/A")
            client_order_id = row.get("client_order_id", "N/A")

            # Expander for each event
            expander_title = f"[{ts_str}] {event_type} | {symbol} (Order: {client_order_id})"
            with st.expander(expander_title, expanded=False):
                st.write(f"**ID:** {row.get('id', 'N/A')}")
                st.write(f"**Created At:** {row.get('created_at', 'N/A')}")
                details = row.get("details")
                if details:
                    st.write("**Details Payload:**")
                    st.json(details)
                else:
                    st.caption("No additional details payload for this event.")
    else:
        st.info("No event logs recorded in `trade_events` yet.")

