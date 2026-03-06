# --- 修改後的核心抓取邏輯 ---

@st.cache_data(ttl=3600)
def get_top_100_by_market_cap():
    """修正版：直接在初始化時帶入 Token 或不使用 login_token"""
    # 方式 A：目前大多數版本建議直接初始化
    dl = DataLoader() 
    # 如果版本要求 token，請改用：dl = DataLoader(token=FINMIND_TOKEN)
    
    # 抓取清單
    df_info = dl.taiwan_stock_info()
    
    # 過濾上市普通股
    df_info = df_info[(df_info['type'] == 'twse') & (df_info['stock_id'].str.len() == 4)]
    
    # 由於 FinMind 免費版 API 有流量限制，我們先取前 120 支來分析
    base_list = [[row['stock_id'], row['stock_name']] for _, row in df_info.head(120).iterrows()]
    return base_list

def fetch_stock_details(sid, sname):
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW"
    
    # 修正點：移除 dl.login_token，因為 yfinance 不需要 FinMind Token
    # 只有在使用 FinMind 抓取營收/財報時才需要 dl
    
    try:
        stock = yf.Ticker(full_sid)
        # 使用 fast_info 獲取基本價格 (效能較佳)
        info = stock.info
        
        # 檢查資料是否成功抓取
        if not info or 'currentPrice' not in info:
            return None

        curr_price = info.get('currentPrice', 0)
        market_cap = info.get('marketCap', 0)
        
        # ... (其餘邏輯保持不變) ...
