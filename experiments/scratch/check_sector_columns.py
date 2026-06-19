import pandas as pd
import json
import os
from vnstock import Listing

print("Đang tải danh sách ngành từ vnstock...")
try:
    listing = Listing()
    df_symbols = listing.all_symbols()
    
    # In một số cột để xem tên chính xác
    print("Columns in all_symbols:", df_symbols.columns.tolist())
    
    # Lưu để check
    df_symbols.to_csv("cache/all_sectors_vnstock.csv", index=False)
except Exception as e:
    print("Lỗi tải all_symbols:", e)
