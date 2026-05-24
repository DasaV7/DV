import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import appdirs as ad
import time

# Fix cache permission on Streamlit Cloud
ad.user_cache_dir = lambda *args, **kwargs: "/tmp"

st.set_page_config(page_title="7-Point Checklist", layout="wide")
st.title("🟢 Market Moves Matt 7-Point Checklist")
st.markdown("**Cash-Secured Put Selling Checklist**")

# Refresh button at the top
if st.button("🔄 Refresh All Data", type="primary", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

# Sidebar inputs
ticker_input = st.sidebar.text_input("Ticker Symbol", value="SPY", max_chars=10).upper().strip()
days = st.sidebar.slider("Historical days", 30, 365, 180)

if not ticker_input:
    st.stop()

# =============================================
@st.cache_data(ttl=300, show_spinner="Fetching market data...")  # 5 minutes cache
def get_data(symbol):
    try:
        stock = yf.Ticker(symbol)
        # Add small delay to be gentle on Yahoo
        time.sleep(1.2)
        
        hist = stock.history(period=f"{days}d", auto_adjust=True)
        
        if hist.empty:
            time.sleep(1)
            hist = stock.history(period=f"{days}d")
        
        info = stock.info
        options_dates = stock.options
        
        return stock, hist, info, options_dates
    except Exception as e:
        if "Too Many Requests" in str(e) or "rate limited" in str(e).lower():
            st.error("🚨 Rate limited by Yahoo Finance. Please wait 20-60 seconds and click **Refresh** again.")
        else:
            st.error(f"Error: {str(e)}")
        return None, pd.DataFrame(), {}, []

# Fetch data
stock, hist, info, options_dates = get_data(ticker_input)

if hist.empty or stock is None:
    st.warning("⚠️ Could not load data. Click the **Refresh** button above after waiting 20-30 seconds.")
    st.stop()

# ====================== CALCULATIONS ======================
close = hist['Close']
current_price = round(close.iloc[-1], 2)

ema9 = close.ewm(span=9, adjust=False).mean()
ema21 = close.ewm(span=21, adjust=False).mean()

def calculate_rsi(data, periods=14):
    delta = data.diff()
    gain = delta.where(delta > 0, 0).rolling(window=periods).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=periods).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

rsi = calculate_rsi(close)
current_rsi = round(rsi.iloc[-1], 1)

is_green_cloud = ema9.iloc[-1] > ema21.iloc[-1]
is_red_day = close.iloc[-1] < close.iloc[-2] if len(close) > 1 else False

# Get IV from nearest expiry
iv = 35.0
try:
    if options_dates:
        chain = stock.option_chain(options_dates[0])
        puts = chain.puts
        if not puts.empty:
            atm_idx = (puts['strike'] - current_price).abs().idxmin()
            iv = round(puts.loc[atm_idx, 'impliedVolatility'] * 100, 1)
except:
    pass

# ====================== UI ======================
st.header(f"**{ticker_input}** — ${current_price}")

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

# Final Verdict
passed = sum([is_green_cloud, current_rsi < 50, iv > 50, is_red_day, 
              position_size <= max_position, est_roi >= 5])

st.markdown("---")
if passed >= 5:
    st.success(f"🎉 **{passed}/6 CHECKS PASSED** — Strong Setup!")
else:
    st.error(f"❌ Only {passed}/6 checks passed. Better to wait.")

# Options Chain
if options_dates:
    try:
        st.subheader(f"Nearest Expiry: {options_dates[0]}")
        chain = stock.option_chain(options_dates[0])
        puts = chain.puts[['strike', 'bid', 'ask', 'impliedVolatility', 'volume']].copy()
        otm = puts[puts['strike'] < current_price * 1.05].head(12)
        st.dataframe(otm.style.format({
            'impliedVolatility': '{:.1%}',
            'bid': '${:.2f}',
            'ask': '${:.2f}'
        }), use_container_width=True)
    except:
        pass

# Charts
st.plotly_chart(go.Figure(data=[
    go.Scatter(x=hist.index, y=close, name="Price"),
    go.Scatter(x=hist.index, y=ema9, name="EMA9"),
    go.Scatter(x=hist.index, y=ema21, name="EMA21")
]), use_container_width=True)

st.caption("Not financial advice • Data from Yahoo Finance • Click Refresh if rate limited")