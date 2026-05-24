import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import appdirs as ad
import time
import random
from datetime import datetime

ad.user_cache_dir = lambda *args, **kwargs: "/tmp"

st.set_page_config(page_title="Matt's 7-Point Checklist", layout="wide")
st.title("🟢 Market Moves Matt 7-Point Checklist")
st.markdown("**Cash-Secured Put Selling Scanner**")

# ====================== WEEKLY TICKERS ======================
@st.cache_data(ttl=3600, show_spinner=False)
def get_weekly_tickers():
    try:
        # Default list from your request
        tickers = ["NVDA", "CEG", "TSLA", "TSLL", "SOXL"]
        # Future: We can scrape https://www.thecapitalflywheel.com/live/2026-05-23 here
        return tickers
    except:
        return ["NVDA", "CEG", "TSLA", "TSLL", "SOXL"]

weekly_tickers = get_weekly_tickers()

# Sidebar for single ticker
st.sidebar.header("Single Ticker Deep Dive")
single_ticker = st.sidebar.text_input("Enter Ticker", value="SPY", max_chars=10).upper().strip()
days = st.sidebar.slider("History (days)", 30, 730, 365)

# Main Tabs
tab1, tab2 = st.tabs(["📊 Multi-Ticker Overview", "🔍 Single Ticker Deep Dive"])

# ====================== MULTI TICKER OVERVIEW (Tab 1) ======================
with tab1:
    st.header("📈 Weekly Watchlist Overview")
    st.caption(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    if st.button("🔄 Refresh All Tickers", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    user_tickers = st.multiselect("Add Extra Tickers", 
                                  ["AAPL", "QQQ", "AMD", "SMCI", "ARM", "AVGO", "COIN", "META"],
                                  default=[])
    
    all_tickers = list(dict.fromkeys(weekly_tickers + user_tickers))

    cols = st.columns(3)
    for i, ticker in enumerate(all_tickers):
        with cols[i % 3]:
            with st.container(border=True):
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="60d")
                    if hist.empty:
                        st.error(f"{ticker} - No data")
                        continue

                    close = hist['Close']
                    price = round(float(close.iloc[-1]), 2)

                    ema9 = close.ewm(span=9, adjust=False).mean()
                    ema21 = close.ewm(span=21, adjust=False).mean()
                    
                    # RSI
                    delta = close.diff()
                    gain = delta.where(delta > 0, 0).rolling(14).mean()
                    loss = -delta.where(delta < 0, 0).rolling(14).mean()
                    rs = gain / loss
                    rsi_val = round(100 - (100 / (1 + rs)).iloc[-1], 1)

                    # Rough IV
                    iv = 35.0
                    try:
                        opts = stock.options
                        if opts:
                            chain = stock.option_chain(opts[0])
                            puts = chain.puts
                            atm_idx = (puts['strike'] - price).abs().idxmin()
                            iv = round(float(puts.loc[atm_idx, 'impliedVolatility']) * 100, 1)
                    except:
                        pass

                    green_cloud = float(ema9.iloc[-1]) > float(ema21.iloc[-1])
                    red_day = float(close.iloc[-1]) < float(close.iloc[-2]) if len(close) > 1 else False

                    score = sum([green_cloud, rsi_val < 50, iv > 50, red_day])

                    color = "🟢" if score >= 3 else "🟡" if score == 2 else "🔴"

                    st.subheader(f"{color} {ticker} — ${price}")
                    st.metric("Score", f"{score}/4", delta=None)
                    st.progress(score / 4)

                    st.write("**Conditions:**")
                    st.success("EMA Cloud Green") if green_cloud else st.error("EMA Cloud")
                    st.success("RSI < 50") if rsi_val < 50 else st.error("RSI")
                    st.success("IV > 50%") if iv > 50 else st.error("IV")
                    st.success("Red Day") if red_day else st.warning("Not Red Day")

                except Exception as e:
                    st.error(f"Error loading {ticker}")

# ====================== SINGLE TICKER DEEP DIVE (Tab 2) ======================
with tab2:
    if not single_ticker:
        st.info("Please enter a ticker in the sidebar")
        st.stop()

    st.header(f"Deep Dive: **{single_ticker}**")

    if st.button("🔄 Refresh This Ticker", type="primary"):
        st.cache_data.clear()
        st.rerun()

    @st.cache_data(ttl=180)
    def get_single_data(symbol, days):
        stock = yf.Ticker(symbol)
        hist = stock.history(period=f"{days}d")
        options_dates = stock.options
        return stock, hist, options_dates

    stock, hist, options_dates = get_single_data(single_ticker, days)

    if hist.empty:
        st.error("No historical data found for this ticker.")
        st.stop()

    close = hist['Close']
    current_price = round(float(close.iloc[-1]), 2)

    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()

    def calculate_rsi(data, periods=14):
        delta = data.diff()
        gain = delta.where(delta > 0, 0).rolling(window=periods).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=periods).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    rsi = calculate_rsi(close)
    current_rsi = round(float(rsi.iloc[-1]), 1)

    is_green_cloud = float(ema9.iloc[-1]) > float(ema21.iloc[-1])
    is_red_day = float(close.iloc[-1]) < float(close.iloc[-2]) if len(close) > 1 else False

    iv = 35.0
    try:
        if options_dates:
            chain = stock.option_chain(options_dates[0])
            puts = chain.puts
            if not puts.empty:
                atm_idx = (puts['strike'] - current_price).abs().idxmin()
                iv = round(float(puts.loc[atm_idx, 'impliedVolatility']) * 100, 1)
    except:
        pass

    # Detailed View
    col1, col2 = st.columns([1.1, 1])
    with col1:
        st.subheader("1. EMA Cloud Green (9 > 21)")
        st.success("✅ PASS") if is_green_cloud else st.error("❌ FAIL")
        
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=hist.index[-90:], y=close[-90:], name="Price"))
        fig1.add_trace(go.Scatter(x=hist.index[-90:], y=ema9[-90:], name="EMA 9"))
        fig1.add_trace(go.Scatter(x=hist.index[-90:], y=ema21[-90:], name="EMA 21"))
        st.plotly_chart(fig1, use_container_width=True)

        st.subheader("2. RSI Below 50")
        st.success("✅ PASS") if current_rsi < 50 else st.error("❌ FAIL")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=hist.index[-90:], y=rsi[-90:], name="RSI"))
        fig2.add_hline(y=50, line_dash="dash", line_color="red")
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        st.subheader("Risk Management")
        account_size = st.number_input("Account Size ($)", value=50000, min_value=10000, step=1000)
        max_pos = account_size * 0.30
        position_size = st.number_input("Planned Position Size ($)", value=int(max_pos * 0.75), step=500)
        
        st.metric("5. Position ≤ 30%?", 
                  "✅ PASS" if position_size <= max_pos else "❌ FAIL",
                  f"Max: ${max_pos:,.0f}")

        credit = st.number_input("Expected Credit per Contract ($)", value=1.25, step=0.05)
        contracts = st.number_input("Number of Contracts", value=5, min_value=1)
        
        premium = credit * 100 * contracts
        capital = current_price * 100 * contracts
        est_roi = round((premium / capital) * 100, 1) if capital > 0 else 0
        
        st.metric("6. ~5% ROI Target?", 
                  "✅ PASS" if est_roi >= 5 else "❌ FAIL", 
                  f"Est. ROI: {est_roi}%")

    st.success(f"**Final Score: {sum([is_green_cloud, current_rsi < 50, iv > 50, is_red_day, position_size <= max_pos, est_roi >= 5])}/6**")

st.caption("Educational tool only • Not financial advice")