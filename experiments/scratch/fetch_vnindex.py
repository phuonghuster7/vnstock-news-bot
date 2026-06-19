import os
import pandas as pd
import numpy as np
from vnstock import Quote

print("Thử fetch VNINDEX từ vnstock...")
try:
    quote = Quote(source="kbs", symbol="VNINDEX")
    df = quote.history(start="2018-01-01", end="2025-12-31", interval="1D")
    print("VNINDEX shape:", df.shape if df is not None else "None")
    if df is not None and not df.empty:
        os.makedirs("cache", exist_ok=True)
        # Đồng bộ hóa định dạng index thành datetime và lưu
        if 'time' in df.columns:
            df['time'] = pd.to_datetime(df['time'])
            df = df.set_index('time')
        df.to_csv("cache/VNINDEX_price.csv")
        print("Đã lưu VNINDEX_price.csv thành công!")
except Exception as e:
    print("Lỗi fetch VNINDEX từ kbs:", e)
    try:
        quote = Quote(source="vci", symbol="VNINDEX")
        df = quote.history(start="2018-01-01", end="2025-12-31", interval="1D")
        print("VNINDEX (vci) shape:", df.shape if df is not None else "None")
        if df is not None and not df.empty:
            os.makedirs("cache", exist_ok=True)
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'])
                df = df.set_index('time')
            df.to_csv("cache/VNINDEX_price.csv")
            print("Đã lưu VNINDEX_price.csv từ VCI thành công!")
    except Exception as e2:
        print("Lỗi fetch VNINDEX từ vci:", e2)
