# ==========================================
# 🎯 新增功能：高成長 + 高殖利率篩選 (修正版)
# ==========================================

# 確保這段程式放在 full_df = process_data(...) 之後
if 'full_df' in locals() and not full_df.empty:
    st.divider()
    st.subheader("🎯 自定義精選：營收連增 + 高殖利率 (前20名)")

    with st.expander("調整篩選標準", expanded=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            target_yield = st.number_input("最低殖利率要求 (%)", value=7.0, step=0.5)
        with col_f2:
            st.info("條件：近三個月營收連續成長 (M0 > M1 > M2)")

    try:
        # 複製一份資料來處理，避免影響原表
        dff = full_df.copy()

        # 數值轉換：處理殖利率 (轉為 float)
        dff['現金殖利率(%)'] = pd.to_numeric(dff['現金殖利率(%)'], errors='coerce').fillna(0)

        # 數值轉換：處理營收 (處理字串中的逗號)
        def clean_rev(val):
            if isinstance(val, str):
                val = val.replace(',', '')
            try:
                return float(val)
            except:
                return 0.0

        dff['r0'] = dff['最新一期營收(千元)'].apply(clean_rev)
        dff['r1'] = dff['上一期營收(千元)'].apply(clean_rev)
        dff['r2'] = dff['上上一期營收(千元)'].apply(clean_rev)

        # 篩選條件 1：殖利率 > 設定值
        cond_yield = dff['現金殖利率(%)'] >= target_yield
        
        # 篩選條件 2：近三個月營收成長 (最新 > 上月 且 上月 > 上上月)
        # 如果你的營收資料是按月份排列，這代表趨勢向上
        cond_growth = (dff['r0'] > dff['r1']) & (dff['r1'] > dff['r2'])

        # 執行篩選
        result_df = dff[cond_yield & cond_growth].copy()

        # 排序並取前 20
        result_df = result_df.sort_values('現金殖利率(%)', ascending=False).head(20)

        if not result_df.empty:
            # 整理顯示欄位
            show_cols = ['股票代號', '公司名稱', '目前股價', '現金殖利率(%)', '最新一期營收(千元)', '與上月比較增減(%)']
            st.success(f"🔥 符合條件個股：共 {len(result_df)} 檔")
            st.dataframe(result_df[show_cols], use_container_width=True, hide_index=True)
        else:
            st.warning("目前沒有股票同時符合「營收連三月成長」且「殖利率 > 7%」的條件。")

    except Exception as e:
        st.error(f"計算篩選時發生錯誤: {e}")
else:
    st.info("💡 尚未載入資料。請先從側邊欄上傳 Excel 或執行雲端抓取。")
