import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import time

# --- 1. 網頁基本設定 (修正超出畫面問題) ---
# layout="wide" 會讓網頁佔滿左右空間，提供更多欄位顯示餘裕
st.set_page_config(page_title="個人投資監控站", layout="wide")

st.title("📈 我的專屬股票監控面板")
st.write("系統狀態：即時數據連線中...")

# --- 2. 核心數據抓取邏輯 (整合優化功能) ---
def fetch_stock_data():
    # 監控清單
    stock_list = ["2330.TW", "2317.TW", "2454.TW", "2881.TW", "2603.TW"]
    final_report = []
    
    # 初始化 FinMind
    try:
        dl = DataLoader()
    except:
        from FinMind.data import DataLoader
        dl = DataLoader()
        
    ticker_to_name = {
        "2330": "台積電", "2317": "鴻海", "2454": "聯發科", 
        "2881": "富邦金", "2603": "長榮"
    }
    
    for sid in stock_list:
        clean_id = sid.replace('.TW', '')
        try:
            # A. yfinance 數據抓取
            stock = yf.Ticker(sid)
            info = stock.info
            curr_price = info.get('currentPrice')
            
            # B. 全年配息總和邏輯
            # 抓取過去 365 天內的所有配息紀錄並加總
            div_history = stock.dividends
            last_year_divs = div_history[div_history.index >= (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')]
            annual_div_sum = last_year_divs.sum()
            
            # C. 物理計算殖利率 (鎖定邏輯：全年總額 / 目前股價)
            # 確保不會出現超過 100% 的異常數值
            calc_yield = round((annual_div_sum / curr_price * 100), 1) if annual_div_sum > 0 and curr_price else 0.0

            # D. FinMind 月營收 (單位：千元)
            df_rev = dl.taiwan_stock_month_revenue(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
            )
            
            rev_m0, m_growth = "", ""
            if not df_rev.empty:
                df_rev = df_rev.sort_values('date', ascending=False)
                # 換算為千元單位並格式化
                rev_m0 = f"{round(df_rev.iloc[0]['revenue'] / 1000):,.0f}"
                r0, r1 = df_rev.iloc[0]['revenue'], df_rev.iloc[1]['revenue']
                m_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else ""

            # E. 季營收與財務指標
            q_fin = stock.quarterly_financials
            rev_q0 = ""
            if not q_fin.empty and 'Total Revenue' in q_fin.index:
                q_revs = q_fin.loc['Total Revenue']
                rev_q0 = f"{round(q_revs.iloc[0]/1000):,.0f}" if len(q_revs)>0 else ""

            # F. 整合至列表 (欄位順序永久鎖定)
            final_report.append({
                '股票代號': clean_id,
                '公司名稱': ticker_to_name.get(clean_id, info.get('shortName', '未知')),
                '目前股價': curr_price,
                '現金殖利率(%)': calc_yield,
                '全年配息總額': round(annual_div_sum, 1),
                '最新一期營收(千元)': rev_m0,
                '營收變動率(%)': m_growth,
                '最新一季營收(千元)': rev_q0,
                '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
                '最新季EPS': round(info.get('trailingEps', 0), 1)
            })
        except Exception as e:
            continue
            
    return pd.DataFrame(final_report)

# --- 3. 顯示介面 (修正滾動與超出螢幕問題) ---
# 一進入網頁自動執行，確保即時看到數據
with st.status("正在連線各數據源並換算全年殖利率...", expanded=True) as status:
    df = fetch_stock_data()
    status.update(label="數據處理完成！", state="complete", expanded=False)

if not df.empty:
    st.success("數據加載成功！")
    
    # 使用 container 包裝以強化佈局控制
    with st.container():
        st.info("💡 提示：若畫面裝不下所有欄位，請直接在下方表格內「向右滑動」查看隱藏資訊。")
        # use_container_width=True 配合 wide 模式自動適應
        st.dataframe(
            df, 
            use_container_width=True, 
            hide_index=True
        )
    
    # 增加圖表輔助
    st.divider()
    st.subheader("📊 關鍵指標對比 (殖利率)")
    st.bar_chart(df.set_index('公司名稱')['現金殖利率(%)'])
else:
    st.error("暫時抓取不到數據，請確認雲端環境連線狀態。")
