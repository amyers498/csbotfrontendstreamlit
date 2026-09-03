# Crypto and Stock Trading Bot 2026 - Streamlit Frontend 📈

A real-time command center and analytics dashboard for the **Crypto and Stock Trading Bot 2026**, built with **Streamlit**, **Supabase**, and **Plotly**.

## 🚀 Features

- **📊 Executive Dashboard**: Real-time portfolio value, buying power, cash balance, and interactive equity curve over time.
- **🎯 Capital Allocation**: Visual breakdown of capital deployed across Crypto, Intraday Stocks, Swing Stocks, and Settled Cash.
- **⚡ Active Positions**: Live tracking of open trades (`trades` table) with stop loss, take profit targets, notional values, and strategy tags.
- **📜 Trade History & Strategy Analytics**: Closed trades log, cumulative PnL curve, win rate metrics, and strategy performance leaderboards.
- **🔍 Audit Logs & Event Stream**: Chronological event monitoring from `trade_events` with full JSON payload inspection.
- **⚙️ Resilient Auth & Auto-refresh**: Seamless connection with Supabase credentials via `.env` or Streamlit secrets with auto-refresh capability.

---

## 🛠️ Installation & Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Supabase Credentials
Ensure your `.env` file in the root directory contains your Supabase credentials:
```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_PUBLISHABLE_KEY=your-supabase-publishable-key
SUPABASE_SECRET_KEY=your-supabase-secret-key
```

### 3. Run the Streamlit App
```bash
streamlit run app.py
```

---

## 🗄️ Database Tables Used

- `public.trades`: Stores raw execution fills and matched round-trips.
- `public.orders`: Stores order lifecycle from Alpaca (working limit/stops, fills, cancels).
- `public.trade_events`: Stores order submissions, stop loss triggers, and audit events.
- `public.account_snapshots`: Stores portfolio equity snapshots for the equity curve and allocation charts.

