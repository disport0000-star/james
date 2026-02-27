import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import time

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="高殖利率精選 30 強", layout="wide")
st.title("📈 台股殖利率前 30 名財務監控")
st.write(f"系統狀態：精選模式已啟動 (更新時間: {datetime.now().strftime('%H:%M:%S')})")

# --- 2. 核心數據抓取函數 (單支處理) ---
def fetch_detailed_data(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    dl = DataLoader()
    try:
        # A. yfinance 數據
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice', 0)
        if curr_price == 0: return None

        # B. 殖利率與配息 (365天物理加總)
        div_history = stock.dividends
        last_year_divs = div_history[div_history.index >= (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')]
        annual_div_sum = last_year_divs.sum()
        calc_yield = round((annual_div_sum / curr_price * 100), 1) if annual_div_sum > 0 else 0.0

        # C. FinMind 三期月營收
        rev_m0, rev_m1, rev_m2, m_growth = "", "", "", ""
        try:
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
            pass

        # D. 季營收
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
            '最新一期營收(千元)': rev_m0, '前一期營收(千元)': rev_m1, '前二期營收(千元)': rev_m2,
            '營收變動率(%)': m_growth, '最新一季營收(千元)': rev_q0, '上一季營收(千元)': rev_q1,
            '季營收變動率(%)': q_growth, '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '營業利益率(%)': round(info.get('operatingMargins', 0) * 100, 1),
            '稅後淨利率(%)': round(info.get('profitMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except:
        return None

# --- 3. 掃描與篩選邏輯 ---
if st.button('🚀 開始分析殖利率前 30 名'):
    with st.status("正在獲取市場名單並篩選高殖利率股...", expanded=True) as status:
        # 步驟 1: 先獲取上市股票基本清單
        dl = DataLoader()
        df_info = dl.taiwan_stock_info()
        # 為了效能，先取前 100 支作為篩選池（或改為您熟悉的特定股票）
        base_list = df_info[df_info['type'] == '上市'].head(100).values.tolist()
        
        # 步驟 2: 平行抓取初步殖利率資訊
        temp_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(fetch_detailed_data, s[0], s[1]) for s in base_list]
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res: temp_results.append(res)
        
        full_df = pd.DataFrame(temp_results)
        
        if not full_df.empty:
            # 步驟 3: 篩選出殖利率最高的前 30 名
            top_30_df = full_df.sort_values(by='現金殖利率(%)', ascending=False).head(30)
            status.update(label="精選 30 強分析完成！", state="complete")
            
            st.success(f"已為您列出當前篩選池中殖利率最高的 30 支股票。")
            st.dataframe(top_30_df, use_container_width=True, hide_index=True)
            
            # 三率圖表
            st.divider()
            st.subheader("📊 前 10 名獲利能力對比")
            chart_data = top_30_df.head(10).set_index('公司名稱')[['毛利率(%)', '營業利益率(%)', '稅後淨利率(%)']]
            st.bar_chart(chart_data)
        else:
            st.error("掃描失敗，請嘗試清除快取後重試。")

if st.button('🧹 清除快取'):
    st.cache_data.clear()
    st.rerun()
