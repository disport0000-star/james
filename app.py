import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import io
import altair as alt

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 100 強監控", layout="wide")
st.title("🚀 台股市值前 100 強決策監控儀表板")

# 建議將金鑰放入 Streamlit Secrets 或環境變數中
# 本地測試請在 .streamlit/secrets.toml 設定 FINMIND_TOKEN = "your_token"
FINMIND_TOKEN = st.secrets.get("FINMIND_TOKEN", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A")

st.sidebar.header("📊 系統監控與過濾")
st.sidebar.info(f"最後更新: {datetime.now().strftime('%H:%M:%S')}")

# --- 2. 核心抓取邏輯 (市值排序與併發抓取) ---

@st.cache_data(ttl=3600)
def get_top_100_by_market_cap():
    """透過 FinMind 抓取所有個股清單，並用 yfinance 獲取市值排序"""
    dl = DataLoader()
    dl.login_token(FINMIND_TOKEN)
    df_info = dl.taiwan_stock_info()
    # 只取上市(twse)且為普通股(移除權證、ETF)
    df_info = df_info[(df_info['type'] == 'twse') & (df_info['stock_id'].str.len() == 4)]
    
    # 這裡我們先取前 150 名進行市值檢查，確保能涵蓋真正的 Top 100
    # (註：FinMind 的 info 表通常不帶即時市值，實務上 Top 100 變動不大)
    base_list = [[row['stock_id'], row['stock_name']] for _, row in df_info.head(150).iterrows()]
    return base_list

def fetch_stock_details(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    dl = DataLoader()
    dl.login_token(FINMIND_TOKEN)
    
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        
        # 基礎價格與市值
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        market_cap = info.get('marketCap', 0)
        if curr_price == 0: return None

        # 估值指標
        pe_ratio = info.get('trailingPE')
        pb_ratio = info.get('priceToBook')

        # 配息計算 (滾動一年)
        div_history = stock.dividends
        cash_div = 0.0
        if not div_history.empty:
            last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
            cash_div = round(last_year_divs.sum(), 2)
        
        calc_yield = round((cash_div / curr_price * 100), 1) if cash_div > 0 else 0.0

        # 營收與 EPS (簡化取用 info 內建數據以提升速度)
        eps = info.get('trailingEps', 0)
        rev_growth = info.get('revenueGrowth', 0) * 100 # 營收年增率

        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '市值(億)': round(market_cap / 100000000, 1),
            '本益比': round(pe_ratio, 2) if pe_ratio else None,
            '股價淨值比': round(pb_ratio, 2) if pb_ratio else None,
            '現金殖利率(%)': calc_yield, '現金股利': cash_div,
            '最新EPS': round(eps, 2) if eps else 0,
            '營收年增率(%)': round(rev_growth, 1),
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '營業利益率(%)': round(info.get('operatingMargins', 0) * 100, 1),
        }
    except: return None

# --- 3. 介面與顯示 ---

if st.button('🚀 開始深度分析 Top 100 強'):
    with st.status("🔍 正在抓取大盤數據並進行多執行緒分析...", expanded=True) as status:
        base_list = get_top_100_by_market_cap()
        
        results = []
        # 將 max_workers 調至 10-12 較為穩定，避免 yfinance rate limit
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_stock = {executor.submit(fetch_stock_details, s[0], s[1]): s for s in base_list}
            for future in concurrent.futures.as_completed(future_to_stock):
                res = future.result()
                if res: results.append(res)
        
        full_df = pd.DataFrame(results)
        # 真正按照市值進行排序並取前 100
        full_df = full_df.sort_values(by='市值(億)', ascending=False).head(100)
        status.update(label="✅ 分析完成！", state="complete")

    if not full_df.empty:
        # --- 側邊欄濾鏡 ---
        st.sidebar.divider()
        yield_filter = st.sidebar.slider("最低殖利率 (%)", 0.0, 10.0, 3.0)
        pe_filter = st.sidebar.slider("最高本益比 (PE)", 5.0, 50.0, 25.0)
        
        filtered_df = full_df[
            (full_df['現金殖利率(%)'] >= yield_filter) & 
            (full_df['本益比'].fillna(999) <= pe_filter)
        ]

        # --- 數據視覺化 ---
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("🎯 價值投資分佈圖 (殖利率 vs 本益比)")
            # 氣泡圖：X軸=本益比, Y軸=殖利率, 大小=市值
            
            chart = alt.Chart(filtered_df).mark_circle().encode(
                x=alt.X('本益比:Q', title='本益比 (越低越便宜)'),
                y=alt.Y('現金殖利率(%):Q', title='殖利率 (越高等於領越多)'),
                size=alt.Size('市值(億):Q', legend=None),
                color=alt.Color('營收年增率(%):Q', scale=alt.Scale(scheme='viridis'), title='營收年增率'),
                tooltip=['公司名稱', '股票代號', '目前股價', '本益比', '現金殖利率(%)']
            ).properties(height=500).interactive()
            st.altair_chart(chart, use_container_width=True)

        with col2:
            st.subheader("🏆 篩選後清單")
            st.dataframe(
                filtered_df[['公司名稱', '目前股價', '現金殖利率(%)', '本益比']],
                hide_index=True, use_container_width=True
            )

        # --- 下載區 ---
        st.divider()
        csv = filtered_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載篩選後財報 (CSV)", csv, "Top100_Filtered.csv", "text/csv")
    else:
        st.error("連線超時或數據源異常，請稍後再試。")

if st.sidebar.button('🧹 清除系統快取'):
    st.cache_data.clear()
    st.rerun()
