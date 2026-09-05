"""
Trade Reconciliation and Net Position Engine.
Matches BUY and SELL orders, calculates realized PnL, and filters out crypto dust.
"""

from typing import List, Dict, Any, Tuple, Optional
import pandas as pd
import numpy as np


from src.supabase_client import OPEN_ORDER_STATUSES


def normalize_side(val: Any) -> str:
    """Normalize 'orderside.buy', 'BUY', 'buy', 'orderside.sell', etc."""
    s = str(val).strip().lower()
    if "buy" in s:
        return "BUY"
    elif "sell" in s:
        return "SELL"
    return str(val).upper()


def enrich_risk_metrics(rec: Dict[str, Any], orders_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """
    Ensure take_profit_price, stop_loss_price, estimated_tp_pnl, estimated_sl_pnl,
    and risk_reward_ratio are fully populated and never missing.
    Checks:
    1. Explicit values in the trade record.
    2. Resting limit/stop orders in orders_df from Alpaca.
    3. Quantitative strategy target formulas (Crypto +6%/-5%, VWAP +2.5%/-1.25%, Swing +5%/-3%).
    """
    qty = float(rec.get("qty") or 0.0)
    entry_price = float(rec.get("entry_price") or 0.0)
    side = normalize_side(rec.get("side", "BUY"))
    symbol = str(rec.get("symbol", "")).upper()
    strategy = str(rec.get("strategy_tag", "")).lower()
    asset_class = str(rec.get("asset_class", "")).lower()

    tp_price = rec.get("take_profit_price")
    sl_price = rec.get("stop_loss_price")

    # 1. If not set, check resting orders in orders_df
    if (tp_price is None or pd.isna(tp_price) or float(tp_price) <= 0) and orders_df is not None and not orders_df.empty:
        open_matches = orders_df[
            (orders_df["symbol"] == symbol) &
            (orders_df["status"].str.lower().isin(OPEN_ORDER_STATUSES))
        ]
        if not open_matches.empty:
            for _, o in open_matches.iterrows():
                o_type = str(o.get("order_type", "")).lower()
                o_limit = float(o.get("limit_price") or 0.0)
                o_stop = float(o.get("stop_price") or 0.0)
                if o_type == "limit" and o_limit > 0:
                    tp_price = o_limit
                elif "stop" in o_type and o_stop > 0:
                    sl_price = o_stop

    # 2. If still not set, calculate based on quantitative strategy profile
    if (tp_price is None or pd.isna(tp_price) or float(tp_price) <= 0) and entry_price > 0:
        if "vwap" in strategy or "intraday" in strategy:
            tp_pct_target = 2.5
        elif "crypto" in strategy or asset_class == "crypto" or "/" in symbol:
            tp_pct_target = 6.0
        else:
            tp_pct_target = 5.0

        if side == "BUY":
            tp_price = entry_price * (1.0 + tp_pct_target / 100.0)
        else:
            tp_price = entry_price * (1.0 - tp_pct_target / 100.0)

    if (sl_price is None or pd.isna(sl_price) or float(sl_price) <= 0) and entry_price > 0:
        if "vwap" in strategy or "intraday" in strategy:
            sl_pct_target = 1.25
        elif "crypto" in strategy or asset_class == "crypto" or "/" in symbol:
            sl_pct_target = 5.0
        else:
            sl_pct_target = 3.0

        if side == "BUY":
            sl_price = entry_price * (1.0 - sl_pct_target / 100.0)
        else:
            sl_price = entry_price * (1.0 + sl_pct_target / 100.0)

    # 3. Format and derive PnL / % values
    if tp_price is not None and float(tp_price) > 0 and entry_price > 0:
        tp_price = float(tp_price)
        rec["take_profit_price"] = round(tp_price, 4)
        tp_pnl = (tp_price - entry_price) * qty if side == "BUY" else (entry_price - tp_price) * qty
        tp_pct = ((tp_price - entry_price) / entry_price * 100) if side == "BUY" else ((entry_price - tp_price) / entry_price * 100)
        rec["estimated_tp_pnl"] = round(tp_pnl, 2)
        rec["estimated_tp_pct"] = round(tp_pct, 2)

    if sl_price is not None and float(sl_price) > 0 and entry_price > 0:
        sl_price = float(sl_price)
        rec["stop_loss_price"] = round(sl_price, 4)
        sl_pnl = (sl_price - entry_price) * qty if side == "BUY" else (entry_price - sl_price) * qty
        sl_pct = ((sl_price - entry_price) / entry_price * 100) if side == "BUY" else ((entry_price - sl_price) / entry_price * 100)
        rec["estimated_sl_pnl"] = round(sl_pnl, 2)
        rec["estimated_sl_pct"] = round(sl_pct, 2)

    tp_pnl_val = rec.get("estimated_tp_pnl")
    sl_pnl_val = rec.get("estimated_sl_pnl")
    if tp_pnl_val is not None and sl_pnl_val is not None and float(sl_pnl_val) != 0:
        rec["risk_reward_ratio"] = round(abs(float(tp_pnl_val) / float(sl_pnl_val)), 2)
    else:
        rec["risk_reward_ratio"] = 1.5

    return rec


def reconcile_trades_and_positions(
    trades_df: pd.DataFrame,
    orders_df: Optional[pd.DataFrame] = None,
    dust_threshold_usd: float = 1.00,
    dust_pct_threshold: float = 0.01,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Takes raw execution rows from public.trades and produces:
    1. active_positions_df: True net open positions (filtering out dust/fee residue).
    2. closed_trades_df: Fully reconciled round-trip trades with calculated realized PnL.
    """
    if trades_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = trades_df.copy()
    
    # Ensure numeric columns are floats
    num_cols = ["qty", "notional", "entry_price", "exit_price", "fees", "realized_pnl", "pnl_percent"]
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Normalize side
    df["norm_side"] = df["side"].apply(normalize_side)
    
    # Sort chronologically by entry_time and id
    sort_cols = [c for c in ["entry_time", "created_at", "id"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, ascending=True)

    closed_records: List[Dict[str, Any]] = []
    active_records: List[Dict[str, Any]] = []

    # Group by symbol to reconcile each asset's order flow
    for symbol, group in df.groupby("symbol", sort=False):
        # Open inventory queue: list of dicts representing unclosed lots
        # Each item: {'qty': float, 'orig_qty': float, 'price': float, 'row': pd.Series}
        inventory: List[Dict[str, Any]] = []

        for _, row in group.iterrows():
            status = str(row.get("status", "")).upper()
            # If the trade is already marked CLOSED in the database, directly add to closed records
            if status == "CLOSED":
                closed_records.append(enrich_risk_metrics(row.to_dict(), orders_df=orders_df))
                continue

            side = row["norm_side"]
            qty = float(row.get("qty", 0.0))
            price = float(row.get("entry_price", 0.0))
            if price == 0.0 and float(row.get("exit_price", 0.0)) > 0:
                price = float(row.get("exit_price", 0.0))
            fees = float(row.get("fees", 0.0))

            if qty <= 0:
                continue

            current_qty = qty

            # Check if this order opposes current inventory
            while inventory and current_qty > 0:
                inv_lot = inventory[0]
                inv_side = inv_lot["side"]

                # If same side, we are adding to position (e.g. BUY after BUY)
                if inv_side == side:
                    break

                # Opposite side detected: MATCH AND CLOSE LOT
                match_qty = min(current_qty, inv_lot["qty"])
                buy_price = inv_lot["price"] if inv_side == "BUY" else price
                sell_price = price if side == "SELL" else inv_lot["price"]
                
                # Realized PnL for this matched lot
                pnl = (sell_price - buy_price) * match_qty - fees
                pnl_pct = ((sell_price - buy_price) / buy_price * 100) if buy_price > 0 else 0.0

                matched_trade = {
                    "id": f"{inv_lot['row']['id']}-{row['id']}",
                    "symbol": symbol,
                    "asset_class": row.get("asset_class", inv_lot["row"].get("asset_class", "crypto")),
                    "strategy_tag": row.get("strategy_tag", inv_lot["row"].get("strategy_tag", "manual")),
                    "side": inv_side,  # Initial direction of trade
                    "qty": match_qty,
                    "notional": round(match_qty * buy_price, 2),
                    "entry_price": buy_price,
                    "exit_price": sell_price,
                    "entry_time": inv_lot["row"].get("entry_time"),
                    "exit_time": row.get("entry_time") or row.get("exit_time"),
                    "status": "CLOSED",
                    "fees": fees,
                    "realized_pnl": round(pnl, 4),
                    "pnl_percent": round(pnl_pct, 2),
                    "stop_loss_order_id": inv_lot["row"].get("stop_loss_order_id"),
                    "take_profit_order_id": inv_lot["row"].get("take_profit_order_id"),
                    "take_profit_price": inv_lot["row"].get("take_profit_price"),
                    "stop_loss_price": inv_lot["row"].get("stop_loss_price"),
                    "estimated_tp_pnl": inv_lot["row"].get("estimated_tp_pnl"),
                    "estimated_tp_pct": inv_lot["row"].get("estimated_tp_pct"),
                    "estimated_sl_pnl": inv_lot["row"].get("estimated_sl_pnl"),
                    "estimated_sl_pct": inv_lot["row"].get("estimated_sl_pct"),
                    "risk_reward_ratio": inv_lot["row"].get("risk_reward_ratio"),
                    "notes": f"Matched Round-Trip: Entry #{inv_lot['row']['id']} -> Exit #{row['id']}",
                    "created_at": row.get("created_at"),
                }
                closed_records.append(enrich_risk_metrics(matched_trade, orders_df=orders_df))

                # Deduct matched quantities
                current_qty -= match_qty
                inv_lot["qty"] -= match_qty

                # If the lot is exhausted or left with dust
                rem_val = inv_lot["qty"] * inv_lot["price"]
                rem_ratio = inv_lot["qty"] / max(1e-8, inv_lot["orig_qty"])
                if inv_lot["qty"] <= 1e-8 or rem_val < dust_threshold_usd or rem_ratio < dust_pct_threshold:
                    inventory.pop(0)

            # If there's still quantity remaining after matching existing inventory
            if current_qty > 0:
                rem_val = current_qty * price
                # Only add if not negligible dust
                if rem_val >= dust_threshold_usd:
                    inventory.append({
                        "qty": current_qty,
                        "orig_qty": current_qty,
                        "price": price,
                        "side": side,
                        "row": row,
                    })

        # Whatever remains in inventory is truly an active position
        for lot in inventory:
            lot_qty = lot["qty"]
            lot_price = lot["price"]
            lot_notional = round(lot_qty * lot_price, 2)
            orig_row = lot["row"]

            # Filter out dust
            if lot_notional >= dust_threshold_usd:
                active_rec = {
                    "id": orig_row.get("id"),
                    "symbol": symbol,
                    "asset_class": orig_row.get("asset_class", "crypto"),
                    "strategy_tag": orig_row.get("strategy_tag", "manual"),
                    "side": lot["side"],
                    "qty": round(lot_qty, 8),
                    "notional": lot_notional,
                    "entry_price": round(lot_price, 4),
                    "exit_price": 0.0,
                    "entry_time": orig_row.get("entry_time"),
                    "exit_time": None,
                    "status": "OPEN",
                    "fees": float(orig_row.get("fees", 0.0)),
                    "realized_pnl": 0.0,
                    "pnl_percent": 0.0,
                    "stop_loss_order_id": orig_row.get("stop_loss_order_id"),
                    "take_profit_order_id": orig_row.get("take_profit_order_id"),
                    "take_profit_price": orig_row.get("take_profit_price"),
                    "stop_loss_price": orig_row.get("stop_loss_price"),
                    "estimated_tp_pnl": orig_row.get("estimated_tp_pnl"),
                    "estimated_tp_pct": orig_row.get("estimated_tp_pct"),
                    "estimated_sl_pnl": orig_row.get("estimated_sl_pnl"),
                    "estimated_sl_pct": orig_row.get("estimated_sl_pct"),
                    "risk_reward_ratio": orig_row.get("risk_reward_ratio"),
                    "notes": orig_row.get("notes"),
                    "created_at": orig_row.get("created_at"),
                }
                active_records.append(enrich_risk_metrics(active_rec, orders_df=orders_df))

    active_df = pd.DataFrame(active_records) if active_records else pd.DataFrame(columns=trades_df.columns)
    closed_df = pd.DataFrame(closed_records) if closed_records else pd.DataFrame(columns=trades_df.columns)

    # Sort results
    if not active_df.empty and "entry_time" in active_df.columns:
        active_df = active_df.sort_values("entry_time", ascending=False)
    if not closed_df.empty and "exit_time" in closed_df.columns:
        closed_df = closed_df.sort_values("exit_time", ascending=False)

    return active_df, closed_df

