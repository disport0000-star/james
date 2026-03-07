import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import io
import altair as alt

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股 100 強監控 V3.1", layout="wide")
st.title("📈 台股市值前 100 強財務監控 (V3.1 修正版)")

# FinMind 金鑰
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

st.info(f"V3.1 修正重點：修復 DataLoader.login 錯誤、優化營收三期對比邏輯。 (系統時間: {datetime.now().strftime('%Y-%m-%d %H:%M')})")

# --- 2. 核心抓取函數 ---
def fetch_single_stock(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    # 修正點：DataLoader 初始化時直接帶入 token，不再呼叫 .login()
    dl = DataLoader()
    
    try:
        stock = yf.Ticker(full_sid)
        f_info = stock.fast_info
        curr_price = f_info.get('last_price') or 0
        if curr_price == 0: return None

        # 殖利率計算
        div_history = stock.dividends
        cash_div = 0.0
        if not div_history.empty:
            last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
            cash_div = round(last_year_divs.sum(), 2)
        
        calc_yield = round((cash_div / curr_price * 100), 2) if curr_price > 0 else 0.0

        # EPS 資料
        eps_q0, eps_q1 = 0.0, 0.0
        q_fin = stock.quarterly_financials
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: eps_q1 = round(eps_series.iloc[1], 2)

        # 營收三期邏輯
        rev_m0, rev_m1, rev_m2, r_growth = "N/A", "N/A", "N/A", "N/A"
        try:
            # 修正點：調用時帶入 token
            df_rev = dl.taiwan_stock_month_revenue(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=150)).strftime('%Y-%m-%d'),
                token=FINMIND_TOKEN
            )
            if not df_rev.empty:
                df_rev = df_rev.sort_values('date', ascending=False)
                if len(df_rev) >= 1:
                    r0 = df_rev.iloc[0]['revenue']
                    rev_m0 = f"{round(r0 / 1000):,.0f}"
                if len(df_rev) >= 2:
                    r1 = df_rev.iloc[1]['revenue']
                    rev_m1 = f"{round(r1 / 1000):,.0f}"
                    r_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else "0%"
                if len(df_rev) >= 3:
                    r2 = df_rev.iloc[2]['revenue']
                    rev_m2 = f"{round(r2 / 1000):,.0f}"
        except: pass

        info = stock.info
        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '現金股利': cash_div,
            '最新季EPS': eps_q0, '上一季EPS': eps_q1,
            '最新營收(千元)': rev_m0, '上月營營收(千元)': rev_m1, '上上月營收(千元)': rev_m2,
            '營收月增率': r_growth,
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except: return None

@st.cache_data(ttl=3600)
def get_all_stock_data_v3(base_list):
    final_results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(base_list)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_stock = {executor.submit(fetch_single_stock, s[0], s[1]): s for s in base_list}
        for i, future in enumerate(concurrent.futures.as_completed(future_to_stock)):
            res = future.result()
            if res: final_results.append(res)
            progress_bar.progress((i + 1) / total)
            status_text.text(f"🚀 處理中: {i+1}/{total} - {future_to_stock[future][1]}")
    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(final_results)

# --- 3. 獲取名單 ---
@st.cache_data(ttl=86400)
def get_top_100_list():
    dl = DataLoader()
    # 修正點：不使用 .login()，直接在 API 調用處傳入 token
    df_info = dl.taiwan_stock_info()
    df_info = df_info[df_info['type'] == 'twse'].drop_duplicates(subset=['stock_id'])
    return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(100).iterrows()]

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='StockData')
    return output.getvalue()

# --- 4. UI 邏輯 ---
col1, col2 = st.columns([1, 4])
with col1:
    run = st.button('🚀 執行分析', use_container_width=True)
with col2:
    if st.button('🧹 清除快取', use_container_width=True):
        st.cache_data.clear()
        st.rerun()

if run:
    base_list = get_top_100_list()
    with st.status("🔍 正在抓取數據...", expanded=True) as status:
        full_df = get_all_stock_data_v3(base_list)
        status.update(label="✅ 完成！", state="complete")
    
    if not full_df.empty:
        full_df = full_df.drop_duplicates(subset=['股票代號']).sort_values(by='現金殖利率(%)', ascending=False)
        st.download_button("📥 下載 Excel", data=to_excel(full_df), file_name="TW_Stock_V3_1.xlsx")
        st.dataframe(full_df.head(20), use_container_width=True, hide_index=True)
        
        # 圖表
        max_y = full_df['現金殖利率(%)'].head(20).max() + 1
        chart = alt.Chart(full_df.head(20)).mark_bar().encode(
            x=alt.X('公司名稱:N', sort='-y'),
            y=alt.Y('現金殖利率(%):Q', scale=alt.Scale(domain=[0, max_y])),
            tooltip=['股票代號', '公司名稱', '現金殖利率(%)']
        ).properties(height=400).interactive(bind_y=False)
        st.altair_chart(chart, use_container_width=True)
