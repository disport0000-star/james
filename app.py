import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import io
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import altair as alt

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 100 強監控 V2", layout="wide")
st.title("📈 台股市值前 100 強財務監控 V2")

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

# --- 側邊欄設定 (功能 2: 篩選器) ---
st.sidebar.header("⚙️ 篩選設定")
min_yield = st.sidebar.slider("最低現金殖利率門檻 (%)", 0.0, 15.0, 5.0, 0.5)

# --- 2. 獲取數據函數 ---

# [優化] 抓取個股外資買超前 10 名 (功能 1)
def get_top_foreign_buys():
    url = "https://api.finmindtrade.com/api/v4/data"
    start_str = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    params = {
        "dataset": "TaiwanStockInstitutionalInvestors",
        "start_date": start_str,
        "token": FINMIND_TOKEN
    }
    try:
        resp = requests.get(url, params=params)
        df = pd.DataFrame(resp.json()["data"])
        latest_date = df['date'].max()
        # 篩選外資且最新日期的數據
        current = df[(df['date'] == latest_date) & (df['name'] == 'Foreign_Investor')].copy()
        # 計算買賣超金額 (單位：億)，通常 diff 為股數，這裡做降序排名前 10
        current = current.sort_values('buy', ascending=False).head(10)
        current['買進股數'] = current['buy']
        return current[['stock_id', '買進股數']], latest_date
    except:
        return None, None

def fetch_stock_info(sid, sname):
    try:
        stock = yf.Ticker(f"{sid}.TW")
        hist = stock.history(period="5d")
        if hist.empty: return None
        curr_price = hist['Close'].iloc[-1]
        divs = stock.dividends
        last_year = datetime.now() - timedelta(days=365)
        cash_div = divs[divs.index.tz_localize(None) >= last_year].sum() if not divs.empty else 0
        return {
            '股票代號': sid, '公司名稱': sname, '目前股價': round(curr_price, 2),
            '現金殖利率(%)': round((cash_div / curr_price * 100), 2) if cash_div > 0 else 0.0,
            '現金股利': round(cash_div, 2)
        }
    except: return None

# --- 3. 畫面佈局 ---

# 第一部分：外資買超排行
st.subheader("🏆 當日外資買進力道前 10 名")
foreign_df, f_date = get_top_foreign_buys()
if foreign_df is not None:
    st.caption(f"數據日期：{f_date}")
    cols = st.columns(10)
    for i, row in enumerate(foreign_df.iterrows()):
        cols[i].metric(label=f"No.{i+1}", value=row[1]['stock_id'])
else:
    st.write("暫時無法取得個股外資排行")

st.divider()

# 第二部分：100 強分析
if 'v2_results' not in st.session_state:
    st.session_state.v2_results = None

c1, c2 = st.columns(2)
with c1:
    if st.button('🚀 執行 100 強數據分析', use_container_width=True):
        dl = DataLoader()
        try:
            df_info = dl.taiwan_stock_info()
            base_list = [[row['stock_id'], row['stock_name']] for _, row in df_info[df_info['type']=='twse'].drop_duplicates('stock_id').head(100).iterrows()]
            with st.status("🔍 深度分析中...", expanded=True) as status:
                res_list = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(fetch_stock_info, s[0], s[1]) for s in base_list]
                    for f in concurrent.futures.as_completed(futures):
                        r = f.result()
                        if r: res_list.append(r)
                st.session_state.v2_results = pd.DataFrame(res_list)
                status.update(label="✅ 分析完成", state="complete")
        except Exception as e:
            st.error(f"分析失敗: {e}")

with c2:
    if st.button('🧹 清除快取', use_container_width=True):
        st.session_state.v2_results = None
        st.cache_data.clear()
        st.rerun()

# 第三部分：結果顯示與 Excel 下載 (功能 3)
if st.session_state.v2_results is not None:
    full_df = st.session_state.v2_results
    
    # 應用篩選器 (功能 2)
    filtered_df = full_df[full_df['現金殖利率(%)'] >= min_yield].sort_values('現金殖利率(%)', ascending=False)
    
    st.subheader(f"💰 篩選結果：殖利率 > {min_yield}% (共 {len(filtered_df)} 檔)")
    
    # Excel 下載按鈕 (功能 3)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        filtered_df.to_excel(writer, index=False, sheet_name='台股分析')
    
    st.download_button(
        label="📥 下載此分析報表 (Excel)",
        data=buffer.getvalue(),
        file_name=f"台股分析_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.ms-excel",
        use_container_width=True
    )

    st.dataframe(filtered_df, use_container_width=True, hide_index=True)

    # 圖表顯示
    if not filtered_df.empty:
        chart = alt.Chart(filtered_df.head(20)).mark_bar(color='#FF4B4B').encode(
            x=alt.X('公司名稱:N', sort='-y'),
            y='現金殖利率(%):Q',
            tooltip=['股票代號', '現金殖利率(%)']
        ).properties(height=400)
        st.altair_chart(chart, use_container_width=True)
