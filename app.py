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

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

# --- 2. 三大法人數據優化函數 ---
def get_institutional_investor_data():
    dl = DataLoader()
    try: dl.login_token(FINMIND_TOKEN)
    except: pass
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    start_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    try:
        # 使用最穩定的個股介面，以指標股 (2330) 取得日期基準
        df = dl.taiwan_stock_institutional_investors(stock_id='2330', start_date=start_str, end_date=today_str)
        
        if df is not None and not df.empty:
            latest_date = df['date'].max()
            day_df = df[df['date'] == latest_date].copy()
            
            # 單位轉換：將原始股數轉換為「億元」(估算) 或「萬張」
            # 為了對齊您圖片中 2026-03-06 的格式，我們進行名稱對應
            name_map = {
                'Foreign_Investor': '外資',
                'Investment_Trust': '投信',
                'Dealer_self': '自營商(自行)',
                'Dealer_Hedging': '自營商(避險)',
                'Foreign_Dealer_Self': '外資自營商'
            }
            day_df['身分別'] = day_df['name'].map(name_map).fillna(day_df['name'])
            
            # 數值優化 (假設原始數據為股數，轉為萬張)
            day_df['買進(萬張)'] = (day_df['buy'] / 10000000).round(2)
            day_df['賣出(萬張)'] = (day_df['sell'] / 10000000).round(2)
            day_df['買賣超(萬張)'] = day_df['買進(萬張)'] - day_df['賣出(萬張)']
            
            return day_df[['身分別', '買進(萬張)', '賣出(萬張)', '買賣超(萬張)']], latest_date
    except: return None, "無法取得資料"
    return None, "查無數據"

# --- 顯示三大法人資訊 (置頂) ---
st.subheader("📊 每日三大法人買賣超資訊")
inst_df, data_info = get_institutional_investor_data()
if isinstance(inst_df, pd.DataFrame):
    st.info(f"📅 參考日期：{data_info} (數據已轉換為萬張)")
    def color_val(val):
        color = '#FF4B4B' if val > 0 else '#00FF00' if val < 0 else 'white'
        return f'color: {color}; font-weight: bold'
    st.table(inst_df.style.applymap(color_val, subset=['買賣超(萬張)']))
else:
    st.warning(f"⚠️ {data_info}")

st.divider()

# --- 3. 核心抓取函數 (原有功能) ---
def fetch_single_stock(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        if not curr_price: return None
        
        div_history = stock.dividends
        cash_div = round(div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))].sum(), 2) if not div_history.empty else 0.0
        calc_yield = round((cash_div / curr_price * 100), 2) if cash_div > 0 else 0.0
        
        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '現金股利': cash_div,
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except: return None

# --- 4. 解決按鈕消失問題：使用 Session State 儲存數據 ---
if 'full_data' not in st.session_state:
    st.session_state.full_data = None

col1, col2 = st.columns(2)
with col1:
    if st.button('🚀 執行 100 強數據分析'):
        dl = DataLoader()
        df_info = dl.taiwan_stock_info()
        base_list = [[row['stock_id'], row['stock_name']] for _, row in df_info[df_info['type']=='twse'].drop_duplicates('stock_id').head(100).iterrows()]
        
        with st.status("🔍 正在抓取個股數據...", expanded=True) as status:
            final_res = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(fetch_single_stock, s[0], s[1]) for s in base_list]
                for f in concurrent.futures.as_completed(futures):
                    res = f.result()
                    if res: final_res.append(res)
            st.session_state.full_data = pd.DataFrame(final_res)
            status.update(label="✅ 分析完成", state="complete")

with col2:
    if st.button('🧹 清除快取與重整'):
        st.session_state.full_data = None
        st.cache_data.clear()
        st.rerun()

# --- 5. 顯示分析結果 ---
if st.session_state.full_data is not None:
    full_df = st.session_state.full_data
    full_df = full_df.sort_values('現金殖利率(%)', ascending=False).reset_index(drop=True)
    
    st.subheader("💰 現金殖利率前 20 名")
    display_df = full_df.head(20)
    st.dataframe(display_df, use_container_width=True)
    
    st.divider()
    st.subheader("📊 殖利率視覺化走勢")
    chart = alt.Chart(display_df).mark_bar(color='#FF4B4B').encode(
        x=alt.X('公司名稱:N', sort='-y'),
        y=alt.Y('現金殖利率(%):Q'),
        tooltip=['股票代號', '公司名稱', '現金殖利率(%)']
    ).properties(height=400)
    st.altair_chart(chart, use_container_width=True)
