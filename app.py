import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import appdirs as ad
import time
import random
from datetime import datetime

# Fix for Streamlit Cloud cache permission
ad.user_cache_dir = lambda *args, **kwargs: "/tmp"

st.set_page_config(page_title="7-Point Checklist", layout="wide")
st.title("🟢 Market Moves Matt 7-Point Checklist")
st.markdown("**Cash-Secured Put Selling Checklist**")

# Auto Refresh Button
if st.button("🔄 Force Refresh Data", type="primary", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

ticker_input = st.sidebar.text_input("Ticker Symbol", value="SPY", max_chars=10).upper().strip()
days = st.sidebar.slider("Historical days", 30, 365, 180)

if not ticker_input:
    st.stop()

# =============================================
@st.cache_data(ttl=600, show_spinner=False)   # 10 minutes cache
def get_data(symbol):
    max_retries = 4
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(symbol)
            
            # Small random delay to avoid hitting limits
            time.sleep(random.uniform(1.0, 2.0))
            
            hist = stock.history(period=f"{days}d", auto_adjust=True)
            
            if hist.empty:
                time.sleep(1.5)
                hist = stock.history(period=f"{days}d")
            
            info = stock.info
            options_dates = stock.options
            
            st.success(f"✅ Data loaded successfully (Attempt {attempt+1})")
            return stock, hist, info, options_dates
            
        except Exception as e:
            error_str = str(e).lower()
            if "too many requests" in error_str or "rate limited" in error_str or "429" in error_str:
                wait_time = (2 ** attempt) + random.uniform(0, 2)  # Exponential backoff
                if attempt < max_retries - 1:
                    st.warning(f"⏳ Rate limited. Waiting {wait_time:.1f} seconds... (Attempt {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    st.error("🚨 Still rate limited after multiple attempts. Try again in 1-2 minutes.")
            else:
                st.error(f"Error: {str(e)}")
                break
    return None, pd.DataFrame(), {}, []

# Fetch data
with st.spinner("Fetching latest market data..."):
    stock, hist, info, options_dates = get_data(ticker_input)

if hist.empty or stock is None:
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

rsi_series = calculate_rsi(close)
current_rsi = round(float(rsi_series.iloc[-1]), 1)

is_green_cloud = float(ema9.iloc[-1]) > float(ema21.iloc[-1])
is_red_day = float(close.iloc[-1]) < float(close.iloc[-2]) if len(close) > 1 else False

# IV
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

# ====================== CHECKLIST ======================
st.header(f"**{ticker_input}** — ${current_price} | Last updated: {datetime.now().strftime('%H:%M:%S')}")

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
    max_position = account_size * 0.30
    position_size = st.number_input("Planned Position Size ($)", value=int(max_position * 0.75), step=500)
    
    st.metric("5. Position ≤ 30%?", 
              "✅ PASS" if position_size <= max_position else "❌ FAIL",
              f"Max: ${max_position:,.0f}")

    credit = st.number_input("Expected Credit per Contract ($)", value=1.25, step=0.05)
    contracts = st.number_input("Number of Contracts", value=5, min_value=1)
    
    premium = credit * 100 * contracts
    capital = current_price * 100 * contracts
    est_roi = round((premium / capital) * 100, 1) if capital > 0 else 0
    
    st.metric("6. ~5% ROI Target?", 
              "✅ PASS" if est_roi >= 5 else "❌ FAIL", 
              f"Est. ROI: {est_roi}%")

# Final Result
passed = sum([is_green_cloud, current_rsi < 50, iv > 50, is_red_day, 
              position_size <= max_position, est_roi >= 5])

st.markdown("---")
if passed >= 5:
    st.success(f"🎉 **{passed}/6 CHECKS PASSED** — Looks like a good setup!")
else:
    st.warning(f"⚠️ Only {passed}/6 checks passed. Consider waiting.")

# Charts + Options (same as before)
# ... (keep the charts and options chain code from previous version)

st.caption("Auto retry enabled • Not financial advice")