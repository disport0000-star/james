import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import time
import io

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 100 強監控", layout="wide")
st.title("📈 台股市值前 100 強財務監控")

# 已填入您的 FinMind 金鑰
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

st.write(f"系統狀態：前 20 名顯示 + 全量 Excel 下載版 (更新時間: {datetime.now().strftime('%H:%M:%S')})")

# --- 2. 單支股票詳細抓取函數 ---
def fetch_detailed_data(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    
    dl = DataLoader()
    try:
        dl.login(token=FINMIND_TOKEN)
    except:
        pass
        
    try:
        # A. yfinance 基礎數據
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        if curr_price == 0: return None

        # B. 殖利率與配息
        div_history = stock.dividends
        last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
        
        cash_div = round(last_year_divs.sum(), 2) if not last_year_divs.empty else 0.0
        stock_div = info.get('stockDividendValue', 0.0)
        if stock_div is None: stock_div = 0.0
        
        calc_yield = round((cash_div / curr_price * 100), 1) if cash_div > 0 else 0.0

        # C. EPS 歷史數據
        eps_q0, eps_q1, eps_q2 = 0.0, 0.0, 0.0
        q_fin = stock.quarterly_financials
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: eps_q1 = round(eps_series.iloc[1], 2)
            if len(eps_series) > 2: eps_q2 = round(eps_series.iloc[2], 2)
        else:
            eps_q0 = round(info.get('trailingEps', 0), 2)

        # D. FinMind 三期月營收
        rev_m0, rev_m1, rev_m2, m_growth = "", "", "", ""
        try:
            df_rev = dl.taiwan_stock_month_revenue(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=150)).strftime('%Y-%m-%d')
            )
            if not df_rev.empty:
                df_rev = df_rev.sort_values('date', ascending=False)
                rev_m0 = f"{round(df_rev.iloc[0]['revenue'] / 1000):,.0f}" if len(df_rev) > 0 else ""
                rev_m1 = f"{round(df_rev.iloc[1]['revenue'] / 1000):,.0f}" if len(df_rev) > 1 else ""
                rev_m2 = f"{round(df_rev.iloc[2]['revenue'] / 1000):,.0f}" if len(df_rev) > 2 else ""
                r0, r1 = df_rev.iloc[0]['revenue'], df_rev.iloc[1]['revenue']
                m_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else ""
        except:
            pass

        # E. 兩期季營收
        rev_q0, rev_q1, q_growth = "", "", ""
        if not q_fin.empty and 'Total Revenue' in q_fin.index:
            q_revs = q_fin.loc['Total Revenue']
            rev_q0 = f"{round(q_revs.iloc[0]/1000):,.0f}" if len(q_revs) > 0 else ""
            rev_q1 = f"{round(q_revs.iloc[1]/1000):,.0f}" if len(q_revs) > 1 else ""
            v0, v1 = q_revs.iloc[0], q_revs.iloc[1]
            q_growth = f"{round(((v0-v1)/v1)*100, 1)}%" if v1 != 0 else ""

        return {
            '股票代號': clean_id, 
            '公司名稱': sname, 
            '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, 
            '現金股利': cash_div,
            '股票股利': stock_div,
            '最新季EPS': eps_q0,
            '上一季EPS': eps_q1,
            '上上一季EPS': eps_q2,
            '最新一期營收(千元)': rev_m0, 
            '前一期營eu營收(千元)': rev_m1, 
            '前二期營收(千元)': rev_m2,
            '與上月比較增減(%)': m_growth, 
            '最新一季營收(千元)': rev_q0, 
            '上一季營收(千元)': rev_q1, 
            '與上季比較增減(%)': q_growth, 
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '營業利益率(%)': round(info.get('operatingMargins', 0) * 100, 1),
            '稅後淨利率(%)': round(info.get('profitMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except Exception as e:
        return None

# --- 3. 獲取前 100 強名單 ---
@st.cache_data(ttl=86400)
def get_top_100_stocks():
    dl = DataLoader()
    dl.login(token=FINMIND_TOKEN)
    df_info = dl.taiwan_stock_info()
    df_info = df_info[df_info['type'] == 'twse']
    return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(100).iterrows()]

# --- 4. 輔助函數：Excel
