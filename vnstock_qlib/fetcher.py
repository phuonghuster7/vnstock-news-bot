import os
import time
import pandas as pd
from datetime import datetime, timedelta
from vnstock import Quote

# Khai báo API Key từ user
os.environ['VNSTOCK_API_KEY'] = 'vnstock_e565f967ef1f8bb272d1d9581e2efa58'

CACHE_DIR = r"D:\Qlib-Vnstock\cache"

def fetch_ohlcv(symbol: str, start: str, end: str, use_cache: bool = True) -> pd.DataFrame:
    """
    Fetch OHLCV data cho 1 mã chứng khoán.
    Returns: columns = [date, open, high, low, close, volume]
    Giá đơn vị: nghìn VNĐ (giữ nguyên, không scale)
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(CACHE_DIR, f"{symbol}_price.parquet")
    
    cached_df = None
    fetch_start = start
    
    if use_cache and os.path.exists(cache_path):
        cached_df = pd.read_parquet(cache_path)
        if not cached_df.empty:
            last_date = pd.to_datetime(cached_df['date'].max())
            end_date = pd.to_datetime(end)
            if last_date >= end_date:
                mask = (pd.to_datetime(cached_df['date']) >= pd.to_datetime(start)) & \
                       (pd.to_datetime(cached_df['date']) <= end_date)
                return cached_df.loc[mask].copy()
            
            # Chỉ lấy data từ ngày cuối + 1
            fetch_start = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
    
    if pd.to_datetime(fetch_start) > pd.to_datetime(end):
        if cached_df is not None:
            mask = (pd.to_datetime(cached_df['date']) >= pd.to_datetime(start)) & \
                   (pd.to_datetime(cached_df['date']) <= pd.to_datetime(end))
            return cached_df.loc[mask].copy()
        return pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])

    max_retries = 2
    new_data = pd.DataFrame()
    for attempt in range(max_retries + 1):
        try:
            quote = Quote(source="kbs", symbol=symbol)
            df = quote.history(start=fetch_start, end=end, interval="1D")
            
            if df is not None and not df.empty:
                if 'time' not in df.columns:
                    df['time'] = df.index
                df['date'] = pd.to_datetime(df['time']).dt.strftime('%Y-%m-%d')
                new_data = df[['date', 'open', 'high', 'low', 'close', 'volume']].copy()
            break
        except Exception as e:
            if attempt < max_retries:
                time.sleep((attempt + 1) * 2)
            else:
                print(f"Error fetching {symbol} after {max_retries} retries: {e}")
                new_data = pd.DataFrame()
    
    # Rate limit: 60 req/min
    time.sleep(1.1)

    if cached_df is not None and not cached_df.empty and not new_data.empty:
        final_df = pd.concat([cached_df, new_data]).drop_duplicates(subset=['date'], keep='last').sort_values('date').reset_index(drop=True)
    elif not new_data.empty:
        final_df = new_data
    elif cached_df is not None:
        final_df = cached_df
    else:
        final_df = pd.DataFrame(columns=['date', 'open', 'high', 'low', 'close', 'volume'])
    
    if not final_df.empty and use_cache:
        final_df.to_parquet(cache_path, index=False)
        
    if final_df.empty:
        return final_df
        
    mask = (pd.to_datetime(final_df['date']) >= pd.to_datetime(start)) & \
           (pd.to_datetime(final_df['date']) <= pd.to_datetime(end))
    return final_df.loc[mask].copy()

if __name__ == '__main__':
    print("Testing fetch HPG...")
    df = fetch_ohlcv("HPG", "2024-01-01", "2024-01-10", use_cache=False)
    print(df)
