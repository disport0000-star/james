# ==========================================
# 📈 台股精選 300 強財務監控 - V1.3 新增股票股利版
# (基於 V1 標準版核心功能延伸)
# ==========================================
import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import io
import altair as alt
import time
import random
import os

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 300 強監控", layout="wide")
st.title("📈 台股市值前 300 強財務監控")

# 您的 FinMind 金鑰
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNyAxNTowNToyNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMTExLjI1NS4xMTAuNDkifQ.FLkCVK6j0S6TfgAI-_hAhaa3i11pmwlntZZP2X1RiIs"

st.write(f"系統狀態：V1.3 新增股票股利版 (目前時間: {datetime.now().strftime('%H:%M:%S')})")

# 【重要修改】更改快取檔名，強迫建立包含「股票股利」的新檔案
LOCAL_CACHE_FILE = "taiwan_top300_cache_v1_3.csv"

# --- 2. 日期邏輯檢查 ---
def get_recent_10th_date():
    now = datetime.now()
    if now.day >= 10:
        return datetime(now.year, now.month, 10).date()
    else:
        if now.month == 1:
            return datetime(now.year - 1, 12, 10).date()
        else:
            return datetime(now.year, now.month - 1, 10).date()

# --- 3. 核心抓取函數 ---
@st.cache_data(ttl=3600)
def get_all_stock_data_v5(base_list):
    final_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch_single_stock, s[0], s[1]) for s in base_list]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: 
                final_results.append(res)
    return pd.DataFrame(final_results)

def fetch_single_stock(sid, sname):
    time.sleep(random.uniform(0.8, 2.0)) 
    
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    
    dl = DataLoader()
    dl.login_by_token(api_token=FINMIND_TOKEN)
    
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        
        if curr_price == 0: 
            return None

        div_history = stock.dividends
        if not div_history.empty:
            last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
            cash_div = round(last_year_divs.sum(), 2)
        else:
            cash_div = 0.0
            
        if cash_div > 0:
            calc_yield = round((cash_div / curr_price * 100), 1)
        else:
            calc_yield = 0.0

        # 【新增】抓取股票股利資訊
        stock_div = info.get('stockDividendValue', 0.0) or 0.0

        eps_q0, eps_q1, eps_q2 = 0.0, 0.0, 0.0
        q_fin = stock.quarterly_financials
        
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: eps_q1 = round(eps_series.iloc[1], 2)
            if len(eps_series) > 2: eps_q2 = round(eps_series.iloc[2], 2)
        else:
            eps_q0 = round(info.get('trailingEps', 0), 2)

        eps_growth = "N/A"
        if eps_q1 != 0:
            eps_growth = f"{round(((eps_q0 - eps_q1) / abs(eps_q1)) * 100, 1)}%"
        else:
            eps_growth = "0%" if eps_q0 == 0 else "N/A"

        rev_m0, rev_m1, rev_m2, r_growth = "N/A", "N/A", "N/A", "N/A"
        
        try:
            df_rev = dl.taiwan_stock_month_revenue(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
            )
            if df_rev is not None and not df_rev.empty:
                df_rev = df_rev.sort_values('date', ascending=False)
                if len(df_rev) > 0: 
                    rev_m0 = f"{round(df_rev.iloc[0]['revenue'] / 1000):,.0f}"
                if len(df_rev) > 1:
                    r0, r1 = df_rev.iloc[0]['revenue'], df_rev.iloc[1]['revenue']
                    rev_m1 = f"{round(r1 / 1000):,.0f}"
                    r_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else "0%"
                if len(df_rev) > 2:
                    rev_m2 = f"{round(df_rev.iloc[2]['revenue'] / 1000):,.0f}"
        except Exception:
            pass 

        return {
            '股票代號': clean_id, 
            '公司名稱': sname, 
            '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, 
            '現金股利': cash_div,
            '股票股利': stock_div,  # 【新增欄位】安插在現金股利後方
            '最新季EPS': eps
