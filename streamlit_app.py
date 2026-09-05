"""
CryptoandStockBot2026 - Quantitative Algorithmic Trading Terminal
Clean, modern, and intuitive Streamlit dashboard for multi-asset automated trading.
Supports 3-Bullet shared pool monitoring, Supabase cloud data with local SQLite fallback,
live spot pricing, interactive Plotly equity analytics, and real-time risk/target command cards.
"""

import os
from datetime import datetime, timezone, time as dtime
from typing import Optional, Tuple, Dict, Any

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Modular system imports
from src.data_manager import load_dashboard_data
from src.trade_reconciliation import reconcile_trades_and_positions
from src.market_data import fetch_live_price
from src.trade_card_ui import format_trade_card_html
from src.supabase_client import OPEN_ORDER_STATUSES

# -----------------------------------------------------------------------------
# 1. PAGE CONFIGURATION & DARK THEME STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Crypto & Stock Bot 2026",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom High-Contrast Terminal Dark CSS
st.markdown(
    """
    <style>
    /* Global Styles */
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    
    /* Metric Cards */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #111827 0%, #1e293b 100%);
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 14px 18px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
    }
    div[data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
        color: #94a3b8 !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.75px !important;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.55rem !important;
        font-weight: 800 !important;
        color: #f8fafc !important;
    }

    /* Badges */
    .badge-buy {
        background-color: rgba(16, 185, 129, 0.18);
        color: #34d399;
        border: 1px solid #059669;
        border-radius: 4px;
        padding: 2px 8px;
        font-weight: 700;
        font-size: 0.75rem;
    }
    .badge-sell {
        background-color: rgba(239, 68, 68, 0.18);
        color: #f87171;
        border: 1px solid #dc2626;
        border-radius: 4px;
        padding: 2px 8px;
        font-weight: 700;
        font-size: 0.75rem;
    }
    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .status-pill-online {
        background-color: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid rgba(16, 185, 129, 0.35);
    }
    .status-pill-offline {
        background-color: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.35);
    }
    .status-pill-market {
        background-color: rgba(59, 130, 246, 0.15);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.35);
    }
    
    /* Bullet Container */
    .bullet-card {
        background: #0f172a;
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
    }
    .bullet-empty {
        background: rgba(15, 23, 42, 0.6);
        border: 1px dashed #334155;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
        color: #64748b;
        font-size: 0.85rem;
    }
    
    /* Clean container spacing */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2.5rem !important;
        max-width: 1440px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 2. HELPER FUNCTIONS & MARKET TIMING
# -----------------------------------------------------------------------------
def get_market_status() -> Tuple[str, str, str]:
    """
    Evaluate US stock market hours (9:30 AM - 4:00 PM EST, Mon-Fri)
    and check for the mandatory 3:45 PM EST intraday flush window.
    """
    now_utc = datetime.now(timezone.utc)
    # Convert UTC to US Eastern (approx UTC - 4 / - 5)
    # Eastern is UTC-4 in daylight saving, UTC-5 standard.
    # We estimate using UTC offset -4
    hour_est = (now_utc.hour - 4) % 24
    minute_est = now_utc.minute
    weekday = now_utc.weekday() # 0 = Monday, 6 = Sunday

    is_weekday = weekday < 5
    current_time_minutes = hour_est * 60 + minute_est

    market_open = 9 * 60 + 30    # 9:30 AM EST
    flush_time = 15 * 60 + 45    # 3:45 PM EST
    market_close = 16 * 60       # 4:00 PM EST

    if is_weekday and market_open <= current_time_minutes < market_close:
        if current_time_minutes >= flush_time:
            return (
                "⚡ Mandatory 3:45 PM EST Flush Active",
                "intraday_flush",
                "Positions closing to preserve overnight cash."
            )
        mins_to_flush = flush_time - current_time_minutes
        hrs = mins_to_flush // 60
        mins = mins_to_flush % 60
        countdown = f"{hrs}h {mins}m" if hrs > 0 else f"{mins}m"
        return (
            "🟢 US Equity Market Open",
            "market_open",
            f"Next Intraday Flush in {countdown} (3:45 PM EST)"
        )
    else:
        return (
            "🌙 US Market Closed (24/7 Crypto Active)",
            "market_closed",
            "Intraday scalp engine waiting for 9:30 AM EST bell."
        )


# -----------------------------------------------------------------------------
# 3. SIDEBAR CONTROLS & REFRESH SETTINGS
# -----------------------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/isometric/100/bot.png", width=64)
    st.title("Trading Bot 2026")
    st.caption("Quantitative Multi-Asset Algorithmic Engine")
    st.markdown("---")

    st.subheader("⚙️ Terminal Controls")
    
    # Auto-refresh selector
    auto_refresh = st.selectbox(
        "Auto-Refresh Interval",
        ["Off", "10 seconds", "30 seconds", "60 seconds"],
        index=2,
        help="Periodically reload positions and market feeds automatically."
    )

    # Convert selection to seconds
    refresh_seconds = 0
    if auto_refresh == "10 seconds":
        refresh_seconds = 10
    elif auto_refresh == "30 seconds":
        refresh_seconds = 30
    elif auto_refresh == "60 seconds":
        refresh_seconds = 60

    # Manual refresh button
    if st.button("🔄 Refresh Data Now", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.subheader("🛡️ Reconciliation Settings")
    tracking_mode = st.radio(
        "Position Engine Mode",
        ["Reconciled Net Positions", "Raw Database Rows"],
        index=0,
        help="Reconciled Net mode groups BUY and SELL round-trips via FIFO matching to prevent double-counting active trades."
    )

    dust_threshold = st.slider(
        "Crypto Dust Filter ($)",
        min_value=0.10,
        max_value=5.00,
        value=1.00,
        step=0.10,
        help="Remaining positions valued below this dollar threshold are absorbed into closed fees instead of cluttering active positions."
    )

    st.markdown("---")
    st.subheader("📦 Strategy Sizing Guide")
    st.markdown(
        """
        - **Account Target**: ~$500.00
        - **3-Bullet Shared Pool**: Max 3 concurrent positions (~$140 each).
        - **⚡ Intraday**: SPY, QQQ, AAPL, NVDA, TSLA (VWAP Scalp).
        - **🟣 Crypto**: BTC, ETH, SOL, AVAX (1H Trend & Pullback).
        - **📈 Swing**: QQQ, SMH, NVDA, AAPL, MSFT (20-day SMA).
        - **🤝 Manual**: Auto-adopted Alpaca trades.
        """
    )
    st.caption(f"App Local Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Inject Auto-Refresh Meta Tag if enabled
if refresh_seconds > 0:
    st.markdown(
        f'<meta http-equiv="refresh" content="{refresh_seconds}">',
        unsafe_allow_html=True
    )

# -----------------------------------------------------------------------------
# 4. DATA INGESTION & RECONCILIATION
# -----------------------------------------------------------------------------
raw_trades, raw_snapshots, raw_orders, raw_events, data_source_label, is_fallback, source_msg = load_dashboard_data()

# Show fallback notice if Supabase is offline
if is_fallback and source_msg:
    st.warning(f"⚠️ **Database Notice**: {source_msg}")

# Apply Reconciliation Engine
if tracking_mode == "Reconciled Net Positions":
    open_trades, closed_trades = reconcile_trades_and_positions(
        raw_trades,
        dust_threshold_usd=dust_threshold
    )
else:
    if not raw_trades.empty:
        open_trades = raw_trades[raw_trades["status"].str.upper() == "OPEN"].copy()
        closed_trades = raw_trades[raw_trades["status"].str.upper() == "CLOSED"].copy()
    else:
        open_trades = pd.DataFrame()
        closed_trades = pd.DataFrame()

# -----------------------------------------------------------------------------
# 5. FINANCIAL CALCULATIONS & "3-BULLET" METRICS
# -----------------------------------------------------------------------------
# Latest Account Snapshot
latest_snap: Dict[str, Any] = {}
baseline_snap: Dict[str, Any] = {}
if not raw_snapshots.empty:
    latest_snap = raw_snapshots.iloc[-1].to_dict()
    baseline_snap = raw_snapshots.iloc[0].to_dict()

portfolio_value = float(latest_snap.get("portfolio_value", 500.00))
settled_cash = float(latest_snap.get("settled_cash", 500.00))
buying_power = float(latest_snap.get("buying_power", settled_cash))
baseline_value = float(baseline_snap.get("portfolio_value", portfolio_value))

# Calculate Overall Session Realized PnL and Delta
total_realized_pnl = float(closed_trades["realized_pnl"].sum()) if not closed_trades.empty and "realized_pnl" in closed_trades.columns else 0.0

# 24h / Session Dollar Delta
portfolio_delta = portfolio_value - baseline_value
portfolio_delta_pct = ((portfolio_value - baseline_value) / baseline_value * 100) if baseline_value > 0 else 0.0

# "3-Bullet" Pool Sizing
TOTAL_BULLETS = 3
ALLOCATION_PER_BULLET = 140.00
active_bullet_count = min(TOTAL_BULLETS, len(open_trades))
available_bullets = max(0, TOTAL_BULLETS - active_bullet_count)

# Win / Loss Statistics
total_closed_count = len(closed_trades)
win_count = 0
loss_count = 0
win_rate = 0.0
if total_closed_count > 0 and "realized_pnl" in closed_trades.columns:
    win_count = int((closed_trades["realized_pnl"] > 0).sum())
    loss_count = int((closed_trades["realized_pnl"] < 0).sum())
    win_rate = (win_count / total_closed_count) * 100

# -----------------------------------------------------------------------------
# 6. HEADER & TOP KPI METRICS (ROW 1)
# -----------------------------------------------------------------------------
market_label, market_state, market_subtext = get_market_status()

header_col1, header_col2 = st.columns([3, 2])
with header_col1:
    st.title("🤖 Crypto & Stock Bot 2026")
    st.markdown(
        "**Quantitative Algorithmic Terminal** • Multi-Asset 3-Bullet Execution Engine"
    )

with header_col2:
    st.markdown("<div style='text-align: right; padding-top: 10px;'>", unsafe_allow_html=True)
    # Badges
    market_badge_class = "status-pill-market" if market_state == "market_open" else "status-pill-offline"
    st.markdown(
        f"""
        <span class="status-pill {market_badge_class}">{market_label}</span>
        <span class="status-pill {'status-pill-online' if not is_fallback else 'status-pill-offline'}">
            {'🟢 ' if not is_fallback else '🟠 '}{data_source_label}
        </span>
        <span class="status-pill status-pill-online">🛡️ Paper Trading</span>
        <div style="font-size: 0.78rem; color: #94a3b8; margin-top: 6px;">{market_subtext}</div>
        """,
        unsafe_allow_html=True
    )
    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<hr style='margin-top: 6px; margin-bottom: 20px; border-color: #1e293b;'>", unsafe_allow_html=True)

# 4 Key Metric Cards (Row 1)
m_col1, m_col2, m_col3, m_col4 = st.columns(4)

with m_col1:
    delta_sign = "+" if portfolio_delta >= 0 else ""
    st.metric(
        label="Portfolio Value ($)",
        value=f"${portfolio_value:,.2f}",
        delta=f"{delta_sign}${portfolio_delta:,.2f} ({delta_sign}{portfolio_delta_pct:.2f}%)"
    )

with m_col2:
    st.metric(
        label="Settled Cash & Buying Power",
        value=f"${settled_cash:,.2f}",
        delta=f"Buying Power: ${buying_power:,.2f}",
        delta_color="off"
    )

with m_col3:
    bullet_icons = "🟢 " * active_bullet_count + "⚪ " * available_bullets
    st.metric(
        label=f"3-Bullet Pool ({active_bullet_count} / {TOTAL_BULLETS} Deployed)",
        value=bullet_icons.strip(),
        delta=f"{available_bullets} Available (~${available_bullets * ALLOCATION_PER_BULLET:,.0f} reserve)",
        delta_color="normal" if available_bullets > 0 else "inverse"
    )

with m_col4:
    pnl_sign = "+" if total_realized_pnl >= 0 else ""
    st.metric(
        label="Realized PnL & Win Rate",
        value=f"{pnl_sign}${total_realized_pnl:,.2f}",
        delta=f"{win_rate:.1f}% Win Rate ({win_count}W / {loss_count}L)",
        delta_color="normal" if total_realized_pnl >= 0 else "inverse"
    )

# -----------------------------------------------------------------------------
# 7. ACTIVE POSITIONS & PROJECTED TARGETS (ROW 2)
# -----------------------------------------------------------------------------
st.markdown("### ⚡ Active Positions & Projected Targets")

# Bullet Capacity Progress Bar
bullet_pct = active_bullet_count / TOTAL_BULLETS
st.progress(bullet_pct, text=f"Active Bullet Capacity: {active_bullet_count} of {TOTAL_BULLETS} Bullets In Play ({bullet_pct * 100:.0f}%)")

if not open_trades.empty:
    pos_header_col1, pos_header_col2 = st.columns([3, 1])
    with pos_header_col2:
        active_view = st.radio(
            "View Mode",
            ["Visual Trade Cards", "Spreadsheet Table"],
            horizontal=True,
            key="active_view_toggle",
            label_visibility="collapsed"
        )

    if active_view == "Visual Trade Cards":
        for _, row in open_trades.iterrows():
            sym = row.get("symbol", "")
            live_px = fetch_live_price(sym)
            card_html = format_trade_card_html(row.to_dict(), live_price=live_px, is_active=True)
            st.markdown(card_html, unsafe_allow_html=True)
    else:
        disp_open = open_trades.copy()
        cols_to_show = [
            "symbol", "asset_class", "strategy_tag", "side", "qty",
            "entry_price", "notional", "take_profit_price", "stop_loss_price",
            "estimated_tp_pnl", "estimated_sl_pnl", "risk_reward_ratio",
            "entry_time", "notes"
        ]
        available_cols = [c for c in cols_to_show if c in disp_open.columns]
        st.dataframe(
            disp_open[available_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "entry_price": st.column_config.NumberColumn("Entry Price", format="$%.4f"),
                "notional": st.column_config.NumberColumn("Notional", format="$%.2f"),
                "qty": st.column_config.NumberColumn("Quantity", format="%.6f"),
                "take_profit_price": st.column_config.NumberColumn("Target (TP)", format="$%.4f"),
                "stop_loss_price": st.column_config.NumberColumn("Max Risk (SL)", format="$%.4f"),
                "estimated_tp_pnl": st.column_config.NumberColumn("Target Profit ($)", format="$%.2f"),
                "estimated_sl_pnl": st.column_config.NumberColumn("Max Risk ($)", format="$%.2f"),
                "risk_reward_ratio": st.column_config.NumberColumn("R:R", format="1:%.1f"),
                "entry_time": st.column_config.DatetimeColumn("Entry Time", format="YYYY-MM-DD HH:mm:ss"),
            },
        )
else:
    st.info("🎯 **All 3 Bullets Ready**: No active positions currently open. The bot is 100% in cash waiting for high-probability signals.")

# -----------------------------------------------------------------------------
# 8. INTERACTIVE CHARTS & CAPITAL ALLOCATION (ROW 3)
# -----------------------------------------------------------------------------
st.markdown("### 📊 Portfolio Analytics & Capital Distribution")
tab_chart_equity, tab_chart_alloc = st.tabs(["📈 Equity Curve & Cash Balance", "🍩 Strategy Capital Allocation"])

with tab_chart_equity:
    if not raw_snapshots.empty and len(raw_snapshots) > 1:
        snap_df = raw_snapshots.copy().sort_values("timestamp")
        # Calculate High-Water Mark
        snap_df["high_water_mark"] = snap_df["portfolio_value"].cummax()
        
        fig_equity = go.Figure()

        # Portfolio Value Trace
        fig_equity.add_trace(
            go.Scatter(
                x=snap_df["timestamp"],
                y=snap_df["portfolio_value"],
                mode="lines+markers",
                name="Portfolio Equity ($)",
                line=dict(color="#10b981", width=2.5),
                marker=dict(size=4),
                hovertemplate="<b>%{x|%b %d, %H:%M:%S}</b><br>Equity: $%{y:,.2f}<extra></extra>"
            )
        )

        # Settled Cash Trace
        fig_equity.add_trace(
            go.Scatter(
                x=snap_df["timestamp"],
                y=snap_df["settled_cash"],
                mode="lines",
                name="Settled Cash ($)",
                line=dict(color="#64748b", width=1.5, dash="dash"),
                hovertemplate="Cash: $%{y:,.2f}<extra></extra>"
            )
        )

        # High-Water Mark Trace
        fig_equity.add_trace(
            go.Scatter(
                x=snap_df["timestamp"],
                y=snap_df["high_water_mark"],
                mode="lines",
                name="High-Water Mark (HWM)",
                line=dict(color="#fbbf24", width=1.5, dash="dot"),
                hovertemplate="Peak HWM: $%{y:,.2f}<extra></extra>"
            )
        )

        fig_equity.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(showgrid=True, gridcolor="#1e293b", tickprefix="$"),
            xaxis=dict(showgrid=True, gridcolor="#1e293b"),
            margin=dict(l=0, r=0, t=20, b=10),
            height=340,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_equity, use_container_width=True)
    elif not raw_snapshots.empty:
        st.info(f"Initial baseline snapshot recorded at ${portfolio_value:,.2f}. As more trades complete, your multi-day equity curve and high-water mark will render here.")
    else:
        st.info("No account snapshots logged yet. Once the bot runs its first cycle, equity history will appear here.")

with tab_chart_alloc:
    alloc_col1, alloc_col2 = st.columns([1, 1])

    intraday_val = float(latest_snap.get("intraday_allocated", 0.0))
    swing_val = float(latest_snap.get("swing_allocated", 0.0))
    crypto_val = float(latest_snap.get("crypto_allocated", 0.0))
    unallocated_cash = max(0.0, settled_cash)

    alloc_data = [
        {"Bucket": "Intraday Scalps (VWAP)", "Value": intraday_val, "Color": "#06b6d4"},
        {"Bucket": "Equity Swings (20 SMA)", "Value": swing_val, "Color": "#3b82f6"},
        {"Bucket": "Crypto Trends (1H)", "Value": crypto_val, "Color": "#a855f7"},
        {"Bucket": "Unallocated Cash Reserve", "Value": unallocated_cash, "Color": "#10b981"},
    ]
    alloc_df = pd.DataFrame(alloc_data)

    with alloc_col1:
        fig_donut = px.pie(
            alloc_df,
            values="Value",
            names="Bucket",
            hole=0.55,
            color="Bucket",
            color_discrete_map={d["Bucket"]: d["Color"] for d in alloc_data},
            title="Capital Distribution by Bucket"
        )
        fig_donut.update_traces(
            textposition="inside",
            textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>Capital: $%{value:,.2f} (%{percent})<extra></extra>"
        )
        fig_donut.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            height=300,
            margin=dict(l=10, r=10, t=30, b=10)
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with alloc_col2:
        st.markdown("#### 🎯 3-Bullet Pool Allocation Breakdown")
        total_account = max(1.0, portfolio_value)
        st.markdown(
            f"""
            - **⚡ Intraday VWAP Mega-caps**: `${intraday_val:,.2f}` *({intraday_val / total_account * 100:.1f}%)*
            - **📈 Equity Swings (20 SMA)**: `${swing_val:,.2f}` *({swing_val / total_account * 100:.1f}%)*
            - **🟣 Crypto 1H Trends**: `${crypto_val:,.2f}` *({crypto_val / total_account * 100:.1f}%)*
            - **💵 Unallocated Cash Reserve**: `${unallocated_cash:,.2f}` *({unallocated_cash / total_account * 100:.1f}%)*
            """
        )
        st.caption("Each bullet allocates ~$140 into high-conviction trades with strictly enforced stop-losses.")

# -----------------------------------------------------------------------------
# 9. TRADE HISTORY & PERFORMANCE LOG (ROW 4)
# -----------------------------------------------------------------------------
st.markdown("### 📜 Trade History & Performance Log")

if not closed_trades.empty:
    filter_col1, filter_col2, filter_col3 = st.columns([2, 1.5, 1.5])
    with filter_col1:
        strategies_available = ["All Strategies"] + sorted(closed_trades["strategy_tag"].dropna().unique().tolist())
        sel_strat = st.selectbox("Filter Strategy", strategies_available)
    with filter_col2:
        assets_available = ["All Assets"] + sorted(closed_trades["asset_class"].dropna().unique().tolist())
        sel_asset = st.selectbox("Filter Asset Class", assets_available)
    with filter_col3:
        hist_view_mode = st.radio("Display Format", ["Spreadsheet Table", "Visual Closed Cards"], horizontal=True)

    # Filter closed trades
    filtered_closed = closed_trades.copy()
    if sel_strat != "All Strategies":
        filtered_closed = filtered_closed[filtered_closed["strategy_tag"] == sel_strat]
    if sel_asset != "All Assets":
        filtered_closed = filtered_closed[filtered_closed["asset_class"] == sel_asset]

    if hist_view_mode == "Visual Closed Cards":
        for _, row in filtered_closed.iterrows():
            c_html = format_trade_card_html(row.to_dict(), is_active=False)
            st.markdown(c_html, unsafe_allow_html=True)
    else:
        hist_cols = [
            "id", "symbol", "asset_class", "strategy_tag", "side", "qty",
            "entry_price", "exit_price", "realized_pnl", "pnl_percent",
            "take_profit_price", "stop_loss_price", "risk_reward_ratio",
            "fees", "entry_time", "exit_time", "notes"
        ]
        av_hist_cols = [c for c in hist_cols if c in filtered_closed.columns]
        st.dataframe(
            filtered_closed[av_hist_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "entry_price": st.column_config.NumberColumn("Entry Price", format="$%.4f"),
                "exit_price": st.column_config.NumberColumn("Exit Price", format="$%.4f"),
                "realized_pnl": st.column_config.NumberColumn("Realized PnL", format="$%.2f"),
                "pnl_percent": st.column_config.NumberColumn("PnL %", format="%.2f%%"),
                "take_profit_price": st.column_config.NumberColumn("TP Target", format="$%.4f"),
                "stop_loss_price": st.column_config.NumberColumn("SL Trigger", format="$%.4f"),
                "risk_reward_ratio": st.column_config.NumberColumn("R:R", format="1:%.1f"),
                "fees": st.column_config.NumberColumn("Fees", format="$%.2f"),
                "entry_time": st.column_config.DatetimeColumn("Entry Time", format="YYYY-MM-DD HH:mm:ss"),
                "exit_time": st.column_config.DatetimeColumn("Exit Time", format="YYYY-MM-DD HH:mm:ss"),
            }
        )

    # Strategy Performance Summary Table
    st.markdown("#### 🏆 Strategy Leaderboard")
    if "strategy_tag" in closed_trades.columns:
        strat_agg = closed_trades.groupby("strategy_tag").agg(
            total_trades=("id", "count"),
            net_pnl=("realized_pnl", "sum"),
            avg_pnl_pct=("pnl_percent", "mean"),
            win_trades=("realized_pnl", lambda x: (x > 0).sum())
        ).reset_index()
        strat_agg["win_rate_pct"] = (strat_agg["win_trades"] / strat_agg["total_trades"]) * 100

        st.dataframe(
            strat_agg,
            use_container_width=True,
            hide_index=True,
            column_config={
                "strategy_tag": "Strategy",
                "total_trades": "Trades",
                "net_pnl": st.column_config.NumberColumn("Net Realized PnL", format="$%.2f"),
                "avg_pnl_pct": st.column_config.NumberColumn("Avg Return", format="%.2f%%"),
                "win_rate_pct": st.column_config.NumberColumn("Win Rate", format="%.1f%%"),
                "win_trades": "Wins",
            }
        )
else:
    st.info("No closed trades recorded yet. Completed round-trips will appear here with audited exit notes and performance metrics.")

# -----------------------------------------------------------------------------
# 10. OPEN ORDERS & SYSTEM AUDIT FEED (ROW 5)
# -----------------------------------------------------------------------------
st.markdown("### 📝 Broker Orders & System Audit Log")
tab_orders_sec, tab_events_sec = st.tabs(["📋 Alpaca Order Book", "⏱️ Live System Audit Feed"])

with tab_orders_sec:
    if not raw_orders.empty:
        open_orders_mask = raw_orders["status"].str.lower().isin(OPEN_ORDER_STATUSES)
        active_orders = raw_orders[open_orders_mask].copy()
        
        ord_kpi1, ord_kpi2, ord_kpi3 = st.columns(3)
        ord_kpi1.metric("Active / Resting Orders", f"{len(active_orders)}")
        ord_kpi2.metric("Total Executed / Filled", f"{(raw_orders['status'].str.lower() == 'filled').sum()}")
        ord_kpi3.metric("Total Canceled", f"{(raw_orders['status'].str.lower() == 'canceled').sum()}")

        filter_order_type = st.radio("Order Filter", ["Open / Working Orders Only", "All Historical Orders"], horizontal=True)
        disp_orders = active_orders if filter_order_type.startswith("Open") else raw_orders

        order_cols = [
            "symbol", "side", "order_type", "qty", "limit_price", "stop_price",
            "status", "submitted_at", "alpaca_order_id"
        ]
        av_ord_cols = [c for c in order_cols if c in disp_orders.columns]
        
        st.dataframe(
            disp_orders[av_ord_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "limit_price": st.column_config.NumberColumn("Limit Price", format="$%.4f"),
                "stop_price": st.column_config.NumberColumn("Stop Price", format="$%.4f"),
                "qty": st.column_config.NumberColumn("Quantity", format="%.6f"),
                "submitted_at": st.column_config.DatetimeColumn("Submitted At", format="YYYY-MM-DD HH:mm:ss"),
            }
        )
    else:
        st.info("No orders logged in `orders` table yet.")

with tab_events_sec:
    if not raw_events.empty:
        st.caption("Chronological audit log of automated triggers, order lifecycle transitions, and risk flushes.")
        disp_events = raw_events.copy().sort_values("timestamp", ascending=False).head(50)
        
        for _, ev in disp_events.iterrows():
            ev_type = str(ev.get("event_type", "INFO")).upper()
            ev_sym = ev.get("symbol") or "SYSTEM"
            ev_time = ev.get("timestamp")
            time_str = ev_time.strftime("%b %d, %H:%M:%S UTC") if pd.notnull(ev_time) else "N/A"
            details = ev.get("details", "")

            badge_color = "#3b82f6"
            if "BUY" in ev_type or "FILL" in ev_type:
                badge_color = "#10b981"
            elif "FLUSH" in ev_type or "STOP" in ev_type or "SELL" in ev_type:
                badge_color = "#ef4444"
            elif "SIGNAL" in ev_type:
                badge_color = "#06b6d4"

            st.markdown(
                f"""
                <div style="background-color: #0f172a; border-left: 3px solid {badge_color}; border-radius: 4px; padding: 10px 14px; margin-bottom: 8px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-weight: 700; color: {badge_color}; font-size: 0.8rem; margin-right: 8px;">[{ev_type}]</span>
                            <span style="font-weight: 600; color: #f8fafc; font-size: 0.85rem;">{ev_sym}</span>
                        </div>
                        <span style="font-size: 0.75rem; color: #64748b;">{time_str}</span>
                    </div>
                    <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 4px; font-family: monospace;">
                        {str(details)}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.info("No system events logged in `trade_events` table yet.")

# -----------------------------------------------------------------------------
# 11. FOOTER
# -----------------------------------------------------------------------------
st.markdown("<hr style='border-color: #1e293b; margin-top: 40px;'>", unsafe_allow_html=True)
st.caption(
    "Crypto & Stock Bot 2026 • Real-time quantitative risk and execution dashboard. "
    "Designed for the 3-Bullet Capital Allocation Framework."
)
