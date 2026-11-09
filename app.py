import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import concurrent.futures

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股大盤K線與高殖利率ETF排行", layout="wide")
st.title("📈 台股大盤走勢與 ETF 殖利率前 20 名監控")
st.write(f"系統狀態：畫面狀態保存版 (最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")

# --- 2. 大盤 K 線圖區塊 (Plotly：動態 Y 軸 + 紅漲綠跌) ---
def display_market_index_kline():
    st.subheader("🌐 台灣加權指數 (大盤日 K 線走勢)")
    try:
        twii = yf.Ticker("^TWII")
        df_twii = twii.history(period="6mo")
        if not df_twii.empty:
            curr_price = df_twii['Close'].iloc[-1]
            prev_price = df_twii['Close'].iloc[-2]
            change = curr_price - prev_price
            pct_change = (change / prev_price) * 100
            
            st.metric(
                label="台股加權指數 (^TWII)", 
                value=f"{curr_price:,.2f}", 
                delta=f"{change:+.2f} ({pct_change:+.2f}%)"
            )
            
            fig = go.Figure(data=[go.Candlestick(
                x=df_twii.index,
                open=df_twii['Open'],
                high=df_twii['High'],
                low=df_twii['Low'],
                close=df_twii['Close'],
                increasing_line_color='#FF4136', # 上漲為紅
                decreasing_line_color='#2ECC40', # 下跌為綠
                name="加權指數"
            )])
            
            fig.update_layout(
                xaxis_rangeslider_visible=False,
                yaxis=dict(autorange=True, fixedrange=False),
                margin=dict(l=20, r=20, t=20, b=20),
                template="plotly_dark",
                height=450
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("暫時無法取得大盤數據。")
    except Exception as e:
        st.error(f"取得大盤數據時發生錯誤: {e}")

# 顯示大盤 K 線
display_market_index_kline()
st.divider()

# --- 3. ETF 數據抓取 logic (包含今年以來漲幅 YTD) ---
def fetch_etf_summary(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice', 0) or info.get('regularMarketPrice', 0) or info.get('previousClose', 0)
        if not curr_price or curr_price == 0:
            return None

        # A. 計算近 365 天配息金額與殖利率
        div_history = stock.dividends
        calc_yield = 0.0
        annual_div_sum = 0.0
        latest_div_date = "無紀錄"
        
        if not div_history.empty:
            div_history.index = div_history.index.tz_localize(None)
            cutoff_date = datetime.now() - timedelta(days=365)
            last_year_divs = div_history[div_history.index >= cutoff_date]
            annual_div_sum = last_year_divs.sum()
            calc_yield = round((annual_div_sum / curr_price * 100), 2) if annual_div_sum > 0 else 0.0
            latest_div_date = div_history.index[-1].strftime('%Y-%m-%d')

        # B. 計算今年以來漲幅 (YTD)
        hist_ytd = stock.history(period="ytd")
        ytd_change_pct = 0.0
        if not hist_ytd.empty and len(hist_ytd) > 1:
            start_price = hist_ytd['Close'].iloc[0] # 今年第一個交易日收盤價
            latest_price = hist_ytd['Close'].iloc[-1]
            ytd_change_pct = round(((latest_price - start_price) / start_price * 100), 2)

        return {
            'ETF代號': clean_id,
            'ETF名稱': sname,
            '目前股價': curr_price,
            '今年以來漲幅(%)': ytd_change_pct,
            '近一年配息總額': round(annual_div_sum, 2),
            '現金殖利率(%)': calc_yield,
            '最新除息日': latest_div_date
        }
    except Exception:
        return None

# --- 4. Session State 狀態控制 (停留上一次畫面) ---
if 'etf_df' not in st.session_state:
    st.session_state.etf_df = None

col1, col2 = st.columns([1, 4])
with col1:
    btn_fetch = st.button('🚀 開始分析 / 更新數據')
with col2:
    if st.button('🧹 清除快取'):
        st.session_state.etf_df = None
        st.cache_data.clear()
        st.rerun()

# 點擊更新按鈕時才執行數據抓取
if btn_fetch:
    with st.status("正在抓取與計算最新 ETF 殖利率與今年漲幅...", expanded=True) as status:
        etf_list = [
            ["0050", "元大台灣50"], ["0056", "元大高股息"], ["00878", "國泰永續高股息"],
            ["00919", "群益台灣精選高息"], ["00929", "復華台灣科技優息"], ["00713", "元大台灣高息低波"],
            ["00918", "大華優利高股息30"], ["00915", "凱基優選高股息30"], ["00940", "元大台灣價值高息"],
            ["00939", "統一台灣高息動能"], ["006208", "富邦台50"], ["00881", "國泰台灣5G+"],
            ["00900", "富邦特選高股息30"], ["00730", "富邦臺灣優質高息"], ["00731", "FH澎湃優質高息"],
            ["00923", "群益台ESG低碳50"], ["00905", "FT臺灣Smart"], ["00922", "國泰台灣領袖50"],
            ["00934", "中信成長高股息"], ["00936", "台新永續高息中小"], ["00944", "野村趨勢動能高息"],
            ["00943", "兆豐電子高息等權"], ["0052", "富邦科技"], ["00692", "富邦公司治理"]
        ]
        
        final_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(fetch_etf_summary, s[0], s[1]) for s in etf_list]
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res:
                    final_results.append(res)
        
        df = pd.DataFrame(final_results)
        if not df.empty:
            # 排序並取前 20 名存入 session_state
            st.session_state.etf_df = df.sort_values(by='現金殖利率(%)', ascending=False).head(20)
        status.update(label="數據更新完成！", state="complete")

# --- 5. 渲染表格與圖表 ---
st.subheader("🎯 台股 ETF 現金殖利率前 20 名排行榜")
if st.session_state.etf_df is not None and not st.session_state.etf_df.empty:
    df_top20 = st.session_state.etf_df
    
    st.dataframe(
        df_top20, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "今年以來漲幅(%)": st.column_config.NumberColumn(format="%.2f%%")
        }
    )
    
    st.divider()
    st.subheader("📊 ETF 現金殖利率 (%) 排行圖表")
    yield_chart = df_top20.set_index('ETF名稱')[['現金殖利率(%)']].sort_values(by='現金殖利率(%)', ascending=False)
    st.bar_chart(yield_chart, color="#FF4B4B")
else:
    st.info("💡 目前無暫存資料。請點擊上方「🚀 開始分析 / 更新數據」按鈕載入最新數據。")
