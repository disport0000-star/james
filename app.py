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

# 您提供的 FinMind Token (請確保此 Token 尚未過期)
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A"

st.write(f"系統狀態：語法與相容性修復版 (更新時間: {datetime.now().strftime('%H:%M:%S')})")

# --- 2. 核心抓取函數 ---
@st.cache_data(ttl=3600)
def get_all_stock_data(base_list):
    final_results = []
    # 限制 max_workers 以減少被 API 封鎖的風險
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_single_stock, s[0], s[1]) for s in base_list]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: final_results.append(res)
    return pd.DataFrame(final_results)

def fetch_single_stock(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    
    # 修正相容性：不使用 dl.login，直接賦值 token
    dl = DataLoader()
    try:
        dl.token = FINMIND_TOKEN
    except:
        pass
    
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        if curr_price == 0: return None

        # --- 配息數據 ---
        div_history = stock.dividends
        if not div_history.empty:
            last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
            cash_div = round(last_year_divs.sum(), 2)
        else:
            cash_div = 0.0
        
        calc_yield = round((cash_div / curr_price * 100), 1) if cash_div > 0 else 0.0

        # --- EPS 數據 ---
        eps_q0, eps_q1, eps_q2 = 0.0, 0.0, 0.0
        q_fin = stock.quarterly_financials
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: eps_q1 = round(eps_series.iloc[1], 2)
            if len(eps_series) > 2: eps_q2 = round(eps_series.iloc[2], 2)

        # --- 三期營收數據 ---
        rev_m0, rev_m1, rev_m2, r_growth = "", "", "", ""
        try:
            df_rev = dl.taiwan_stock_month_revenue(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
            )
            if df_rev is not None and not df_rev.empty:
                df_rev = df_rev.sort_values('date', ascending=False)
                rev_m0 = f"{round(df_rev.iloc[0]['revenue'] / 1000):,.0f}" 
                if len(df_rev) >= 2:
                    rev_m1 = f"{round(df_rev.iloc[1]['revenue'] / 1000):,.0f}" 
                    r0, r1 = df_rev.iloc[0]['revenue'], df_rev.iloc[1]['revenue']
                    r_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else ""
                if len(df_rev) >= 3:
                    rev_m2 = f"{round(df_rev.iloc[2]['revenue'] / 1000):,.0f}" 
        except:
            pass

        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '現金股利': cash_div,
            '最新季EPS': eps_q0, '上一季EPS': eps_q1, '上上一季EPS': eps_q2,
            '最新一期營收(千元)': rev_m0, 
            '上一期營收(千元)': rev_m1, 
            '上上一期營收(千元)': rev_m2,
            '與上月比較增減(%)': r_growth,
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except:
        return None

# --- 3. 名單獲取 (修正截圖中的名單獲取錯誤) ---
@st.cache_data(ttl=86400)
def get_top_100_list():
    try:
        dl = DataLoader()
        dl.token = FINMIND_TOKEN
        df_info = dl.taiwan_stock_info()
        # 增加防禦性檢查：若 API 回傳 None 則回傳空名單
        if df_info is None or df_info.empty:
            return []
        df_info = df_info[df_info['type'] == 'twse']
        return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(100).iterrows()]
    except:
        return []

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- 4. 介面邏輯 ---
if st.button('🚀 執行 100 強數據分析'):
    base_list = get_top_100_list()
    
    if not base_list:
        st.error("❌ 無法獲取股票名單。請點擊下方的『清除快取』後再試一次，或確認 FinMind Token 是否正確。")
        st.stop()

    with st.status("🔍 正在同步抓取財報數據...", expanded=True) as status:
        full_df = get_all_stock_data(base_list)
        status.update(label="✅ 分析完成！", state="complete")
    
    if not full_df.empty:
        full_df = full_df.sort_values(by='現金殖利率(%)', ascending=False)
        
        st.download_button(
            label="📥 下載 Excel 報表",
            data=to_excel(full_df),
            file_name=f"Taiwan_Top100_{datetime.now().strftime('%Y%m%d')}.xlsx"
        )
        
        st.subheader("💰 殖利率前 20 名與營收三期對比")
        display_df = full_df.head(20).reset_index(drop=True)
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        # --- 5. 視覺化圖表 (修正截圖中的 SyntaxError) ---
        st.divider()
        st.subheader("📊 殖利率視覺化圖表")
        
        display_df['現金殖利率(%)'] = pd.to_numeric(display_df['現金殖利率(%)'], errors='coerce').fillna(0)
        
        # 修正後的圖表代碼，確保鏈式調用完整且
