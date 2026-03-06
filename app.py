import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import io
import altair as alt

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 100 強監控", layout="wide")
st.title("📈 台股市值前 100 強財務監控")

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNSAwMToyNzoxNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMjcuMjQwLjE3OC41MCJ9.23luowIBnVWfgnNDoclVYo6nwFWqzEf3zxya81Cnl2A" 

st.write(f"系統狀態：三大法人資訊新增版 (更新時間: {datetime.now().strftime('%H:%M:%S')})")

# --- [新功能] 獲取三大法人數據 ---
def get_institutional_investor_data():
    dl = DataLoader()
    dl.login_token(FINMIND_TOKEN)
    # 抓取最近 3 天的資料確保能拿到最新交易日
    today_str = datetime.now().strftime('%Y-%m-%d')
    start_str = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    
    try:
        df = dl.taiwan_stock_institutional_investors_summary(start_date=start_str, end_date=today_str)
        if not df.empty:
            # 取最新日期
            latest_date = df['date'].max()
            current_df = df[df['date'] == latest_date].copy()
            
            # 格式化單位 (將原始數據轉為 億)
            current_df['buy'] = (current_df['buy'] / 100000000).round(0).astype(int)
            current_df['sell'] = (current_df['sell'] / 100000000).round(0).astype(int)
            current_df['diff'] = (current_df['diff'] / 100000000).round(0).astype(int)
            
            # 重新命名欄位以對應您的圖片格式
            current_df = current_df.rename(columns={
                'name': '身分別',
                'buy': '買進 (億)',
                'sell': '賣出 (億)',
                'diff': '買賣超 (億)'
            })
            return current_df[['身分別', '買進 (億)', '賣出 (億)', '買賣超 (億)']], latest_date
    except:
        return None, None
    return None, None

# --- 顯示三大法人區塊 ---
st.subheader("📊 每日三大法人買賣超資訊")
inst_df, data_date = get_institutional_investor_data()

if inst_df is not None:
    st.info(f"數據日期：{data_date}")
    # 使用 Styled DataFrame 標註顏色 (正數紅、負數綠)
    def color_diff(val):
        color = 'red' if val > 0 else 'green' if val < 0 else 'black'
        return f'color: {color}; font-weight: bold'
    
    st.table(inst_df.style.applymap(color_diff, subset=['買賣超 (億)']))
else:
    st.warning("暫時無法取得法人資料，請確認 API 狀態。")

st.divider()

# --- 2. 核心抓取函數 (原有功能保持不變) ---
@st.cache_data(ttl=3600)
def get_all_stock_data(base_list):
    final_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(fetch_single_stock, s[0], s[1]) for s in base_list]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: final_results.append(res)
    return pd.DataFrame(final_results)

def fetch_single_stock(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    dl = DataLoader()
    
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        if curr_price == 0: return None

        div_history = stock.dividends
        if not div_history.empty:
            last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
            cash_div = round(last_year_divs.sum(), 2)
        else:
            cash_div = 0.0
            
        stock_div = info.get('stockDividendValue', 0.0) or 0.0
        calc_yield = round((cash_div / curr_price * 100), 1) if cash_div > 0 else 0.0

        eps_q0, eps_q1, eps_q2 = 0.0, 0.0, 0.0
        q_fin = stock.quarterly_financials
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: eps_q1 = round(eps_series.iloc[1], 2)
            if len(eps_series) > 2: eps_q2 = round(eps_series.iloc[2], 2)
        else:
            eps_q0 = round(info.get('trailingEps', 0), 2)

        rev_m0, r_growth = "", ""
        try:
            df_rev = dl.taiwan_stock_month_revenue(stock_id=clean_id, start_date=(datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d'))
            if not df_rev.empty:
                df_rev = df_rev.sort_values('date', ascending=False)
                rev_m0 = f"{round(df_rev.iloc[0]['revenue'] / 1000):,.0f}"
                r0, r1 = df_rev.iloc[0]['revenue'], df_rev.iloc[1]['revenue']
                r_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else ""
        except: pass

        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '現金股利': cash_div, '股票股利': stock_div,
            '最新季EPS': eps_q0, '上一季EPS': eps_q1, '上上一季EPS': eps_q2,
            '最新一期營收(千元)': rev_m0, '與上月比較增減(%)': r_growth,
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '營業利益率(%)': round(info.get('operatingMargins', 0) * 100, 1),
            '稅後淨利率(%)': round(info.get('profitMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except: return None

# --- 3. 獲取名單與 Excel 轉換 (原有功能保持不變) ---
@st.cache_data(ttl=86400)
def get_top_100_list():
    dl = DataLoader()
    df_info = dl.taiwan_stock_info()
    df_info = df_info[df_info['type'] == 'twse']
    df_info = df_info.drop_duplicates(subset=['stock_id'])
    return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(100).iterrows()]

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- 4. 介面主邏輯 (原有功能保持不變) ---
if st.button('🚀 執行 100 強數據分析'):
    base_list = get_top_100_list()
    
    with st.status("🔍 正在分析台股市值前 100 大個股...", expanded=True) as status:
        full_df = get_all_stock_data(base_list)
        status.update(label="✅ 分析完成！", state="complete")
    
    if not full_df.empty:
        full_df = full_df.drop_duplicates(subset=['股票代號'])
        full_df = full_df.sort_values(by='現金殖利率(%)', ascending=False)
        
        st.download_button(
            label="📥 下載完整 100 強個股財報 Excel",
            data=to_excel(full_df),
            file_name=f"Taiwan_Top100_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        st.subheader("💰 現金殖利率前 20 名")
        display_df = full_df.head(20).reset_index(drop=True)
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("📊 前 20 名殖利率視覺化")
        
        chart = alt.Chart(display_df).mark_bar(color='#FF4B4B').encode(
            x=alt.X('公司名稱:N', sort='-y', title='公司名稱'),
            y=alt.Y('現金殖利率(%):Q', scale=alt.Scale(domain=[0, 15]), title='現金殖利率 (%)'),
            tooltip=['公司名稱', '現金殖利率(%)']
        ).properties(height=400).interactive(bind_y=False)
