# ==========================================
# 📈 台股精選 300 強財務監控 - V1.99 智慧月更版 (黃金現貨修復)
# 更新重點：替換 TradingView 代碼為 OANDA:XAUUSD (黃金現貨)，解除嵌入限制
# ==========================================
import streamlit as st
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import io
import streamlit.components.v1 as components
import os

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 300 強監控", layout="wide")
st.title("📈 台股市值前 300 強財務監控")

# 您的 FinMind 金鑰
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNyAxNTowNToyNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMTExLjI1NS4xMTAuNDkifQ.FLkCVK6j0S6TfgAI-_hAhaa3i11pmwlntZZP2X1RiIs"

st.write(f"系統狀態：V1.99 智慧月更版 (目前時間: {datetime.now().strftime('%H:%M:%S')})")

LOCAL_CACHE_FILE = "taiwan_top300_cache_v1_99.csv"

# --- 2. 核心邏輯：每月 15 號時間鎖 ---
def get_target_update_date():
    """取得最近一次應該更新的日期 (每月 15 號)"""
    now = datetime.now()
    if now.day >= 15:
        return datetime(now.year, now.month, 15).date()
    else:
        if now.month == 1:
            return datetime(now.year - 1, 12, 15).date()
        else:
            return datetime(now.year, now.month - 1, 15).date()

# --- 3. 雲端抓取爬蟲 (加入防封鎖延遲) ---
@st.cache_data(ttl=3600)
def get_all_stock_data(base_list):
    final_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
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
            df_div = dl.taiwan_stock_dividend(stock_id=clean_id, start_date=(datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d'))
            if df_div is not None and not df_div.empty:
                df_div = df_div.sort_values('date', ascending=False)
                if 'stock_dividend' in df_div.columns:
                    stock_div = round(float(df_div.iloc[0]['stock_dividend']), 2)
        except Exception: pass 

        eps_q0 = round(info.get('trailingEps', 0), 2)

        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '現金股利': cash_div, '股票股利': stock_div,
            '最新季EPS': eps_q0, '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except Exception: return None

# --- 4. 獲取台股 4 碼純數字名單 ---
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
        df_info = df_info[is_four_digits & is_numeric].drop_duplicates(subset=['stock_id'])
        return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(400).iterrows()] 
    except Exception: return []

def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- 5. 智慧判斷與主流程 ---
def process_data(force_update=False):
    need_update = force_update
    cached_df = pd.DataFrame()
    target_date = get_target_update_date()
    
    if not force_update and os.path.exists(LOCAL_CACHE_FILE):
        try:
            cached_df = pd.read_csv(LOCAL_CACHE_FILE, dtype={'股票代號': str})
            cached_df = cached_df.fillna("N/A")
            
            if not cached_df.empty and '更新日期' in cached_df.columns:
                last_update_str = str(cached_df['更新日期'].iloc[0])
                last_update_date = datetime.strptime(last_update_str, '%Y-%m-%d').date()
                
                if last_update_date < target_date:
                    need_update = True
                    st.info(f"💡 系統偵測：上次更新為 {last_update_str}，已跨過本月 15 號 ({target_date})，將自動執行雲端抓取。")
                else:
                    st.success(f"⚡ 系統偵測：資料為最新狀態 (最後更新: {last_update_str})，無需消耗額度重新抓取！")
            else:
                need_update = True
        except Exception:
            need_update = True
    else:
        if not force_update:
            need_update = True
            st.info("💡 系統偵測：雲端暫存已重置，啟動自動復原抓取作業...")

    if need_update:
        base_list = get_base_stock_list()
        if not base_list: return pd.DataFrame()
        with st.status("🔍 正在透過雲端自動更新最新財務數據 (預計需要 3~5 分鐘)...", expanded=True) as status:
            new_df = get_all_stock_data(base_list)
            if not new_df.empty:
                new_df = new_df.drop_duplicates(subset=['股票代號']).sort_values(by='現金殖利率(%)', ascending=False).head(300)
                new_df.to_csv(LOCAL_CACHE_FILE, index=False, encoding='utf-8-sig')
                status.update(label=f"✅ 更新完成！成功儲存至本月 15 號週期。", state="complete")
                return new_df
            else:
                status.update(label="❌ 抓取失敗：雲端 IP 暫時被封鎖，請使用左側『專家模式』匯入本地 Excel。", state="error")
                return cached_df if not cached_df.empty else pd.DataFrame()
    else:
        return cached_df

# --- 6. 側邊欄：專家保底匯入介面 ---
with st.sidebar:
    st.markdown("### 🔌 專家保底模式：匯入本地資料")
    st.info("💡 如果雲端自動更新被 Yahoo 阻擋，您可以手動將 VS Code 產出的 Excel 拖曳到下方！")
    
    uploaded_file = st.file_uploader("📂 上傳全台股 Excel", type=['xlsx'])
    if uploaded_file is not None:
        try:
            df_uploaded = pd.read_excel(uploaded_file, dtype={'股票代號': str})
            df_top300 = df_uploaded.sort_values(by='現金殖利率(%)', ascending=False).head(300)
            df_top300.to_csv(LOCAL_CACHE_FILE, index=False, encoding='utf-8-sig')
            st.success("✅ 資料匯入成功！系統將以此檔案作為本月快取。請點擊下方按鈕重啟。")
        except Exception as e:
            st.error(f"檔案讀取失敗：{e}")

    st.divider()
    force_update = st.button('🔄 無視日期：強制重新抓取')
    if st.button('🧹 清除快取並重啟網頁'):
        st.cache_data.clear()
        st.rerun()

# --- 7. 主畫面呈現 (台股 300 強) ---
full_df = process_data(force_update=force_update)

if not full_df.empty:
    st.download_button(
        label=f"📥 下載前 {len(full_df)} 強財報 Excel",
        data=to_excel(full_df),
        file_name=f"Taiwan_Top300_{datetime.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    st.subheader("💰 台股現金殖利率前 40 名")
    display_df = full_df.head(40).reset_index(drop=True)
    st.dataframe(display_df, use_container_width=True, hide_index=True)
else:
    st.error("分析結果為空。由於雲端主機休眠重置且自動抓取受阻，請由左側邊欄上傳您的 Excel 檔案進行保底復原！")

# ==========================================
# 🌟 全新模塊：總經雙指標 (TradingView 現貨黃金 + 國發會燈號連結)
# ==========================================
st.divider()
st.subheader("🌍 總經戰情室：景氣循環與資金流向")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 🟡 近一年黃金價格走勢 (現貨 XAU/USD)")
    # 將期貨 COMEX:GC1! 替換為完全公開允許嵌入的外匯現貨 OANDA:XAUUSD
    tv_widget_html = """
    <div class="tradingview-widget-container" style="height: 350px; width: 100%;">
      <div id="tradingview_gold" style="height: calc(100% - 32px); width: 100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {
      "autosize": true,
      "symbol": "OANDA:XAUUSD",
      "interval": "D",
      "timezone": "Asia/Taipei",
      "theme": "dark",
      "style": "2",
      "locale": "zh_TW",
      "enable_publishing": false,
      "backgroundColor": "rgba(0, 0, 0, 0)",
      "hide_top_toolbar": true,
      "hide_legend": true,
      "save_image": false,
      "container_id": "tradingview_gold",
      "lineColor": "#FFD700",
      "topColor": "rgba(255, 215, 0, 0.3)",
      "bottomColor": "rgba(255, 215, 0, 0.0)"
    }
      );
      </script>
    </div>
    """
    components.html(tv_widget_html, height=360)
    st.caption("📈 資料來源：TradingView 官方即時現貨數據")

with col2:
    st.markdown("#### 🚦 台灣景氣對策信號")
    st.info("💡 掌握官方即時燈號與景氣分數，請前往國發會網站。")
    st.markdown("**(紅燈：熱絡 / 綠燈：穩定 / 藍燈：低迷)**")
    
    st.write("") 
    st.link_button(
        label="👉 點擊前往【國發會景氣指標查詢系統】查看最新燈號",
        url="https://index.ndc.gov.tw/n/zh_tw",
        use_container_width=True
    )
    st.caption("💡 官方數據通常於每月 27 號左右更新上個月數據。")
