import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import altair as alt

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 100 強監控", layout="wide")
st.title("📈 台股市值前 100 強財務監控")

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

# --- 2. 三大法人數據處理 (對齊圖片的億元格式) ---
def get_institutional_investor_data():
    dl = DataLoader()
    dl.login_token(FINMIND_TOKEN)
    
    # 搜尋最近交易日
    start_str = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    try:
        # 使用 taiwan_market_daily 取得全市場法人統計 (包含外資、投信、自營商金額)
        df = dl.taiwan_market_daily(start_date=start_str)
        if df is not None and not df.empty:
            latest_data = df.sort_values('date').iloc[-1]
            data_date = latest_data['date']
            
            # 定義顯示項目與計算
            # 單位轉換：原始單位為元，除以 100,000,000 轉為「億」
            def to_billion(val): return round(val / 100000000, 2)

            summary = [
                {'身分別': '外資', '買進 (億)': to_billion(latest_data['Foreign_Investor_Buy']), 
                 '賣出 (億)': to_billion(latest_data['Foreign_Investor_Sell']), 
                 '買賣超 (億)': to_billion(latest_data['Foreign_Investor_Buy'] - latest_data['Foreign_Investor_Sell'])},
                {'身分別': '投信', '買進 (億)': to_billion(latest_data['Investment_Trust_Buy']), 
                 '賣出 (億)': to_billion(latest_data['Investment_Trust_Sell']), 
                 '買賣超 (億)': to_billion(latest_data['Investment_Trust_Buy'] - latest_data['Investment_Trust_Sell'])},
                {'身分別': '自營商 (合計)', '買進 (億)': to_billion(latest_data['Dealer_Self_Buy'] + latest_data['Dealer_Hedging_Buy']), 
                 '賣出 (億)': to_billion(latest_data['Dealer_Self_Sell'] + latest_data['Dealer_Hedging_Sell']), 
                 '買賣超 (億)': to_billion((latest_data['Dealer_Self_Buy'] + latest_data['Dealer_Hedging_Buy']) - (latest_data['Dealer_Self_Sell'] + latest_data['Dealer_Hedging_Sell']))}
            ]
            return pd.DataFrame(summary), data_date
    except: return None, "無法取得大盤法人資料，請確認 API 狀態"
    return None, "查無數據"

# 顯示三大法人資訊
st.subheader("📊 每日三大法人買賣超資訊")
inst_df, data_date = get_institutional_investor_data()

if isinstance(inst_df, pd.DataFrame):
    st.info(f"📅 數據日期：{data_date} (全市場統計，單位：億元)")
    def color_picker(val):
        color = '#FF4B4B' if val > 0 else '#00FF00' if val < 0 else 'white'
        return f'color: {color}; font-weight: bold'
    
    st.table(inst_df.style.format({'買進 (億)': '{:,.2f}', '賣出 (億)': '{:,.2f}', '買賣超 (億)': '{:,.2f}'})
             .applymap(color_picker, subset=['買賣超 (億)']))
else:
    st.warning(data_date)

st.divider()

# --- 3. 核心數據抓取 (強化防錯機制，避免 KeyError) ---
def fetch_stock_info(sid, sname):
    try:
        stock = yf.Ticker(f"{sid}.TW")
        info = stock.info
        # 優先從 info 抓價錢，抓不到再改用 history
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice')
        if not curr_price:
            hist = stock.history(period="1d")
            if not hist.empty: curr_price = hist['Close'].iloc[-1]
        
        if not curr_price: return None

        # 殖利率計算
        divs = stock.dividends
        last_year = datetime.now() - timedelta(days=365)
        cash_div = divs[divs.index.tz_localize(None) >= last_year].sum() if not divs.empty else 0
        
        return {
            '股票代號': sid, '公司名稱': sname, '目前股價': round(curr_price, 2),
            '現金殖利率(%)': round((cash_div / curr_price * 100), 2) if cash_div > 0 else 0.0,
            '現金股利': round(cash_div, 2)
        }
    except: return None

# --- 4. 介面與狀態管理 ---
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None

col1, col2 = st.columns(2)
with col1:
    if st.button('🚀 執行 100 強數據分析', use_container_width=True):
        dl = DataLoader()
        try:
            df_info = dl.taiwan_stock_info()
            base_list = [[row['stock_id'], row['stock_name']] for _, row in df_info[df_info['type']=='twse'].drop_duplicates('stock_id').head(100).iterrows()]
            
            with st.status("🔍 分析中...", expanded=True) as status:
                res_list = []
                with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                    futures = [executor.submit(fetch_stock_info, s[0], s[1]) for s in base_list]
                    for f in concurrent.futures.as_completed(futures):
                        r = f.result()
                        if r: res_list.append(r)
                
                if res_list:
                    st.session_state.analysis_results = pd.DataFrame(res_list)
                    status.update(label="✅ 分析完成", state="complete")
                else:
                    st.error("分析失敗：無法從 Yahoo Finance 抓取數據")
        except Exception as e:
            st.error(f"分析過程出錯: {e}")

with col2:
    if st.button('🧹 清除快取與重整', use_container_width=True):
        st.session_state.analysis_results = None
        st.cache_data.clear()
        st.rerun()

# --- 5. 顯示分析結果 (增加檢查避免 KeyError) ---
if st.session_state.analysis_results is not None:
    full_df = st.session_state.analysis_results
    if not full_df.empty and '現金殖利率(%)' in full_df.columns:
        full_df = full_df.sort_values('現金殖利率(%)', ascending=False).reset_index(drop=True)
        
        st.subheader("💰 現金殖利率前 20 名")
        st.dataframe(full_df.head(20), use_container_width=True, hide_index=True)
        
        chart = alt.Chart(full_df.head(20)).mark_bar(color='#FF4B4B').encode(
            x=alt.X('公司名稱:N', sort='-y', title='個股名稱'),
            y=alt.Y('現金殖利率(%):Q', title='殖利率 (%)'),
            tooltip=['股票代號', '目前股價', '現金殖利率(%)']
        ).properties(height=400)
        st.altair_chart(chart, use_container_width=True)
