# ==========================================
# 📈 台股精選 300 強財務監控 - V2.0 智慧選股版
# 更新重點：導入三大分頁模組，嵌入 4 大指標複合選股核心篩選器
# ==========================================
import streamlit as st
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components
import io
import os

st.set_page_config(page_title="台股智慧監控與量化選股戰情室", layout="wide")
st.title("📈 台股精選 300 強與量化篩選器")

st.write(f"系統狀態：V2.0 智慧選股版 (目前時間: {datetime.now().strftime('%H:%M:%S')})")

LOCAL_CACHE_FILE = "taiwan_top300_cache_v2_0.csv"

# --- 1. 輔助函數 ---
def to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Data')
    return output.getvalue()

# --- 2. 側邊欄專家匯入 ---
with st.sidebar:
    st.markdown("### 🔌 數據中心：匯入本地資料")
    st.info("💡 請將 VS Code 產出的最新「全台股多因子財報 Excel」拖曳到下方！")
    
    uploaded_file = st.file_uploader("📂 上傳全能型 Excel", type=['xlsx'])
    if uploaded_file is not None:
        try:
            df_uploaded = pd.read_excel(uploaded_file, dtype={'股票代號': str})
            # 自動補零至 4 碼
            df_uploaded['股票代號'] = df_uploaded['股票代號'].str.zfill(4)
            df_uploaded.to_csv(LOCAL_CACHE_FILE, index=False, encoding='utf-8-sig')
            st.success("✅ 多因子數據庫同步完畢！請重啟網頁。")
        except Exception as e:
            st.error(f"檔案讀取失敗：{e}")

    st.divider()
    if st.button('🧹 清除記憶並重啟網頁'):
        st.cache_data.clear()
        st.rerun()

# --- 3. 核心數據處理與分頁架構 ---
if os.path.exists(LOCAL_CACHE_FILE):
    raw_df = pd.read_csv(LOCAL_CACHE_FILE, dtype={'股票代號': str})
    raw_df = raw_df.fillna(0) # 防禦性填空值

    # 建立三個專業分頁
    tab1, tab2, tab3 = st.tabs(["🏆 現金殖利率 300 強", "🔍 潛力股智慧篩選器", "🌍 總經戰情室"])

    # --- TAB 1：傳統強項排行榜 ---
    with tab1:
        df_top300 = raw_df.sort_values(by='現金殖利率(%)', ascending=False).head(300)
        st.download_button(
            label="📥 下載當前 300 強財報 Excel",
            data=to_excel(df_top300),
            file_name=f"Taiwan_Top300_{datetime.now().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.subheader("💰 高殖利率純個股前 40 名")
        st.dataframe(df_top300.head(40), use_container_width=True, hide_index=True)

    # --- TAB 2：全新多因子選股器 ---
    with tab2:
        st.subheader("🎯 多因子量化潛力股篩選")
        st.markdown("系統已自動套用您的智慧篩選濾網：")
        
        # 顯示條件清單
        st.markdown("""
        1. **月營收動能**：最新月營收 > 上月營收 > 上上月營收 📈
        2. **獲利成長性**：最新季 EPS > 上一季 EPS > 上上季 EPS 📈
        3. **估值安全區**：本益比介於 **10 倍至 20 倍** 之間 ⚖️
        4. **高防禦護城河**：現金殖利率 **> 5%** 💰
        """)
        
        # 進行邏輯過濾
        cond_rev = (raw_df['最新月營收'] > raw_df['上月營收']) & (raw_df['上月營收'] > raw_df['上上月營收'])
        cond_eps = (raw_df['最新季EPS'] > raw_df['上一季EPS']) & (raw_df['上一季EPS'] > raw_df['上上一季EPS'])
        cond_pe = (raw_df['本益比'] >= 10) & (raw_df['本益比'] <= 20)
        cond_yield = raw_df['現金殖利率(%)'] > 5.0
        
        # 總過濾結果
        filtered_df = raw_df[cond_rev & cond_eps & cond_pe & cond_yield].copy()
        
        if not filtered_df.empty:
            st.success(f"🎉 偵測成功！全市場共篩選出 **{len(filtered_df)}** 檔完美符合條件的黃金潛力股：")
            
            # 美化呈現欄位
            output_cols = ['股票代號', '公司名稱', '目前股價', '現金殖利率(%)', '本益比', '最新季EPS', '最新月營收']
            st.dataframe(
                filtered_df[output_cols].reset_index(drop=True),
                use_container_width=True,
                hide_index=True
            )
            
            # 額外提供篩選結果的單獨下載按鈕
            st.download_button(
                label="📥 匯出此份潛力股名單",
                data=to_excel(filtered_df[output_cols]),
                file_name=f"量化篩選潛力股_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )
        else:
            st.warning("⚠️ 目前名單中暫時沒有股票同時完美符合這 4 項嚴格條件。建議您可以擴大後台爬蟲掃描範圍（如調整至全市場1700檔），獲取更多基底樣本！")

    # --- TAB 3：總經戰情室 ---
    with tab3:
        st.subheader("🌍 總經戰情室：景氣循環與資金流向")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🟡 近一年黃金價格走勢 (現貨 XAU/USD)")
            tv_widget_html = """
            <div class="tradingview-widget-container" style="height: 350px; width: 100%;">
              <div id="tradingview_gold" style="height: calc(100% - 32px); width: 100%;"></div>
              <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
              <script type="text/javascript">
              new TradingView.widget({"autosize": true, "symbol": "OANDA:XAUUSD", "interval": "D", "timezone": "Asia/Taipei", "theme": "dark", "style": "2", "locale": "zh_TW", "container_id": "tradingview_gold", "lineColor": "#FFD700", "topColor": "rgba(255, 215, 0, 0.3)", "bottomColor": "rgba(255, 215, 0, 0.0)"});
              </script>
            </div>
            """
            components.html(tv_widget_html, height=360)
        with col2:
            st.markdown("#### 🚦 台灣景氣對策信號")
            st.info("💡 掌握官方即時燈號與景氣分數，請前往國發會網站。")
            st.link_button(label="👉 點擊前往【國發會景氣指標查詢系統】", url="https://index.ndc.gov.tw/n/zh_tw", use_container_width=True)

else:
    st.error("分析結果為空。請由左側邊欄上傳最新產出的「多因子財報 Excel」檔案來啟動戰情室！")
