import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import datetime, timedelta
import concurrent.futures
import altair as alt

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 100 強監控", layout="wide")
st.title("📈 台股市值前 100 強財務監控")

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

# --- 2. [根據 API 截圖修正] 直接使用 Requests 抓取三大法人 ---
def get_institutional_investors_api():
    url = "https://api.finmindtrade.com/api/v4/data"
    start_str = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    
    params = {
        "dataset": "TaiwanStockTotalInstitutionalInvestors",
        "start_date": start_str,
        "token": FINMIND_TOKEN
    }
    
    try:
        resp = requests.get(url, params=params)
        data = resp.json()
        
        if data.get("msg") == "success" and data.get("data"):
            df = pd.DataFrame(data["data"])
            # 取得最新日期
            latest_date = df['date'].max()
            current_df = df[df['date'] == latest_date].copy()
            
            # 單位轉換：元 -> 億 (除以 10^8)
            current_df['買進(億)'] = (current_df['buy'] / 100000000).round(2)
            current_df['賣出(億)'] = (current_df['sell'] / 100000000).round(2)
            current_df['買賣超(億)'] = (current_df['diff'] / 100000000).round(2)
            
            # 中文名稱對應 (對齊您的圖片名稱)
            name_map = {
                'Foreign_Investor': '外資',
                'Investment_Trust': '投信',
                'Dealer_Self': '自營商自行買賣',
                'Dealer_Hedging': '自營商避險',
                'Foreign_Dealer_Self': '外資自營商'
            }
            current_df['身分別'] = current_df['name'].map(name_map).fillna(current_df['name'])
            
            return current_df[['身分別', '買進(億)', '賣出(億)', '買賣超(億)']], latest_date
    except Exception as e:
        return None, f"API 連線失敗: {e}"
    return None, "查無數據"

# 顯示三大法人區塊
st.subheader("📊 每日三大法人買賣超資訊 (全市場)")
inst_df, data_date = get_institutional_investors_api()

if isinstance(inst_df, pd.DataFrame):
    st.info(f"📅 數據日期：{data_date} (單位：億元)")
    def color_picker(val):
        color = '#FF4B4B' if val > 0 else '#00FF00' if val < 0 else 'white'
        return f'color: {color}; font-weight: bold'
    
    # 呈現如同您要求的精簡表格
    st.table(inst_df.style.format({'買進(億)': '{:,.2f}', '賣出(億)': '{:,.2f}', '買賣超(億)': '{:,.2f}'})
             .applymap(color_picker, subset=['買賣超(億)']))
else:
    st.warning(f"⚠️ {data_date}")

st.divider()

# --- 3. 核心數據抓取 (Yahoo Finance 殖利率) ---
def fetch_stock_data(sid, sname):
    try:
        stock = yf.Ticker(f"{sid}.TW")
        # 抓取最近 5 天價格確保不為空
        hist = stock.history(period="5d")
        if hist.empty: return None
        curr_price = hist['Close'].iloc[-1]
        
        # 滾動一年股利計算
        divs = stock.dividends
        last_year = datetime.now() - timedelta(days=365)
        cash_div = divs[divs.index.tz_localize(None) >= last_year].sum() if not divs.empty else 0
        
        return {
            '股票代號': sid, '公司名稱': sname, '目前股價': round(curr_price, 2),
            '現金殖利率(%)': round((cash_div / curr_price * 100), 2) if cash_div > 0 else 0.0,
            '現金股利': round(cash_div, 2)
        }
    except: return None

# --- 4. 介面與狀態保持 ---
if 'results' not in st.session_state:
    st.session_state.results = None

c1, c2 = st.columns(2)
with c1:
    if st.button('🚀 執行 100 強數據分析', use_container_width=True):
        # 抓取前 100 名單 (直接調用 API 避免 DataLoader 報錯)
        try:
            url = "https://api.finmindtrade.com/api/v4/data"
            params = {"dataset": "TaiwanStockInfo", "token": FINMIND_TOKEN}
            df_info = pd.DataFrame(requests.get(url, params=params).json()["data"])
            base_list = [[row['stock_id'], row['stock_name']] for _, row in df_info[df_info['type']=='twse'].drop_duplicates('stock_id').head(100).iterrows()]
            
            with st.status("🔍 數據同步分析中...", expanded=True) as status:
                res_list = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(fetch_stock_data, s[0], s[1]) for s in base_list]
                    for f in concurrent.futures.as_completed(futures):
                        r = f.result()
                        if r: res_list.append(r)
                
                if res_list:
                    st.session_state.results = pd.DataFrame(res_list)
                    status.update(label="✅ 分析完成", state="complete")
        except Exception as e:
            st.error(f"分析失敗: {e}")

with c2:
    if st.button('🧹 清除快取', use_container_width=True):
        st.session_state.results = None
        st.cache_data.clear()
        st.rerun()

# --- 5. 顯示結果 ---
if st.session_state.results is not None:
    full_df = st.session_state.results
    if not full_df.empty:
        full_df = full_df.sort_values('現金殖利率(%)', ascending=False).reset_index(drop=True)
        st.subheader("💰 現金殖利率前 20 名")
        st.dataframe(full_df.head(20), use_container_width=True, hide_index=True)
        
        chart = alt.Chart(full_df.head(20)).mark_bar(color='#FF4B4B').encode(
            x=alt.X('公司名稱:N', sort='-y'),
            y=alt.Y('現金殖利率(%):Q'),
            tooltip=['股票代號', '現金殖利率(%)']
        ).properties(height=400)
        st.altair_chart(chart, use_container_width=True)
