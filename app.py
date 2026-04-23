# ==========================================
# 🎯 新增功能：自定義篩選 (連 3 月營收成長 + 殖利率 > 7%)
# 放置位置：請確保放在主程式最下方
# ==========================================

# 1. 檢查 streamlit 是否已定義，以及 full_df 是否有資料
if 'st' in globals() and 'full_df' in locals() and not full_df.empty:
    st.divider()
    st.subheader("🎯 自定義精選：營收連增 + 高殖利率 (前20名)")

    # 讓使用者微調條件
    with st.expander("🔍 篩選條件說明與設定", expanded=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            target_yield = st.number_input("最低殖利率要求 (%)", value=7.0, step=0.5)
        with col_f2:
            st.write("營收成長判定：")
            st.caption("最新營收 > 上月營收 > 上上月營收")

    try:
        # 複製一份資料進行運算，避免破壞原始表格
        dff = full_df.copy()

        # 數值轉換函數：處理字串中的逗號並轉為數字
        def to_num(val):
            if isinstance(val, str):
                val = val.replace(',', '')
            try:
                return float(val)
            except:
                return 0.0

        # 處理殖利率 (確保是數字)
        dff['現金殖利率(%)'] = pd.to_numeric(dff['現金殖利率(%)'], errors='coerce').fillna(0)

        # 處理三個月營收資料
        dff['r0'] = dff['最新一期營收(千元)'].apply(to_num)
        dff['r1'] = dff['上一期營收(千元)'].apply(to_num)
        dff['r2'] = dff['上上一期營收(千元)'].apply(to_num)

        # 條件篩選
        # A. 殖利率門檻
        cond_yield = dff['現金殖利率(%)'] >= target_yield
        # B. 營收連三月成長 (M0 > M1 且 M1 > M2)
        cond_growth = (dff['r0'] > dff['r1']) & (dff['r1'] > dff['r2'])

        # 執行複合篩選
        final_selection = dff[cond_yield & cond_growth].copy()

        # 排序並取前 20 名
        final_selection = final_selection.sort_values(by='現金殖利率(%)', ascending=False).head(20)

        if not final_selection.empty:
            st.success(f"✅ 篩選完成！共有 {len(final_selection)} 檔符合條件")
            # 整理顯示欄位
            display_cols = ['股票代號', '公司名稱', '目前股價', '現金殖利率(%)', '最新一期營收(千元)', '與上月比較增減(%)']
            st.dataframe(final_selection[display_cols], use_container_width=True, hide_index=True)
        else:
            st.warning(f"目前沒有個股同時符合「殖利率 > {target_yield}%」且「營收連續成長」。")

    except Exception as e:
        st.error(f"篩選邏輯執行失敗，請檢查資料格式。錯誤訊息: {e}")
else:
    # 如果還沒有資料，顯示導引文字
    if 'st' in globals():
        st.info("💡 尚未載入資料。請由左側上傳 Excel 檔案或執行雲端抓取以啟用精選功能。")
