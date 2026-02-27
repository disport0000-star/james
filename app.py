import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import time

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="個人投資監控站-全功能版", layout="wide")

st.title("📈 我的專屬股票監控面板")
st.write(f"系統狀態：數據連線中... (最後更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")

# --- 2. 核心數據抓取邏輯 (補齊 Excel 所有欄位) ---
def fetch_stock_data():
    stock_list = ["2330.TW", "2317.TW", "2454.TW", "2881.TW", "2603.TW"]
    final_report = []
    
    try:
        dl = DataLoader()
    except:
        from FinMind.data import DataLoader
        dl = DataLoader()
        
    ticker_to_name = {"2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2881": "富邦金", "2603": "長榮"}
    
    for sid in stock_list:
        clean_id = sid.replace('.TW', '')
        try:
            # A. yfinance 基礎數據
            stock = yf.Ticker(sid)
            info = stock.info
            curr_price = info.get('currentPrice')
            
            # B. 全年配息計算 (365天總和)
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

            # E. 整合所有欄位 (對齊 Excel A-Q 欄)
            final_report.append({
                '股票代號': clean_id,
                '公司名稱': ticker_to_name.get(clean_id, info.get('shortName', '未知')),
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
            })
        except:
            continue
    return pd.DataFrame(final_report)

# --- 3. 顯示介面與滑動優化 ---
with st.status("正在抓取與計算完整財務指標...", expanded=True) as status:
    df = fetch_stock_data()
    status.update(label="數據處理完成！", state="complete", expanded=False)

if not df.empty:
    st.info("💡 操作提示：表格已補齊營業利益率等 17 項指標，請「按住表格向右滑動」查看完整資料。")
    
    # 強制設定每一欄的寬度，確保觸發水平捲軸
    st.dataframe(
        df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "股票代號": st.column_config.TextColumn(width=80),
            "公司名稱": st.column_config.TextColumn(width=100),
            "目前股價": st.column_config.NumberColumn(width=100),
            "現金殖利率(%)": st.column_config.NumberColumn(width=110),
            "最新配息金額": st.column_config.NumberColumn(width=110),
            "最新季EPS": st.column_config.NumberColumn(width=100),
            "最新一期營收(千元)": st.column_config.TextColumn(width=150),
            "前一期營收(千元)": st.column_config.TextColumn(width=150),
            "前二期營收(千元)": st.column_config.TextColumn(width=150),
            "營收變動率(%)": st.column_config.TextColumn(width=120),
            "最新一季營收(千元)": st.column_config.TextColumn(width=150),
            "上一季營收(千元)": st.column_config.TextColumn(width=150),
            "季營收變動率(%)": st.column_config.TextColumn(width=120),
            "毛利率(%)": st.column_config.NumberColumn(width=100),
            "營業利益率(%)": st.column_config.NumberColumn(width=110),
            "稅後淨利率(%)": st.column_config.NumberColumn(width=110),
            "更新日期": st.column_config.TextColumn(width=120),
        }
    )
    
    st.divider()
    st.subheader("📊 關鍵獲利能力對比 (三率)")
    # 這裡顯示一個三率對比圖供參考
    chart_data = df.set_index('公司名稱')[['毛利率(%)', '營業利益率(%)', '稅後淨利率(%)']]
    st.line_chart(chart_data)

else:
    st.error("暫時抓取不到數據，請檢查 GitHub Secrets 或環境設定。")
