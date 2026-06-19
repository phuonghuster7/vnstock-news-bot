import os
import pandas as pd
from vnstock import Listing

# Đọc vn100_clean
with open("instruments/vn100_clean.txt", "r") as f:
    symbols = [line.strip() for line in f if line.strip()]

print("Đang lấy thông tin ngành từ vnstock...")
listing = Listing()
df_ind = listing.symbols_by_industries()

SECTOR_NORMALIZE = {
    "Ngân hàng":              "bank",
    "Bất động sản":           "realestate", 
    "Thép":                   "steel",
    "Tài nguyên cơ bản":      "steel", # map tài nguyên (thép)
    "Hàng & Dịch vụ Công nghiệp": "consumer",
    "Hàng tiêu dùng":         "consumer",
    "Thực phẩm và đồ uống":   "consumer",
    "Công nghệ thông tin":    "tech",
    "Dầu khí":                "energy",
    "Hàng không":             "aviation",
    "Du lịch và Giải trí":    "aviation",
    "Bán lẻ":                 "retail",
    "Xây dựng và Vật liệu":   "construction",
    "Xây dựng":               "construction",
    "Điện":                   "utilities",
    "Tiện ích công cộng":     "utilities",
    "Bảo hiểm":               "insurance",
    "Dịch vụ tài chính":      "securities", # Chứng khoán
    "Hóa chất":               "chemicals",
    "Y tế":                   "pharma",
    "Dược phẩm":              "pharma",
    "Viễn thông":             "tech",
}

sector_map = {}
for sym in symbols:
    try:
        row = df_ind[df_ind["symbol"] == sym].iloc[0]
        raw_sector = row["industry_name"]
        sector_map[sym] = SECTOR_NORMALIZE.get(raw_sector, "other")
    except Exception as e:
        sector_map[sym] = "other"

# In báo cáo unmapped
other_symbols = [s for s, v in sector_map.items() if v == "other"]
print(f"Tổng số mã đã ánh xạ: {len(sector_map)}")
print(f"Mã còn 'other': {len(other_symbols)}")
if other_symbols:
    # In ra industry_name gốc của các mã 'other' để xem
    for s in other_symbols:
        matched = df_ind[df_ind["symbol"] == s]
        if not matched.empty:
            print(f"  {s}: {matched.iloc[0]['industry_name']}")
        else:
            print(f"  {s}: không tìm thấy thông tin ngành")

# In ra sector_map dưới dạng Python dict code
print("\nDICT CODE CHUẨN ĐỂ UPDATE SECTOR_MAP:")
print("SECTOR_MAP = {")
for s, v in sorted(sector_map.items()):
    print(f"    '{s}': '{v}',")
print("}")
