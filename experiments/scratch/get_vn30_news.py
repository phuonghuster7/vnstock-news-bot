import pandas as pd
import time
from datetime import datetime
from vnstock import Company

vn30_symbols = [
    'ACB', 'BCM', 'BID', 'CTG', 'DGC', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 
    'LPB', 'MBB', 'MSN', 'MWG', 'PLX', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 
    'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE'
]

print("Scanning VN30 for recent news (10/06 - 12/06)...")
all_news = []

for i, sym in enumerate(vn30_symbols):
    try:
        company = Company(symbol=sym, source='vci')
        df = company.news()
        if df is not None and not df.empty:
            df['public_date'] = pd.to_datetime(df['public_date'])
            # Filter news from June 10th to June 12th, 2026
            filtered = df[df['public_date'] >= '2026-06-10']
            for _, row in filtered.iterrows():
                all_news.append({
                    'symbol': sym,
                    'title': row['news_title'],
                    'date': row['public_date'].strftime('%Y-%m-%d %H:%M:%S')
                })
    except Exception as e:
        pass
    time.sleep(0.1)
    if (i+1) % 10 == 0:
        print(f"Scanned {i+1}/{len(vn30_symbols)}...")

df_news = pd.DataFrame(all_news)
df_news.to_csv("experiments/scratch/vn30_recent_news.csv", index=False)
print(f"Scan complete. Found {len(df_news)} recent articles.")
