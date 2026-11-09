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
    
    # 建立三個分頁或欄位呈現大盤、匯率與黃金
    tab1, tab2, tab3 = st.tabs(["📊 加權指數 (日K線)", "💵 美元/台幣匯率 (USDTWD)", "🥇 黃金走勢 (新台幣/每兩)"])
    
    # --- Tab 1: 大盤 K 線圖 ---
    with tab1:
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
        except Exception as e:
            st.error(f"讀取大盤數據失敗: {e}")

    # 抓取匯率與黃金歷史資料
    try:
        usdtwd_ticker = yf.Ticker("TWD=X")
        gold_ticker = yf.Ticker("GC=F")
        
        df_fx = usdtwd_ticker.history(period="6mo")
        df_gold = gold_ticker.history(period="6mo")
    except Exception:
        df_fx, df_gold = pd.DataFrame(), pd.DataFrame()

    # --- Tab 2: 台幣兌美元匯率 ---
    with tab2:
        if not df_fx.empty:
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
        else:
            st.warning("暫時無法取得匯率數據。")

    # --- Tab 3: 黃金走勢 (新台幣 / 每兩) ---
    with tab3:
        if not df_gold.empty and not df_fx.empty:
            # 依日期對齊黃金與匯率價格
            df_gold_twd = pd.merge(df_gold[['Close']], df_fx[['Close']], left_index=True, right_index=True, suffixes=('_gold', '_fx')).dropna()
            
            # 換算公式： (美金/金衡盎司) * 匯率 (新台幣/美金) / 0.8294 (盎司/兩) = 新台幣/每兩
            df_gold_twd['TWD_per_liang'] = (df_gold_twd['Close_gold'] * df_gold_twd['Close_fx']) / 0.8294
            
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
            st.warning("暫時無法取得黃金走勢數據。")

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
            last_year_divs = div_history[div_history.index >= cutoff_date]
            annual_div_sum = last_year_divs.sum()
            calc_yield = round((annual_div_sum / curr_price * 100), 2) if annual_div_sum > 0 else 0.0
            latest_div_date = div_history.index[-1].strftime('%Y-%m-%d')

        # 今年以來漲幅 (YTD)
        hist_ytd = stock.history(period="ytd")
        ytd_change_pct = 0.0
        if not hist_ytd.empty and len(hist_ytd) > 1:
            start_price = hist_ytd['Close'].iloc[0]
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

# --- 4. Session State 狀態控制 (畫面保持上一頁數據) ---
if 'etf_df' not in st.session_state:
    st.session_state.etf_df = None

col1, col2 = st.columns([1, 4])
with col1:
    btn_fetch = st.button('🚀 開始分析 / 更新 ETF 數據')
with col2:
    if st.button('🧹 清除快取'):
        st.session_state.etf_df = None
        st.cache_data.clear()
        st.rerun()

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
            st.session_state.etf_df = df.sort_values(by='現金殖利率(%)', ascending=False).head(20)
        status.update(label="數據更新完成！", state="complete")

# --- 5. 渲染 ETF 表格與圖表 ---
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
    st.info("💡 目前無暫存 ETF 資料。請點擊上方「🚀 開始分析 / 更新 ETF 數據」按鈕載入最新數據。")
