import os
import time
import argparse
import pandas as pd
from datetime import datetime
from vnstock import Finance
from vnstock_qlib.mcalendar import build_calendar
from vnstock_qlib.instruments import build_instruments
from vnstock_qlib.fetcher import fetch_ohlcv
from vnstock_qlib.converter import convert_symbol_data

QLIB_DATA_DIR = os.path.expanduser('~/.qlib/qlib_data/vn_data')
CACHE_DIR = r"D:\Qlib-Vnstock\cache"

def fetch_fundamentals(symbol: str) -> pd.DataFrame:
    """
    Fetch fundamentals (P/E, P/B, ROE, etc) and forward fill to daily frequency.
    Applies a 45-day delay from the end of the quarter to prevent look-ahead bias.
    """
    try:
        finance = Finance(source="kbs", symbol=symbol)
        df_raw = finance.ratio(period="quarter")
        if df_raw is None or df_raw.empty:
            return pd.DataFrame()
            
        # Map item string to short column names
        ITEM_MAP = {
            "Thu nhập trên mỗi cổ phần của 4 quý gần nhất (EPS)": "eps",
            "Giá trị sổ sách của cổ phiếu (BVPS)": "bvps",
            "Chỉ số giá thị trường trên thu nhập (P/E)": "pe",
            "Chỉ số giá thị trường trên giá trị sổ sách (P/B)": "pb",
            "Tỷ suất lợi nhuận trên vốn chủ sở hữu (ROE)": "roe",
            "Tỷ suất sinh lợi trên tổng tài sản (ROA)": "roa"
        }
        
        # Filter supported items
        df = df_raw[df_raw['item'].isin(ITEM_MAP.keys())].copy()
        df['col'] = df['item'].map(ITEM_MAP)
        
        # Drop item/item_id columns to get only quarter columns
        df = df.drop(columns=['item', 'item_id'])
        
        # Melt to long format: (col, quarter, value)
        df = df.melt(id_vars=['col'], var_name='quarter', value_name='value')
        
        # Drop missing values and filter out non-quarter strings like '2025-Q4_1' if any
        df = df.dropna(subset=['value'])
        df = df[df['quarter'].str.match(r'^\d{4}-Q\d$')]
        
        if df.empty:
            return pd.DataFrame()
            
        # Convert quarter "YYYY-QX" to end of quarter date
        # Q1: 03-31, Q2: 06-30, Q3: 09-30, Q4: 12-31
        def q_to_date(q_str):
            y, q = q_str.split('-Q')
            q_end_dates = {'1': '03-31', '2': '06-30', '3': '09-30', '4': '12-31'}
            return f"{y}-{q_end_dates[q]}"
            
        df['report_date'] = df['quarter'].apply(q_to_date)
        df['report_date'] = pd.to_datetime(df['report_date'])
        
        # Apply 45 days delay for look-ahead bias
        df['release_date'] = df['report_date'] + pd.Timedelta(days=45)
        
        # Pivot back to wide format: index=release_date, columns=eps, pe, etc.
        df_wide = df.pivot(index='release_date', columns='col', values='value').sort_index()
        
        # Forward fill to daily frequency up to current date
        # Create a daily date range from the first release_date to today
        min_date = df_wide.index.min()
        max_date = pd.to_datetime('today')
        daily_idx = pd.date_range(start=min_date, end=max_date, freq='D')
        
        df_daily = df_wide.reindex(daily_idx).ffill().reset_index()
        df_daily = df_daily.rename(columns={'index': 'date'})
        df_daily['date'] = df_daily['date'].dt.strftime('%Y-%m-%d')
        
        return df_daily
        
    except Exception as e:
        print(f"Warning: Failed to fetch fundamentals for {symbol}: {e}")
        return pd.DataFrame()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--universe', type=str, default='vn30', choices=['vn30', 'vn100', 'all'])
    args = parser.parse_args()
    
    os.makedirs(QLIB_DATA_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    
    print("1. Building calendar...")
    calendar_path = os.path.join(QLIB_DATA_DIR, 'calendars', 'day.txt')
    calendar_dates = build_calendar(calendar_path)
    
    print("2. Building instruments...")
    instruments_dir = os.path.join(QLIB_DATA_DIR, 'instruments')
    build_instruments(instruments_dir)
    
    universe_file = os.path.join(instruments_dir, f"{args.universe}.txt")
    if not os.path.exists(universe_file):
        raise FileNotFoundError(f"Universe file not found: {universe_file}")
        
    with open(universe_file, 'r', encoding='utf-8') as f:
        symbols = [line.split('\t')[0].strip() for line in f if line.strip()]
    
    print(f"3. Fetching and converting data for {len(symbols)} symbols in {args.universe}...")
    
    features_dir = os.path.join(QLIB_DATA_DIR, 'features')
    os.makedirs(features_dir, exist_ok=True)
    
    success_count = 0
    error_count = 0
    
    start_time = time.time()
    
    for i, symbol in enumerate(symbols):
        try:
            print(f"[{i+1}/{len(symbols)}] Processing {symbol}...")
            # Cập nhật end_date tự động đến hôm nay để hỗ trợ auto-run
            today_str = datetime.today().strftime('%Y-%m-%d')
            price_df = fetch_ohlcv(symbol, "2015-01-01", today_str, use_cache=True)
            
            fund_df = fetch_fundamentals(symbol)
            
            convert_symbol_data(symbol, price_df, fund_df, calendar_dates, features_dir)
            success_count += 1
        except Exception as e:
            print(f"Error processing {symbol}: {e}")
            error_count += 1
            
        elapsed = time.time() - start_time
        avg_time = elapsed / (i + 1)
        remaining = avg_time * (len(symbols) - (i + 1))
        print(f"   -> ETA: {remaining:.1f}s")
        
    print("\n" + "="*40)
    print("RUN RESULT REPORT")
    print(f"Total symbols: {len(symbols)}")
    print(f"Success: {success_count}")
    print(f"Error/Missing: {error_count}")
    print("="*40)

if __name__ == '__main__':
    main()
