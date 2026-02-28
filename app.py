# B. 殖利率與配息 (優化：區分現金與股票股利)
        div_history = stock.dividends
        last_year_divs = div_history[div_history.index >= (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')]
        
        # 現金股利：通常 yfinance 的 dividends 主要紀錄現金
        cash_div = round(last_year_divs.sum(), 2) if not last_year_divs.empty else 0.0
        
        # 股票股利：從 info 中嘗試取得 (yfinance 有時定義為淨利分配中的 stock split 或特定欄位)
        # 若 info 抓不到，預設為 0.0
        stock_div = info.get('stockDividendValue', 0.0) 
        if stock_div is None: stock_div = 0.0

        # ... (中間營收抓取邏輯不變) ...

        return {
            '股票代號': clean_id, 
            '公司名稱': sname, 
            '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, 
            '現金股利': cash_div,       # 已更名
            '股票股利': stock_div,     # 新增欄位，位置在現金股利右邊
            '最新季EPS': round(info.get('trailingEps', 0), 2),
            '最新一期營收(千元)': rev_m0, 
            '前一期營收(千元)': rev_m1, 
            '前二期營收(千元)': rev_m2,
            '與上月比較增減(%)': m_growth, 
            '最新一季營收(千元)': rev_q0, 
            '上一季營收(千元)': rev_q1, 
            '與上季比較增減(%)': q_growth, 
            '毛利率(%)': round(info.get('grossMargins', 0) * 100, 1),
            '營業利益率(%)': round(info.get('operatingMargins', 0) * 100, 1),
            '稅後淨利率(%)': round(info.get('profitMargins', 0) * 100, 1),
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
