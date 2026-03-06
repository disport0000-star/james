# --- [V1 修正版] 獲取全市場三大法人數據 (對齊億元單位) ---
def get_institutional_investor_data():
    import requests
    url = "https://api.finmindtrade.com/api/v4/data"
    # 抓取最近 10 天確保包含交易日
    start_str = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
    
    params = {
        "dataset": "TaiwanStockTotalInstitutionalInvestors",
        "start_date": start_str,
        "token": FINMIND_TOKEN
    }
    
    try:
        # 直接向伺服器拿資料，不透過可能會報錯的 DataLoader 物件方法
        resp = requests.get(url, params=params)
        data = resp.json()
        
        if data.get("msg") == "success" and data.get("data"):
            df = pd.DataFrame(data["data"])
            latest_date = df['date'].max()
            current_df = df[df['date'] == latest_date].copy()
            
            # 單位轉換：元 -> 億 (除以 10^8)
            # 這樣外資買賣超就會出現像 -352.00 這種正確的億元數字
            current_df['買進(億)'] = (current_df['buy'] / 100000000).round(2)
            current_df['賣出(億)'] = (current_df['sell'] / 100000000).round(2)
            current_df['買賣超(億)'] = (current_df['diff'] / 100000000).round(2)
            
            # 中文名稱對應
            name_map = {
                'Foreign_Investor': '外資',
                'Investment_Trust': '投信',
                'Dealer_Self': '自營商自行買賣',
                'Dealer_Hedging': '自營商避險',
                'Foreign_Dealer_Self': '外資自營商'
            }
            current_df['身分別'] = current_df['name'].map(name_map).fillna(current_df['name'])
            
            return current_df[['身分別', '買進(億)', '賣出(億)', '買賣超(億)']], latest_date
    except:
        return None, "API 連線失敗，請檢查網路或 Token"
    return None, "查無數據"
