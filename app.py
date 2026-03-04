import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import time
import io

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 100 強監控", layout="wide")
st.title("📈 台股市值前 100 強財務監控")

# 已填入您的 FinMind 金鑰
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

st.write(f"系統狀態：穩定除錯版 (更新時間: {datetime.now().strftime('%H:%M:%S')})")

# --- 2. 核心抓取函數 ---
@st.cache_data(ttl=3600)  # 資料快取 1 小時
def get_all_stock_data(base_list):
    final_results = []
    # 使用線程池加速
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(fetch_single_stock, s[0], s[1]) for s in base_list]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: final_results.append(res)
    return pd.DataFrame(final_results)

def fetch_single_stock(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    # 修正：DataLoader 不使用 login，直接初始化或在需要時帶入 token
    dl = DataLoader()
    
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        if curr_price == 0: return None

        # 配息資料 (修正時區比較問題)
        div_history = stock.dividends
        if not div_history.empty:
            last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
            cash_div = round(last_year_divs.sum(), 2)
        else:
            cash_div = 0.0
            
        stock_div = info.get('stockDividendValue', 0.0) or 0.0
        calc_yield = round((cash_div / curr_price * 100), 1) if cash_div > 0 else 0.0

        # EPS 資料
        eps_q0, eps_q1, eps_q2 = 0.0, 0.0, 0.0
        q_fin = stock.quarterly_financials
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: eps_q1 = round(eps_series.iloc[1], 2)
            if len(eps_series) > 2: eps_q2 = round(eps_series.iloc[2], 2)
        else:
            eps_q0 = round(info.get('trailingEps', 0), 2)

        # 營收抓取 (使用 token 提高穩定性)
        rev_m0, r_growth = "", ""
        try:
            df_rev = dl.taiwan_stock_month_revenue(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
            )
            if not df_rev.empty:
                df_rev = df_rev.sort_values('date', ascending=False)
                rev_m0 = f"{round(df_rev.iloc[0]['revenue'] / 1000):,.0f}"
                r0, r1 = df_rev.iloc[0]['revenue'], df_rev.iloc[1]['revenue']
                r_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else ""
        except: pass

        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '現金股利': cash_div, '股票股利': stock_div,
            '最新季EPS': eps_q0, '上一季EPS': eps_q1, '上上一季EPS': eps_q2,
            '最新一期營收(千元)': rev_m0, '與上月比較增減(%)': r_growth,
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '營業利益率(%)': round(info.get('operatingMargins', 0) * 100, 1),
            '稅後淨利率(%)': round(info.get('profitMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except: return None

# --- 3. 獲取名單與 Excel 轉換 ---
@st.cache_data(ttl=86400)
def get_top_100_list():
    # 修正：DataLoader 移除 login 呼叫
    dl = DataLoader()
    df_info = dl.taiwan_stock_info()
    df_info = df_info[df_info['type'] == 'twse']
    # 根據代號排序或直接取前 100
    return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(100).iterrows()]

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- 4. 介面主邏輯 ---
# 使用 st.session_state 確保資料顯示更穩定
if st.button('🚀 執行 100 強數據分析'):
    base_list = get_top_100_list()
    
    with st.status("🔍 正在掃描台股市值前 100 大個股財報...", expanded=True) as status:
        full_df = get_all_stock_data(base_list)
        status.update(label="✅ 100 強數據分析完成！", state="complete")
    
    if not full_df.empty:
        # 排序
        full_df = full_df.sort_values(by='現金殖利率(%)', ascending=False)
        
        # 下載按鈕
        st.download_button(
            label="📥 下載完整 100 強個股財報 Excel",
            data=to_excel(full_df),
            file_name=f"Taiwan_Top100_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # 顯示前 20
        st.subheader("💰 現金殖利率前 20 名名單")
        st.dataframe(full_df.head(20), use_container_width=True, hide_index=True)
        
        # 圖表
        st.divider()
        st.subheader("📊 前 20 名殖利率視覺化")
        st.bar_chart(full_df.head(20).set_index('公司名稱')[['現金殖利率(%)']])
    else:
        st.error("無法取得數據，請確認您的網路環境或稍後再試。")

if st.button('🧹 清除快取重整'):
    st.cache_data.clear()
    st.rerun()
