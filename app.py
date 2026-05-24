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
    **Core Strategy**: Sell Cash-Secured Puts on strong stocks during pullbacks (Red Day + High IV + EMA Cloud Green).
    Use Candle Analysis to confirm reversal or continuation before entering.
    """)

@st.cache_data(ttl=3600)
def get_weekly_tickers():
    return ["NVDA", "CEG", "TSLA", "TSLL", "SOXL"]

weekly_tickers = get_weekly_tickers()

st.sidebar.header("Single Ticker Mode")
single_ticker = st.sidebar.text_input("Ticker", value="SPY", max_chars=10).upper().strip()
days = st.sidebar.slider("History (days)", 30, 730, 365)

tab1, tab2, tab3 = st.tabs(["📊 Multi-Ticker Overview", "🔍 Single Ticker Deep Dive", "🕯️ Candle Analyzer"])

# TAB 1 & TAB 2 (assumed working from previous version)
# Paste your previous working Tab 1 and Tab 2 code here if needed

# ====================== TAB 3: ADVANCED CANDLE ANALYZER ======================
with tab3:
    st.header("🕯️ Advanced Candle Analyzer")
    st.caption("Monthly | Weekly | Daily + Pattern Detection")

    col_input, col_btn = st.columns([3, 1])
    with col_input:
        candle_ticker = st.text_input("Enter Ticker", value=single_ticker, max_chars=10).upper().strip()
    with col_btn:
        if st.button("🔄 Analyze Candles", type="primary", use_container_width=True):
            with st.spinner(f"Analyzing {candle_ticker}..."):
                try:
                    ticker_obj = yf.Ticker(candle_ticker)
                    daily = ticker_obj.history(period="180d")

                    if daily.empty:
                        st.error("No data found")
                        st.stop()

                    # Resample
                    weekly = daily.resample('W').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})
                    monthly = daily.resample('ME').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'})

                    def detect_patterns(df):
                        if len(df) < 3:
                            return []
                        latest = df.iloc[-1]
                        prev = df.iloc[-2]
                        prev2 = df.iloc[-3] if len(df) > 2 else prev

                        body = abs(latest['Close'] - latest['Open'])
                        upper_wick = latest['High'] - max(latest['Open'], latest['Close'])
                        lower_wick = min(latest['Open'], latest['Close']) - latest['Low']
                        range_size = latest['High'] - latest['Low']

                        patterns = []

                        # Doji
                        if body <= range_size * 0.1:
                            patterns.append("⚪ Doji (Indecision)")

                        # Hammer
                        if lower_wick >= body * 2 and upper_wick <= body * 0.3 and latest['Close'] > latest['Open']:
                            patterns.append("🔨 Hammer (Bullish Reversal)")

                        # Inverted Hammer
                        if upper_wick >= body * 2 and lower_wick <= body * 0.3 and latest['Close'] > latest['Open']:
                            patterns.append("🛠️ Inverted Hammer")

                        # Shooting Star
                        if upper_wick >= body * 2 and lower_wick <= body * 0.3 and latest['Close'] < latest['Open']:
                            patterns.append("☄️ Shooting Star (Bearish)")

                        # Bullish Engulfing
                        if (prev['Close'] < prev['Open'] and 
                            latest['Close'] > latest['Open'] and 
                            latest['Close'] > prev['Open'] and 
                            latest['Open'] < prev['Close']):
                            patterns.append("🐂 Bullish Engulfing")

                        # Bearish Engulfing
                        if (prev['Close'] > prev['Open'] and 
                            latest['Close'] < latest['Open'] and 
                            latest['Close'] < prev['Open'] and 
                            latest['Open'] > prev['Close']):
                            patterns.append("🐻 Bearish Engulfing")

                        return patterns

                    def analyze_timeframe(df, name):
                        if df.empty: return None
                        latest = df.iloc[-1]
                        prev = df.iloc[-2] if len(df)>1 else latest
                        
                        body = abs(latest['Close'] - latest['Open'])
                        upper = latest['High'] - max(latest['Open'], latest['Close'])
                        lower = min(latest['Open'], latest['Close']) - latest['Low']
                        change_pct = ((latest['Close'] - prev['Close']) / prev['Close']) * 100
                        
                        bullish = latest['Close'] > latest['Open']
                        score = 50
                        if bullish: score += 20
                        if body > (latest['High']-latest['Low'])*0.6: score += 15
                        if lower > body*1.5 and bullish: score += 20
                        
                        patterns = detect_patterns(df)
                        
                        return {
                            'timeframe': name,
                            'price': round(latest['Close'], 2),
                            'change_pct': round(change_pct, 2),
                            'score': round(score, 1),
                            'bullish': bullish,
                            'patterns': patterns
                        }

                    analyses = [
                        analyze_timeframe(monthly, "Monthly"),
                        analyze_timeframe(weekly, "Weekly"),
                        analyze_timeframe(daily, "Daily")
                    ]

                    # Display Cards
                    cols = st.columns(3)
                    for i, a in enumerate(analyses):
                        with cols[i]:
                            with st.container(border=True):
                                st.subheader(f"**{a['timeframe']}**")
                                st.metric("Price", f"${a['price']}", f"{a['change_pct']}%")
                                
                                if a['bullish']:
                                    st.success("🟢 Bullish")
                                else:
                                    st.error("🔴 Bearish")
                                
                                st.write(f"**Strength: {a['score']}%**")
                                st.progress(a['score']/100)
                                
                                if a['patterns']:
                                    for p in a['patterns']:
                                        st.write(p)

                    # Summary Table
                    st.subheader("📋 Consolidated Analysis")
                    df_summary = pd.DataFrame(analyses)
                    st.dataframe(df_summary[['timeframe', 'price', 'change_pct', 'score']], 
                                use_container_width=True, hide_index=True)

                    # Overall Verdict
                    avg_score = np.mean([a['score'] for a in analyses])
                    if avg_score >= 70:
                        st.success(f"🟢 **STRONG BUY SIGNAL** - Overall Score: {avg_score:.1f}%")
                    elif avg_score >= 55:
                        st.warning(f"🟡 **Neutral to Mildly Bullish** - Overall Score: {avg_score:.1f}%")
                    else:
                        st.error(f"🔴 **Weak / Bearish** - Overall Score: {avg_score:.1f}%")

                except Exception as e:
                    st.error(f"Error: {str(e)}")

    else:
        st.info("Enter ticker above and click **Analyze Candles** to see patterns (Hammer, Engulfing, Doji, etc.)")

st.caption("Educational tool only • Not financial advice")