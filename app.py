@st.cache_data(ttl=3600)
def get_gold_trend():
    try:
        gold = yf.Ticker("GC=F")
        df_gold = gold.history(period="1y")
        if not df_gold.empty:
            df_gold = df_gold.reset_index()
            df_gold['Date'] = pd.to_datetime(df_gold['Date']).dt.date
            return df_gold[['Date', 'Close']]
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=86400)
def get_taiwan_economic_light():
    try:
        # 呼叫國發會 (NDC) 官方 Open Data API
        url = "https://od.ndc.gov.tw/api/v1/rest/datastore/A53000000A-000009"
        res = requests.get(url, timeout=10)
        data = res.json()
        
        if data.get('success'):
            records = data['result']['records']
            df = pd.DataFrame(records)
            
            # 整理國發會的欄位
            df = df[['年月', '景氣對策信號綜合分數', '景氣對策信號檢查值']].copy()
            df.columns = ['Date', 'Score', 'Light']
            
            # 轉換日期格式
            df['Date'] = df['Date'].astype(str).apply(lambda x: f"{x[:4]}/{x[4:]}")
            df['Score'] = pd.to_numeric(df['Score'], errors='coerce')
            df = df.dropna()
            
            # 取最近 24 個月的數據
            df = df.tail(24).reset_index(drop=True)
            return df
    except Exception as e:
        print(f"Fetch Economic Light Error: {e}")
    return pd.DataFrame()
