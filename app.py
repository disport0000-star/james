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

st.write(f"系統狀態：三大法人終極除錯版 (更新時間: {datetime.now().strftime('%H:%M:%S')})")

# --- 2. [優化修正] 獲取每日三大法人數據 ---
def get_institutional_investor_data():
    dl = DataLoader()
    # 這裡不呼叫 login_token 避免錯誤，直接進行資料抓取
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    
    try:
        # 使用 taiwan_market_daily 抓取大盤層級的法人統計，這在舊版 FinMind 也很穩定
        df = dl.taiwan_market_daily(start_date=start_date, end_date=end_date)
        
        if df is not None and not df.empty:
            # 取得最新一天的資料
            latest_date = df['date'].max()
            today_data = df[df['date'] == latest_date].copy()
            
            # 根據 FinMind 大盤資料結構整理數據 (通常包含外資、投信、自營商總計)
            # 將單位轉為「億」，原始單位通常為元
            summary_list = []
            
            mapping = {
                'Foreign_Investor_Buy': 'Foreign_Investor_Sell',
                'Investment_Trust_Buy': 'Investment_Trust_Sell',
                'Dealer_Self_Buy': 'Dealer_Self_Sell'
            }
            
            labels = {
                'Foreign_Investor': '外資',
                'Investment_Trust': '投信',
                'Dealer_Self': '自營商'
            }

            for prefix, label in labels.items():
                buy_col = f"{prefix}_Buy"
                sell_col = f"{prefix}_Sell"
                if buy_col in today_data.columns and sell_col in today_data.columns:
                    buy_val = today_data[buy_col].values[0]
                    sell_val = today_data[sell_col].values[0]
                    diff_val = buy_val - sell_val
                    summary_list.append({
                        '身分別': label,
                        '買進 (億)': round(buy_val / 100000000, 2),
                        '賣出 (億)': round(sell_val / 100000000, 2),
                        '買賣超 (億)': round(diff_val / 100000000, 2)
                    })
            
            if summary_list:
                return pd.DataFrame(summary_list), latest_date
        
        return None, "目前尚無當日交易數據，請稍後再試。"

    except Exception as e:
        return None, f"連線異常：{str(e)}"

# --- 顯示三大法人資訊區塊 ---
st.subheader("📊 每日三大法人買賣超資訊")
inst_df, data_info = get_institutional_investor_data()

if isinstance(inst_df, pd.DataFrame):
    st.markdown(f"📅 **數據日期**：`{data_info}`")
    
    # 數值美化：正數紅、負數綠
    def style_diff(val):
        color = '#FF4B4B' if val > 0 else '#00FF00' if val < 0 else 'white'
        return f'color: {color}; font-weight: bold;'

    st.table(inst_df.style.applymap(style_diff, subset=['買賣超 (億)']))
else:
    st.warning(f"⚠️ {data_info}")

st.divider()

# --- 3. 核心分析函數 (原有 100 強邏輯) ---
@st.cache_data(ttl=3600)
def get_all_stock_data(base_list):
    final_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_single_stock, s[0], s[1]) for s in base_list]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: final_results.append(res)
    return pd.DataFrame(final_results)

def fetch_single_stock(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        if curr_price == 0: return None
        
        div_history = stock.dividends
        cash_div = round(div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))].sum(), 2) if not div_history.empty else 0.0
        calc_yield = round((cash_div / curr_price * 100), 1) if cash_div > 0 else 0.0
        
        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '現金股利': cash_div,
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except: return None

# --- 4. 介面邏輯 ---
if st.button('🚀 執行 100 強數據分析'):
    dl = DataLoader()
    df_info = dl.taiwan_stock_info()
    base_list = [[row['stock_id'], row['stock_name']] for _, row in df_info[df_info['type']=='twse'].drop_duplicates('stock_id').head(100).iterrows()]
    
    with st.status("🔍 分析中...") as status:
        full_df = get_all_stock_data(base_list)
        status.update(label="✅ 分析完成", state="complete")
    
    if not full_df.empty:
        st.dataframe(full_df.sort_values('現金殖利率(%)', ascending=False), use_container_width=True, hide_index=True)

if st.button('🧹 清除快取'):
    st.cache_data.clear()
    st.rerun()
