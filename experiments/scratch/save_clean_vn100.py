# Tạo file danh sách mã sạch cố định
clean_symbols = [
    "ACB", "BCG", "BID", "BMP", "BSI", "BVH", "CII", "CMG", "CTD", "CTG",
    "CTR", "DBC", "DCM", "DGC", "DGW", "DHC", "DHG", "DIG", "DPM", "DXG",
    "EIB", "EVF", "FPT", "FRT", "FTS", "GAS", "GEX", "GMD", "GVR", "HCM",
    "HDB", "HDC", "HDG", "HHV", "HPG", "HSG", "IJC", "KBC", "KDC", "KDH",
    "LPB", "MBB", "MSN", "MWG", "NLG", "NT2", "PAN", "PC1", "PDR", "PHR",
    "PLX", "PNJ", "POW", "PTB", "PVD", "PVT", "REE", "SAB", "SAM", "SBT",
    "SCS", "SHB", "SJS", "SSB", "SSI", "STB", "SZC", "TCB", "TCH", "TDM",
    "TIP", "TPB", "VCB", "VCG", "VCI", "VGC", "VHC", "VHM", "VIB", "VIC",
    "VIX", "VJC", "VND", "VNM", "VPB", "VPI", "VRE"
]

import os
os.makedirs("instruments", exist_ok=True)
with open("instruments/vn100_clean.txt", "w") as f:
    f.write("\n".join(clean_symbols))
print(f"Đã lưu cố định {len(clean_symbols)} mã vào instruments/vn100_clean.txt")
