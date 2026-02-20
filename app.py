import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import time

# --- 1. 網頁基本設定 (確保一進來就有畫面) ---
st.set_page_config(page_title="個人投資監控站", layout="wide")
st.title("📈 我的專屬股票監控面板")
st.write("系統狀態：正在連線數據源...")

# --- 2. 核心邏輯 (鎖定全年配息計算與千元單位) ---
def fetch_stock_data():
    stock_list = ["2330.TW", "2317.TW", "2454.TW", "2881.TW", "2603.TW"]
    final_report = []
    dl = DataLoader()
    ticker_to_name = {"2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2881": "富邦金", "2603": "長榮"}
    
    for sid in stock_list:
        clean_id = sid.replace('.TW', '')
        try:
            # 股價與配息 (全年總和邏輯)
            stock = yf.Ticker(sid)
            info = stock.info
            curr_price = info.get('currentPrice')
            
            div_history = stock.dividends
            last_year_divs = div_history[div_history.index >= (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')]
            annual_div_sum = last_year_divs.sum()
            
            # 物理計算殖利率 (鎖定：全年總額/目前股價)
            calc_yield = round((annual_div_sum / curr_price * 100), 1) if annual_div_sum > 0 and curr_price else 0.0

            # FinMind 月營收 (單位：千元)
            df_rev = dl.taiwan_stock_month_revenue(stock_id=clean_id, start_date=(datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d'))
            rev_m0 = f"{round(df_rev.sort_values('date', ascending=False).iloc[0]['revenue'] / 1000):,.0f}" if not df_rev.empty else ""

            final_report.append({
                '股票代號': clean_id,
                '公司名稱': ticker_to_name.get(clean_id, info.get('shortName', '未知')),
                '目前股價': curr_price,
                '現金殖利率(%)': calc_yield,
                '全年配息總額': round(annual_div_sum, 1),
                '最新一期營收(千元)': rev_m0,
                '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
                '最新季EPS': round(info.get('trailingEps', 0), 1)
            })
        except Exception as e:
            continue
    return pd.DataFrame(final_report)

# --- 3. 執行與顯示 ---
# 直接執行，不放按鈕，確保一開啟網頁就有東西
with st.status("正在抓取最新市場數據...", expanded=True) as status:
    df = fetch_stock_data()
    status.update(label="數據抓取完成！", state="complete", expanded=False)

if not df.empty:
    st.success("數據加載成功！")
    # 顯示表格 (欄位順序鎖定)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    st.divider()
    st.subheader("📊 殖利率分布")
    st.bar_chart(df.set_index('公司名稱')['現金殖利率(%)'])
else:
    st.error("暫時無法獲取數據，請稍後再試。")
