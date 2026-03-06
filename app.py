import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import altair as alt

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 100 強監控", layout="wide")
st.title("📈 台股市值前 100 強財務監控")

# 您的 FinMind 金鑰
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

st.write(f"系統狀態：V1 修正版 (全市場三大法人金額彙整) | 更新時間: {datetime.now().strftime('%H:%M:%S')}")

# --- 2. [V1 修正內容] 獲取全市場三大法人買賣超金額 ---
def get_institutional_investor_total():
    url = "https://api.finmindtrade.com/api/v4/data"
    # 搜尋最近 10 天確保包含最新交易日
    start_str = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    
    params = {
        "dataset": "TaiwanStockTotalInstitutionalInvestors",
        "start_date": start_str,
        "token": FINMIND_TOKEN
    }
    
    try:
        # 直接使用 requests 避開 DataLoader 版本過舊的 AttributeError
        resp = requests.get(url, params=params)
        data = resp.json()
        
        if data.get("msg") == "success" and data.get("data"):
            df = pd.DataFrame(data["data"])
            # 取得最新交易日數據
            latest_date = df['date'].max()
            current_df = df[df['date'] == latest_date].copy()
            
            # 單位轉換：原始數據為「元」，除以 10^8 轉換為「億元」
            current_df['買進(億)'] = (current_df['buy'] / 100000000).round(2)
            current_df['賣出(億)'] = (current_df['sell'] / 100000000).round(2)
            current_df['買賣超(億)'] = (current_df['diff'] / 100000000).round(2)
            
            # 對照名稱中文化
            name_map = {
                'Foreign_Investor': '外資',
                'Investment_Trust': '投信',
                'Dealer_Self': '自營商自行買賣',
                'Dealer_Hedging': '自營商避險',
                'Foreign_Dealer_Self': '外資自營商'
            }
            current_df['身分別'] = current_df['name'].map(name_map).fillna(current_df['name'])
            
            # 整理輸出欄位
            result = current_df[['身分別', '買進(億)', '賣出(億)', '買賣超(億)']]
            return result, latest_date
    except Exception as e:
        return None, f"API 連線異常: {str(e)}"
    return None, "查無數據"

# --- 顯示三大法人資訊區塊 (置頂) ---
st.subheader("📊 每日全市場三大法人買賣超 (金額)")
inst_df, data_info = get_institutional_investor_total()

if isinstance(inst_df, pd.DataFrame):
    st.info(f"📅 數據日期：{data_info} (全市場統計，單位：億元)")
    
    # 設定數值顏色：正數紅、負數綠
    def color_val(val):
        if isinstance(val, (int, float)):
            color = '#FF4B4B' if val > 0 else '#00FF00' if val < 0 else 'white'
            return f'color: {color}; font-weight: bold'
        return ''
    
    # 呈現表格，限制顯示寬度
    st.table(inst_df.style.format({'買進(億)': '{:,.2f}', '賣出(億)': '{:,.2f}', '買賣超(億)': '{:,.2f}'})
             .applymap(color_val, subset=['買賣超(億)']))
else:
    st.warning(f"⚠️ {data_info}")

st.divider()

# --- 3. 核心抓取函數 (殖利率分析) ---
def fetch_stock_info(sid, sname):
    try:
        stock = yf.Ticker(f"{sid}.TW")
        # 抓取 5 天歷史價格確保不為空值
        hist = stock.history(period="5d")
        if hist.empty: return None
        curr_price = hist['Close'].iloc[-1]
        
        # 股利計算 (最近一年)
        divs = stock.dividends
        last_year = datetime.now() - timedelta(days=365)
        cash_div = divs[divs.index.tz_localize(None) >= last_year].sum() if not divs.empty else 0
        
        return {
            '股票代號': sid, '公司名稱': sname, '目前股價': round(curr_price, 2),
            '現金殖利率(%)': round((cash_div / curr_price * 100), 2) if cash_div > 0 else 0.0,
