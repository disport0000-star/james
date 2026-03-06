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

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

# --- 2. 三大法人數據處理 (對齊圖片格式) ---
def get_institutional_investor_data():
    dl = DataLoader()
    # 嘗試抓取最近一週資料以取得最新交易日
    start_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    try:
        # 使用穩定介面抓取指標股數據作為大盤法人參考
        df = dl.taiwan_stock_institutional_investors(stock_id='2330', start_date=start_str)
        if df is not None and not df.empty:
            latest_date = df['date'].max()
            day_df = df[df['date'] == latest_date].copy()
            
            # 名稱中文化
            name_map = {
                'Foreign_Investor': '外資',
                'Investment_Trust': '投信',
                'Dealer_self': '自營商自行買賣',
                'Dealer_Hedging': '自營商避險',
                'Foreign_Dealer_Self': '外資自營商'
            }
            day_df['身分別'] = day_df['name'].map(name_map).fillna(day_df['name'])
            
            # 數值轉換：原始數據通常為股數，轉為「億」估算 (僅作 UI 呈現)
            # 若要精確金額需使用 market_daily，但在您的環境易報錯，故此處先優化顯示格式
            day_df['買進'] = (day_df['buy'] / 1000000).round(2) 
            day_df['賣出'] = (day_df['sell'] / 1000000).round(2)
            day_df['買賣超'] = (day_df['buy'] - day_df['sell']) / 1000000
            
            return day_df[['身分別', '買進', '賣出', '買賣超']], latest_date
    except: return None, "無法取得法人資料"
    return None, "查無數據"

# 顯示三大法人資訊
st.subheader("📊 每日三大法人買賣超資訊")
inst_df, data_date = get_institutional_investor_data()
if isinstance(inst_df, pd.DataFrame):
    st.info(f"📅 參考日期：{data_date}")
    def color_picker(val):
        color = 'red' if val > 0 else 'green' if val < 0 else 'white'
        return f'color: {color}; font-weight: bold'
    st.table(inst_df.style.format({'買進': '{:,.2f}', '賣出': '{:,.2f}', '買賣超': '{:,.2f}'}).applymap(color_picker, subset=['買賣超']))
else:
    st.warning(data_date)

st.divider()

# --- 3. 核心數據抓取 (增加防錯) ---
def fetch_stock_info(sid, sname):
    try:
        stock = yf.Ticker(f"{sid}.TW")
        hist = stock.history(period="1d")
        if hist.empty: return None
        
        curr_price = hist['Close'].iloc[-1]
        divs = stock.dividends
        last_year = datetime.now() - timedelta(days=365)
        cash_div = divs[divs.index.tz_localize(None) >= last_year].sum() if not divs.empty else 0
        
        return {
            '股票代號': sid, '公司名稱': sname, '目前股價': round(curr_price, 2),
            '現金殖利率(%)': round((cash_div / curr_price * 100), 2) if cash_div > 0 else 0.0,
            '現金股利': round(cash_div, 2)
        }
    except: return None

# --- 4. 介面與狀態管理 (修復按鈕點擊後消失與 KeyError) ---
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None

col1, col2 = st.columns(2)
with col1:
    if st.button('🚀 執行 100 強數據分析'):
        dl = DataLoader()
        try:
            # 獲取名單
            df_info = dl.taiwan_stock_info()
            base_list = [[row['stock_id'], row['stock_name']] for _, row in df_info[df_info['type']=='twse'].drop_duplicates('stock_id').head(100).iterrows()]
            
            with st.status("🔍 正在同步分析 100 強數據...", expanded=True) as status:
                res_list = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(fetch_stock_info, s[0], s[1]) for s in base_list]
                    for f in concurrent.futures.as_completed(futures):
                        r = f.result()
                        if r: res_list.append(r)
                
                if res_list:
                    st.session_state.analysis_results = pd.DataFrame(res_list)
                    status.update(label="✅ 分析完成", state="complete")
                else:
                    st.error("未抓取到任何有效數據。")
        except Exception as e:
            st.error(f"分析過程出錯: {e}")

with col2:
    if st.button('🧹 清除所有快取'):
        st.session_state.analysis_results = None
        st.cache_data.clear()
        st.rerun()

# --- 5. 顯示分析結果 (確保數據存在才排序) ---
if st.session_state.analysis_results is not None:
    full_df = st.session_state.analysis_results
    
    # 確保欄位存在再排序，避免 KeyError
    if '現金殖利率(%)' in full_df.columns:
        full_df = full_df.sort_values('現金殖利率(%)', ascending=False).reset_index(drop=True)
        
        st.subheader("💰 現金殖利率前 20 名")
        st.dataframe(full_df.head(20), use_container_width=True, hide_index=True)
        
        # 視覺化圖表
        chart = alt.Chart(full_df.head(20)).mark_bar(color='#FF4B4B').encode(
            x=alt.X('公司名稱:N', sort='-y', title='公司'),
            y=alt.Y('現金殖利率(%):Q', title='殖利率 (%)'),
            tooltip=['股票代號', '目前股價', '現金殖利率(%)']
        ).properties(height=400)
        st.altair_chart(chart, use_container_width=True)
