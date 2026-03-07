# --- 優化後的 Altair 圖表區塊 ---
st.divider()
st.subheader("📊 前 20 名殖利率視覺化 (優化版)")

# 確保數據類型正確
display_df['現金殖利率(%)'] = pd.to_numeric(display_df['現金殖利率(%)'], errors='coerce')

chart = alt.Chart(display_df).mark_bar(
    color='#FF4B4B',
    cornerRadiusTopLeft=3,
    cornerRadiusTopRight=3
).encode(
    x=alt.X('公司名稱:N', sort='-y', title='公司名稱', axis=alt.Axis(labelAngle=-45)),
    y=alt.Y('現金殖利率(%):Q', scale=alt.Scale(domain=[0, display_df['現金殖利率(%)'].max() + 2]), title='現金殖利率 (%)'),
    tooltip=['股票代號', '公司名稱', '現金殖利率(%)', '目前股價'],
    color=alt.condition(
        alt.datum['現金殖利率(%)'] >= 5, # 殖利率大於 5% 顯示深色
        alt.value('#FF4B4B'),
        alt.value('#FFAAAA')
    )
).properties(
    height=450
).configure_view(
    strokeWidth=0
)

st.altair_chart(chart, use_container_width=True)
