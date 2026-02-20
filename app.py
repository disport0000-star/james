import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures

st.set_page_config(page_title="台股 500 強高效監控站", layout="wide")
st.title("📈 500 支個股財務監控中心 (穩定優化版)")

# --- 1. 獲取股票清單 ---
@st.cache_data(ttl=86400)
def get_500_stock_list():
    try:
        dl = DataLoader()
        df_info = dl.taiwan_stock_info()
        stocks = df_info[df_info['type'] == '上市'].head(500)
        return stocks[['stock_id', 'stock_name']].values.tolist()
    except:
        # 若 API 失效，提供備援的基本清單
        return [["2330", "台積電"], ["2317", "鴻海"], ["2454", "聯發科"], ["2881", "富邦金"], ["2603", "長榮"]]

# --- 2. 核心抓取邏輯 (增加錯誤容忍) ---
def process_single_stock(stock_info):
    sid, sname = stock_info
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    dl = DataLoader()
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice', 0)
        if curr_price == 0: return None # 價格異常直接跳過

        # 殖利率計算
        div_history = stock.dividends
        last_year_divs = div_history[div_history.index >= (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')]
        annual_div_sum = last_year_divs.sum()
        calc_yield = round((annual_div_sum / curr_price * 100), 1) if annual_div_sum > 0 else 0.0

        # FinMind 數據 (若失敗則給空值，不中斷程式)
        try:
            df_rev = dl.taiwan_stock_month_revenue(stock_id=clean_id, start_date=(datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d'))
            rev_m0 = f"{round(df_rev.sort_values('date', ascending=False).iloc[0]['revenue'] / 1000):,.0f}" if not df_rev.empty else ""
        except:
            rev_m0 = ""

        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '最新配息金額': round(annual_div_sum, 1),
            '最新季EPS': round(info.get('trailingEps', 0), 2),
            '最新一期營收(千元)': rev_m0,
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '營業利益率(%)': round(info.get('operatingMargins', 0) * 100, 1),
            '稅後淨利率(%)': round(info.get('profitMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except:
        return None

# --- 3. 執行與快取 ---
@st.cache_data(ttl=86400, show_spinner=False)
def run_full_scan(stock_list):
    final_data = []
    # 限制 worker 數量為 3，雖然慢一點但更穩定，不會被封鎖
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(process_single_stock, s) for s in stock_list]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: final_data.append(res)
    return pd.DataFrame(final_data)

# --- 4. 介面與自動排序 ---
stock_list = get_500_stock_list()

if st.button('🚀 執行 500 支全掃描'):
    with st.status("正在進行大規模掃描 (預計需 5-8 分鐘)...", expanded=True):
        df = run_full_scan(stock_list)
    
    if not df.empty:
        # 💡 自動排序：現金殖利率(%) 由高到低
        df = df.sort_values(by='現金殖利率(%)', ascending=False)
        st.success(f"完成！已為您篩選出前 {len(df)} 支具備數據的股票，並依殖利率排序。")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.error("掃描失敗，可能是 API 達到今日上限。請嘗試點擊『清除快取』後再試。")

if st.button('🧹 清除舊數據快取'):
    st.cache_data.clear()
    st.rerun()
