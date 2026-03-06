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
st.title("📈 台股市值前 100 強財務監控")

# 您的 FinMind 金鑰
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

# --- 2. 擷取並製作「盤後」三大法人畫面 ---
def display_institutional_investors():
    dl = DataLoader()
    try:
        # 抓取過去 10 天的資料，確保週末或連假也能抓到最新盤後結算數據
        df = dl.taiwan_stock_institutional_investors(
            stock_id="", 
            start_date=(datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        )
        if df.empty:
            st.info("💡 目前尚未取得最新盤後法人統計數據。")
            return
        
        # 取得資料庫中最新的一個交易日
        latest_date = df['date'].max()
        df_latest = df[df['date'] == latest_date]
        
        st.subheader(f"🏛️ 三大法人盤後買賣超統計 (結算日期: {latest_date})")
        
        # 建立三欄佈局模仿圖片編排
        col1, col2, col3 = st.columns(3)
        
        def render_box(container, display_name, data_names):
            # 加總該類別數據
            sub_df = df_latest[df_latest['name'].isin(data_names)]
            if not sub_df.empty:
                buy = sub_df['buy'].sum() / 10**8
                sell = sub_df['sell'].sum() / 10**8
                net = buy - sell
                # 顏色邏輯：正數綠色 (+)，負數紅色 (-)
                color = "#00ff00" if net >= 0 else "#ff4b4b"
                sign = "+" if net >= 0 else ""
                
                with container:
                    st.markdown(f"**{display_name}**")
                    st.markdown(f"<h3 style='color: {color}; margin-top: 0;'>{sign}{net:.1f} 億</h3>", unsafe_allow_html=True)
                    st.markdown(f"<p style='font-size: 0.8em;'>買進 {buy:.1f} 億 | 賣出 {sell:.1f} 億</p>", unsafe_allow_html=True)
                    st.write("---")

        # 依照圖片樣式分列顯示
        render_box(col1, "外資及陸資", ["Foreign_Investor"])
        render_box(col1, "自營商(避險)", ["Dealer_Hedging"])
        
        render_box(col2, "投信", ["Investment_Trust"])
        render_box(col2, "自營商(自行買賣)", ["Dealer_self"])
        
        render_box(col3, "外資自營商", ["Foreign_Dealer_Self"])

    except Exception as e:
        st.info("💡 盤後數據更新中，請稍候再試。")

# 顯示置頂法人看板
display_institutional_investors()
st.divider()

# --- 3. 核心個股抓取函數 ---
@st.cache_data(ttl=3600)
def get_all_stock_data(base_list):
    final_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(fetch_single_stock, s[0], s[1]) for s in base_list]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: final_results.append(res)
    return pd.DataFrame(final_results)

def fetch_single_stock(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        if curr_price == 0: return None

        # 殖利率計算
        div_history = stock.dividends
        if not div_history.empty:
            last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
            cash_div = round(last_year_divs.sum(), 2)
        else:
            cash_div = 0.0
        calc_yield = round((cash_div / curr_price * 100), 1) if cash_div > 0 else 0.0

        # EPS 歷史數據
        eps_q0, eps_q1, eps_q2 = 0.0, 0.0, 0.0
        q_fin = stock.quarterly_financials
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: eps_q1 = round(eps_series.iloc[1], 2)
            if len(eps_series) > 2: eps_q2 = round(eps_series.iloc[2], 2)

        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '現金股利': cash_div,
            '最新季EPS': eps_q0, '上一季EPS': eps_q1, '上上一季EPS': eps_q2,
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except: return None

# --- 4. 名單與 Excel 下載邏輯 ---
@st.cache_data(ttl=86400)
def get_top_100_list():
    dl = DataLoader()
    df_info = dl.taiwan_stock_info()
    # 修正：去重並取前 100
    df_info = df_info[df_info['type'] == 'twse'].drop_duplicates(subset=['stock_id
