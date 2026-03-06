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
st.set_page_config(page_title="台股 100 強監控 V2", layout="wide")
st.title("📈 台股市值前 100 強財務監控 V2")

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

# --- 側邊欄：功能 2 - 殖利率篩選器 ---
st.sidebar.header("⚙️ 篩選與下載")
min_yield = st.sidebar.slider("最低現金殖利率門檻 (%)", 0.0, 15.0, 5.0, 0.5)

# --- 2. 核心數據處理函數 ---

# [修正] 獲取全市場三大法人買賣超金額 (取代原本的台積電替代方案)
def get_total_market_institutional_investors():
    url = "https://api.finmindtrade.com/api/v4/data"
    start_str = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    params = {
        "dataset": "TaiwanStockTotalInstitutionalInvestors",
        "start_date": start_str,
        "token": FINMIND_TOKEN
    }
    try:
        resp = requests.get(url, params=params)
        df = pd.DataFrame(resp.json()["data"])
        latest_date = df['date'].max()
        current = df[df['date'] == latest_date].copy()
        
        # 單位轉換：元 -> 億 (除以 10^8)
        current['買進(億)'] = (current['buy'] / 100000000).round(2)
        current['賣出(億)'] = (current['sell'] / 100000000).round(2)
        current['買賣超(億)'] = (current['diff'] / 100000000).round(2)
        
        name_map = {
            'Foreign_Investor': '外資', 'Investment_Trust': '投信',
            'Dealer_Self': '自營商自行買賣', 'Dealer_Hedging': '自營商避險'
        }
        current['身分別'] = current['name'].map(name_map).fillna(current['name'])
        return current[['身分別', '買進(億)', '賣出(億)', '買賣超(億)']], latest_date
    except:
        return None, "數據抓取失敗"

# [優化] 功能 1 - 外資買超前 10 名個股
def get_top_foreign_buys():
    url = "https://api.finmindtrade.com/api/v4/data"
    start_str = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    params = {"dataset": "TaiwanStockInstitutionalInvestors", "start_date": start_str, "token": FINMIND_TOKEN}
    try:
        resp = requests.get(url, params=params)
        df = pd.DataFrame(resp.json()["data"])
        latest_date = df['date'].max()
        # 篩選外資並按買進股數排序
        current = df[(df['date'] == latest_date) & (df['name'] == 'Foreign_Investor')].copy()
        current = current.sort_values('buy', ascending=False).head(10)
        return current[['stock_id', 'buy']], latest_date
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

# --- 3. 介面佈局 ---

# 第一部分：全市場三大法人金額 (修正後的數據)
st.subheader("📊 每日全市場三大法人買賣超 (金額：億元)")
total_inst_df, total_date = get_total_market_institutional_investors()
if total_inst_df is not None:
    st.info(f"📅 數據日期：{total_date}")
    st.table(total_inst_df)
else:
    st.warning("暫時無法取得全市場法人數據")

st.divider()

# 第二部分：功能 1 - 外資個股買超排行
st.subheader("🏆 當日外資買進股數前 10 名個股")
foreign_top_df, f_date = get_top_foreign_buys()
if foreign_top_df is not None:
    cols = st.columns(10)
    for i, (_, row) in enumerate(foreign_top_df.iterrows()):
        cols[i].metric(label=f"No.{i+1}", value=row['stock_id'])
else:
    st.write("暫時無法取得個股排行")

st.divider()

# 第三部分：100 強數據分析
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

# 第四部分：結果顯示與 Excel 下載 (功能 3)
if st.session_state.v2_results is not None:
    # 應用側邊欄篩選器
    filtered_df = st.session_state.v2_results[st.session_state.v2_results['現金殖利率(%)'] >= min_yield].sort_values('現金殖利率(%)', ascending=False)
    
    st.subheader(f"💰 篩選結果 (殖利率 > {min_yield}%)")
    
    # 功能 3: Excel 下載
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
