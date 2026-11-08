import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="個人投資監控站 - 高相容版", layout="wide")

st.title("📈 我的專屬股票監控面板")
st.write(f"系統狀態：本地資料模式 (頁面更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")

# --- 2. 側邊欄：檔案上傳區 ---
st.sidebar.header("📁 數據中心：匯入本地資料")
st.sidebar.info("💡 請將最新產出的「全台股多因子財報 Excel」拖曳到下方！")

uploaded_file = st.sidebar.file_uploader("上傳全能型 Excel", type=["xlsx", "xls"])

if st.sidebar.button("🧹 清除記憶並重啟網頁"):
    st.cache_data.clear()
    st.rerun()

# --- 3. 欄位安全檢查與別名對應函數 ---
def safe_get_column(df, possible_names):
    """
    從可能的名稱清單中找出存在於 df 中的欄位名稱
    """
    for name in possible_names:
        if name in df.columns:
            return name
    return None

# --- 4. 主顯示邏輯 ---
if uploaded_file is not None:
    try:
        # 讀取 Excel 檔案
        df = pd.read_excel(uploaded_file)
        
        # 清除欄位名稱前後的不必要空白
        df.columns = [str(col).strip() for col in df.columns]

        st.success(f"🎉 成功匯入數據！共 {len(df)} 筆個股資料。")

        # -------------------------------------------------------------
        # 欄位對應矩陣 (避免名稱不同導致 KeyError)
        # -------------------------------------------------------------
        col_code = safe_get_column(df, ['股票代號', '代號', 'Ticker', 'stock_id'])
        col_name = safe_get_column(df, ['公司名稱', '名稱', 'Name', 'stock_name'])
        col_price = safe_get_column(df, ['目前股價', '收盤價', '股價', 'Price'])
        col_yield = safe_get_column(df, ['現金殖利率(%)', '殖利率(%)', '殖利率', 'Yield(%)'])
        col_div_cash = safe_get_column(df, ['現金股利', '最新配息金額', '現金股利(元)'])
        col_div_stock = safe_get_column(df, ['股票股利', '股票股利(元)'])
        col_eps = safe_get_column(df, ['最新季EPS', 'EPS', 'EPS(元)'])
        
        col_m_growth = safe_get_column(df, ['與上月比較增減(%)', '營收變動率(%)', '月營收變動率(%)'])
        col_q_growth = safe_get_column(df, ['與上季比較增減(%)', '季營收變動率(%)', '季營收成長率(%)'])
        
        col_gross = safe_get_column(df, ['毛利率(%)', '毛利率', 'Gross Margin(%)'])
        col_op = safe_get_column(df, ['營業利益率(%)', '營業利益率', 'Operating Margin(%)'])
        col_net = safe_get_column(df, ['稅後淨利率(%)', '淨利率(%)', 'Net Margin(%)'])
        col_date = safe_get_column(df, ['更新日期', '日期', 'Date'])

        # -------------------------------------------------------------
        # 表格顯示 (使用安全的點擊排序)
        # -------------------------------------------------------------
        st.info("💡 提示：點擊欄位名稱可直接進行排序，表格支援向右滾動查看完整指標。")
        
        # 如果存在殖利率欄位，預設由高到低排序
        if col_yield and col_yield in df.columns:
            df_display = df.sort_values(by=col_yield, ascending=False)
        else:
            df_display = df

        st.dataframe(df_display, use_container_width=True, hide_index=True)

        # -------------------------------------------------------------
        # 圖表展示 (加入全方位的 KeyError 防護)
        # -------------------------------------------------------------
        st.divider()
        
        # 1. 獲利三率長條圖 (若欄位存在才畫)
        margin_cols = [c for c in [col_gross, col_op, col_net] if c is not None and c in df.columns]
        
        if col_name and margin_cols:
            st.subheader("📊 關鍵獲利能力 (三率) 長條圖對比")
            # 排除純文字或空值的公司名稱
            chart_df = df_display.dropna(subset=[col_name]).set_index(col_name)[margin_cols]
            
            # 將數值轉換為 float 避免繪圖錯誤
            for m_col in margin_cols:
                chart_df[m_col] = pd.to_numeric(chart_df[m_col], errors='coerce').fillna(0)
            
            # 依據第一個三率指標排序
            chart_df = chart_df.sort_values(by=margin_cols[0], ascending=False).head(20)
            st.bar_chart(chart_df)
        
        # 2. 現金殖利率長條圖 (若欄位存在才畫)
        if col_name and col_yield and col_yield in df.columns:
            st.subheader("💰 現金殖利率 (%) 概覽 (前 20 強)")
            yield_df = df_display.dropna(subset=[col_name, col_yield]).set_index(col_name)[[col_yield]]
            yield_df[col_yield] = pd.to_numeric(yield_df[col_yield], errors='coerce').fillna(0)
            yield_df = yield_df.sort_values(by=col_yield, ascending=False).head(20)
            st.bar_chart(yield_df, color="#FF4B4B")

    except Exception as e:
        st.error(f"⚠️ 解析 Excel 檔案時發生錯誤：{str(e)}")
        st.warning("請確認上傳的 Excel 檔案格式與欄位內容是否符合規範。")

else:
    st.info("👈 請點擊左側邊欄上傳 Excel 檔案以開始分析。")
