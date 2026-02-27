import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股 500 強全功能監控", layout="wide")
st.title("📈 500 支個股財務監控中心 (批量優化版)")

# --- 2. 批量數據準備 (這是解決掃描失敗的關鍵) ---
@st.cache_data(ttl=86400) # 每天只需抓一次全市場營收
def get_bulk_finmind_data():
    dl = DataLoader()
    # 抓取上市股票名單
    df_info = dl.taiwan_stock_info()
    stock_list_500 = df_info[df_info['type'] == '上市'].head(500)
    
    # 批量抓取全市場月營收 (不帶 stock_id 即可抓取全部)
    # 抓取過去 120 天，確保能涵蓋到最新三個月
    df_all_rev = dl.taiwan_stock_month_revenue(
        start_date=(datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
    )
    return stock_list_500, df_all_rev

# --- 3. 單支股票處理 (僅處理 yfinance 部分，其餘用批量數據對應) ---
def process_stock(sid, sname, bulk_rev_df):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    try:
        # A. yfinance 數據
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice')
        if not curr_price: return None

        # B. 殖利率計算
        div_history = stock.dividends
        last_year_divs = div_history[div_history.index >= (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')]
        annual_div_sum = last_year_divs.sum()
        calc_yield = round((annual_div_sum / curr_price * 100), 1) if annual_div_sum > 0 else 0.0

        # C. 從批量數據過濾該股營收 (這步不消耗 API 額度)
        stock_rev = bulk_rev_df[bulk_rev_df['stock_id'] == clean_id].sort_values('date', ascending=False)
        rev_m0, rev_m1, rev_m2, m_growth = "", "", "", ""
        if not stock_rev.empty:
            rev_m0 = f"{round(stock_rev.iloc[0]['revenue'] / 1000):,.0f}" if len(stock_rev) > 0 else ""
            rev_m1 = f"{round(stock_rev.iloc[1]['revenue'] / 1000):,.0f}" if len(stock_rev) > 1 else ""
            rev_m2 = f"{round(stock_rev.iloc[2]['revenue'] / 1000):,.0f}" if len(stock_rev) > 2 else ""
            r0, r1 = stock_rev.iloc[0]['revenue'], stock_rev.iloc[1]['revenue']
            m_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else ""

        # D. 季報 (因 FinMind 季報結構複雜，此處維持 yfinance 抓取)
        q_fin = stock.quarterly_financials
        rev_q0, rev_q1, q_growth = "", "", ""
        if not q_fin.empty and 'Total Revenue' in q_fin.index:
            q_revs = q_fin.loc['Total Revenue']
            rev_q0 = f"{round(q_revs.iloc[0]/1000):,.0f}" if len(q_revs) > 0 else ""
            rev_q1 = f"{round(q_revs.iloc[1]/1000):,.0f}" if len(q_revs) > 1 else ""
            v0, v1 = q_revs.iloc[0], q_revs.iloc[1]
            q_growth = f"{round(((v0-v1)/v1)*100, 1)}%" if v1 != 0 else ""

        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '最新配息金額': round(annual_div_sum, 1),
            '最新季EPS': round(info.get('trailingEps', 0), 2),
            '最新一期營收(千元)': rev_m0, '前一期營元)': rev_m1, '前二期營收(千元)': rev_m2,
            '營收變動率(%)': m_growth, '最新一季營收(千元)': rev_q0, '上一季營收(千元)': rev_q1,
            '季營收變動率(%)': q_growth, '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '營業利益率(%)': round(info.get('operatingMargins', 0) * 100, 1),
            '稅後淨利率(%)': round(info.get('profitMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except:
        return None

# --- 4. 執行按鈕 ---
col1, col2 = st.columns([1, 4])
with col1:
    start_btn = st.button('🚀 執行 500 支全掃描')
with col2:
    if st.button('🧹 清除舊數據'):
        st.cache_data.clear()
        st.rerun()

if start_btn:
    with st.status("正在下載全市場營收清單並執行 500 支掃描...", expanded=True) as status:
        # 第一步：一口氣抓下 2000 支股票的營收，只算 1 次 API 請求
        stocks_info, all_rev_df = get_bulk_finmind_data()
        
        # 第二步：平行處理 yfinance 股價與殖利率
        final_data = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_stock, row['stock_id'], row['stock_name'], all_rev_df) 
                       for _, row in stocks_info.iterrows()]
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res: final_data.append(res)
        
        df = pd.DataFrame(final_data)
        status.update(label="數據處理完成！", state="complete")

    if not df.empty:
        # 自動依照殖利率排序
        df = df.sort_values(by='現金殖利率(%)', ascending=False)
        st.success(f"成功抓取 {len(df)} 支個股數據。")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.error("掃描失敗，請確認 API 狀態或 Token 額度。")
