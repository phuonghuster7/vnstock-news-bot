import pandas as pd
import time
from vnstock import Company

vn30_symbols = [
    'ACB', 'BCM', 'BID', 'CTG', 'DGC', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 
    'LPB', 'MBB', 'MSN', 'MWG', 'PLX', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 
    'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE'
]

print("--- LATEST VN30 NEWS (10/06 - 12/06) ---")
count = 0
for sym in vn30_symbols:
    try:
        company = Company(symbol=sym, source='vci')
        df = company.news()
        if df is not None and not df.empty:
            df['public_date'] = pd.to_datetime(df['public_date'])
            # Filter news from June 10th to June 12th, 2026
            filtered = df[df['public_date'] >= '2026-06-10']
            for _, row in filtered.iterrows():
                print(f"[{sym}] {row['news_title']} ({row['public_date'].strftime('%d/%m')})")
                count += 1
    except Exception as e:
        pass
    time.sleep(0.05)

print(f"\nTotal articles printed: {count}")
