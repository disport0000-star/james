import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import concurrent.futures

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股大盤(含KD/MACD)、匯率、黃金與高殖利率ETF監控", layout="wide")
st.title("📈 總體經濟 (大盤/KD/MACD/匯率/黃金) 與高殖利率 ETF 監控面板")
st.write(f"系統狀態：畫面狀態保存版 (最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")

# --- 2. 總體經濟指標 (大盤 K 線 + KD + MACD / 匯率 / 黃金趨勢圖) ---
def display_macro_indicators():
    st.subheader("🌐 總體經濟關鍵指標走勢")
    
    tab1, tab2, tab3 = st.tabs(["📊 加權指數 (K線 + KD + MACD)", "💵 美元/台幣匯率 (USDTWD)", "🥇 黃金走勢 (新台幣/每兩)"])
    
    # --- Tab 1: 大盤 K 線圖 + KD + MACD (含滑鼠懸停數值與十字光標) ---
    with tab1:
        try:
            twii = yf.Ticker("^TWII")
            df_twii = twii.history(period="6mo")
            
            if not df_twii.empty and len(df_twii) > 35:
                curr_price = df_twii['Close'].iloc[-1]
                prev_price = df_twii['Close'].iloc[-2]
                change = curr_price - prev_price
                pct_change = (change / prev_price) * 100
                
                st.metric(
                    label="台股加權指數 (^TWII)", 
                    value=f"{curr_price:,.2f}", 
                    delta=f"{change:+.2f} ({pct_change:+.2f}%)"
                )
                
                # --- 計算 KD 指標 (9日) ---
                low_min = df_twii['Low'].rolling(window=9).min()
                high_max = df_twii['High'].rolling(window=9).max()
                rsv = (df_twii['Close'] - low_min) / (high_max - low_min) * 100
                rsv = rsv.fillna(50)
                
                k_list, d_list = [50.0], [50.0]
                for r in rsv.iloc[1:]:
                    k_val = (2/3) * k_list[-1] + (1/3) * r
                    d_val = (2/3) * d_list[-1] + (1/3) * k_val
                    k_list.append(k_val)
                    d_list.append(d_val)
                
                df_twii['K'] = k_list
                df_twii['D'] = d_list

                # --- 計算 MACD 指標 (12, 26, 9) ---
                ema12 = df_twii['Close'].ewm(span=12, adjust=False).mean()
                ema26 = df_twii['Close'].ewm(span=26, adjust=False).mean()
                df_twii['DIF'] = ema12 - ema26
                df_twii['MACD'] = df_twii['DIF'].ewm(span=9, adjust=False).mean()
                df_twii['MACD_Hist'] = df_twii['DIF'] - df_twii['MACD']

                # --- 建立 3 列子圖 ---
                fig = make_subplots(
                    rows=3, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.03,
                    row_heights=[0.6, 0.2, 0.2]
                )

                # Row 1: 主 K 線圖 (加上懸停提示格式)
                fig.add_trace(go.Candlestick(
                    x=df_twii.index,
                    open=df_twii['Open'],
                    high=df_twii['High'],
                    low=df_twii['Low'],
                    close=df_twii['Close'],
                    increasing_line_color='#FF4136',
                    decreasing_line_color='#2ECC40',
                    name="加權指數",
                    hoverinfo="x+y"
                ), row=1, col=1)

                # Row 2: KD 指標
                fig.add_trace(go.Scatter(
                    x=df_twii.index, y=df_twii['K'], mode='lines', 
                    line=dict(color='#FFDC00', width=1.5), name='K (9)',
                    hovertemplate="K值: %{y:.2f}<extra></extra>"
                ), row=2, col=1)
                
                fig.add_trace(go.Scatter(
                    x=df_twii.index, y=df_twii['D'], mode='lines', 
                    line=dict(color='#0074D9', width=1.5), name='D (9)',
                    hovertemplate="D值: %{y:.2f}<extra></extra>"
                ), row=2, col=1)
                
                fig.add_hline(y=80, line_dash="dash", line_color="gray", opacity=0.5, row=2, col=1)
                fig.add_hline(y=20, line_dash="dash", line_color="gray", opacity=0.5, row=2, col=1)

                # Row 3: MACD 指標
                hist_colors = ['#FF4136' if val >= 0 else '#2ECC40' for val in df_twii['MACD_Hist']]
                fig.add_trace(go.Bar(
                    x=df_twii.index, y=df_twii['MACD_Hist'], 
                    marker_color=hist_colors, name='柱狀體',
                    hovertemplate="柱狀體: %{y:.2f}<extra></extra>"
                ), row=3, col=1)
                
                fig.add_trace(go.Scatter(
                    x=df_twii.index, y=df_twii['DIF'], mode='lines', 
                    line=dict(color='#FF851B', width=1.5), name='DIF (12,26)',
                    hovertemplate="DIF: %{y:.2f}<extra></extra>"
                ), row=3, col=1)
                
                fig.add_trace(go.Scatter(
                    x=df_twii.index, y=df_twii['MACD'], mode='lines', 
                    line=dict(color='#7FDBFF', width=1.5), name='MACD (9)',
                    hovertemplate="MACD: %{y:.2f}<extra></extra>"
                ), row=3, col=1)

                # 版面設定與懸停十字線模式 (hovermode="x unified")
                fig.update_layout(
                    xaxis_rangeslider_visible=False,
                    template="plotly_dark",
                    height=750,
                    margin=dict(l=20, r=20, t=20, b=20),
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    hovermode="x unified" # 關鍵設定：游移時橫向對齊顯示全套指標數值
                )
                
                # 啟用垂直與橫向對齊線 (Crosshair)
                fig.update_xaxes(showspikes=True, spikemode='across', spikesnap='cursor', spikedash='solid', spikecolor='gray', spikethickness=1)
                fig.update_yaxes(autorange=True, fixedrange=False, row=1, col=1)
                fig.update_yaxes(range=[0, 100], row=2, col=1, title="KD")
                fig.update_yaxes(autorange=True, fixedrange=False, row=3, col=1, title="MACD")

                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("暫時無法取得足夠之大盤數據。")
        except Exception as e:
            st.warning(f"讀取大盤與技術指標數據失敗: {e}")

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
                    name='USD/TWD',
                    hovertemplate="日期: %{x}<br>匯率: %{y:.3f}<extra></extra>"
                )])
                fig_fx.update_layout(
                    xaxis_rangeslider_visible=False,
                    yaxis=dict(autorange=True, fixedrange=False, title="匯率 (TWD)"),
                    margin=dict(l=20, r=20, t=20, b=20),
                    template="plotly_dark",
                    height=400,
                    hovermode="x"
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
                df_g = df_gold[['Close']].copy()
                df_f = df_fx[['Close']].copy()
                df_g.index = df_g.index.tz_localize(None)
                df_f.index = df_f.index.tz_localize(None)
                
                df_gold_twd = pd.concat([df_g, df_f], axis=1, keys=['gold', 'fx']).ffill().bfill().dropna()
                
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
                        name='台幣黃金(每兩)',
                        hovertemplate="日期: %{x}<br>每兩價格: NT$ %{y:,.0f}<extra></extra>"
                    )])
                    fig_gold.update_layout(
                        xaxis_rangeslider_visible=False,
                        yaxis=dict(autorange=True, fixedrange=False, title="新台幣 (NT$)"),
                        margin=dict(l=20, r=20, t=20, b=20),
                        template="plotly_dark",
                        height=400,
                        hovermode="x"
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

# --- 3. ETF 數據抓取 logic ---
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

# --- 4. Session State 狀態控制 ---
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
