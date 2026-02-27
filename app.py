import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import time

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股 500 強監控面板", layout="wide")
st.title("📈 500 支個股財務監控中心 (穩定修正版)")

# --- 2. 獲取 500 支股票清單 ---
@st.cache_data(ttl=86400)
def get_500_stock_list():
    try:
        dl = DataLoader()
        df_info = dl.taiwan_stock_info()
        stocks = df_info[df_info['type'] == '上市'].head(500)
        return stocks[['stock_id', 'stock_name']].values.tolist()
    except:
        # 備援清單 (避免 API 連線失敗導致網頁全黑)
        return [["2330", "台積電"], ["2317", "鴻海"], ["2454", "聯發科"]]

# --- 3. 單支股票處理 (強化穩定性，避開 KeyError) ---
def process_single_stock(stock_info):
    sid, sname = stock_info
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    dl = DataLoader()
    
    try:
        # A. yfinance 數據 (比較穩定，先抓)
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice', 0)
        if curr_price == 0: return None

        # B. 殖利率與配息
        div_history = stock.dividends
        last_year_divs = div_history[div_history.index >= (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')]
        annual_div_sum = last_year_divs.sum()
        calc_yield = round((annual_div_sum / curr_price * 100), 1) if annual_div_sum > 0 else 0.0

        # C. FinMind 數據 (加入強大的錯誤攔截)
        rev_m0, rev_m1, rev_m2, m_growth = "", "", "", ""
        try:
            # 增加一點延遲，避免 API 請求過於密集
            time.sleep(0.05)
            df_rev = dl.taiwan_stock_month_revenue(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=150)).strftime('%Y-%m-%d')
            )
            if not df_rev.empty:
                df_rev = df_rev.sort_values('date', ascending=False)
                rev_m0 = f"{round(df_rev.iloc[0]['revenue'] / 1000):,.0f}" if len(df_rev) > 0 else ""
                rev_m1 = f"{round(df_rev.iloc[1]['revenue'] / 1000):,.0f}" if len(df_rev) > 1 else ""
                rev_m2 = f"{round(df_rev.iloc[2]['revenue'] / 1000):,.0f}" if len(df_rev) > 2 else ""
                r0, r1 = df_rev.iloc[0]['revenue'], df_rev.iloc[1]['revenue']
                m_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else ""
        except:
            pass # 即使營收抓不到，也要保留股價資訊

        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '最新配息金額': round(annual_div_sum, 1),
            '最新季EPS': round(info.get('trailingEps', 0), 2),
            '最新一期營收(千元)': rev_m0, '前一期營收(千元)': rev_m1, '前二期營收(千元)': rev_m2,
            '營收變動率(%)': m_growth,
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '營業利益率(%)': round(info.get('operatingMargins', 0) * 100, 1),
            '稅後淨利率(%)': round(info.get('profitMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except:
        return None

# --- 4. 執行按鈕與快取處理 ---
stock_list = get_500_stock_list()

if st.button('🚀 執行 500 支台股掃描'):
    with st.status("正在逐一分析個股財報 (預計 5-8 分鐘)...", expanded=True) as status:
        final_data = []
        # 將執行緒降為 3，這最能兼顧速度與 API 穩定性
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(process_single_stock, s) for s in stock_list]
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                res = future.result()
                if res: final_data.append(res)
                if (i+1) % 50 == 0:
                    st.write(f"目前進度: 已完成 {i+1} 支個股...")
        
        df = pd.DataFrame(final_data)
        status.update(label="數據處理完成！", state="complete")

    if not df.empty:
        df = df.sort_values(by='現金殖利率(%)', ascending=False)
        st.success(f"成功掃描 {len(df)} 支個股！已依殖利率排序。")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.error("掃描失敗，請確認 API 狀態。")

if st.button('🧹 清除數據快取'):
    st.cache_data.clear()
    st.rerun()
