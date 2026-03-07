import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import io
import altair as alt

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股 100 強監控 V3", layout="wide")
st.title("📈 台股市值前 100 強財務監控 (V3 三期營收強化版)")

# FinMind 金鑰
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

st.info(f"V3 更新重點：新增連續三期營收對比、優化效能、動態座標軸圖表。 (系統時間: {datetime.now().strftime('%Y-%m-%d %H:%M')})")

# --- 2. 核心抓取函數 ---
def fetch_single_stock(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    dl = DataLoader()
    dl.login(token=FINMIND_TOKEN)
    
    try:
        stock = yf.Ticker(full_sid)
        
        # 快速抓取基本股價資訊 (yfinance fast_info 較快)
        f_info = stock.fast_info
        curr_price = f_info.get('last_price') or 0
        if curr_price == 0: return None

        # 殖利率計算 (過去 365 天配息總和)
        div_history = stock.dividends
        cash_div = 0.0
        if not div_history.empty:
            last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
            cash_div = round(last_year_divs.sum(), 2)
        
        calc_yield = round((cash_div / curr_price * 100), 2) if curr_price > 0 else 0.0

        # EPS 資料 (抓取最新兩季)
        eps_q0, eps_q1 = 0.0, 0.0
        q_fin = stock.quarterly_financials
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: eps_q1 = round(eps_series.iloc[1], 2)

        # --- V3 營收三期邏輯 ---
        rev_m0, rev_m1, rev_m2, r_growth = "N/A", "N/A", "N/A", "N/A"
        try:
            # 抓取 120 天數據以確保包含三期月營收
            df_rev = dl.taiwan_stock_month_revenue(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
            )
            if not df_rev.empty:
                df_rev = df_rev.sort_values('date', ascending=False)
                
                # 依序填入三期數據 (單位：千元)
                if len(df_rev) >= 1:
                    r0 = df_rev.iloc[0]['revenue']
                    rev_m0 = f"{round(r0 / 1000):,.0f}"
                if len(df_rev) >= 2:
                    r1 = df_rev.iloc[1]['revenue']
                    rev_m1 = f"{round(r1 / 1000):,.0f}"
                    # 計算最新月增率 (MOM)
                    r_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else "0%"
                if len(df_rev) >= 3:
                    r2 = df_rev.iloc[2]['revenue']
                    rev_m2 = f"{round(r2 / 1000):,.0f}"
        except: pass

        # 獲取毛利資訊 (info 請求較慢，放最後)
        info = stock.info
        
        return {
            '股票代號': clean_id, 
            '公司名稱': sname, 
            '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, 
            '現金股利': cash_div,
            '最新季EPS': eps_q0, 
            '上一季EPS': eps_q1,
            '最新營收(千元)': rev_m0, 
            '上月營收(千元)': rev_m1, 
            '上上月營收(千元)': rev_m2,
            '營收月增率': r_growth,
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except: return None

@st.cache_data(ttl=3600)
def get_all_stock_data_v3(base_list):
    final_results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    total = len(base_list)
    # 並行處理提升效率
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_stock = {executor.submit(fetch_single_stock, s[0], s[1]): s for s in base_list}
        
        for i, future in enumerate(concurrent.futures.as_completed(future_to_stock)):
            res = future.result()
            if res: final_results.append(res)
            
            # 更新 Streamlit 進度條
            current_progress = (i + 1) / total
            progress_bar.progress(current_progress)
            status_text.text(f"🚀 進度: {i+1}/{total} | 正在分析: {future_to_stock[future][1]}")
            
    progress_bar.empty()
    status_text.empty()
    return pd.DataFrame(final_results)

# --- 3. 名單抓取與 Excel 轉換 ---
@st.cache_data(ttl=86400)
def get_top_100_list():
    dl = DataLoader()
    dl.login(token=FINMIND_TOKEN)
    df_info = dl.taiwan_stock_info()
    df_info = df_info[df_info['type'] == 'twse'].drop_duplicates(subset=['stock_id'])
    # 目前預設取台股上市前 100 筆
    return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(100).iterrows()]

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Stock_Data')
    return output.getvalue()

# --- 4. Streamlit 介面渲染 ---
col_run, col_clear = st.columns([1, 4])
with col_run:
    run_btn = st.button('🚀 執行 V3 分析', use_container_width=True)
with col_clear:
    if st.button('🧹 清除快取', use_container_width=True):
        st.cache_data.clear()
        st.rerun()

if run_btn:
    base_list = get_top_100_list()
    
    with st.status("🔍 正在進行深度財務分析...", expanded=True) as status:
        full_df = get_all_stock_data_v3(base_list)
        status.update(label="✅ 分析完成！", state="complete")
    
    if not full_df.empty:
        # 去重與排序
        full_df = full_df.drop_duplicates(subset=['股票代號'])
        full_df = full_df.sort_values(by='現金殖利率(%)', ascending=False)
        
        # 下載按鈕
        st.download_button(
            label="📥 下載完整 V3 Excel 報表",
            data=to_excel(full_df),
            file_name=f"Taiwan_Stock_V3_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # 數據預覽
        st.subheader("💰 財務指標概覽 (殖利率前 20 名)")
        st.dataframe(full_df.head(20), use_container_width=True, hide_index=True)
        
        # 視覺化圖表
        st.divider()
        st.subheader("📊 現金殖利率分佈 (前 20 名)")
        # 動態調整 Y 軸高度
        max_y = full_df['現金殖利率(%)'].head(20).max() + 2
        chart = alt.Chart(full_df.head(20)).mark_bar(
            cornerRadiusTopLeft=5,
            cornerRadiusTopRight=5,
            color='#17a2b8'
        ).encode(
            x=alt.X('公司名稱:N', sort='-y', title='公司'),
            y=alt.Y('現金殖利率(%):Q', scale=alt.Scale(domain=[0, max_y])),
            tooltip=['股票代號', '公司名稱', '現金殖利率(%)', '最新營收(千元)', '營收月增率']
        ).properties(height=450).interactive(bind_y=False)
        
        st.altair_chart(chart, use_container_width=True)
    else:
        st.error("分析結果為空，請確認 API 權限或網路狀態。")
