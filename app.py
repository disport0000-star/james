import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import concurrent.futures

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股大盤、匯率、黃金與高殖利率ETF監控", layout="wide")
st.title("📈 總體經濟 (大盤/匯率/黃金) 與高殖利率 ETF 監控面板")
st.write(f"系統狀態：畫面狀態保存版 (最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")

# --- 2. 總體經濟指標 (大盤 K 線 + 匯率 & 黃金趨勢圖) ---
def display_macro_indicators():
    st.subheader("🌐 總體經濟關鍵指標走勢")
    
    tab1, tab2, tab3 = st.tabs(["📊 加權指數 (日K線)", "💵 美元/台幣匯率 (USDTWD)", "🥇 黃金走勢 (新台幣/每兩)"])
    
    # --- Tab 1: 大盤 K 線圖 ---
    with tab1:
        try:
            twii = yf.Ticker("^TWII")
            df_twii = twii.history(period="6mo")
            if not df_twii.empty and len(df_twii) > 1:
                curr_price = df_twii['Close'].iloc[-1]
                prev_price = df_twii['Close'].iloc[-2]
                change = curr_price - prev_price
                pct_change = (change / prev_price) * 100
                
                st.metric(
                    label="台股加權指數 (^TWII)", 
                    value=f"{curr_price:,.2f}", 
                    delta=f"{change:+.2f} ({pct_change:+.2f}%)"
                )
                
                fig_twii = go.Figure(data=[go.Candlestick(
                    x=df_twii.index,
                    open=df_twii['Open'],
                    high=df_twii['High'],
                    low=df_twii['Low'],
                    close=df_twii['Close'],
                    increasing_line_color='#FF4136', # 上漲為紅
                    decreasing_line_color='#2ECC40', # 下跌為綠
                    name="加權指數"
                )])
                fig_twii.update_layout(
                    xaxis_rangeslider_visible=False,
                    yaxis=dict(autorange=True, fixedrange=False),
                    margin=dict(l=20, r=20, t=20, b=20),
                    template="plotly_dark",
                    height=400
                )
                st.plotly_chart(fig_twii, use_container_width=True)
            else:
                st.warning("暫時無法取得大盤數據。")
        except Exception as e:
            st.warning(f"讀取大盤數據失敗: {e}")

    # 安全抓取匯率歷史資料
    df_fx = pd.DataFrame()
    try:
        usdtwd_ticker = yf.Ticker("TWD=X")
        df_fx = usdtwd_ticker.history(period="6mo")
    except Exception:
        pass

    # --- Tab 2: 台幣兌美元匯率 ---
    with tab2:
        if not df_fx.empty and len(df_fx) > 1:
            try:
                curr_fx = df_fx['Close'].iloc[-1]
                prev_fx = df_fx['Close'].iloc[-2]
                change_fx = curr_fx - prev_fx
                pct_fx = (change_fx / prev_fx) * 100
                
                st.metric(
                    label="美元 / 新台幣 (USD/TWD)", 
                    value=f"{curr_fx:.3f}", 
                    delta=f"{change_fx:+.3f} ({pct_fx:+.2f}%)"
                )
                
                fig_fx = go.Figure(data=[go.Scatter(
                    x=df_fx.index, 
                    y=df_fx['Close'], 
                    mode='lines',
                    line=dict(color='#17BECF', width=2),
                    name='USD/TWD'
                )])
                fig_fx.update_layout(
                    xaxis_rangeslider_visible=False,
                    yaxis=dict(autorange=True, fixedrange=False, title="匯率 (TWD)"),
                    margin=dict(l=20, r=20, t=20, b=20),
                    template="plotly_dark",
                    height=400
                )
                st.plotly_chart(fig_fx, use_container_width=True)
            except Exception as e:
                st.warning(f"匯率圖表渲染失敗: {e}")
        else:
            st.warning("暫時無法取得匯率數據。")

    # --- Tab 3: 黃金走勢 (新台幣 / 每兩) ---
    with tab3:
        try:
            gold_ticker = yf.Ticker("GC=F")
            df_gold = gold_ticker.history(period="6mo")
            
            if not df_gold.empty and not df_fx.empty:
                # 1. 移除時區限制，避免對齊失敗
                df_g = df_gold[['Close']].copy()
                df_f = df_fx[['Close']].copy()
                df_g.index = df_g.index.tz_localize(None)
                df_f.index = df_f.index.tz_localize(None)
                
                # 2. 合併資料並用前後值填補缺漏 (避免休市日不同導致 0 筆資料)
                df_gold_twd = pd.concat([df_g, df_f], axis=1, keys=['gold', 'fx']).ffill().bfill().dropna()
                
                # 3. 換算公式： (美元/金衡盎司) * 匯率 (NT/USD) / 0.8294 (盎司/兩) = NT/每兩
                if not df_gold_twd.empty and len(df_gold_twd) > 1:
                    df_gold_twd['TWD_per_liang'] = (df_gold_twd[('gold', 'Close')] * df_gold_twd[('fx', 'Close')]) / 0.8294
                    
                    curr_gold_twd = df_gold_twd['TWD_per_liang'].iloc[-1]
                    prev_gold_twd = df_gold_twd['TWD_per_liang'].iloc[-2]
                    change_gold = curr_gold_twd - prev_gold_twd
                    pct_gold = (change_gold / prev_gold_twd) * 100
                    
                    st.metric(
                        label="黃金估算價格 (新台幣 / 每兩)", 
                        value=f"NT$ {curr_gold_twd:,.0f}", 
                        delta=f"{change_gold:+,.0f} ({pct_gold:+.2f}%)"
                    )
                    
                    fig_gold = go.Figure(data=[go.Scatter(
                        x=df_gold_twd.index, 
                        y=df_gold_twd['TWD_per_liang'], 
                        mode='lines',
                        line=dict(color='#FFD700', width=2),
                        name='台幣黃金(每兩)'
                    )])
                    fig_gold.update_layout(
                        xaxis_rangeslider_visible=False,
                        yaxis=dict(autorange=True, fixedrange=False, title="新台幣 (NT$)"),
                        margin=dict(l=20, r=20, t=20, b=20),
                        template="plotly_dark",
                        height=400
                    )
                    st.plotly_chart(fig_gold, use_container_width=True)
                else:
                    st.warning("黃金與匯率對齊數據不足，暫無法繪製圖表。")
            else:
                st.warning("暫時無法取得黃金或匯率數據。")
        except Exception as e:
            st.warning(f"黃金數據處理異常: {e}")

# 執行顯示總經指標
display_macro_indicators()
st.divider()

# --- 3. ETF 數據抓取 logic (包含殖利率與 YTD 今年漲幅) ---
def fetch_etf_summary(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice', 0) or info.get('regularMarketPrice', 0) or info.get('previousClose', 0)
        if not curr_price or curr_price == 0:
            return None

        # 近 365 天配息金額與殖利率
        div_history = stock.dividends
        calc_yield = 0.0
        annual_div_sum = 0.0
        latest_div_date = "無紀錄"
        
        if not div_history.empty:
            div_history.index = div_history.index.tz_localize(None)
            cutoff_date = datetime.now() - timedelta(days=365)
            last_year_divs = div_
