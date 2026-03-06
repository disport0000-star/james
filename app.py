import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import io
import altair as alt

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股 100 強財務監控", layout="wide")
st.title("📈 台股市值前 100 強財務監控")

# 您的 FinMind 金鑰
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

# --- 2. 擷取三大法人盤後統計並製作表格 ---
def display_institutional_table():
    dl = DataLoader()
    try:
        # 抓取過去 10 天資料以確保包含最新結算日
        df = dl.taiwan_stock_institutional_investors(
            stock_id="", 
            start_date=(datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        )
        if df.empty:
            st.info("💡 目前尚未取得最新盤後法人統計數據。")
            return
        
        # 取得最新交易日數據
        latest_date = df['date'].max()
        df_latest = df[df['date'] == latest_date].copy()
        
        # 定義中文名稱對照
        name_map = {
            'Foreign_Investor': '外資及陸資',
            'Investment_Trust': '投信',
            'Dealer_self': '自營商(自行買賣)',
            'Dealer_Hedging': '自營商(避險)',
            'Foreign_Dealer_Self': '外資自營商'
        }
        
        df_latest['買進(億)'] = (df_latest['buy'] / 10**8).round(1)
        df_latest['賣出(億)'] = (df_latest['sell'] / 10**8).round(1)
        df_latest['買賣超(億)'] = df_latest['買進(億)'] - df_latest['賣出(億)']
        df_latest['法人項目'] = df_latest['name'].map(name_map)
        
        final_table = df_latest.dropna(subset=['法人項目'])
        final_table = final_table[['法人項目', '買進(億)', '賣出(億)', '買賣超(億)']]
        
        st.subheader(f"🏛️ 三大法人盤後買賣超統計表 ({latest_date})")
        
        def color_net(val):
            color = 'red' if val < 0 else 'green'
            return f'color: {color}; font-weight: bold'

        st.dataframe(
            final_table.style.map(color_net, subset=['買賣超(億)']),
            use_container_width=True,
            hide_index=True
        )
    except Exception:
        st.info("💡 盤後數據更新中，請稍候。")

# 顯示置頂表格
display_institutional_table()
st.divider()

# --- 3. 核心個股抓取函數 ---
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
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        if curr_price == 0: return None

        div_history = stock.dividends
        if not div_history.empty:
            last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
            cash_div = round(last_year_divs.sum(), 2)
        else:
            cash_div = 0.0
        calc_yield = round((cash_div / curr_price * 100), 1) if cash_div > 0 else 0.0

        eps_q0, eps_q1, eps_q2 = 0.0, 0.0, 0.0
        q_fin = stock.quarterly_financials
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: eps_q1 = round(eps_series.iloc[1], 2)
            if len(eps_series) > 2: eps_q2 = round(eps_series.iloc[2], 2)

        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '現金股利': cash_div,
            '最新季EPS': eps_q0, '上一季EPS': eps_q1, '上上一季EPS': eps_q2,
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except Exception: return None

# --- 4. 名單與 Excel 邏輯 ---
@st.cache_data(ttl=86400)
def get_top_100_list():
    dl = DataLoader()
    # 修正：移除 dl.login，改直接去重
    df_info = dl.taiwan_stock_info()
    df_info = df_info[df_info['type'] == 'twse'].drop_duplicates(subset=['stock_id'])
    return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(100).iterrows()]

def to_excel(df):
    output = io.BytesIO()
    # 修正：使用 openpyxl 避免 xlsxwriter 缺失錯誤
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- 5. 介面操作區 ---
if st.button('🚀 執行 100 強全方位掃描'):
    base_list = get_top_100_list()
    with st.status("🔍 正在分析台股市值前 100 大個股財報...", expanded=True) as status:
        full_df = get_all_stock_data(base_list)
        status.update(label="✅ 分析完成！", state="complete")
    
    if not full_df.empty:
        # 修正：去重確保一零四不重複出現
        full_df = full_df.drop_duplicates(subset=['股票代號']).sort_values(by='現金殖利率(%)', ascending=False)
        
        file_timestamp = datetime.now().strftime('%Y%m%d')
        # 修正：確保檔名字串正確閉合
        st.download_button(
            label="📥 下載完整 100 強個股財報 Excel",
            data=to_excel(full_df),
            file_name=f"Taiwan_Top100_{file_timestamp}.xlsx",
            mime="application/
