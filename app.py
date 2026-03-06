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

# --- 2. [根據 API 文件修正] 獲取全市場三大法人數據 ---
def get_total_market_investors():
    dl = DataLoader()
    # 避開 login_token 可能的錯誤，改用通用 API 調用方式
    start_str = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    
    try:
        # 根據您提供的文件截圖，使用正確的 dataset
        df = dl.taiwan_stock_total_institutional_investors(
            start_date=start_str
        )
        
        if df is not None and not df.empty:
            # 取得最新一天的日期
            latest_date = df['date'].max()
            current_df = df[df['date'] == latest_date].copy()
            
            # 轉換單位為「億元」(原始單位通常為元)
            def to_billion(val): return round(val / 100000000, 2)
            
            current_df['買進(億)'] = current_df['buy'].apply(to_billion)
            current_df['賣出(億)'] = current_df['sell'].apply(to_billion)
            current_df['買賣超(億)'] = current_df['diff'].apply(to_billion)
            
            # 將英文身分別對應至中文
            name_map = {
                'Foreign_Investor': '外資',
                'Investment_Trust': '投信',
                'Dealer': '自營商(合計)',
                'Dealer_Self': '自營商自行買賣',
                'Dealer_Hedging': '自營商避險'
            }
            current_df['身分別'] = current_df['name'].map(name_map).fillna(current_df['name'])
            
            return current_df[['身分別', '買進(億)', '賣出(億)', '買賣超(億)']], latest_date
    except Exception as e:
        return None, f"API 調用失敗，建議檢查連線。{e}"
    return None, "查無數據"

# 顯示三大法人資訊區塊 (置頂)
st.subheader("📊 每日三大法人買賣超資訊 (全市場統計)")
inst_df, data_date = get_total_market_investors()

if isinstance(inst_df, pd.DataFrame):
    st.info(f"📅 數據日期：{data_date} (單位：億元)")
    def color_picker(val):
        color = '#FF4B4B' if val > 0 else '#00FF00' if val < 0 else 'white'
        return f'color: {color}; font-weight: bold'
    
    st.table(inst_df.style.format({'買進(億)': '{:,.2f}', '賣出(億)': '{:,.2f}', '買賣超(億)': '{:,.2f}'})
             .applymap(color_picker, subset=['買賣超(億)']))
else:
    st.warning(data_date)

st.divider()

# --- 3. 核心數據抓取 (個股殖利率) ---
def fetch_stock_fundamental(sid, sname):
    try:
        stock = yf.Ticker(f"{sid}.TW")
        # 嘗試取得最新收盤價
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice')
        if not curr_price:
            hist = stock.history(period="1d")
            if not hist.empty: curr_price = hist['Close'].iloc[-1]
        
        if not curr_price: return None

        # 殖利率計算 (滾動一年)
        divs = stock.dividends
        last_year = datetime.now() - timedelta(days=365)
        cash_div = divs[divs.index.tz_localize(None) >= last_year].sum() if not divs.empty else 0
        
        return {
            '股票代號': sid, '公司名稱': sname, '目前股價': round(curr_price, 2),
            '現金殖利率(%)': round((cash_div / curr_price * 100), 2) if cash_div > 0 else 0.0,
            '現金股利': round(cash_div, 2)
        }
    except: return None

# --- 4. 介面與 Session State (修復 KeyError 與按鈕消失問題) ---
if 'results' not in st.session_state:
    st.session_state.results = None

c1, c2 = st.columns(2)
with c1:
    if st.button('🚀 執行 100 強數據分析', use_container_width=True):
        dl = DataLoader()
        try:
            df_info = dl.taiwan_stock_info()
            # 取得台股上市前 100 支名單
            base_list = [[row['stock_id'], row['stock_name']] for _, row in df_info[df_info['type']=='twse'].drop_duplicates('stock_id').head(100).iterrows()]
            
            with st.status("🔍 分析進行中...", expanded=True) as status:
                res_list = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    futures = [executor.submit(fetch_stock_fundamental, s[0], s[1]) for s in base_list]
                    for f in concurrent.futures.as_completed(futures):
                        r = f.result()
                        if r: res_list.append(r)
                
                if res_list:
                    st.session_state.results = pd.DataFrame(res_list)
                    status.update(label="✅ 分析完成", state="complete")
                else:
                    st.error("無法抓取數據。")
        except Exception as e:
            st.error(f"分析錯誤: {e}")

with c2:
    if st.button('🧹 清除快取', use_container_width=True):
        st.session_state.results = None
        st.cache_data.clear()
        st.rerun()

# --- 5. 顯示結果 (包含視覺化) ---
if st.session_state.results is not None:
    full_df = st.session_state.results
    if not full_df.empty and '現金殖利率(%)' in full_df.columns:
        full_df = full_df.sort_values('現金殖利率(%)', ascending=False).reset_index(drop=True)
        
        st.subheader("💰 現金殖利率前 20 名")
        st.dataframe(full_df.head(20), use_container_width=True, hide_index=True)
        
        chart = alt.Chart(full_df.head(20)).mark_bar(color='#FF4B4B').encode(
            x=alt.X('公司名稱:N', sort='-y', title='公司名稱'),
            y=alt.Y('現金殖利率(%):Q', title='殖利率 (%)'),
            tooltip=['股票代號', '公司名稱', '現金殖利率(%)']
        ).properties(height=400)
        st.altair_chart(chart, use_container_width=True)
