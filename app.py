import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
import appdirs as ad

# Fix for yfinance cache permission error on Streamlit Cloud
ad.user_cache_dir = lambda *args, **kwargs: "/tmp"

st.set_page_config(page_title="7-Point Options Checklist", layout="wide")
st.title("🟢 Market Moves Matt 7-Point Checklist")
st.markdown("**Cash-Secured Put Selling Checklist**")

# Sidebar
ticker_input = st.sidebar.text_input("Ticker Symbol", value="SPY", max_chars=10).upper().strip()
days = st.sidebar.slider("Historical days", 30, 365, 180)
target_dte = st.sidebar.slider("Target Days to Expiration", 7, 60, 30)

if not ticker_input:
    st.stop()

# Fetch data with better error handling
@st.cache_data(ttl=180, show_spinner=False)
def get_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        hist = stock.history(period=f"{days}d", auto_adjust=True)
        
        if hist.empty:
            # Try with different parameters
            hist = stock.history(period=f"{days}d", interval="1d")
        
        info = stock.info
        options_dates = stock.options
        return stock, hist, info, options_dates
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return None, pd.DataFrame(), {}, []

stock, hist, info, options_dates = get_data(ticker_input)

if hist.empty or stock is None:
    st.error(f"❌ Could not fetch data for **{ticker_input}**. Try these common fixes:")
    st.markdown("""
    - Check if the ticker is correct (e.g. SPY, QQQ, AAPL, TSLA)
    - Try again in 10-30 seconds (yfinance rate limits)
    - Try a different ticker
    """)
    st.stop()

# Calculations
close = hist['Close']
current_price = close.iloc[-1]

# EMA
ema9 = close.ewm(span=9, adjust=False).mean()
ema21 = close.ewm(span=21, adjust=False).mean()

# RSI
def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = delta.where(delta > 0, 0).rolling(window=periods).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=periods).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

rsi = calculate_rsi(close)
current_rsi = rsi.iloc[-1]

is_green_cloud = ema9.iloc[-1] > ema21.iloc[-1]
is_red_day = close.iloc[-1] < close.iloc[-2] if len(close) > 1 else False

# Get IV
iv = None
try:
    if options_dates:
        chain = stock.option_chain(options_dates[0])
        puts = chain.puts
        if not puts.empty:
            atm_idx = (puts['strike'] - current_price).abs().idxmin()
            iv = puts.loc[atm_idx, 'impliedVolatility'] * 100
except:
    iv = None

if iv is None:
    iv = 35.0  # fallback

# ====================== CHECKLIST ======================
st.header(f"Analysis for **{ticker_input}** — ${current_price:.2f}")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1-4 Market Conditions")
    st.metric("1. EMA Cloud Green?", "✅ PASS" if is_green_cloud else "❌ FAIL", 
              f"EMA9 {ema9.iloc[-1]:.2f} > EMA21 {ema21.iloc[-1]:.2f}")
    
    st.metric("2. RSI < 50?", "✅ PASS" if current_rsi < 50 else "❌ FAIL", 
              f"RSI = {current_rsi:.1f}")
    
    st.metric("3. IV > 50%?", "✅ PASS" if iv > 50 else "❌ FAIL", 
              f"IV ≈ {iv:.1f}%")
    
    st.metric("4. Red Day?", "✅ PASS" if is_red_day else "❌ FAIL", 
              "Price closed lower than previous day")

with col2:
    st.subheader("5-7 Risk Management")
    account_size = st.number_input("Account Size ($)", value=50000, min_value=5000, step=1000)
    max_risk = account_size * 0.30
    position_size = st.number_input("Planned Position Size ($)", value=int(max_risk * 0.7), step=500)
    
    st.metric("5. Position ≤ 30% of Account?", 
              "✅ PASS" if position_size <= max_risk else "❌ FAIL", 
              f"Max allowed: ${max_risk:,.0f}")

    credit = st.number_input("Expected Credit per Contract ($)", value=1.20, step=0.05)
    contracts = st.number_input("Number of Contracts", value=5, min_value=1)
    
    premium = credit * 100 * contracts
    capital_required = current_price * 100 * contracts
    est_roi = (premium / capital_required) * 100 if capital_required > 0 else 0
    
    st.metric("6. ~5% Return Potential?", 
              "✅ PASS" if est_roi >= 5 else "❌ FAIL", 
              f"Est. ROI: {est_roi:.1f}%")

# Final Result
checks_passed = sum([
    is_green_cloud,
    current_rsi < 50,
    iv > 50,
    is_red_day,
    position_size <= max_risk,
    est_roi >= 5
])

st.markdown("---")
if checks_passed >= 6:
    st.success(f"🎉 **{checks_passed}/6 CHECKS PASSED** — Trade looks good!")
else:
    st.error(f"❌ Only {checks_passed}/6 checks passed — Skip or wait for better setup.")

# Options Preview
if options_dates:
    try:
        st.subheader(f"Nearest Expiry: {options_dates[0]}")
        chain = stock.option_chain(options_dates[0])
        puts = chain.puts[['strike', 'bid', 'ask', 'impliedVolatility', 'volume', 'openInterest']]
        otm_puts = puts[puts['strike'] < current_price * 1.02].head(10)
        st.dataframe(otm_puts.style.format({
            'impliedVolatility': '{:.1%}',
            'bid': '${:.2f}',
            'ask': '${:.2f}'
        }), use_container_width=True)
    except:
        st.info("Options chain not available right now.")

# Charts
st.subheader("Price Chart with EMAs")
fig = go.Figure()
fig.add_trace(go.Scatter(x=hist.index, y=close, name="Close"))
fig.add_trace(go.Scatter(x=hist.index, y=ema9, name="EMA 9"))
fig.add_trace(go.Scatter(x=hist.index, y=ema21, name="EMA 21"))
st.plotly_chart(fig, use_container_width=True)

st.caption("Educational tool only • Not financial advice")