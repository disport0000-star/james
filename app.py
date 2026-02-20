import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股 500 強監控面板", layout="wide")

st.title("📈 500 支個股財務監控中心")
st.write(f"系統狀態：大規模數據平行處理中... (更新時間: {datetime.now().strftime('%H:%M:%S')})")

# --- 2. 獲取股票清單 (從 FinMind 自動抓取前 500 名上市股票) ---
@st.cache_data(ttl=86400)
def get_500_stock_list():
    dl = DataLoader()
    df_info = dl.taiwan_stock_info()
    # 篩選上市股票並取前 500 筆，確保包含您關注的指標股
    stocks = df_info[df_info['type'] == '上市'].head(500)
    return stocks[['stock_id', 'stock_name']].values.tolist()

# --- 3. 單支股票處理邏輯 (保持所有欄位不變) ---
def process_single_stock(stock_info):
    sid, sname = stock_info
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    dl = DataLoader() # 每個執行緒獨立初始化
    
    try:
        # A. yfinance 數據
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice')
        
        # B. 殖利率與配息 (365天物理計算)
        div_history = stock.dividends
        last_year_divs = div_history[div_history.index >= (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')]
        annual_div_sum = last_year_divs.sum()
        calc_yield = round((annual_div_sum / curr_price * 100), 1) if annual_div_sum > 0 and curr_price else 0.0

        # C. FinMind 三期月營收 (單位：千元)
        df_rev = dl.taiwan_stock_month_revenue(
            stock_id=clean_id, 
            start_date=(datetime.now() - timedelta(days=150)).strftime('%Y-%m-%d')
        )
        rev_m0, rev_m1, rev_m2, m_growth = "", "", "", ""
        if not df_rev.empty:
            df_rev = df_rev.sort_values('date', ascending=False)
            rev_m0 = f"{round(df_rev.iloc[0]['revenue'] / 1000):,.0f}" if len(df_rev) > 0 else ""
            rev_m1 = f"{round(df_rev.iloc[1]['revenue'] / 1000):,.0f}" if len(df_rev) > 1 else ""
            rev_m2 = f"{round(df_rev.iloc[2]['revenue'] / 1000):,.0f}" if len(df_rev) > 2 else ""
            r0, r1 = df_rev.iloc[0]['revenue'], df_rev.iloc[1]['revenue']
            m_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else ""

        # D. 兩期季營收
        q_fin = stock.quarterly_financials
        rev_q0, rev_q1, q_growth = "", "", ""
        if not q_fin.empty and 'Total Revenue' in q_fin.index:
            q_revs = q_fin.loc['Total Revenue']
            rev_q0 = f"{round(q_revs.iloc[0]/1000):,.0f}" if len(q_revs) > 0 else ""
            rev_q1 = f"{round(q_revs.iloc[1]/1000):,.0f}" if len(q_revs) > 1 else ""
            v0, v1 = q_revs.iloc[0], q_revs.iloc[1]
            q_growth = f"{round(((v0-v1)/v1)*100, 1)}%" if v1 != 0 else ""

        return {
            '股票代號': clean_id,
            '公司名稱': sname,
            '目前股價': curr_price,
            '現金殖利率(%)': calc_yield,
            '最新配息金額': round(annual_div_sum, 1),
            '最新季EPS': round(info.get('trailingEps', 0), 2),
            '最新一期營收(千元)': rev_m0,
            '前一期營收(千元)': rev_m1,
            '前二期營收(千元)': rev_m2,
            '營收變動率(%)': m_growth,
            '最新一季營收(千元)': rev_q0,
            '上一季營收(千元)': rev_q1,
            '季營收變動率(%)': q_growth,
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '營業利益率(%)': round(info.get('operatingMargins', 0) * 100, 1),
            '稅後淨利率(%)': round(info.get('profitMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except:
        return None

# --- 4. 平行執行主程序 ---
stock_list = get_500_stock_list()
final_data = []

if st.button('🚀 開始執行 500 支股票掃描'):
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 使用 ThreadPoolExecutor 同時啟動 5 個執行緒 (避免被 Yahoo 封鎖)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_single_stock, s) for s in stock_list]
        
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            if result:
                final_data.append(result)
            
            # 更新進度條
            prog = (i + 1) / len(stock_list)
            progress_bar.progress(prog)
            status_text.text(f"已處理: {i+1} / 500 (目前抓取: {result['公司名稱'] if result else '跳過'})")

    df = pd.DataFrame(final_data)
    
    if not df.empty:
        st.success(f"完成！共成功抓取 {len(df)} 支股票數據。")
        st.dataframe(
            df, 
            use_container_width=True, 
            hide_index=True,
            column_config={"股票代號": st.column_config.TextColumn(width=80)} # 其餘欄位自動適應
        )
    else:
        st.error("掃描失敗，請檢查網路或 API 狀態。")
else:
    st.info("請點擊上方按鈕開始掃描 500 支台股，過程約需 3-5 分鐘。")
