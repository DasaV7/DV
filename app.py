import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go

st.set_page_config(page_title="Options Selling Checklist", layout="wide")
st.title("🟢 Market Moves Matt 7-Point Checklist")
st.markdown("**For selling cash-secured puts** - Enter a ticker to run the full checklist.")

# Sidebar inputs
ticker = st.sidebar.text_input("Ticker Symbol", value="SPY", max_chars=10).upper().strip()
days = st.sidebar.slider("Days of historical data", 30, 365, 180)
expiry_days = st.sidebar.slider("Target DTE (days to expiration)", 7, 60, 30)

if not ticker:
    st.stop()

# Fetch data
@st.cache_data(ttl=300)
def get_data(symbol):
    stock = yf.Ticker(symbol)
    hist = stock.history(period=f"{days}d")
    info = stock.info
    options = stock.options
    return stock, hist, info, options

try:
    stock, hist, info, options_dates = get_data(ticker)
except:
    st.error("Invalid ticker or data unavailable.")
    st.stop()

if hist.empty:
    st.error("No historical data found.")
    st.stop()

# Calculate indicators
close = hist['Close']
high = hist['High']
low = hist['Low']

# EMA Clouds (typically 8/21 or similar - using common 9/21)
ema9 = close.ewm(span=9, adjust=False).mean()
ema21 = close.ewm(span=21, adjust=False).mean()

# RSI
def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

rsi = calculate_rsi(close)

# Current values
current_price = close.iloc[-1]
current_rsi = rsi.iloc[-1]
is_green_cloud = ema9.iloc[-1] > ema21.iloc[-1]
is_red_day = close.iloc[-1] < close.iloc[-2] if len(close) > 1 else False

# IV - approximate from options
iv = None
try:
    if options_dates:
        nearest_expiry = options_dates[0]
        opt_chain = stock.option_chain(nearest_expiry)
        calls = opt_chain.calls
        puts = opt_chain.puts
        # Rough ATM IV
        atm_strike = round(current_price / 5) * 5
        atm_put = puts.iloc[(puts['strike'] - current_price).abs().argsort()[:1]]
        if not atm_put.empty:
            iv = atm_put['impliedVolatility'].iloc[0] * 100
except:
    pass

if iv is None:
    iv = 35  # fallback

# Checklist
st.header(f"Checklist for **{ticker}** @ ${current_price:.2f}")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Technical & Market Conditions")
    
    # 1. EMA Clouds Green?
    status1 = "✅ PASS" if is_green_cloud else "❌ FAIL"
    st.metric("1. EMA Clouds Green?", status1, f"EMA9: {ema9.iloc[-1]:.2f} | EMA21: {ema21.iloc[-1]:.2f}")
    
    # 2. RSI < 50?
    status2 = "✅ PASS" if current_rsi < 50 else "❌ FAIL"
    st.metric("2. RSI Below 50?", status2, f"RSI: {current_rsi:.1f}")
    
    # 3. IV > 50%?
    status3 = "✅ PASS" if iv > 50 else "❌ FAIL"
    st.metric("3. Implied Volatility > 50%?", status3, f"IV: {iv:.1f}%")
    
    # 4. Red Day?
    status4 = "✅ PASS" if is_red_day else "❌ FAIL (Green/Flat day)"
    st.metric("4. Red Day?", status4)

with col2:
    st.subheader("Risk & Trade Setup")
    
    # 5. Position size (manual input)
    account_size = st.number_input("Your Account Size ($)", min_value=1000, value=50000, step=1000)
    max_position = account_size * 0.3
    position_size = st.number_input("Planned Position Size ($)", min_value=100, value=int(max_position * 0.8), step=100)
    status5 = "✅ PASS" if position_size <= max_position else "❌ FAIL (Too large)"
    st.metric("5. Position < 30% of Account?", status5, f"Max: ${max_position:,.0f}")

    # 6. Target 5% in 30 days
    credit_target = st.number_input("Expected Credit per Contract ($)", value=1.5, step=0.1)
    contracts = st.number_input("Number of Contracts", min_value=1, value=5)
    premium_collected = credit_target * 100 * contracts
    roi = (premium_collected / (current_price * 100 * contracts)) * 100 if contracts > 0 else 0
    status6 = "✅ PASS" if roi >= 5 else "❌ FAIL"
    st.metric("6. ~5% Return Target?", status6, f"Est. ROI: {roi:.1f}%")

# Summary
all_pass = all([is_green_cloud, current_rsi < 50, iv > 50, is_red_day, position_size <= max_position, roi >= 5])

st.markdown("---")
if all_pass:
    st.success("🎉 **ALL 7 CHECKS PASSED** - Consider selling the put!")
    st.balloons()
else:
    st.error("❌ Some checks failed. Do not enter the trade.")

# Options chain preview
if options_dates:
    st.subheader("Nearest Options Chain")
    try:
        chain = stock.option_chain(options_dates[0])
        puts = chain.puts[['strike', 'lastPrice', 'bid', 'ask', 'impliedVolatility', 'volume', 'openInterest']]
        puts = puts[puts['strike'] < current_price * 1.05]  # OTM puts
        st.dataframe(puts.head(12), use_container_width=True)
    except:
        st.info("Options data unavailable")

# Charts
st.subheader("Price + EMAs")
fig = go.Figure()
fig.add_trace(go.Scatter(x=hist.index, y=close, name="Price"))
fig.add_trace(go.Scatter(x=hist.index, y=ema9, name="EMA9"))
fig.add_trace(go.Scatter(x=hist.index, y=ema21, name="EMA21"))
st.plotly_chart(fig, use_container_width=True)

st.subheader("RSI")
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=hist.index, y=rsi, name="RSI"))
fig2.add_hline(y=50, line_dash="dash")
st.plotly_chart(fig2, use_container_width=True)

st.caption("Disclaimer: This is for educational purposes only. Not financial advice.")