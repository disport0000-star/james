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
        # 抓取過去 10 天的資料，確保在連假或週末也能抓到最後一個交易日的盤後數據
        df = dl.taiwan_stock_institutional_investors(
            stock_id="", 
            start_date=(datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        )
        if df.empty:
            st.info("💡 目前尚未取得最新盤後法人數據。")
            return
        
        # 取得資料庫中最新的一個交易日日期
        latest_date = df['date'].max()
        df_latest = df[df['date'] == latest_date]
        
        st.subheader(f"🏛️ 三大法人盤後買賣超統計 (結算日期: {latest_date})")
        
        # 建立三欄佈局模仿圖片
        col1, col2, col3 = st.columns(3)
        
        def render_box(container, display_name, data_names):
            # 加總該類別所有細項 (例如外資可能包含外資自營商)
            sub_df = df_latest[df_latest['name'].isin(data_names)]
            if not sub_df.empty:
                buy = sub_df['buy'].sum() / 10**8
                sell = sub_df['sell'].sum() / 10**8
                net = buy - sell
                color = "#00ff00" if net >= 0 else "#ff4b4b" # 綠漲
