import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import time

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 20 強監控", layout="wide")
st.title("📈 台股殖利率精選 20 強財務監控")
st.write(f"系統狀態：EPS 歷史數據優化版 (更新時間: {datetime.now().strftime('%H:%M:%S')})")

# --- 2. 單支股票詳細抓取函數 ---
def fetch_detailed_data(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    dl = DataLoader()
    try:
        # A. yfinance 基礎數據
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        if curr_price == 0: return None

        # B. 殖利率與配息
        div_history = stock.dividends
        last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
        
        cash_div = round(last_year_divs.sum(), 2) if not last_year_divs.empty else 0.0
        stock_div = info.get('stockDividendValue', 0.0)
        if stock_div is None: stock_div = 0.0
        
        calc_yield = round((cash_div / curr_price * 100), 1) if cash_div > 0 else 0.0

        # C. EPS 歷史數據 (新增：上一季與上上季)
        # yfinance 的 trailingEps 通常代表最新一季或滾動四季，這裡從財報中抓取更準確的季資料
        q_earnings = stock.quarterly_earnings
        eps_q0, eps_q1, eps_q2 = 0.0, 0.0, 0.0
        
        # 嘗試從 info 抓取最新 EPS
        eps_q0 = round(info.get('trailingEps', 0), 2)
        
        # 從 quarterly_financials 抓取歷史 EPS (Diluted EPS)
        q_fin = stock.quarterly_financials
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: eps_q1 = round(eps_series.iloc[1], 2)
            if len(eps_series) > 2: eps_q2 = round(eps_series.iloc[2], 2)

        # D. FinMind 三期月營收
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

        # E. 兩期季營收
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
            '現金股利': cash_div,
            '股票股利': stock_div,
            '最新季EPS': eps_q0,            # 原始欄位
            '上一季EPS': eps_q1,            # 新增欄位
            '上上一季EPS': eps_q2,          # 新增欄位
            '最新一期營收(千元)': rev_m0, 
            '前一期營收(千元)': rev_m1, 
            '前二期營收(千元)': rev_m2,
            '與上月比較增減(%)': m_growth, 
            '最新一季營收(千元)': rev_q0, 
            '上一季營收(千元)': rev_q1, 
            '與上季比較增減(%)': q_growth, 
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '營業利益率(%)': round(info.get('operatingMargins', 0) * 100, 1),
            '稅後淨利率(%)': round(info.get('profitMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except Exception as e:
        return None

# --- 3. 介面控制與顯示 ---
if st.button('🚀 分析精選 20 強'):
    with st.status("正在抓取精選個股財報指標...", expanded=True) as status:
        base_list = [
            ["2330", "台積電"], ["2317", "鴻海"], ["2454", "聯發科"], ["2881", "富邦金"], 
            ["2603", "長榮"], ["2002", "中鋼"], ["2886", "兆豐金"], ["2382", "廣達"],
            ["2324", "仁寶"], ["2357", "華碩"], ["2882", "國泰金"], ["2891", "中信金"],
            ["1101", "台泥"], ["2303", "聯電"], ["2308", "台達電"], ["2412", "中華電"],
            ["2884", "玉山金"], ["3231", "緯創"], ["2376", "技嘉"], ["2609", "陽明"]
        ]
        
        final_results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(fetch_detailed_data, s[0], s[1]) for s in base_list]
            for future in concurrent.futures.as_completed(futures):
                res = future.result()
                if res: final_results.append(res)
        
        df = pd.DataFrame(final_results)
        status.update(label="數據分析完成！", state="complete")

    if not df.empty:
        df = df.sort_values(by='現金殖利率(%)', ascending=False)
        st.success("數據加載成功！")
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("📊 關鍵獲利三率對比 (依序排列)")
        chart_df = df.set_index('公司名稱')[['毛利率(%)', '營業利益率(%)', '稅後淨利率(%)']].sort_values(by='毛利率(%)', ascending=False)
        st.bar_chart(chart_df)
        
        st.subheader("💰 現金殖利率 (%) 概覽 (由高至低)")
        yield_chart = df.set_index('公司名稱')[['現金殖利率(%)']].sort_values(by='現金殖利率(%)', ascending=False)
        st.bar_chart(yield_chart, color="#FF4B4B")
        
    else:
        st.error("掃描失敗，請檢查 API 連線。")

if st.button('🧹 清除快取'):
    st.cache_data.clear()
    st.rerun()
