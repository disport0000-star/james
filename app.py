# ==========================================
# 📈 後台獨立爬蟲：全台股多因子財務數據擷取腳本
# 支援功能：完整三季EPS、三個月營收原始額、本益比自動計算
# ==========================================
import yfinance as yf
import pandas as pd
from FinMind.data import DataLoader
from datetime import datetime, timedelta
import concurrent.futures
import time
import random

FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0wNyAxNTowNToyNiIsInVzZXJfaWQiOiJqYW1lc2FjZTA4IiwiZW1haWwiOiJkaXNwb3J0YWNlQHlhaG9vLmNvbS50dyIsImlwIjoiMTExLjI1NS4xMTAuNDkifQ.FLkCVK6j0S6TfgAI-_hAhaa3i11pmwlntZZP2X1RiIs"

print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🚀 數據引擎啟動...")

def get_all_taiwan_stocks():
    try:
        dl = DataLoader()
        dl.login_by_token(api_token=FINMIND_TOKEN)
        df_info = dl.taiwan_stock_info()
        if df_info is None or df_info.empty: return []
        df_info = df_info[df_info['type'].isin(['twse', 'tpex'])]
        is_four_digits = df_info['stock_id'].astype(str).str.len() == 4
        is_numeric = df_info['stock_id'].astype(str).str.isnumeric()
        df_info = df_info[is_four_digits & is_numeric].drop_duplicates(subset=['stock_id'])
        # 預設抓取前 500 檔進行高效分析，若要全抓取可改為 df_info.iterrows()
        return [[row['stock_id'], row['stock_name']] for _, row in df_info.head(500).iterrows()]
    except Exception as e:
        print(f"獲取名單失敗: {e}")
        return []

def fetch_single_stock(sid, sname):
    time.sleep(random.uniform(0.5, 1.5)) 
    clean_id = str(sid)
    full_sid = f"{clean_id}.TW" 
    dl = DataLoader()
    dl.login_by_token(api_token=FINMIND_TOKEN)
    
    try:
        stock = yf.Ticker(full_sid)
        info = stock.info
        curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
        
        if curr_price == 0: 
            full_sid = f"{clean_id}.TWO"
            stock = yf.Ticker(full_sid)
            info = stock.info
            curr_price = info.get('currentPrice') or info.get('regularMarketPrice', 0)
            if curr_price == 0: return None

        # 1. 現金與股票股利 (去年日曆年總和)
        cash_div, stock_div = 0.0, 0.0
        try:
            df_div = dl.taiwan_stock_dividend(stock_id=clean_id, start_date=(datetime.now() - timedelta(days=730)).strftime('%Y-%m-%d'))
            if df_div is not None and not df_div.empty:
                df_div['year'] = pd.to_datetime(df_div['date']).dt.year
                last_year_data = df_div[df_div['year'] == (datetime.now().year - 1)]
                if not last_year_data.empty:
                    cash_div = round(pd.to_numeric(last_year_data['cash_dividend'], errors='coerce').sum(), 2)
                    stock_div = round(pd.to_numeric(last_year_data['stock_dividend'], errors='coerce').sum(), 2)
        except Exception: pass 
            
        calc_yield = round((cash_div / curr_price * 100), 2) if cash_div > 0 else 0.0

        # 2. 本益比計算 (使用目前股價 / 近四季總EPS)
        trailing_eps = info.get('trailingEps') or 0
        pe_ratio = round(curr_price / trailing_eps, 2) if trailing_eps > 0 else 0.0

        # 3. 擷取連續三季的季 EPS 原始數值
        eps_q0, eps_q1, eps_q2 = 0.0, 0.0, 0.0
        q_fin = stock.quarterly_financials
        if not q_fin.empty and 'Diluted EPS' in q_fin.index:
            eps_series = q_fin.loc['Diluted EPS'].dropna()
            if len(eps_series) > 0: eps_q0 = round(float(eps_series.iloc[0]), 2)
            if len(eps_series) > 1: eps_q1 = round(float(eps_series.iloc[1]), 2)
            if len(eps_series) > 2: eps_q2 = round(float(eps_series.iloc[2]), 2)
        else:
            eps_q0 = round(trailing_eps, 2)

        # 4. 擷取連續三個月的月營收原始數值 (不進行字串格式化，保留數字以便篩選)
        rev_m0, rev_m1, rev_m2 = 0, 0, 0
        try:
            df_rev = dl.taiwan_stock_month_revenue(stock_id=clean_id, start_date=(datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d'))
            if df_rev is not None and not df_rev.empty:
                df_rev = df_rev.sort_values('date', ascending=False)
                if len(df_rev) > 0: rev_m0 = int(df_rev.iloc[0]['revenue'])
                if len(df_rev) > 1: rev_m1 = int(df_rev.iloc[1]['revenue'])
                if len(df_rev) > 2: rev_m2 = int(df_rev.iloc[2]['revenue'])
        except Exception: pass 

        print(f"  ✅ 成功解析: {clean_id} {sname}")
        return {
            '股票代號': clean_id, '公司名稱': sname, '目前股價': curr_price,
            '現金殖利率(%)': calc_yield, '現金股利': cash_div, '股票股利': stock_div, '本益比': pe_ratio,
            '最新季EPS': eps_q0, '上一季EPS': eps_q1, '上上一季EPS': eps_q2,
            '最新月營收': rev_m0, '上月營收': rev_m1, '上上月營收': rev_m2,
            '更新日期': datetime.now().strftime('%Y-%m-%d')
        }
    except Exception:
        return None

def main():
    base_list = get_all_taiwan_stocks()
    if not base_list: return
    final_results = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(fetch_single_stock, s[0], s[1]) for s in base_list]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: final_results.append(res)
                
    if final_results:
        df = pd.DataFrame(final_results).drop_duplicates(subset=['股票代號'])
        file_name = f"全台股多因子財報_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        df.to_excel(file_name, index=False, engine='openpyxl')
        print(f"\n🎉 大功告成！高階 Excel 數據已產出：【{file_name}】")

if __name__ == "__main__":
    main()
