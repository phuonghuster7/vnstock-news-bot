import os
import numpy as np
import pandas as pd

def df_to_qlib_bin(df: pd.DataFrame, calendar: list[str], col: str) -> np.ndarray:
    """Tạo float32 array aligned với calendar"""
    cal_index = {d: i for i, d in enumerate(calendar)}
    arr = np.full(len(calendar), np.nan, dtype=np.float32)
    
    # Đảm bảo index/loop an toàn
    for _, row in df.iterrows():
        # Bỏ qua nan, None
        date_str = str(row['date'])
        idx = cal_index.get(date_str)
        if idx is not None:
            val = row[col]
            if pd.notna(val):
                arr[idx] = float(val)
    return arr

def write_bin(arr: np.ndarray, path: str):
    """Ghi array thành Qlib little-endian float32 binary có header start_index"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Thêm start_index = 0 vào đầu mảng (vì arr đã được padding bằng độ dài calendar)
    start_index_arr = np.array([0], dtype='<f')
    data_arr = arr.astype('<f')
    
    with open(path, "wb") as f:
        f.write(start_index_arr.tobytes())
        f.write(data_arr.tobytes())

def convert_symbol_data(symbol: str, price_df: pd.DataFrame, fundamental_df: pd.DataFrame, calendar: list[str], output_dir: str):
    """
    Convert price và fundamental data sang định dạng qlib cho 1 symbol.
    """
    symbol_dir = os.path.join(output_dir, symbol.lower())
    
    # 1. Price features
    if not price_df.empty:
        # Tính vwap = (high + low + close) / 3
        price_df['vwap'] = (price_df['high'] + price_df['low'] + price_df['close']) / 3.0
        
        # factor = 1.0 vì vnstock cung cấp giá đã điều chỉnh
        price_df['factor'] = 1.0

        cols = ['open', 'high', 'low', 'close', 'volume', 'vwap', 'factor']
        for col in cols:
            if col in price_df.columns:
                arr = df_to_qlib_bin(price_df, calendar, col)
                write_bin(arr, os.path.join(symbol_dir, f"{col}.day.bin"))
                
    # 2. Fundamental features (nếu có)
    if fundamental_df is not None and not fundamental_df.empty:
        fund_cols = ['roe', 'roa', 'eps', 'pe', 'pb', 'nim', 'npl']
        for col in fund_cols:
            if col in fundamental_df.columns:
                arr = df_to_qlib_bin(fundamental_df, calendar, col)
                write_bin(arr, os.path.join(symbol_dir, f"{col}.day.bin"))

if __name__ == '__main__':
    # Unit test nhỏ
    calendar = ["2024-01-01", "2024-01-02", "2024-01-03"]
    df = pd.DataFrame({
        'date': ["2024-01-02", "2024-01-04"],
        'close': [15.5, 16.0]
    })
    
    arr = df_to_qlib_bin(df, calendar, 'close')
    print("Calendar:", calendar)
    print("Array aligned:", arr)
    assert np.isnan(arr[0]), "2024-01-01 phải là NaN"
    assert arr[1] == 15.5, "2024-01-02 phải là 15.5"
    assert np.isnan(arr[2]), "2024-01-03 phải là NaN"
    print("Test passed!")
