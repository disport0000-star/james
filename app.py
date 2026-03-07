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
st.set_page_config(page_title="台股精選 100 強監控", layout="wide")
st.title("📈 台股市值前 100 強財務監控")

# 您更新後的 FinMind 金鑰
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNyAxNTowNToyNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMTExLjI1NS4xMTAuNDkifQ.FLkCVK6j0S6TfgAI-_hAhaa3i11pmwlntZZP2X1RiIs"

st.write(f"系統狀態：金鑰更新與防錯強化版 (最後檢查時間: {datetime.now().strftime('%H:%M:%S')})")

# --- 2. 核心抓取函數 ---
@st.cache_data(ttl=3600)
def get_all_stock_data(base_list):
    final_results = []
    # 調降並發數至 8，增加穩定性，避免觸發 FinMind 頻率限制 (429 Error)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_single_stock, s[0], s[1]) for s in base_list]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: final_results.append(res)
    return pd.DataFrame(final_results)

def fetch_single_stock(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    dl = DataLoader()
    dl.login_by_token(api_token=FINMIND_TOKEN) # 明確登入驗證
    
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        if curr_price == 0: return None

        # 配息計算
        div_history = stock.dividends
        if not div_history.empty:
            last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
            cash_div = round(last_year_divs.sum(), 2)
        else:
            cash_div = 0.0
            
        calc_yield = round((cash_div / curr_price * 100), 1) if cash_div > 0 else 0.0

        # EPS 處理 (Yahoo Finance)
        eps_q0, eps_q1, eps_q2 = 0.0, 0.0, 0.0
        q_fin = stock.quarterly_financials
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: eps_q1 = round(eps_series.iloc[1], 2)
            if len(eps_series) > 2: eps_q2 = round(eps_series.iloc[2], 2)
        else:
            eps_q0 = round(info.get('trailingEps', 0), 2)

        # 營收處理 (FinMind) - 加入例外捕捉防止 KeyError
        rev_m0, r_growth = "N/A", "N/A"
        try:
            df_rev = dl.taiwan_stock_month_revenue(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
            )
            if df_rev is not None and not df_rev.empty:
                df_rev = df_rev.sort_values('date', ascending=False)
                rev_m0 = f"{round(df_rev.iloc[0]['revenue'] / 1000):,.0f}"
                if len(df_rev) > 1:
                    r0, r1 = df_rev.iloc[0]['revenue'], df_rev.iloc[1]['revenue']
                    r_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else "0%"
        except: pass

        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '現金股利': cash_div,
            '最新季EPS': eps_q0, '上一季EPS': eps_q1,
            '最新一期營收(千元)': rev_m0, '與上月比較增減(%)': r_growth,
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '稅後淨利率(%)': round(info.get('profitMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except Exception: return None

# --- 3. 獲取名單與 Excel 轉換 ---
@st.cache_data(ttl=86400)
def get_top_100_list():
    try:
        dl = DataLoader()
        dl.login_by_token(api_token=FINMIND_TOKEN)
        df_info = dl.taiwan_stock_info()
        
        # 關鍵檢查：確保數據非空且包含必要欄位
        if df_info is None or df_info.empty:
            st.warning("⚠️ 無法從 FinMind 取得股票清單，請確認 Token 配額。")
            return []
            
        df_info = df_info[df_info['type'] == 'twse']
        return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(100).iterrows()]
    except Exception as e:
        st.error(f"❌ 獲取清單時發生錯誤: {e}")
        return []

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- 4. 介面主邏輯 ---
if st.button('🚀 啟動 100 強數據分析'):
    base_list = get_top_100_list()
    
    if not base_list:
        st.error("目前無法獲取股票名單，請稍後再試。")
    else:
        with st.status("🔍 正在抓取個股財務數據...", expanded=True) as status:
            full_df = get_all_stock_data(base_list)
            status.update(label="✅ 分析完成！", state="complete")
        
        if not full_df.empty:
            full_df = full_df.sort_values(by='現金殖利率(%)', ascending=False)
            
            # 下載按鈕
            st.download_button(
                label="📥 下載完整 100 強個股財報 Excel",
                data=to_excel(full_df),
                file_name=f"Taiwan_Top100_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # 顯示數據
            st.subheader("💰 現金殖利率前 20 名")
            display_df = full_df.head(20).reset_index(drop=True)
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            # 視覺化
            st.divider()
            st.subheader("📊 殖利率分佈視覺化")
            chart = alt.Chart(display_df).mark_bar(color='#FF4B4B').encode(
                x=alt.X('公司名稱:N', sort='-y', title='公司名稱'),
                y=alt.Y('現金殖利率(%):Q', title='現金殖利率 (%)'),
                tooltip=['公司名稱', '現金殖利率(%)', '目前股價']
            ).properties(height=400).interactive(bind_y=False)
            
            st.altair_chart(chart, use_container_width=True)
        else:
            st.error("分析結果為空，請確認 API 連線狀態。")

# 側邊欄
with st.sidebar:
    st.info("若出現 KeyError，通常是 API 配額用盡或伺服器超載。")
    if st.button('🧹 清除快取'):
        st.cache_data.clear()
        st.rerun()
