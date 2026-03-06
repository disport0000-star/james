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

st.write(f"系統狀態：三大法人功能修正版 (更新時間: {datetime.now().strftime('%H:%M:%S')})")

# --- 2. [修正] 獲取每日三大法人數據 ---
def get_institutional_investor_data():
    dl = DataLoader()
    # 這裡不使用 login_token 避免 Attribute Error
    
    # 嘗試抓取最近交易日
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    try:
        # 改用較通用的法人統計介面
        # 如果 summary 方法不存在，我們抓取統計資訊
        df = dl.taiwan_stock_institutional_investors_summary(
            start_date=start_date, 
            end_date=end_date
        )
        
        if df is None or df.empty:
            # 備援方案：若彙總介面失效，告知使用者
            return None, "目前 API 未回傳數據，可能為非交易日或套件版本限制。"

        # 取得最新日期
        latest_date = df['date'].max()
        df = df[df['date'] == latest_date].copy()
        
        # 轉換單位：原始數據通常是元，轉為「億」
        for col in ['buy', 'sell', 'diff']:
            df[col] = (df[col] / 100000000).round(2)
            
        # 重新命名與排序，對應圖片需求
        df = df.rename(columns={
            'name': '身分別',
            'buy': '買進 (億)',
            'sell': '賣出 (億)',
            'diff': '買賣超 (億)'
        })
        return df[['身分別', '買進 (億)', '賣出 (億)', '買賣超 (億)']], latest_date

    except Exception as e:
        # 如果還是報錯，可能是方法徹底不同，改用基礎抓取嘗試
        try:
            # 這是另一個常見的 FinMind API 命名
            df = dl.taiwan_market_daily(start_date=start_date, end_date=end_date)
            # 這裡僅作範例，實際若要法人需特定 API
            return None, f"API 方法不相容，請嘗試更新 FinMind 套件: pip install --upgrade FinMind"
        except:
            return None, f"連線異常: {str(e)}"

# --- 顯示三大法人資訊區塊 ---
st.subheader("📊 每日三大法人買賣超資訊")
inst_df, data_info = get_institutional_investor_data()

if isinstance(inst_df, pd.DataFrame):
    st.info(f"📅 數據日期：{data_info}")
    
    def color_diff(val):
        if isinstance(val, (int, float)):
            if val > 0: return 'color: #FF4B4B; font-weight: bold;' # 紅色
            if val < 0: return 'color: #00FF00; font-weight: bold;' # 綠色
        return ''
    
    # 呈現表格
    st.table(inst_df.style.applymap(color_diff, subset=['買賣超 (億)']))
else:
    st.warning(f"⚠️ {data_info}")

st.divider()

# --- 3. 核心抓取函數 (維持原狀) ---
@st.cache_data(ttl=3600)
def get_all_stock_data(base_list):
    final_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(fetch_single_stock, s[0], s[1]) for s in base_list]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: final_results.append(res)
    return pd.DataFrame(final_results)

def fetch_single_stock(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    dl = DataLoader()
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        if curr_price == 0: return None
        
        # 配息
        div_history = stock.dividends
        cash_div = round(div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))].sum(), 2) if not div_history.empty else 0.0
        calc_yield = round((cash_div / curr_price * 100), 1) if cash_div > 0 else 0.0
        
        # EPS
        eps_q0 = 0.0
        q_fin = stock.quarterly_financials
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_q0 = round(q_fin.loc['Diluted EPS'].dropna().iloc[0], 2)
        else:
            eps_q0 = round(info.get('trailingEps', 0), 2)

        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '現金股利': cash_div,
            '最新季EPS': eps_q0, '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except: return None

# --- 4. 名單獲取 ---
@st.cache_data(ttl=86400)
def get_top_100_list():
    dl = DataLoader()
    df_info = dl.taiwan_stock_info()
    df_info = df_info[df_info['type'] == 'twse'].drop_duplicates(subset=['stock_id'])
    return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(100).iterrows()]

# --- 5. 介面執行 ---
if st.button('🚀 執行 100 強數據分析'):
    base_list = get_top_100_list()
    with st.status("🔍 分析中...", expanded=True) as status:
        full_df = get_all_stock_data(base_list)
        status.update(label="✅ 完成！", state="complete")
    
    if not full_df.empty:
        st.dataframe(full_df.sort_values(by='現金殖利率(%)', ascending=False), use_container_width=True)

if st.button('🧹 清除快取'):
    st.cache_data.clear()
    st.rerun()
