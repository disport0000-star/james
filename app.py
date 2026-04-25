# ==========================================
# 📈 台股精選 300 強財務監控 - V1.9 修正版
# 新增：黃金價格走勢 + 國發會官方景氣燈號即時連線
# ==========================================
import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import io
import altair as alt
import os
import requests

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 300 強監控", layout="wide")
st.title("📈 台股市值前 300 強財務監控")

# 建議將此 Token 放在 st.secrets 中以維護安全
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNyAxNTowNToyNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMTExLjI1NS4xMTAuNDkifQ.FLkCVK6j0S6TfgAI-_hAhaa3i11pmwlntZZP2X1RiIs"

st.write(f"系統狀態：V1.9 總經雙箭頭修正版 (目前時間: {datetime.now().strftime('%H:%M:%S')})")

LOCAL_CACHE_FILE = "taiwan_top300_cache_v1_9.csv"

# --- 2. 總經數據抓取函數 (黃金 + 景氣燈號) ---
@st.cache_data(ttl=3600)
def get_gold_trend():
    try:
        gold = yf.Ticker("GC=F")
        df_gold = gold.history(period="1y")
        if not df_gold.empty:
            df_gold = df_gold.reset_index()
            # 修正：確保日期格式乾淨且無時區問題
            df_gold['Date'] = pd.to_datetime(df_gold['Date']).dt.tz_localize(None).dt.date
            return df_gold[['Date', 'Close']]
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=86400)
def get_taiwan_economic_light():
    try:
        # 呼叫國發會 (NDC) 官方 Open Data API
        url = "https://od.ndc.gov.tw/api/v1/rest/datastore/A53000000A-000009"
        res = requests.get(url, timeout=10)
        data = res.json()
        
        if data.get('success'):
            records = data['result']['records']
            df = pd.DataFrame(records)
            
            # 整理國發會的欄位，並清除可能存在的空白字元
            df.columns = df.columns.str.strip()
            df = df[['年月', '景氣對策信號綜合分數', '景氣對策信號檢查值']].copy()
            df.columns = ['Date', 'Score', 'Light']
            
            # 轉換日期格式 (從 202401 變成 2024/01)
            df['Date'] = df['Date'].astype(str).apply(lambda x: f"{x[:4]}/{x[4:]}")
            df['Score'] = pd.to_numeric(df['Score'], errors='coerce')
            df = df.dropna()
            
            # 取最近 24 個月的數據來畫圖
            df = df.tail(24).reset_index(drop=True)
            return df
    except Exception as e:
        st.error(f"景氣燈號抓取失敗: {e}")
    return pd.DataFrame()

# --- 3. 台股核心抓取函數 ---
def fetch_single_stock(sid, sname):
    import time, random
    time.sleep(random.uniform(1.0, 2
