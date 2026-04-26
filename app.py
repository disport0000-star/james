# ==========================================
# 📈 台股精選 300 強財務監控 - V1.97 零死角全互動版
# 更新重點：捨棄後端爬蟲，導入 TradingView 前端微服務，100% 免疫防火牆
# ==========================================
import streamlit as st
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components
import io
import altair as alt
import os

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="台股精選 300 強監控", layout="wide")
st.title("📈 台股市值前 300 強財務監控")

st.write(f"系統狀態：V1.97 零死角全互動版 (目前時間: {datetime.now().strftime('%H:%M:%S')})")

LOCAL_CACHE_FILE = "taiwan_top300_cache_v1_97.csv"

# --- 2. 輔助函數：Excel 下載 ---
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- 3. 側邊欄：專家匯入介面 ---
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
    if st.button('🧹 清除快取並重啟網頁'):
        st.cache_data.clear()
        st.rerun()

# --- 4. 主畫面呈現 (台股 300 強) ---
if os.path.exists(LOCAL_CACHE_FILE):
    full_df = pd.read_csv(LOCAL_CACHE_FILE, dtype={'股票代號': str})
    full_df = full_df.fillna("N/A")
    
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
    st.error("分析結果為空。請由左側邊欄上傳您在 VS Code 抓取好的 Excel 檔案！")

# ==========================================
# 🌟 全新模塊：總經雙指標 (TradingView 黃金 + 國發會燈號連結)
# ==========================================
st.divider()
st.subheader("🌍 總經戰情室：景氣循環與資金流向")

col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 🟡 近一年黃金期貨走勢 (紐約 COMEX)")
    
    # 【核心破解】使用 TradingView 前端微服務，直接由使用者的瀏覽器去抓資料
    # 絕對不會被 Streamlit Cloud 的 IP 防火牆阻擋！
    tv_widget_html = """
    <div class="tradingview-widget-container" style="height: 350px; width: 100%;">
      <div id="tradingview_gold" style="height: calc(100% - 32px); width: 100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {
      "autosize": true,
      "symbol": "COMEX:GC1!",
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
    
    # 嵌入 HTML 小工具
    components.html(tv_widget_html, height=360)
    st.caption("📈 資料來源：TradingView 官方即時數據")

with col2:
    st.markdown("#### 🚦 台灣景氣對策信號")
    st.info("💡 掌握官方即時燈號與景氣分數，請前往國發會網站。")
    st.markdown("**(紅燈：熱絡 / 綠燈：穩定 / 藍燈：低迷)**")
    
    st.write("") 
    st.link_button(
        label="👉 點擊前往【國發會】查看最新景氣燈號",
        url="https://www.ndc.gov.tw/Content_List.aspx?n=275A4EA8B860FEBB",
        use_container_width=True
    )
    st.caption("💡 官方數據通常於每月 27 號左右更新上個月數據。")
