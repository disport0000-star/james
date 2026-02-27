import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import time

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="高殖利率精選 20 強", layout="wide")
st.title("📈 台股殖利率前 20 名財務監控")
st.write(f"系統狀態：精準模式已啟動 (最後更新時間: {datetime.now().strftime('%H:%M:%S')})")

# --- 2. 單支股票詳細抓取函數 ---
def fetch_detailed_data(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    dl = DataLoader()
    try:
        # A. yfinance 基礎數據
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice', 0)
        if curr_price == 0: return None

        # B. 殖利率與配息 (365天物理加總)
        div_history = stock.dividends
        last_year_divs = div_history[div_history.index >= (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')]
        annual_div_sum = last_year_divs.sum()
        calc_yield = round((annual_div_sum / curr_price * 100), 1) if annual_div_sum > 0 else 0.0

        # C. FinMind 三期月營收 (加入小延遲保護 API)
        time.sleep(0.1) 
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

# --- 3. 執行邏輯 ---
if st.button('🚀 分析殖利率精選 20 強'):
    with st.status("正在擴大掃描 20 支權值股財報...", expanded=True) as status:
        # 擴充至 20 支具有代表性的高股息與權值股
        base_list = [
            ["2330", "台積電"], ["2317", "鴻海"], ["2454", "聯發科"], ["2881", "富邦金"], 
            ["2603", "長榮"], ["2002", "中鋼"], ["2886", "兆豐金"], ["2382", "廣達"],
            ["2324", "仁寶"], ["2357", "華碩"], ["2882", "國泰金"], ["2891", "中信金"],
            ["1101", "台泥"], ["2303", "聯電"], ["2308", "台達電"], ["2412", "中華電"],
            ["2884", "玉山金"], ["3231", "緯創"], ["2376", "技嘉"], ["2609", "陽明"]
        ]
        
        final_results = []
        # 使用 3 個執行緒併發，既保持速度又不會太激進
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(fetch_detailed_data, s[0], s[1]) for s in base_list]
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res: final_results.append(res)
        
        df = pd.DataFrame(final_results)
        status.update(label="20 支數據抓取完成！", state="complete")

    if not df.empty:
        df = df.sort_values(by='現金殖利率(%)', ascending=False)
        st.success("成功加載 20 支重點個股！已自動依殖利率由高至低排序。")
        
        # 顯示全功能表格
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # 視覺化圖表
        st.divider()
        st.subheader("📊 關鍵獲利能力 (三率) 走勢對比")
        chart_data = df.set_index('公司名稱')[['毛利率(%)', '營業利益率(%)', '稅後淨利率(%)']]
        st.line_chart(chart_data)
    else:
        st.error("掃描失敗，請嘗試清除快取後重試。")

if st.button('🧹 清除快取'):
    st.cache_data.clear()
    st.rerun()

