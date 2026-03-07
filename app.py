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

# 您提供的 FinMind Token
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A"

st.write(f"系統狀態：終極相容性與語法修正版 (更新時間: {datetime.now().strftime('%H:%M:%S')})")

# --- 2. 核心抓取函數 ---
@st.cache_data(ttl=3600)
def get_all_stock_data(base_list):
    final_results = []
    # 使用 ThreadPoolExecutor 平行處理，建議 max_workers 不要太高以防被封鎖
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_single_stock, s[0], s[1]) for s in base_list]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: final_results.append(res)
    return pd.DataFrame(final_results)

def fetch_single_stock(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    
    # 修正：直接在初始化時帶入 token，這是最穩定的相容做法
    dl = DataLoader()
    try:
        # 手動設置 token 以符合部分舊版要求
        dl.token = FINMIND_TOKEN 
    except: pass
    
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        if curr_price == 0: return None

        # --- 配息數據 ---
        div_history = stock.dividends
        if not div_history.empty:
            last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
            cash_div = round(last_year_divs.sum(), 2)
        else:
            cash_div = 0.0
        
        calc_yield = round((cash_div / curr_price * 100), 1) if cash_div > 0 else 0.0

        # --- EPS 數據 ---
        eps_q0, eps_q1, eps_q2 = 0.0, 0.0, 0.0
        q_fin = stock.quarterly_financials
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: eps_q1 = round(eps_series.iloc[1], 2)
            if len(eps_series) > 2: eps_q2 = round(eps_series.iloc[2], 2)

        # --- 三期營收數據 ---
        rev_m0, rev_m1, rev_m2, r_growth = "", "", "", ""
        try:
            df_rev = dl.taiwan_stock_month_revenue(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
            )
            if not df_rev.empty:
                df_rev = df_rev.sort_values('date', ascending=False)
                rev_m0 = f"{round(df_rev.iloc[0]['revenue'] / 1000):,.0f}" 
                if len(df_rev) >= 2:
                    rev_m1 = f"{round(df_rev.iloc[1]['revenue'] / 1000):,.0f}" 
                    r0, r1 = df_rev.iloc[0]['revenue'], df_rev.iloc[1]['revenue']
                    r_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else ""
                if len(df_rev) >= 3:
                    rev_m2 = f"{round(df_rev.iloc[2]['revenue'] / 1000):,.0f}" 
        except: pass

        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '
