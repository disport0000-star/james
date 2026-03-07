import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import io
import altair as alt
import time  # 必須引入 time 來做延遲

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 100 強監控", layout="wide")
st.title("📈 台股市值前 100 強財務監控")

# 您的 FinMind 金鑰
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNyAxNTowNToyNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMTExLjI1NS4xMTAuNDkifQ.FLkCVK6j0S6TfgAI-_hAhaa3i11pmwlntZZP2X1RiIs"

st.write(f"系統狀態：修正 Excel 縮排錯誤版 (更新時間: {datetime.now().strftime('%H:%M:%S')})")

# --- 2. 核心抓取函數 ---
@st.cache_data(ttl=3600)
def get_all_stock_data_v3(base_list):
    final_results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch_single_stock, s[0], s[1]) for s in base_list]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: 
                final_results.append(res)
    return pd.DataFrame(final_results)

def fetch_single_stock(sid, sname):
    time.sleep(0.5) 
    
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    
    dl = DataLoader()
    dl.login_by_token(api_token=FINMIND_TOKEN)
    
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        
        if curr_price == 0: 
            return None

        # 配息計算
        div_history = stock.dividends
        if not div_history.empty:
            last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
            cash_div = round(last_year_divs.sum(), 2)
        else:
            cash_div = 0.0
            
        if cash_div > 0:
            calc_yield = round((cash_div / curr_price * 100), 1)
        else:
            calc_yield = 0.0

        # EPS 處理 (Yahoo Finance)
        eps_q0 = 0.0
        eps_q1 = 0.0
        eps_q2 = 0.0
        q_fin = stock.quarterly_financials
        
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: 
                eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: 
                eps_q1 = round(eps_series.iloc[1], 2)
            if len(eps_series) > 2: 
                eps_q2 = round(eps_series.iloc[2], 2)
        else:
            eps_q0 = round(info.get('trailingEps', 0), 2)

        # 營收處理 (FinMind)
        rev_m0 = "N/A"
        rev_m1 = "N/A"
        rev_m2 = "N/A"
        r_growth = "N/A"
        
        try:
            df_rev = dl.taiwan_stock_month_revenue(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
            )
            if df_rev is not None and not df_rev.empty:
                df_rev = df_rev.sort_values('date', ascending=False)
                if len(df_rev) > 0: 
                    rev_m0 = f"{round(df_rev.iloc[0]['revenue'] / 1000):,.0f}"
                if len(df_rev) > 1:
                    r0 = df_rev.iloc[0]['revenue']
                    r1 = df_rev.iloc[1]['revenue']
                    rev_m1 = f"{round(r1 / 1000):,.0f}"
                    if r1 != 0:
                        r_growth = f"{round(((r0-r1)/r1)*100, 1)}%"
                    else:
                        r_growth = "0%"
                if len(df_rev) > 2:
                    rev_m2 = f"{round(df_rev.iloc[2]['revenue'] / 1000):,.0f}"
        except Exception:
            pass 

        # 整理最終輸出的欄位順序
        return {
            '股票代號': clean_id, 
            '公司名稱': sname, 
            '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, 
            '現金股利': cash_div,
            '最新季EPS': eps_q0, 
            '上一季EPS': eps_q1, 
            '上上一季EPS': eps_q2,
            '最新一期營收(千元)': rev_m0, 
            '上一期營收(千元)': rev_m1, 
            '上上一期營收(千元)': rev_m2, 
            '與上月比較增減(%)': r_growth,
            '毛利率(%)': round((info.get('grossMargins') or 0) * 100, 1),
            '稅後淨利率(%)': round((info.get('profitMargins') or 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
        
    except Exception as e:
        return None

# --- 3. 獲取名單與 Excel 轉換 ---
@st.cache_data(ttl=86400)
def get_top_100_list_v3():
    try:
        dl = DataLoader()
        dl.login_by_token(api_token=FINMIND_TOKEN)
        df_info = dl.taiwan_stock_info()
        
        if df_info is None or df_info.empty:
            st.warning("⚠️ 無法從 FinMind 取得股票清單，請確認 Token 配額。")
            return []
            
        df_info = df_info[df_info['type'] == 'twse']
        df_info = df_info.drop_duplicates(subset=['stock_id'])
        
        return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(100).iterrows()]
    except Exception as e:
        st.error(f"❌ 獲取清單時發生錯誤: {e}")
        return []

# 這裡就是報錯的地方，已經為您嚴格對齊了！
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- 4. 介面主邏輯 ---
if st.button('🚀 啟動 100 強數據分析 (請耐心等待約1分鐘)'):
    base_list = get_top_100_list_v3()
    
    if not base_list:
        st.error("目前無法獲取股票名單，請稍後再試。")
    else:
        with st.status("🔍 正在緩慢抓取個股財務數據，避免被伺服器封鎖...", expanded=True) as status:
            full_df = get_all_stock_data_v3(base_list)
            status.update(label="✅ 分析完成！", state="complete")
        
        if not full_df.empty:
            full_df = full_df.drop_duplicates(subset=['股票代號'])
            full_df = full_df.sort_values(by='現金殖利率(%)', ascending=False)
            
            excel_df = full_df.head(100)
            
            if len(full_df) >= 90:
                st.success(f"✅ 太棒了！本次成功分析並獲取 {len(full_df)} 檔股票資料！")
            else:
                st.warning(f"⚠️ 伺服器稍稍不給力，本次成功獲取 {len(full_df)} 檔股票資料。如果您希望抓滿 100 檔，可以稍後再試。")
            
            st.download_button(
                label=f"📥 下載完整前 {len(excel_df)} 強個股財報 Excel",
                data=to_excel(excel_df),
                file_name=f"Taiwan_Top100_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            st.subheader("💰 現金殖利率前 40 名")
            display_df = full_df.head(40).reset_index(drop=True)
            st.dataframe(display_df, use_container_width=True, hide_index=True)
            
            st.divider()
            st.subheader("📊 前 40 名殖利率分佈視覺化")
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
    if st.button('🧹 清除快取並重啟'):
        st.cache_data.clear()
        st.rerun()
