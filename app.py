import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime

import appdirs as ad
ad.user_cache_dir = lambda *args, **kwargs: "/tmp"

st.set_page_config(page_title="Matt's 7-Point Checklist", layout="wide")
st.title("🟢 Market Moves Matt 7-Point Checklist")
st.markdown("**Cash-Secured Put Selling Scanner**")

with st.expander("📌 Matt's Strategy Summary"):
    st.markdown("""
    **Strategy**: Sell Cash-Secured Puts on strong stocks during pullbacks.  
    Look for: EMA Cloud Green + RSI < 50 + High IV + Red Day + Bullish Candle Confirmation.
    """)

# Weekly Tickers
@st.cache_data(ttl=3600)
def get_weekly_tickers():
    return ["NVDA", "CEG", "TSLA", "TSLL", "SOXL"]

weekly_tickers = get_weekly_tickers()

st.sidebar.header("Single Ticker Mode")
single_ticker = st.sidebar.text_input("Ticker", value="SPY", max_chars=10).upper().strip()
days = st.sidebar.slider("History (days)", 30, 730, 365)

tab1, tab2, tab3 = st.tabs(["📊 Multi-Ticker Overview", "🔍 Single Ticker Deep Dive", "🕯️ Candle Analyzer"])

# ====================== TAB 1: MULTI-TICKER ======================
with tab1:
    st.header("📈 Weekly Watchlist Overview")
    st.caption(f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    if st.button("🔄 Refresh All Data", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    user_tickers = st.multiselect("Add more tickers", 
                                  ["AAPL", "QQQ", "AMD", "SMCI", "ARM", "AVGO", "META", "COIN"], 
                                  default=[])
    all_tickers = list(dict.fromkeys(weekly_tickers + user_tickers))

    cols = st.columns(3)
    for idx, ticker in enumerate(all_tickers):
        with cols[idx % 3]:
            with st.container(border=True):
                try:
                    stock = yf.Ticker(ticker)
                    hist = stock.history(period="60d")
                    if hist.empty:
                        st.error(f"No data for {ticker}")
                        continue

                    close = hist['Close']
                    price = round(float(close.iloc[-1]), 2)
                    ema9 = close.ewm(span=9, adjust=False).mean()
                    ema21 = close.ewm(span=21, adjust=False).mean()

                    delta = close.diff()
                    gain = delta.where(delta > 0, 0).rolling(14).mean()
                    loss = -delta.where(delta < 0, 0).rolling(14).mean()
                    rsi_val = round(100 - (100 / (1 + gain / loss)).iloc[-1], 1)

                    iv = 35.0
                    try:
                        if stock.options:
                            chain = stock.option_chain(stock.options[0])
                            puts = chain.puts
                            if not puts.empty:
                                atm_idx = (puts['strike'] - price).abs().idxmin()
                                iv = round(float(puts.loc[atm_idx, 'impliedVolatility']) * 100, 1)
                    except:
                        pass

                    green_cloud = float(ema9.iloc[-1]) > float(ema21.iloc[-1])
                    red_day = float(close.iloc[-1]) < float(close.iloc[-2]) if len(close) > 1 else False
                    score = sum([green_cloud, rsi_val < 50, iv > 50, red_day])

                    color = "🟢" if score >= 3 else "🟡" if score == 2 else "🔴"

                    st.subheader(f"{color} {ticker} — ${price}")
                    st.metric("Score", f"{score}/4")
                    st.progress(score / 4)

                    st.write("**Conditions:**")
                    st.write("✅ EMA Cloud Green" if green_cloud else "❌ EMA Cloud")
                    st.write("✅ RSI < 50" if rsi_val < 50 else "❌ RSI ≥ 50")
                    st.write("✅ IV > 50%" if iv > 50 else f"❌ IV {iv:.1f}%")
                    st.write("✅ Red Day" if red_day else "⚪ Not Red Day")
                except:
                    st.error(f"Error loading {ticker}")

# ====================== TAB 2: SINGLE TICKER DEEP DIVE ======================
with tab2:
    if not single_ticker:
        st.info("Enter ticker in sidebar")
        st.stop()

    st.header(f"Deep Dive: **{single_ticker}**")

    if st.button("🔄 Refresh This Ticker", type="primary", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    @st.cache_data(ttl=180)
    def get_single_data(symbol, days):
        stock = yf.Ticker(symbol)
        hist = stock.history(period=f"{days}d")
        return hist, stock.options

    hist, options_dates = get_single_data(single_ticker, days)

    if hist.empty:
        st.error("No data found.")
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
            temp = yf.Ticker(single_ticker)
            chain = temp.option_chain(options_dates[0])
            puts = chain.puts
            if not puts.empty:
                atm_idx = (puts['strike'] - current_price).abs().idxmin()
                iv = round(float(puts.loc[atm_idx, 'impliedVolatility']) * 100, 1)
    except:
        pass

    col1, col2 = st.columns([1.1, 1])
    with col1:
        st.subheader("1. EMA Cloud Green (9 > 21)")
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
        st.subheader("Risk Management")
        account_size = st.number_input("Account Size ($)", value=50000, min_value=10000, step=1000)
        max_pos = account_size * 0.30
        position_size = st.number_input("Planned Position Size ($)", value=int(max_pos*0.75), step=500)
        
        st.metric("5. Position ≤ 30%?", "✅ PASS" if position_size <= max_pos else "❌ FAIL", f"Max: ${max_pos:,.0f}")

        credit = st.number_input("Expected Credit per Contract ($)", value=1.25, step=0.05)
        contracts = st.number_input("Number of Contracts", value=5, min_value=1)
        premium = credit * 100 * contracts
        capital = current_price * 100 * contracts
        est_roi = round((premium / capital) * 100, 1) if capital > 0 else 0
        st.metric("6. ~5% ROI Target?", "✅ PASS" if est_roi >= 5 else "❌ FAIL", f"{est_roi}%")

    total = sum([is_green_cloud, current_rsi < 50, iv > 50, is_red_day])
    st.success(f"**Technical Score: {total}/4** | IV: {iv:.1f}%")

# ====================== TAB 3: CANDLE ANALYZER ======================
with tab3:
    st.header("🕯️ Advanced Candle Analyzer")
    st.caption("Monthly • Weekly • Daily + Patterns + Next Candle Probability")

    col1, col2 = st.columns([3,1])
    with col1:
        candle_ticker = st.text_input("Ticker for Candle Analysis", value=single_ticker, max_chars=10).upper().strip()
    with col2:
        analyze_btn = st.button("🔄 Analyze Candles", type="primary", use_container_width=True)

    if analyze_btn and candle_ticker:
        with st.spinner(f"Analyzing {candle_ticker}..."):
            try:
                daily = yf.Ticker(candle_ticker).history(period="180d")
                if daily.empty:
                    st.error("No data found")
                    st.stop()

                weekly = daily.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
                monthly = daily.resample('ME').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})

                def analyze_tf(df, name):
                    if df.empty: return None, None
                    df = df.tail(40).copy()
                    latest = df.iloc[-1]
                    prev = df.iloc[-2] if len(df)>1 else latest

                    body = abs(latest['Close'] - latest['Open'])
                    upper = latest['High'] - max(latest['Open'], latest['Close'])
                    lower = min(latest['Open'], latest['Close']) - latest['Low']
                    change_pct = ((latest['Close'] - prev['Close']) / prev['Close']) * 100
                    vol_change = ((latest['Volume'] - prev['Volume']) / prev['Volume']) * 100 if prev['Volume'] > 0 else 0

                    bullish = latest['Close'] > latest['Open']
                    score = 50
                    if bullish: score += 25
                    if body > (latest['High']-latest['Low'])*0.6: score += 20
                    if lower > body*1.8 and bullish: score += 20

                    patterns = []
                    if body <= (latest['High']-latest['Low'])*0.1: patterns.append("⚪ Doji")
                    if lower > body*2 and bullish: patterns.append("🔨 Hammer (Bullish Reversal)")
                    if upper > body*2 and not bullish: patterns.append("☄️ Shooting Star")
                    if prev['Close'] < prev['Open'] and latest['Close'] > prev['Open'] and bullish:
                        patterns.append("🐂 Bullish Engulfing")

                    next_bull_prob = min(88, score + (10 if vol_change > 20 else 0))

                    return {
                        'timeframe': name,
                        'price': round(latest['Close'],2),
                        'change': round(change_pct,2),
                        'vol_change': round(vol_change,1),
                        'score': round(score,1),
                        'bullish': bullish,
                        'patterns': patterns,
                        'next_bull_prob': next_bull_prob
                    }, df

                monthly_info, m_df = analyze_tf(monthly, "Monthly")
                weekly_info, w_df = analyze_tf(weekly, "Weekly")
                daily_info, d_df = analyze_tf(daily, "Daily")

                infos = [monthly_info, weekly_info, daily_info]
                dfs = [m_df, w_df, d_df]

                cols = st.columns(3)
                for i, (info, df) in enumerate(zip(infos, dfs)):
                    with cols[i]:
                        with st.container(border=True):
                            st.subheader(f"**{info['timeframe']}**")
                            st.metric("Price", f"${info['price']}", f"{info['change']}%")

                            fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'],
                                        low=df['Low'], close=df['Close'])])
                            fig.update_layout(height=380, title=f"{info['timeframe']} Candlestick")
                            st.plotly_chart(fig, use_container_width=True)

                            st.success("🟢 Bullish") if info['bullish'] else st.error("🔴 Bearish")
                            st.write(f"**Strength**: {info['score']}%")
                            st.progress(info['score']/100)
                            st.write(f"**Volume**: {info['vol_change']}%")
                            for p in info['patterns']:
                                st.write(p)
                            st.write(f"**Next Candle Bullish Prob**: **{info['next_bull_prob']}%**")

                st.subheader("Summary Table")
                st.dataframe(pd.DataFrame(infos), use_container_width=True, hide_index=True)

            except Exception as e:
                st.error(f"Error: {str(e)}")
    else:
        st.info("Enter ticker & click button to analyze candles")

st.caption("Educational tool only • Not financial advice")