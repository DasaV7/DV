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

st.set_page_config(page_title="7-Point Checklist", layout="wide")
st.title("🟢 Market Moves Matt 7-Point Checklist")
st.markdown("**Cash-Secured Put Selling Checklist**")

# Refresh Button
if st.button("🔄 Refresh All Data", type="primary", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

ticker_input = st.sidebar.text_input("Ticker Symbol", value="SPY", max_chars=10).upper().strip()
days = st.sidebar.slider("Historical days", 30, 365, 180)

if not ticker_input:
    st.stop()

# Use a refresh key to force update when button is clicked
refresh_key = st.session_state.get("refresh_key", 0)

# =============================================
@st.cache_data(ttl=300, show_spinner=False)
def get_market_data(symbol, days, refresh_key):
    max_retries = 4
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(symbol)
            time.sleep(random.uniform(1.0, 1.8))
            
            hist = stock.history(period=f"{days}d", auto_adjust=True)
            if hist.empty:
                time.sleep(1.5)
                hist = stock.history(period=f"{days}d")
            
            options_dates = stock.options
            info = stock.info
            
            st.toast(f"✅ Loaded {symbol} successfully", icon="✅")
            return hist, info, options_dates, True
            
        except Exception as e:
            error_str = str(e).lower()
            if any(x in error_str for x in ["too many requests", "rate", "429"]):
                wait = (2 ** attempt) + random.uniform(0.5, 2.5)
                if attempt < max_retries - 1:
                    st.warning(f"⏳ Rate limited. Waiting {wait:.1f}s... (Attempt {attempt+1})")
                    time.sleep(wait)
                continue
            else:
                st.error(f"Error fetching {symbol}: {str(e)}")
                break
    return pd.DataFrame(), {}, [], False

# Fetch data
with st.spinner(f"Fetching data for **{ticker_input}**..."):
    hist, info, options_dates, success = get_market_data(ticker_input, days, refresh_key)

if not success or hist.empty:
    st.error("❌ Failed to load data. Try clicking **Refresh** again after 15-30 seconds.")
    st.stop()

# ====================== CALCULATIONS ======================
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

current_rsi = round(float(calculate_rsi(close).iloc[-1]), 1)
is_green_cloud = float(ema9.iloc[-1]) > float(ema21.iloc[-1])
is_red_day = float(close.iloc[-1]) < float(close.iloc[-2]) if len(close) > 1 else False

# IV
iv = 35.0
try:
    if options_dates:
        stock = yf.Ticker(ticker_input)
        chain = stock.option_chain(options_dates[0])
        puts = chain.puts
        if not puts.empty:
            atm_idx = (puts['strike'] - current_price).abs().idxmin()
            iv = round(float(puts.loc[atm_idx, 'impliedVolatility']) * 100, 1)
except:
    pass

# ====================== UI ======================
st.header(f"**{ticker_input}** — ${current_price} | {datetime.now().strftime('%H:%M:%S')}")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Market Conditions")
    st.metric("1. EMA Cloud Green?", "✅ PASS" if is_green_cloud else "❌ FAIL")
    st.metric("2. RSI < 50?", "✅ PASS" if current_rsi < 50 else "❌ FAIL", f"RSI: {current_rsi}")
    st.metric("3. IV > 50%?", "✅ PASS" if iv > 50 else "❌ FAIL", f"IV: {iv}%")
    st.metric("4. Red Day?", "✅ PASS" if is_red_day else "❌ FAIL")

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

passed = sum([is_green_cloud, current_rsi < 50, iv > 50, is_red_day, 
              position_size <= max_pos, est_roi >= 5])

st.markdown("---")
if passed >= 5:
    st.success(f"🎉 **{passed}/6 CHECKS PASSED** — Good setup!")
else:
    st.warning(f"⚠️ Only {passed}/6 checks passed.")

# Chart
fig = go.Figure()
fig.add_trace(go.Scatter(x=hist.index, y=close, name="Price"))
fig.add_trace(go.Scatter(x=hist.index, y=ema9, name="EMA 9"))
fig.add_trace(go.Scatter(x=hist.index, y=ema21, name="EMA 21"))
st.plotly_chart(fig, use_container_width=True)

st.caption("Educational tool only • Not financial advice")