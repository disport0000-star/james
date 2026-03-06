import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import altair as alt

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 100 強監控", layout="wide")
st.title("📈 台股市值前 100 強財務監控")

# 您的 FinMind 金鑰
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

st.write(f"系統狀態：V1 穩定版恢復 | 更新時間: {datetime.now().strftime('%H:%M:%S')}")

# --- 2. [V1 原有功能] 獲取三大法人數據處理 (指標股替代方案) ---
def get_institutional_investor_data():
    dl = DataLoader()
    # 避開 login_token 可能在舊版本產生的錯誤
    try:
        dl.login_token(FINMIND_TOKEN)
    except:
        pass
    
    start_str = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    try:
        # V1 原邏輯：以指標股 (2330) 取得日期基準
        df = dl.taiwan_stock_institutional_investors(stock_id='2330', start_date=start_str)
        if df is not None and not df.empty:
            latest_date = df['date'].max()
            day_df = df[df['date'] == latest_date].copy()
            
            # 對齊身分別名稱
            name_map = {
                'Foreign_Investor': '外資',
                'Investment_Trust': '投信',
                'Dealer_self': '自營商自行買賣',
                'Dealer_Hedging': '自營商避險',
                'Foreign_Dealer_Self': '外資自營商'
            }
            day_df['身分別'] = day_df['name'].map(name_map).fillna(day_df['name'])
            
            # 單位轉換：根據原始數據優化為顯示數值
            day_df['買進(億)'] = (day_df['buy'] / 10000000).round(2)
            day_df['賣出(億)'] = (day_df['sell'] / 10000000).round(2)
            day_df['買賣超(億)'] = day_df['買進(億)'] - day_df['賣出(億)']
            
            return day_df[['身分別', '買進(億)', '賣出(億)', '買賣超(億)']], latest_date
    except:
        return None, "目前 API 方法受限，請嘗試更新 FinMind 套件。"
    return None, "查無數據"

# 顯示三大法人資訊區塊 (置頂)
st.subheader("📊 每日三大法人買賣超資訊")
inst_df, data_info = get_institutional_investor_data()
if isinstance(inst_df, pd.DataFrame):
    st.info(f"📅 參考日期：{data_info} (指標股數據參考)")
    def color_picker(val):
        color = '#FF4B4B' if val > 0 else '#00FF00' if val < 0 else 'white'
        return f'color: {color}; font-weight: bold'
    st.table(inst_df.style.applymap(color_picker, subset=['買賣超(億)']))
else:
    st.warning(f"⚠️ {data_info}")

st.divider()

# --- 3. 核心抓取函數 (殖利率分析) ---
def fetch_stock_info(sid, sname):
    try:
        stock = yf.Ticker(f"{sid}.TW")
        # 增加緩衝抓取最新收盤價
        hist = stock.history(period="5d")
        if hist.empty: return None
        curr_price = hist['Close'].iloc[-1]
        
        # 殖利率計算
        divs = stock.dividends
        last_year = datetime.now() - timedelta(days=365)
        cash_div = divs[divs.index.tz_localize(None) >= last_year].sum() if not divs.empty else 0
        
        return {
            '股票代號': sid, '公司名稱': sname, '目前股價': round(curr_price, 2),
            '現金殖利率(%)': round((cash_div / curr_price * 100), 2) if cash_div > 0 else 0.0,
            '現金股利': round(cash_div, 2)
        }
    except: return None

# --- 4. 介面與狀態管理 ---
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None

col1, col2 = st.columns(2)
with col1:
    if st.button('🚀 執行 100 強數據分析', use_container_width=True):
        dl = DataLoader()
        try:
            df_info = dl.taiwan_stock_info()
            # 確保取得台股上市名單
            base_list = [[row['stock_id'], row['stock_name']] for _, row in df_info[df_info['type']=='twse'].drop_duplicates('stock_id').head(100).iterrows()]
            
            with st.status("🔍 正在同步分析 100 強個股數據...", expanded=True) as status:
                res_list = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    futures = [executor.submit(fetch_stock_info, s[0], s[1]) for s in base_list]
                    for f in concurrent.futures.as_completed(futures):
                        r = f.result()
                        if r: res_list.append(r)
                
                if res_list:
                    st.session_state.analysis_results = pd.DataFrame(res_list)
                    status.update(label="✅ 分析完成", state="complete")
                else:
                    st.error("無法抓取數據，請檢查網路連線。")
        except Exception as e:
            st.error(f"分析失敗: {e}")

with col2:
    if st.button('🧹 清除所有快取', use_container_width=True):
        st.session_state.analysis_results = None
        st.cache_data.clear()
        st.rerun()

# --- 5. 顯示分析結果 ---
if st.session_state.analysis_results is not None:
    full_df = st.session_state.analysis_results
    if '現金殖利率(%)' in full_df.columns:
        full_df = full_df.sort_values('現金殖利率(%)', ascending=False).reset_index(drop=True)
        
        st.subheader("💰 現金殖利率前 20 名")
        st.dataframe(full_df.head(20), use_container_width=True, hide_index=True)
        
        # 視覺化圖表
        chart = alt.Chart(full_df.head(20)).mark_bar(color='#FF4B4B').encode(
            x=alt.X('公司名稱:N', sort='-y', title='公司'),
            y=alt.Y('現金殖利率(%):Q', title='殖利率 (%)'),
            tooltip=['股票代號', '公司名稱', '現金殖利率(%)']
        ).properties(height=400)
        st.altair_chart(chart, use_container_width=True)
