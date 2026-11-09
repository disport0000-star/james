import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import concurrent.futures

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股大盤K線與高殖利率(>8%)監控", layout="wide")
st.title("📈 台股大盤走勢與高殖利率(>8%)個股監控")
st.write(f"系統狀態：即時數據連線中 (更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")

# --- 2. 大盤 K 線圖區塊 (Plotly 實現：動態 Y 軸 + 紅漲綠跌) ---
def display_market_index_kline():
    st.subheader("🌐 台灣加權指數 (大盤日 K 線走勢)")
    try:
        twii = yf.Ticker("^TWII")
        # 抓取近 6 個月的日 K 線數據
        df_twii = twii.history(period="6mo")
        if not df_twii.empty:
            curr_price = df_twii['Close'].iloc[-1]
            prev_price = df_twii['Close'].iloc[-2]
            change = curr_price - prev_price
            pct_change = (change / prev_price) * 100
            
            # 顯示當前指數與漲跌幅
            st.metric(
                label="台股加權指數 (^TWII)", 
                value=f"{curr_price:,.2f}", 
                delta=f"{change:+.2f} ({pct_change:+.2f}%)"
            )
            
            # 繪製專業 K 線圖 (Candlestick)
            fig = go.Figure(data=[go.Candlestick(
                x=df_twii.index,
                open=df_twii['Open'],
                high=df_twii['High'],
                low=df_twii['Low'],
                close=df_twii['Close'],
                increasing_line_color='#FF4136', # 台股習慣：上漲為紅
                decreasing_line_color='#2ECC40', # 台股習慣：下跌為綠
                name="加權指數"
            )])
            
            # 版面優化：使 Y 軸貼合實際數值範圍，隱藏底部 rangeslider 保持乾淨
            fig.update_layout(
                xaxis_rangeslider_visible=False,
                yaxis=dict(autorange=True, fixedrange=False), # Y 軸自動跟著資料變動
                margin=dict(l=20, r=20, t=20, b=20),
                template="plotly_dark",
                height=450
            )
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("暫時無法取得大盤數據。")
    except Exception as e:
        st.error(f"取得大盤數據時發生錯誤: {e}")

# 執行顯示大盤 K 線
display_market_index_kline()
st.divider()

# --- 3. 個股數據抓取 logic (純 yfinance 高速穩定版) ---
def fetch_stock_summary(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice', 0) or info.get('regularMarketPrice', 0)
        if not curr_price or curr_price == 0:
            return None

        # 計算近 365 天殖利率與找出最新除權息日
        div_history = stock.dividends
        calc_yield = 0.0
        latest_div_date = "無紀錄"
        
        if not div_history.empty:
            div_history.index = div_history.index.tz_localize(None)
            cutoff_date = datetime.now() - timedelta(days=365)
            last_year_divs = div_history[div_history.index >= cutoff_date]
            annual_div_sum = last_year_divs.sum()
            calc_yield = round((annual_div_sum / curr_price * 100), 1) if annual_div_sum > 0 else 0.0
            
            # 最新一筆配息日期
            latest_div_date = div_history.index[-1].strftime('%Y-%m-%d')

        # 核心篩選：殖利率 > 8% 才回傳
        if calc_yield > 8.0:
            return {
                '股票代號': clean_id,
                '公司名稱': sname,
                '目前股價': curr_price,
                '現金殖利率(%)': calc_yield,
                '最新除權息日': latest_div_date
            }
        else:
            return None
    except Exception:
        return None

# --- 4. 執行與畫面呈現 ---
if st.button('🚀 開始掃描高殖利率(>8%)個股'):
    with st.status("正在分析市場個股殖利率與除權息日程...", expanded=True) as status:
        # 熱門權值與高股息標的名單
        base_list = [
            ["2330", "台積電"], ["2317", "鴻海"], ["2454", "聯發科"], ["2881", "富邦金"], 
            ["2603", "長榮"], ["2002", "中鋼"], ["2886", "兆豐金"], ["2382", "廣達"],
            ["2324", "仁寶"], ["2357", "華碩"], ["2882", "國泰金"], ["2891", "中信金"],
            ["1101", "台泥"], ["2303", "聯電"], ["2308", "台達電"], ["2412", "中華電"],
            ["2884", "玉山金"], ["3231", "緯創"], ["2376", "技嘉"], ["2609", "陽明"],
            ["2615", "萬海"], ["3034", "聯詠"], ["3711", "日月光投控"], ["2408", "南亞科"]
        ]
        
        final_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(fetch_stock_summary, s[0], s[1]) for s in base_list]
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res:
                    final_results.append(res)
        
        df = pd.DataFrame(final_results)
        status.update(label="數據分析完成！", state="complete")

    st.subheader("🎯 現金殖利率大於 8% 的精選個股")
    if not df.empty:
        # 依殖利率高到低排序
        df = df.sort_values(by='現金殖利率(%)', ascending=False)
        st.success(f"找到 {len(df)} 檔殖利率超過 8% 的個股！")
        
        # 顯示精簡表格
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # 殖利率柱狀圖
        st.divider()
        st.subheader("📊 高殖利率 (>8%) 個股對比")
        yield_chart = df.set_index('公司名稱')[['現金殖利率(%)']].sort_values(by='現金殖利率(%)', ascending=False)
        st.bar_chart(yield_chart, color="#FF4B4B")
    else:
        st.info("目前掃描的名單中，暫無現金殖利率 > 8% 的股票。")

if st.button('🧹 清除快取重整網頁'):
    st.cache_data.clear()
    st.rerun()
