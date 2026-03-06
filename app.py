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
st.title("📈 台股市值前 100 強決策監控")

# 金鑰管理：優先從 Streamlit Secrets 讀取，若無則使用預設值
FINMIND_TOKEN = st.secrets.get("FINMIND_TOKEN", "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A")

# --- 2. 核心抓取函數 ---

@st.cache_data(ttl=86400)
def get_top_100_list():
    """獲取台股上市股票清單"""
    try:
        dl = DataLoader()
        # 修正：新版 FinMind 不再使用 login_token()
        df_info = dl.taiwan_stock_info()
        df_info = df_info[(df_info['type'] == 'twse') & (df_info['stock_id'].str.len() == 4)]
        df_info = df_info.drop_duplicates(subset=['stock_id'])
        # 先取前 120 支，後續再由市值篩選前 100
        return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(120).iterrows()]
    except Exception as e:
        st.error(f"獲取股票清單失敗: {e}")
        return []

def fetch_single_stock(sid, sname):
    """抓取個別股票財務數據"""
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        
        # 基礎價格與市值
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        if curr_price == 0: return None
        
        market_cap = info.get('marketCap', 0)
        
        # 配息資料 (計算過去一年總和)
        div_history = stock.dividends
        cash_div = 0.0
        if not div_history.empty:
            # 確保時間戳不含時區以便比較
            last_year = datetime.now() - timedelta(days=365)
            last_year_divs = div_history[div_history.index.tz_localize(None) >= last_year]
            cash_div = round(last_year_divs.sum(), 2)
            
        calc_yield = round((cash_div / curr_price * 100), 1) if cash_div > 0 else 0.0

        return {
            '股票代號': clean_id, 
            '公司名稱': sname, 
            '目前股價': curr_price,
            '市值(億)': round(market_cap / 100000000, 1),
            '現金殖利率(%)': calc_yield, 
            '現金股利': cash_div,
            '本益比': info.get('trailingPE'),
            '股價淨值比': info.get('priceToBook'),
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except:
        return None

# --- 3. 介面主邏輯 ---

st.sidebar.header("🎯 篩選條件")
min_yield = st.sidebar.slider("最低殖利率 (%)", 0.0, 12.0, 3.0)

if st.button('🚀 執行 100 強深度分析'):
    base_list = get_top_100_list()
    
    if not base_list:
        st.warning("清單為空，請檢查網路連線或 API 金鑰。")
    else:
        with st.status("🔍 正在分析台股市值排名前 100 大個股...", expanded=True) as status:
            final_results = []
            # 使用多執行緒加速
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(fetch_single_stock, s[0], s[1]) for s in base_list]
                for future in concurrent.futures.as_completed(futures):
                    res = future.result()
                    if res: final_results.append(res)
            
            full_df = pd.DataFrame(final_results)
            # 真正按市值排序並取前 100
            full_df = full_df.sort_values(by='市值(億)', ascending=False).head(100)
            status.update(label="✅ 分析完成！", state="complete")
        
        if not full_df.empty:
            # 應用濾鏡
            display_df = full_df[full_df['現金殖利率(%)'] >= min_yield].copy()
            
            # 圖表展示
            st.subheader("📊 市值與殖利率分佈 (氣泡大小代表市值)")
            chart = alt.Chart(display_df).mark_circle().encode(
                x=alt.X('本益比:Q', title='本益比'),
                y=alt.Y('現金殖利率(%):Q', title='現金殖利率 (%)'),
                size=alt.Size('市值(億):Q', title='市值 (億)'),
                color=alt.Color('公司名稱:N', legend=None),
                tooltip=['公司名稱', '目前股價', '現金殖利率(%)', '本益比']
            ).properties(height=450).interactive()
            st.altair_chart(chart, use_container_width=True)

            # 資料表格
            st.subheader(f"💰 符合條件個股 (共 {len(display_df)} 檔)")
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # 下載功能
            csv = display_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載分析結果 (CSV)", csv, "Taiwan_Stock_Analysis.csv", "text/csv")
        else:
            st.error("無法取得有效數據。")

if st.sidebar.button('🧹 清除系統快取'):
    st.cache_data.clear()
    st.rerun()
