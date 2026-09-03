"""
Market Data Service for Live Price Lookups.
Fetches real-time spot prices for crypto and equities with caching.
"""

from typing import Optional, Dict
import requests
import streamlit as st


@st.cache_data(ttl=10, show_spinner=False)
def fetch_live_price(symbol: str) -> Optional[float]:
    """
    Fetch current market price for a given symbol (e.g. 'BTC/USD', 'ETH/USD', 'AAPL').
    Cached for 10 seconds to ensure high performance and zero rate limiting.
    """
    sym = symbol.strip().upper()
    
    # 1. Crypto Pairs (e.g. BTC/USD, ETH/USD, BTCUSD, ETHUSD)
    clean_sym = sym.replace("/", "-")
    if "-" not in clean_sym and ("USD" in clean_sym or "USDT" in clean_sym):
        clean_sym = clean_sym.replace("USD", "-USD").replace("USDT", "-USD")
        
    if "-USD" in clean_sym or sym.startswith(("BTC", "ETH", "SOL", "DOGE", "AVAX", "LINK", "UNI")):
        try:
            # Normalize to Coinbase format (e.g. BTC-USD)
            cb_pair = clean_sym if "-USD" in clean_sym else f"{clean_sym}-USD"
            url = f"https://api.coinbase.com/v2/prices/{cb_pair}/spot"
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                price = data.get("amount")
                if price:
                    return float(price)
        except Exception:
            pass

    # 2. Equities via free public Yahoo Finance quote endpoint
    try:
        stock_sym = sym.split("/")[0]
        yf_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{stock_sym}?interval=1m&range=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(yf_url, headers=headers, timeout=3)
        if resp.status_code == 200:
            result = resp.json().get("chart", {}).get("result")
            if result and len(result) > 0:
                meta = result[0].get("meta", {})
                price = meta.get("regularMarketPrice")
                if price:
                    return float(price)
    except Exception:
        pass

    return None

