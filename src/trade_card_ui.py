"""
Trade Card Component for Crypto & Stock Trading Bot 2026.
Renders high-contrast, institutional trading terminal cards with live PnL,
take profit targets, stop loss risk metrics, and risk/reward ratios.
Guarantees clean HTML output with zero markdown indentation leakage.
"""

from typing import Optional, Dict, Any
import pandas as pd


def strip_html_indentation(html_text: str) -> str:
    """
    Remove leading whitespace from each line and strip blank lines.
    Streamlit markdown parses 4+ indented spaces after a newline as a code block,
    which causes raw HTML/CSS to appear on the screen.
    """
    return "\n".join(line.strip() for line in html_text.splitlines() if line.strip())


def format_trade_card_html(
    row: Dict[str, Any],
    live_price: Optional[float] = None,
    is_active: bool = True,
    working_order_desc: Optional[str] = None,
) -> str:
    """
    Format a single trade card with exact target profit, max risk, and R:R styling.
    """
    symbol = str(row.get("symbol", "N/A")).upper()
    side = str(row.get("side", "BUY")).upper()
    if "BUY" in side:
        side = "BUY"
    elif "SELL" in side:
        side = "SELL"

    qty = float(row.get("qty") or 0.0)
    entry_price = float(row.get("entry_price") or 0.0)
    notional = float(row.get("notional") or (qty * entry_price))
    strategy = str(row.get("strategy_tag") or "manual")
    asset_class = str(row.get("asset_class") or "crypto").upper()
    notes = row.get("notes") or ""
    strat_lower = strategy.lower()

    # Timestamps
    entry_time = row.get("entry_time")
    time_str = entry_time.strftime("%b %d, %H:%M:%S UTC") if (entry_time is not None and pd.notnull(entry_time)) else "N/A"

    # Live Price & PnL calculation
    curr_price = float(live_price) if (live_price is not None and float(live_price) > 0) else entry_price

    if is_active:
        if side == "BUY":
            curr_pnl = (curr_price - entry_price) * qty
            curr_pnl_pct = ((curr_price - entry_price) / entry_price * 100) if entry_price > 0 else 0.0
        else:
            curr_pnl = (entry_price - curr_price) * qty
            curr_pnl_pct = ((entry_price - curr_price) / entry_price * 100) if entry_price > 0 else 0.0
    else:
        curr_pnl = float(row.get("realized_pnl") or 0.0)
        curr_pnl_pct = float(row.get("pnl_percent") or 0.0)
        curr_price = float(row.get("exit_price") or curr_price)

    # Styling colors for PnL
    pnl_color = "#10b981" if curr_pnl >= 0 else "#ef4444"
    pnl_sign = "+" if curr_pnl >= 0 else ""
    pnl_label = "Current PnL" if is_active else "Realized PnL"

    # Target Profit calculation & Fallbacks
    tp_price = row.get("take_profit_price")
    tp_pnl = row.get("estimated_tp_pnl")
    tp_pct = row.get("estimated_tp_pct")

    # If missing / 0 / NaN, compute using bot quantitative strategy rules
    if (tp_price is None or pd.isna(tp_price) or float(tp_price) <= 0) and entry_price > 0:
        if "vwap" in strat_lower or "intraday" in strat_lower:
            tp_pct = 2.5
        elif "crypto" in strat_lower or asset_class == "CRYPTO" or "/" in symbol:
            tp_pct = 6.0
        else:
            tp_pct = 5.0
        tp_price = entry_price * (1.0 + tp_pct / 100.0) if side == "BUY" else entry_price * (1.0 - tp_pct / 100.0)
        tp_pnl = (tp_price - entry_price) * qty if side == "BUY" else (entry_price - tp_price) * qty
    else:
        if tp_price is not None and float(tp_price) > 0 and entry_price > 0:
            tp_price = float(tp_price)
            if tp_pnl is None or pd.isna(tp_pnl):
                tp_pnl = (tp_price - entry_price) * qty if side == "BUY" else (entry_price - tp_price) * qty
            if tp_pct is None or pd.isna(tp_pct):
                tp_pct = ((tp_price - entry_price) / entry_price * 100) if side == "BUY" else ((entry_price - tp_price) / entry_price * 100)

    if tp_price is not None and float(tp_price) > 0:
        tp_price = float(tp_price)
        tp_pnl_val = float(tp_pnl) if tp_pnl is not None and not pd.isna(tp_pnl) else 0.0
        tp_pct_val = float(tp_pct) if tp_pct is not None and not pd.isna(tp_pct) else 0.0
        tp_sign = "+" if tp_pnl_val >= 0 else ""
        tp_pct_sign = "+" if tp_pct_val >= 0 else ""
        tp_str = f"🎯 Target Profit: <strong>{tp_sign}${abs(tp_pnl_val):,.2f} ({tp_pct_sign}{abs(tp_pct_val):.1f}%)</strong> at ${tp_price:,.2f}"
    else:
        tp_str = "🎯 Target Profit: <span style='color: #64748b;'>Not Set</span>"

    # Stop Loss / Max Risk calculation & Fallbacks
    sl_price = row.get("stop_loss_price")
    sl_pnl = row.get("estimated_sl_pnl")
    sl_pct = row.get("estimated_sl_pct")

    if (sl_price is None or pd.isna(sl_price) or float(sl_price) <= 0) and entry_price > 0:
        if "vwap" in strat_lower or "intraday" in strat_lower:
            sl_pct = -1.25
        elif "crypto" in strat_lower or asset_class == "CRYPTO" or "/" in symbol:
            sl_pct = -5.0
        else:
            sl_pct = -3.0
        sl_price = entry_price * (1.0 + sl_pct / 100.0) if side == "BUY" else entry_price * (1.0 - sl_pct / 100.0)
        sl_pnl = (sl_price - entry_price) * qty if side == "BUY" else (entry_price - sl_price) * qty
    else:
        if sl_price is not None and float(sl_price) > 0 and entry_price > 0:
            sl_price = float(sl_price)
            if sl_pnl is None or pd.isna(sl_pnl):
                sl_pnl = (sl_price - entry_price) * qty if side == "BUY" else (entry_price - sl_price) * qty
            if sl_pct is None or pd.isna(sl_pct):
                sl_pct = ((sl_price - entry_price) / entry_price * 100) if side == "BUY" else ((entry_price - sl_price) / entry_price * 100)

    if sl_price is not None and float(sl_price) > 0:
        sl_price = float(sl_price)
        sl_pnl_val = float(sl_pnl) if sl_pnl is not None and not pd.isna(sl_pnl) else 0.0
        sl_pct_val = float(sl_pct) if sl_pct is not None and not pd.isna(sl_pct) else 0.0
        sl_sign = "-" if sl_pnl_val <= 0 else "+"
        sl_pct_sign = "-" if sl_pct_val <= 0 else "+"
        sl_str = f"🛑 Max Risk: <strong>{sl_sign}${abs(sl_pnl_val):,.2f} ({sl_pct_sign}{abs(sl_pct_val):.1f}%)</strong> at ${sl_price:,.2f}"
    else:
        sl_str = "🛑 Max Risk: <span style='color: #64748b;'>Not Set</span>"

    # Risk to Reward calculation
    rr = row.get("risk_reward_ratio")
    if rr is not None and pd.notnull(rr) and float(rr) > 0:
        rr_val = float(rr)
    elif tp_price and sl_price and tp_pnl and sl_pnl and float(sl_pnl) != 0:
        rr_val = abs(float(tp_pnl) / float(sl_pnl))
    else:
        rr_val = 1.5
    rr_str = f"⚖️ R:R: <strong>1:{rr_val:.1f}</strong>"

    # Duration calculation
    duration_str = ""
    if pd.notnull(entry_time):
        try:
            now_dt = pd.Timestamp.now(tz=entry_time.tz) if getattr(entry_time, "tz", None) else pd.Timestamp.now()
            end_time = row.get("exit_time") if not is_active else now_dt
            if pd.notnull(end_time):
                if getattr(end_time, "tz", None) != getattr(entry_time, "tz", None):
                    if getattr(entry_time, "tz", None):
                        end_time = end_time.tz_convert(entry_time.tz)
                diff = end_time - entry_time
                total_sec = max(0, int(diff.total_seconds()))
                hrs = total_sec // 3600
                mins = (total_sec % 3600) // 60
                days = hrs // 24
                if days > 0:
                    duration_str = f"{days}d {hrs % 24}h"
                elif hrs > 0:
                    duration_str = f"{hrs}h {mins}m"
                else:
                    duration_str = f"{mins}m"
        except Exception:
            duration_str = ""

    # Strategy badge styling
    if "vwap" in strat_lower or "intraday" in strat_lower:
        strat_badge = '<span style="background-color: rgba(6, 182, 212, 0.18); color: #22d3ee; border: 1px solid #0891b2; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; font-weight: 600; margin-left: 6px;">⚡ Intraday VWAP</span>'
    elif "crypto" in strat_lower or asset_class == "CRYPTO" or "/" in symbol:
        strat_badge = '<span style="background-color: rgba(168, 85, 247, 0.18); color: #c084fc; border: 1px solid #9333ea; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; font-weight: 600; margin-left: 6px;">🟣 Crypto 1H Trend</span>'
    elif "swing" in strat_lower or "sma" in strat_lower:
        strat_badge = '<span style="background-color: rgba(59, 130, 246, 0.18); color: #60a5fa; border: 1px solid #2563eb; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; font-weight: 600; margin-left: 6px;">📈 Equity Swing (20 SMA)</span>'
    elif "manual" in strat_lower:
        strat_badge = '<span style="background-color: rgba(245, 158, 11, 0.18); color: #fbbf24; border: 1px solid #d97706; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; font-weight: 600; margin-left: 6px;">🤝 Alpaca Manual Swing</span>'
    else:
        strat_badge = f'<span style="background-color: #1e293b; color: #94a3b8; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; font-weight: 500; margin-left: 6px;">🏷️ {strategy}</span>'

    duration_badge = f'<span style="background-color: rgba(51, 65, 85, 0.7); color: #cbd5e1; border: 1px solid #475569; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; margin-left: 6px;">⏱️ Held: {duration_str}</span>' if duration_str else ""

    # Badges
    side_badge = f'<span class="badge-buy">{side}</span>' if side == "BUY" else f'<span class="badge-sell">{side}</span>'
    asset_badge = f'<span style="background-color: rgba(99, 102, 241, 0.15); color: #a5b4fc; border: 1px solid #4f46e5; border-radius: 4px; padding: 2px 7px; font-weight: 600; font-size: 0.75rem; margin-left: 6px;">{asset_class}</span>'
    notes_snippet = f'<div style="font-size: 0.78rem; color: #64748b; margin-top: 8px; font-style: italic;">📝 {notes}</div>' if notes else ""

    # Exit Plan & Trigger Rules
    exit_plan_html = ""
    if is_active:
        exit_triggers = []
        if tp_price is not None and float(tp_price) > 0:
            exit_triggers.append(f"🎯 <b>Take-Profit Target</b>: ${float(tp_price):,.2f}")
        if sl_price is not None and float(sl_price) > 0:
            exit_triggers.append(f"🛑 <b>Stop-Loss Trigger</b>: ${float(sl_price):,.2f}")

        if "vwap" in strat_lower or "intraday" in strat_lower:
            exit_triggers.append("⏰ <b>EOD Flush</b>: 3:45 PM EST liquidation")
        elif "crypto" in strat_lower or asset_class == "CRYPTO" or "/" in symbol:
            exit_triggers.append("🟣 <b>Trend Rule</b>: 1H trend flip or TP/SL")
        elif "swing" in strat_lower:
            exit_triggers.append("📈 <b>Swing Rule</b>: Multi-day hold until TP/SL or 20 SMA break")

        broker_badge = ""
        if working_order_desc:
            broker_badge = f"<div style='color: #38bdf8; font-size: 0.8rem; font-weight: 600; margin-top: 5px;'>🛡️ <b>Live on Alpaca</b>: {working_order_desc}</div>"

        triggers_text = " &bull; ".join(exit_triggers) if exit_triggers else "TP / SL monitored by bot"
        exit_plan_html = (
            f"<div style='background-color: rgba(30, 41, 59, 0.45); border: 1px dashed #334155; border-radius: 6px; padding: 10px 14px; margin-top: 10px; font-size: 0.8rem; color: #cbd5e1;'>"
            f"<div>⚡ <b>Exit Plan</b>: {triggers_text}</div>"
            f"{broker_badge}"
            f"</div>"
        )

    # Risk & Target Command Box HTML
    command_box_html = (
        f"<div style='background-color: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 6px;'>"
        f"<div style='font-size: 0.95rem; font-weight: 700; color: {pnl_color};'>"
        f"Current PnL: {pnl_sign}${curr_pnl:,.2f} ({pnl_sign}{curr_pnl_pct:.2f}%)"
        f"</div>"
        f"<div style='font-size: 0.9rem; color: #34d399;'>"
        f"{tp_str}"
        f"</div>"
        f"<div style='font-size: 0.9rem; color: #f87171;'>"
        f"{sl_str}"
        f"</div>"
        f"<div style='font-size: 0.9rem; color: #fcd34d;'>"
        f"{rr_str}"
        f"</div>"
        f"</div>"
    )

    # Assembled Card HTML without indentation or blank lines
    raw_html = f"""<div style="background-color: #0f172a; border: 1px solid #1e293b; border-radius: 10px; padding: 18px 22px; margin-bottom: 16px; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.25);">
<div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #1e293b; padding-bottom: 10px; margin-bottom: 14px; flex-wrap: wrap; gap: 8px;">
<div style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">
<span style="font-size: 1.28rem; font-weight: 700; color: #f8fafc; margin-right: 8px; letter-spacing: 0.5px;">{symbol}</span>
{side_badge}
{asset_badge}
{strat_badge}
{duration_badge}
</div>
<div style="font-size: 0.8rem; color: #94a3b8;">
🕒 {time_str}
</div>
</div>
<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 14px; margin-bottom: 12px;">
<div>
<div style="font-size: 0.72rem; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Entry Price</div>
<div style="font-size: 1.12rem; font-weight: 700; color: #f1f5f9;">${entry_price:,.4f}</div>
</div>
<div>
<div style="font-size: 0.72rem; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Current / Exit Price</div>
<div style="font-size: 1.12rem; font-weight: 700; color: #f1f5f9;">${curr_price:,.4f}</div>
</div>
<div>
<div style="font-size: 0.72rem; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Position Size</div>
<div style="font-size: 1.12rem; font-weight: 700; color: #f1f5f9;">{qty:,.6f} <small style='color: #64748b;'>(${notional:,.2f})</small></div>
</div>
<div>
<div style="font-size: 0.72rem; color: #94a3b8; text-transform: uppercase; font-weight: 600;">{pnl_label}</div>
<div style="font-size: 1.18rem; font-weight: 700; color: {pnl_color};">
{pnl_sign}${curr_pnl:,.2f} ({pnl_sign}{curr_pnl_pct:.2f}%)
</div>
</div>
</div>
{command_box_html}
{exit_plan_html}
{notes_snippet}
</div>"""

    return strip_html_indentation(raw_html)


