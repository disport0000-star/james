# --- 新增功能：自定義條件篩選區 ---
st.divider()
st.subheader("🎯 自定義精選：高成長+高殖利率篩選")

# 檢查是否有資料源 (優先使用上傳的 full_df)
if not full_df.empty:
    with st.expander("展開篩選條件設定", expanded=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            min_yield = st.number_input("最低殖利率要求 (%)", value=7.0, step=0.5)
        with col_f2:
            st.write("營收條件：近三個月營收連續成長 (系統自動判定)")

    # 開始篩選邏輯
    try:
        # 1. 殖利率篩選
        filter_df = full_df.copy()
        filter_df['現金殖利率(%)'] = pd.to_numeric(filter_df['現金殖利率(%)'], errors='coerce')
        condition_yield = filter_df['現金殖利率(%)'] >= min_yield
        
        # 2. 近三個月營收成長篩選 (比較 最新 vs 上一期 vs 上上期)
        # 注意：原程式中營收是字串(含逗號)，需要轉換為數值
        def clean_revenue(x):
            if isinstance(x, str):
                return float(x.replace(',', ''))
            return float(x)

        filter_df['r0'] = filter_df['最新一期營收(千元)'].apply(clean_revenue)
        filter_df['r1'] = filter_df['上一期營收(千元)'].apply(clean_revenue)
        filter_df['r2'] = filter_df['上上一期營收(千元)'].apply(clean_revenue)
        
        # 條件：最新 > 上一期 且 上一期 > 上上期 (連兩月成長，涵蓋三個月趨勢)
        condition_revenue = (filter_df['r0'] > filter_df['r1']) & (filter_df['r1'] > filter_df['r2'])
        
        # 執行複合篩選
        final_selection = filter_df[condition_yield & condition_revenue].copy()
        
        # 排序並取前 20 名 (依殖利率排序)
        final_selection = final_selection.sort_values(by='現金殖利率(%)', ascending=False).head(20)
        
        # 移除輔助運算欄位後顯示
        display_cols = ['股票代號', '公司名稱', '目前股價', '現金殖利率(%)', '最新一期營收(千元)', '與上月比較增減(%)', '最新季EPS']
        
        if not final_selection.empty:
            st.success(f"✅ 找到 {len(final_selection)} 檔符合條件之個股")
            st.dataframe(final_selection[display_cols], use_container_width=True, hide_index=True)
        else:
            st.warning("查無符合條件之個股，請嘗試放寬篩選標準。")
            
    except Exception as e:
        st.error(f"篩選運算錯誤：{e}。請確保 Excel 欄位格式正確。")
else:
    st.info("請先上傳 Excel 檔案以啟用自定義篩選功能。")
