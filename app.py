import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import io
import altair as alt
import time

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 100 強監控 V2", layout="wide")
st.title("🚀 台股市值前 100 強財務監控 (V2 優化版)")

# FinMind 金鑰
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

st.info(f"V2 版本說明：優化抓取效能、加入動態進度條、修正營收日期邏輯 (更新時間: {datetime.now().strftime('%H:%M:%S')})")

# --- 2. 核心抓取函數 ---
def fetch_single_stock(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    dl = DataLoader()
    dl.login(token=FINMIND_TOKEN) # V2: 顯式登入確保權限
    
    try:
        stock = yf.Ticker(full_sid)
        
        # V2 優化：優先抓取 fast_info 減少等待時間
        f_info = stock.fast_info
        curr_price = f_info.get('last_price') or 0
        if curr_price == 0: return None

        # V2 優化：更穩定的殖利率抓取
        # 先嘗試從歷史配息計算過去 365 天總和
        div_history = stock.dividends
        if not div_history.empty:
            last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
            cash_div = round(last_year_divs.sum(), 2)
        else:
            cash_div = 0.0
        
        calc_yield = round((cash_div / curr_price * 100), 2) if cash_div > 0 else 0.0

        # EPS 邏輯 (維持 V1 穩定部分)
        eps_q0, eps_q1 = 0.0, 0.0
        q_fin = stock.quarterly_financials
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: eps_q1 = round(eps_series.iloc[1], 2)
        
        # V2 優化：營收日期拉長至 90 天，確保跨月數據完整
        rev_m0, r_growth = "N/A", "N/A"
        try:
            df_rev = dl.taiwan_stock_month_revenue(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            )
            if not df_rev.empty and len(df_rev) >= 2:
                df_rev = df_rev.sort_values('date', ascending=False)
                r0 = df_rev.iloc[0]['revenue']
                r1 = df_rev.iloc[1]['revenue']
                rev_m0 = f"{round(r0 / 1000):,.0f}"
                r_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else "0%"
        except: pass

        # 獲取毛利 (僅在必要時調用 info)
        info = stock.info
        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '現金股利': cash_div,
            '最新季EPS': eps_q0, '上一季EPS': eps_q1,
            '最新營收(千元)': rev_m0, '營收月增率': r_growth,
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except: return None

@st.cache_data(ttl=3600)
def get_all_stock_data_v2(base_list):
    final_results = []
    progress_bar = st.progress(0) # V2: 加入進度條
    status_text = st.empty()
    
    total = len(base_list)
    
    # 增加 max_workers 以提升速度
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_stock = {executor.submit(fetch_single_stock, s[0], s[1]): s for s in base_list}
        
        for i, future in enumerate(concurrent.futures.as_completed(future_to_stock)):
            res = future.result()
            if res: final_results.append(res)
            
            # 更新進度
            current_progress = (i + 1) / total
            progress_bar.progress(current_progress)
            status_text.text(f"🚀 已完成: {i+1} / {total} (正在分析: {future_to_stock[future][1]})")
            
    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(final_results)

# --- 3. 獲取名單與 Excel 轉換 ---
@st.cache_data(ttl=86400)
def get_top_100_list():
    dl = DataLoader()
    dl.login(token=FINMIND_TOKEN)
    df_info = dl.taiwan_stock_info()
    df_info = df_info[df_info['type'] == 'twse'].drop_duplicates(subset=['stock_id'])
    # 注意：這裡若能加入市值排序會更精準，目前維持 V1 的前 100 筆邏輯以確保穩定性
    return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(100).iterrows()]

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- 4. 介面主邏輯 ---
col1, col2 = st.columns([1, 4])
with col1:
    run_btn = st.button('🚀 執行 V2 深度分析', use_container_width=True)
with col2:
    clear_btn = st.button('🧹 清除快取', use_container_width=True)

if clear_btn:
    st.cache_data.clear()
    st.rerun()

if run_btn:
    base_list = get_top_100_list()
    
    with st.status("🔍 V2 引擎啟動：正在進行並行數據分析...", expanded=True) as status:
        full_df = get_all_stock_data_v2(base_list)
        status.update(label="✅ 分析完成！", state="complete")
    
    if not full_df.empty:
        full_df = full_df.drop_duplicates(subset=['股票代號']).sort_values(by='現金殖利率(%)', ascending=False)
        
        # 下載區
        st.download_button(
            label="📥 下載完整 Excel 報表",
            data=to_excel(full_df),
            file_name=f"TW_Top100_V2_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # 顯示區
        st.subheader("💰 現金殖利率前 20 強")
        st.dataframe(full_df.head(20), use_container_width=True, hide_index=True)
        
        # V2 圖表：動態 Y 軸
        st.divider()
        st.subheader("📊 殖利率視覺化 (動態座標軸)")
        
        max_y = full_df['現金殖利率(%)'].head(20).max() + 1
        chart = alt.Chart(full_df.head(20)).mark_bar(
            cornerRadiusTopLeft=3,
            cornerRadiusTopRight=3,
            color='#1f77b4'
        ).encode(
            x=alt.X('公司名稱:N', sort='-y', title='公司名稱'),
            y=alt.Y('現金殖利率(%):Q', scale=alt.Scale(domain=[0, max_y]), title='現金殖利率 (%)'),
            tooltip=['股票代號', '公司名稱', '現金殖利率(%)', '目前股價']
        ).properties(height=450).interactive(bind_y=False)
        
        st.altair_chart(chart, use_container_width=True)
    else:
        st.error("分析結果為空，請檢查網路或 API Token 是否有效。")
