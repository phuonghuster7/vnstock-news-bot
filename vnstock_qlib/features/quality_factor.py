import os
import pandas as pd
import numpy as np
from vnstock import Finance

# Global cache dict to store fetched ROE Series per symbol during execution
_ROE_CACHE = {}

def fetch_quarterly_roe(symbol: str) -> pd.Series:
    """
    Lấy ROE quarterly historical từ vnstock với cơ chế cache file toàn bộ lịch sử.
    """
    # 1. Check in-memory cache
    if symbol in _ROE_CACHE:
        return _ROE_CACHE[symbol]
        
    # 2. Check file cache
    cache_dir = "cache/quality_roe"
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"{symbol}.pkl")
    
    if os.path.exists(cache_path):
        try:
            roe = pd.read_pickle(cache_path)
            _ROE_CACHE[symbol] = roe
            return roe
        except:
            pass
            
    # 3. Fetch from API
    try:
        fin = Finance(symbol=symbol, source="VCI")
        df = fin._provider._get_report(
            report_type="ratio", 
            lang="en", 
            get_all=True, 
            period="quarter", 
            limit=50
        )
        if df.empty:
            return pd.Series(dtype=float)
            
        valid_cols = [c for c in df.columns if '-' in c]
        roe_row = df[df['item_id'] == 'roe']
        if roe_row.empty:
            return pd.Series(dtype=float)
            
        roe = roe_row[valid_cols].iloc[0].astype(float)
        
        # Ánh xạ index từ YYYY-QX sang ngày cuối quý
        quarter_map = {
            'Q1': '-03-31',
            'Q2': '-06-30',
            'Q3': '-09-30',
            'Q4': '-12-31'
        }
        new_index = []
        for idx in roe.index:
            year, q = idx.split('-')
            new_index.append(pd.Timestamp(year + quarter_map[q]))
            
        roe.index = new_index
        roe = roe.sort_index()
        
        # Save to cache
        pd.to_pickle(roe, cache_path)
        _ROE_CACHE[symbol] = roe
        return roe
        
    except Exception as e:
        print(f"Lỗi fetch ROE {symbol}: {e}")
        return pd.Series(dtype=float)


def compute_quality_score(symbol: str,
                          as_of_date: str,
                          n_quarters: int = 8) -> float:
    """
    Quality score tại as_of_date.
    """
    import os
    roe = fetch_quarterly_roe(symbol)
    if roe.empty:
        return np.nan
        
    # Lấy dữ liệu trước as_of_date
    roe = roe.loc[:as_of_date].tail(n_quarters)
    if len(roe) < 4:
        return np.nan
        
    mean_roe = roe.mean()
    std_roe  = roe.std()
    
    if abs(mean_roe) < 1e-4:
        return np.nan
        
    # Coefficient of variation — thấp = ổn định
    cv = std_roe / abs(mean_roe)
    
    # Earnings consistency: % quý có ROE dương
    consistency = (roe > 0).mean()
    
    # Combined quality score: thấp biến động -> cao điểm; nhiều quý dương -> cao điểm
    quality = -cv * 0.6 + consistency * 0.4
    return float(quality)
