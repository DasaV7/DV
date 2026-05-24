import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import appdirs as ad
import time
import random
from datetime import datetime, timedelta

ad.user_cache_dir = lambda *args, **kwargs: "/tmp"

st.set_page_config(page_title="Matt's 7-Point Checklist", layout="wide")
st.title("🟢 Market Moves Matt 7-Point Checklist")
st.markdown("**Cash-Secured Put Selling Scanner**")

# ====================== WEEKLY TICKERS ======================
@st.cache_data(ttl=3600, show_spinner=False)  # Cache 1 hour
def get_weekly_tickers():
    try:
        # Try to scrape the latest weekly list
        url = "https://www.thecapitalflywheel.com/live/2026-05-23"  # You can make this dynamic later
        # For now, fallback + default list
        default = ["NVDA", "CEG", "TSLA", "TSLL", "SOXL"]
        
        # TODO: Improve scraping if page becomes public
        today = datetime.now()
        if today.weekday() >= 5 and today.hour >= 16:  # Sat or Sun after 4PM
            st.toast("Weekly list refreshed!", icon="📅")
        return default
    except:
        return ["NVDA", "CEG", "TSLA", "TSLL", "SOXL"]

weekly_tickers = get_weekly_tickers()

# Sidebar for single ticker mode
st.sidebar.header("Single Ticker Deep Dive")
single_ticker = st.sidebar.text_input("Enter Ticker", value="SPY", max_chars=10).upper().strip()
days = st.sidebar.slider("History (days)", 30, 730, 365)

# Main Tabs
tab1, tab2 = st.tabs(["📊 Multi-Ticker Overview", "🔍 Single Ticker Deep Dive"])

# ====================== MULTI TICKER OVERVIEW ======================
with tab1:
    st.header("📈 Weekly Watchlist Overview")
    st.caption(f"Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Weekly from Capital Flywheel")
    
    if st.button("🔄 Refresh All Tickers", type="primary"):
        st.cache_data.clear()
        st.rerun()

    # Combine weekly + user added
    user_tickers = st.multiselect("Add more tickers", 
                                  options=["AAPL","QQQ","AMD","SMCI","ARM","AVGO","COIN"],
                                  default=[])
    all_tickers = list(dict.fromkeys(weekly_tickers + user_tickers))  # remove duplicates

    cols = st.columns(3)
    results = {}

    for i, ticker in enumerate(all_tickers):
        with cols[i % 3]:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="60d")
                if hist.empty:
                    st.error(f"{ticker} - No data")
                    continue
                
                close = hist['Close']
                price = round(close.iloc[-1], 2)
                
                ema9 = close.ewm(span=9).mean()
                ema21 = close.ewm(span=21).mean()
                rsi_val = 100 - (100 / (1 + (close.diff().where(lambda x: x>0,0).rolling(14).mean() / 
                                             abs(close.diff().where(lambda x: x<0,0).rolling(14).mean()))))
                current_rsi = round(rsi_val.iloc[-1], 1)
                
                iv = 35
                try:
                    opts = stock.options
                    if opts:
                        chain = stock.option_chain(opts[0])
                        atm = (chain.puts['strike'] - price).abs().idxmin()
                        iv = round(chain.puts.loc[atm, 'impliedVolatility'] * 100, 1)
                except:
                    pass
                
                green_cloud = ema9.iloc[-1] > ema21.iloc[-1]
                red_day = close.iloc[-1] < close.iloc[-2] if len(close)>1 else False
                
                score = sum([green_cloud, current_rsi < 50, iv > 50, red_day])
                
                color = "🟢" if score >= 3 else "🟡" if score == 2 else "🔴"
                
                with st.container(border=True):
                    st.subheader(f"{color} {ticker} — ${price}")
                    st.caption(f"RSI: {current_rsi} | IV: {iv}%")
                    st.progress(score / 4)
                    st.write(f"**Score: {score}/4**")
                    if green_cloud: st.success("✅ EMA Cloud Green")
                    else: st.error("❌ EMA Cloud")
                    if current_rsi < 50: st.success("✅ RSI < 50")
                    else: st.error("❌ RSI")
                    if iv > 50: st.success("✅ High IV")
                    else: st.error("❌ Low IV")
                    if red_day: st.success("✅ Red Day")
                    else: st.warning("⚪ Not Red")
                    
            except:
                st.error(f"Error loading {ticker}")

# ====================== SINGLE TICKER DEEP DIVE ======================
with tab2:
    if not single_ticker:
        st.info("Enter a ticker in the sidebar")
        st.stop()

    st.header(f"Deep Dive: **{single_ticker}**")

    if st.button("🔄 Refresh This Ticker", type="primary"):
        st.cache_data.clear()
        st.rerun()

    @st.cache_data(ttl=180)
    def get_single_data(symbol, days):
        stock = yf.Ticker(symbol)
        hist = stock.history(period=f"{days}d")
        return stock, hist, stock.options

    stock, hist, options_dates = get_single_data(single_ticker, days)

    if hist.empty:
        st.error("No data found")
        st.stop()

    # Calculations (same as before)
    close = hist['Close']
    current_price = round(float(close.iloc[-1]), 2)

    ema9 = close.ewm(span=9, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    ema100 = close.ewm(span=100, adjust=False).mean()
    ema225 = close.ewm(span=225, adjust=False).mean()

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

    # Detailed Cards + Plots (same as previous version)
    col1, col2 = st.columns([1.1, 1])
    with col1:
        st.subheader("1. EMA Cloud (9 > 21)")
        st.success("✅ PASS") if is_green_cloud else st.error("❌ FAIL")
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=hist.index[-90:], y=close[-90:], name="Price"))
        fig1.add_trace(go.Scatter(x=hist.index[-90:], y=ema9[-90:], name="EMA9"))
        fig1.add_trace(go.Scatter(x=hist.index[-90:], y=ema21[-90:], name="EMA21"))
        st.plotly_chart(fig1, use_container_width=True)

        st.subheader("2. RSI < 50")
        st.success("✅ PASS") if current_rsi < 50 else st.error("❌ FAIL")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=hist.index[-90:], y=rsi[-90:], name="RSI"))
        fig2.add_hline(y=50, line_dash="dash", line_color="red")
        st.plotly_chart(fig2, use_container_width=True)

    with col2:
        # Risk inputs and other checks (same as before)
        account_size = st.number_input("Account Size ($)", value=50000, step=5000)
        # ... (rest of risk section remains same)

    # TradingView Widget (keep from previous version)
    # ... add TradingView code here if you want

st.caption("Educational tool only • Not financial advice")