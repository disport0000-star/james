# ==========================================
# 📈 台股精選 300 強財務監控 - V1.3 新增股票股利版
# (基於 V1 標準版核心功能延伸)
# ==========================================
import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import io
import altair as alt
import time
import random
import os

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 300 強監控", layout="wide")
st.title("📈 台股市值前 300 強財務監控")

# 您的 FinMind 金鑰
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNyAxNTowNToyNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMTExLjI1NS4xMTAuNDkifQ.FLkCVK6j0S6TfgAI-_hAhaa3i11pmwlntZZP2X1RiIs"

st.write(f"系統狀態：V1.3 新增股票股利版 (目前時間: {datetime.now().strftime('%H:%M:%S')})")

LOCAL_CACHE_FILE = "taiwan_top300_cache_v1_3.csv"

# --- 2. 日期邏輯檢查 ---
def get_recent_10th_date():
    now = datetime.now()
    if now.day >= 10:
        return datetime(now.year, now.month, 10).date()
    else:
        if now.month == 1:
            return datetime(now.year - 1, 12, 10).date()
        else:
            return datetime(now.year, now.month - 1, 10).date()

# --- 3. 核心抓取函數 ---
@st.cache_data(ttl=3600)
def get_all_stock_data_v5(base_list):
    final_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(fetch_single_stock, s[0], s[1]) for s in base_list]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: 
                final_results.append(res)
    return pd.DataFrame(final_results)

def fetch_single_stock(sid, sname):
    time.sleep(random.uniform(0.8, 2.0)) 
    
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    
    dl = DataLoader()
    dl.login_by_token(api_token=FINMIND_TOKEN)
    
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        
        if curr_price == 0: 
            return None

        div_history = stock.dividends
        if not div_history.empty:
            last_year_divs = div_history[div_history.index.tz_localize(None) >= (datetime.now() - timedelta(days=365))]
            cash_div = round(last_year_divs.sum(), 2)
        else:
            cash_div = 0.0
            
        if cash_div > 0:
            calc_yield = round((cash_div / curr_price * 100), 1)
        else:
            calc_yield = 0.0

        stock_div = info.get('stockDividendValue', 0.0) or 0.0

        eps_q0, eps_q1, eps_q2 = 0.0, 0.0, 0.0
        q_fin = stock.quarterly_financials
        
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(eps_series.iloc[0], 2)
            if len(eps_series) > 1: eps_q1 = round(eps_series.iloc[1], 2)
            if len(eps_series) > 2: eps_q2 = round(eps_series.iloc[2], 2)
        else:
            eps_q0 = round(info.get('trailingEps', 0), 2)

        eps_growth = "N/A"
        if eps_q1 != 0:
            eps_growth = f"{round(((eps_q0 - eps_q1) / abs(eps_q1)) * 100, 1)}%"
        else:
            eps_growth = "0%" if eps_q0 == 0 else "N/A"

        rev_m0, rev_m1, rev_m2, r_growth = "N/A", "N/A", "N/A", "N/A"
        
        try:
            df_rev = dl.taiwan_stock_month_revenue(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
            )
            if df_rev is not None and not df_rev.empty:
                df_rev = df_rev.sort_values('date', ascending=False)
                if len(df_rev) > 0: 
                    rev_m0 = f"{round(df_rev.iloc[0]['revenue'] / 1000):,.0f}"
                if len(df_rev) > 1:
                    r0 = df_rev.iloc[0]['revenue']
                    r1 = df_rev.iloc[1]['revenue']
                    rev_m1 = f"{round(r1 / 1000):,.0f}"
                    r_growth = f"{round(((r0-r1)/r1)*100, 1)}%" if r1 != 0 else "0%"
                if len(df_rev) > 2:
                    rev_m2 = f"{round(df_rev.iloc[2]['revenue'] / 1000):,.0f}"
        except Exception:
            pass 

        return {
            '股票代號': clean_id, 
            '公司名稱': sname, 
            '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, 
            '現金股利': cash_div,
            '股票股利': stock_div,
            '最新季EPS': eps_q0, 
            '上一季EPS': eps_q1, 
            '上上一季EPS': eps_q2,
            '與上一季EPS比較增減(%)': eps_growth,
            '最新一期營收(千元)': rev_m0, 
            '上一期營收(千元)': rev_m1, 
            '上上一期營收(千元)': rev_m2, 
            '與上月比較增減(%)': r_growth,
            '毛利率(%)': round((info.get('grossMargins') or 0) * 100, 1),
            '稅後淨利率(%)': round((info.get('profitMargins') or 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except Exception as e:
        return None

# --- 4. 獲取名單與 Excel 轉換 ---
@st.cache_data(ttl=86400)
def get_base_stock_list():
    try:
        dl = DataLoader()
        dl.login_by_token(api_token=FINMIND_TOKEN)
        df_info = dl.taiwan_stock_info()
        
        if df_info is None or df_info.empty:
            st.warning("⚠️ 無法從 FinMind 取得股票清單。")
            return []
            
        df_info = df_info[df_info['type'] == 'twse']
        df_info = df_info.drop_duplicates(subset=['stock_id'])
        
        return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(500).iterrows()]
    except Exception as e:
        return []

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- 5. 主流程 (智慧判斷是否需要重新抓取) ---
def process_data(force_update=False):
    need_update = force_update
    cached_df = pd.DataFrame()
    
    if not force_update and os.path.exists(LOCAL_CACHE_FILE):
        try:
            cached_df = pd.read_csv(LOCAL_CACHE_FILE, dtype={'股票代號': str})
            cached_df = cached_df.fillna("N/A")
            
            if not cached_df.empty and '更新日期' in cached_df.columns:
                last_update_str = str(cached_df['更新日期'].iloc[0])
                last_update_date = datetime.strptime(last_update_str, '%Y-%m-%d').date()
                target_date = get_recent_10th_date()
                
                if last_update_date < target_date:
                    need_update = True
                    st.info(f"💡 系統偵測到需要更新 (上次更新: {last_update_str}，應更新基準: {target_date})，將自動擷取最新資料。")
                else:
                    st.success(f"⚡ 已瞬間載入本地儲存的資料 (最後更新: {last_update_str})，無需消耗 API 額度！")
            else:
                need_update = True
        except Exception:
            need_update = True

    if need_update:
        base_list = get_base_stock_list()
        if not base_list:
            st.error("目前無法獲取股票名單，請稍後再試。")
            return pd.DataFrame()
            
        with st.status("🔍 正在抓取 500 檔備胎數據，以確保能完美篩選出 300 強 (預計需耐心等待 5~8 分鐘)...", expanded=True) as status:
            new_df = get_all_stock_data_v5(base_list)
            
            if not new_df.empty:
                new_df = new_df.drop_duplicates(subset=['股票代號'])
                new_df = new_df.sort_values(by='現金殖利率(%)', ascending=False)
                
                new_df = new_df.head(300)
                
                new_df.to_csv(LOCAL_CACHE_FILE, index=False, encoding='utf-8-sig')
                status.update(label=f"✅ 新資料分析並儲存完成！成功鎖定 {len(new_df)} 檔股票。", state="complete")
                return new_df
            else:
                status.update(label="❌ 抓取失敗", state="error")
                return pd.DataFrame()
    else:
        return cached_df

# --- 6. 介面呈現 ---
with st.sidebar:
    st.info("💡 系統預設：開啟網頁自動顯示快取。每月 10 號會自動上網更新。")
    force_update = st.button('🔄 強制重新抓取 (無視 10 號限制)')

normal_update = st.button('🚀 載入 / 更新 300 強數據分析')

full_df = process_data(force_update=force_update)

if not full_df.empty:
    st.download_button(
        label=f"📥 下載完整前 {len(full_df)} 強個股財報 Excel",
        data=to_excel(full_df),
        file_name=f"Taiwan_Top300_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
