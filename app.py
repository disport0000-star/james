# V3 優化：營收三期對比 (最新、上月、上上月)
        rev_m0, rev_m1, rev_m2, r_growth = "N/A", "N/A", "N/A", "N/A"
        try:
            # 抓取 120 天確保有足夠樣本
            df_rev = dl.taiwan_stock_month_revenue(
                stock_id=clean_id, 
                start_date=(datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
            )
            if not df_rev.empty and len(df_rev) >= 3:
                df_rev = df_rev.sort_values('date', ascending=False)
                
                # 取得三期數值 (單位：千元)
                r0 = df_rev.iloc[0]['revenue']
                r1 = df_rev.iloc[1]['revenue']
                r2 = df_rev.iloc[2]['revenue']
                
                rev_m0 = f"{round(r0 / 1000):,.0f}" # 本月
                rev_m1 = f"{round(r1 / 1000):,.0f}" # 上月
                rev_m2 = f"{round(r2 / 1000):,.0f}" # 上上月
                
                # 計算最新一期的月增率
                if r1 > 0:
                    r_growth = f"{round(((r0-r1)/r1)*100, 1)}%"
        except:
            pass

        # 在回傳的 Dictionary 中新增欄位
        return {
            '股票代號': clean_id, 
            '公司名稱': sname, 
            '目前股價': curr_price,
            '現金殖利率(%)': calc_yield,
            '最新季EPS': eps_q0,
            '最新營收(千元)': rev_m0,
            '上月營收(千元)': rev_m1,     # 新增欄位
            '上上月營收(千元)': rev_m2,   # 新增欄位
            '營收月增率': r_growth,
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
