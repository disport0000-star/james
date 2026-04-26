# ==========================================
# 📈 台股精選 300 強財務監控 - V1.95 終極穩定版
# 更新重點：黃金數據源切換至美國聯準會 (FRED)，確保雲端不封鎖
# 保留：台股專家匯入模式 + 景氣燈號官方導航按鈕
# ==========================================
import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import io
import altair as alt
import os

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 300 強監控", layout="wide")
st.title("📈 台股市值前 300 強財務監控")

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNyAxNTowNToyNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMTExLjI1NS4xMTAuNDkifQ.FLkCVK6j0S6TfgAI-_hAhaa3i11pmwlntZZP2X1RiIs"

st.write(f"系統狀態：V1.95 終極穩定版 (目前時間: {datetime.now().strftime('%H:%M:%S')})")

LOCAL_CACHE_FILE = "taiwan_top300_cache_v1_95.csv"

# --- 2. 總經數據抓取函數 (切換至 FRED 來源) ---
@st.cache_data(ttl=86400) # 官方每日更新一次，快取設為 24 小時
def get_gold_trend():
    try:
        # 使用美國聯準會 (FRED) 官方開放資料 (倫敦黃金市場定盤價 USD/oz)
        # 此來源為政府官方 CSV，極度穩定且不會阻擋雲端 IP
        url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GOLDAMGBD228NLBM"
        
        # 讀取 CSV，並處理可能的缺失值 (假日)
        df_gold = pd.read_csv(url, na_values='.')
        df_gold = df_gold.dropna()
        
        # 整理欄位格式
        df_gold['DATE'] = pd.to_datetime(df_gold['DATE']).dt.date
        df_gold = df_gold.rename(columns={'DATE': 'Date', 'GOLDAMGBD228NLBM': 'Close'})
        
        # 返回近一年 (約 252 個交易日) 的資料
        return df_gold.tail(252).reset_index(drop=True)
    except Exception as e:
        print(f"FRED Gold Fetch Error: {e}")
        return pd.DataFrame()

# --- 3. 台股核心抓取函數 (保留雲端備用) ---
@st.cache_data(ttl=3600)
def get_all_stock_data_v10(base_list):
    final_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch_single_stock, s[0], s[1]) for s in base_list]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: final_results.append(res)
    return pd.DataFrame(final_results)

def fetch_single_stock(sid, sname):
    import time, random
    time.sleep(random.uniform(1.0, 2.5)) 
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    dl = DataLoader()
    dl.login_by_token(api_token=FINMIND_TOKEN)
    
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        if curr_price == 0: return None

        div_history = stock.dividends
        if not div_history.empty:
            target_year = datetime.now().year - 1
            div_dates = div_history.index.tz_localize(None)
            last_year_divs = div_history[div_dates.year == target_year]
            cash_div = round(last_year_divs.sum(), 2)
        else: cash_div = 0.0
            
        calc_yield = round((cash_div / curr_price * 100), 1) if cash_div > 0 else 0.0

        stock_div = 0.0
        try:
            df_div = dl.taiwan_stock_dividend(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d')
            )
            if df_div is not None and not df_div.empty:
                df_div = df_div.sort_values('date', ascending=False)
                if 'stock_dividend' in df_div.columns:
                    stock_div = round(float(df_div.iloc[0]['stock_dividend']), 2)
        except Exception: pass 

        eps_q0, eps_q1, eps_q2 = 0.0, 0.0, 0.0
        q_fin = stock.quarterly_financials
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: eps_q1 = round(eps_series.iloc[1], 2)
            if len(eps_series) > 2: eps_q2 = round(eps_series.iloc[2], 2)
        else: eps_q0 = round(info.get('trailingEps', 0), 2)

        eps_growth = "0%" if eps_q0 == 0 else "N/A"
        if eps_q1 != 0: eps_growth = f"{round(((eps_q0 - eps_q1) / abs(eps_q1)) * 100, 1)}%"

        rev_m0, rev_m1, rev_m2, r_growth = "N/A", "N/A", "N/A", "N/A"
        try:
            df_rev = dl.taiwan_stock_month_revenue(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
            )
            if df_rev is not None and not df_rev.empty:
                df_rev = df_rev.sort_values('date', ascending=False)
                if len(df_rev) > 0: rev_m0 = f"{round(df_rev.iloc[0]['revenue'] / 1000):,.0f}"
                if len(df_rev) > 1:
                    r0, r1 = df_rev.iloc[0]['revenue'], df_rev.iloc[1]['revenue']
                    rev_m1 = f"{round(r1 / 1000):,.0f}"
                    r_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else "0%"
                if len(df_rev) > 2: rev_m2 = f"{round(df_rev.iloc[2]['revenue'] / 1000):,.0f}"
        except Exception: pass 

        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '現金股利': cash_div, '股票股利': stock_div,
            '最新季EPS': eps_q0, '上一季EPS': eps_q1, '上上一季EPS': eps_q2,
            '與上一季EPS比較增減(%)': eps_growth,
            '最新一期營收(千元)': rev_m0, '上一期營收(千元)': rev_m1, '上上一期營收(千元)': rev_m2,
            '與上月比較增減(%)': r_growth,
            '毛利率(%)': round((info.get('grossMargins') or 0) * 100, 1),
            '稅後淨利率(%)': round((info.get('profitMargins') or 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except Exception: return None

# --- 4. 獲取名單與 Excel 轉換 ---
@st.cache_data(ttl=86400)
def get_base_stock_list():
    try:
        dl = DataLoader()
        dl.login_by_token(api_token=FINMIND_TOKEN)
        df_info = dl.taiwan_stock_info()
        if df_info is None or df_info.empty: return []
        df_info = df_info[df_info['type'] == 'twse']
        is_four_digits = df_info['stock_id'].astype(str).str.len() == 4
        is_numeric = df_info['stock_id'].astype(str).str.isnumeric()
        df_info = df_info[is_four_digits & is_numeric]
        df_info = df_info.drop_duplicates(subset=['stock_id'])
        return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(500).iterrows()]
    except Exception: return []

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- 5. 主流程 ---
def process_data(force_update=False):
    cached_df = pd.DataFrame()
    if os.path.exists(LOCAL_CACHE_FILE):
        try:
            cached_df = pd.read_csv(LOCAL_CACHE_FILE, dtype={'股票代號': str})
            cached_df = cached_df.fillna("N/A")
            if not cached_df.empty:
                return cached_df
        except Exception: pass

    if force_update:
        base_list = get_base_stock_list()
        if not base_list: return pd.DataFrame()
        with st.status("🔍 正在透過雲端抓取備胎數據...", expanded=True) as status:
            new_df = get_all_stock_data_v10(base_list)
            if not new_df.empty:
                new_df = new_df.drop_duplicates(subset=['股票代號']).sort_values(by='現金殖利率(%)', ascending=False).head(300)
                new_df.to_csv(LOCAL_CACHE_FILE, index=False, encoding='utf-8-sig')
                status.update(label=f"✅ 抓取完成！", state="complete")
                return new_df
            else:
                status.update(label="❌ 抓取失敗：請由側邊欄匯入 VS Code Excel。", state="error")
                return pd.DataFrame()
    return pd.DataFrame()

# --- 6. 側邊欄：專家匯入介面 ---
with st.sidebar:
    st.markdown("### 🔌 專家模式：匯入本地資料")
    st.info("💡 將 VS Code 產出的全台股 Excel 拖曳到下方更新畫面！")
    
    uploaded_file = st.file_uploader("📂 上傳全台股 Excel", type=['xlsx'])
    if uploaded_file is not None:
        try:
            df_uploaded = pd.read_excel(uploaded_file, dtype={'股票代號': str})
            df_top300 = df_uploaded.sort_values(by='現金殖利率(%)', ascending=False).head(300)
            df_top300.to_csv(LOCAL_CACHE_FILE, index=False, encoding='utf-8-sig')
            st.success("✅ 資料匯入成功！請點擊下方的「重啟網頁」按鈕。")
        except Exception as e:
            st.error(f"檔案讀取失敗：{e}")

    st.divider()
    force_update = st.button('🔄 強制雲端抓取台股 (容易失敗)')
    if st.button('🧹 清除快取並重啟網頁'):
        st.cache_data.clear()
        st.rerun()

# --- 7. 主畫面呈現 ---
full_df = process_data(force_update=force_update)

if not full_df.empty:
    st.download_button(
        label=f"📥 下載完整前 {len(full_df)} 強純個股財報 Excel",
        data=to_excel(full_df),
        file_name=f"Taiwan_Top300_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.subheader("💰 台股現金殖利率前 40 名")
    display_df = full_df.head(40).reset_index(drop=True)
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.error("分析結果為空。請由左側邊欄上傳您在 VS Code 抓取好的 Excel 檔案！")

# ==========================================
# 🌟 全新模塊：總經雙指標 (FRED 黃金 + 景氣燈號連結)
# ==========================================
st.divider()
st.subheader("🌍 總經戰情室：景氣循環與資金流向")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 🟡 近一年黃金定盤價走勢 (FRED)")
    df_gold = get_gold_trend()
    if not df_gold.empty:
        # 使用金黃色 (#FFD700) 畫出穩定的走勢圖
        gold_chart = alt.Chart(df_gold).mark_line(color='#FFD700', strokeWidth=3).encode(
            x=alt.X('Date:T', title='日期'),
            y=alt.Y('Close:Q', title='USD/oz', scale=alt.Scale(zero=False)),
            tooltip=[alt.Tooltip('Date:T', title='日期'), alt.Tooltip('Close:Q', title='價格', format='.2f')]
        ).properties(height=350).interactive(bind_y=False)
        st.altair_chart(gold_chart, use_container_width=True)
        st.caption("📈 資料來源：美國聯準會 (FRED - London Fixing Price)")
    else:
        st.warning("暫時無法取得 FRED 黃金資料。")

with col2:
    st.markdown("#### 🚦 台灣景氣對策信號")
    st.info("💡 為確保獲取最精準的官方燈號與景氣分數，請前往國發會網站。")
    st.markdown("**(紅燈：熱絡 / 綠燈：穩定 / 藍燈：低迷)**")
    
    st.write("") 
    st.link_button(
        label="👉 點擊前往【國發會】查看最新景氣燈號",
        url="https://www.ndc.gov.tw/Content_List.aspx?n=275A4EA8B860FEBB",
        use_container_width=True
    )
    st.caption("💡 官方數據通常於每月 27 號左右更新上個月數據。")
