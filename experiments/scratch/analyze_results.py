import pandas as pd

df = pd.read_csv("experiments/scratch/vn100_scan_results.csv")

# Filter top candidates
# 1. RS Leaders (Top 10 relative strength compared to VN100 basket in the last 10 days)
rs_leaders = df.sort_values(by='rs_score', ascending=False).head(10)

# 2. Tight Consolidation / Low Vol Squeeze (cung cạn kiệt, bb_width hẹp)
cung_can = df[(df['ma_alignment'] != 'Strong Downtrend') & (df['is_cung_can'] == True)].sort_values(by='bb_width')

# 3. Pocket Pivot / Institutional Entry (dòng tiền lớn kích hoạt)
pocket_pivots = df[df['is_pocket_pivot'] == True].sort_values(by='vol_ratio', ascending=False)

print("--- TOP RS LEADERS (10 DAYS ALPHA VS VN100) ---")
print(rs_leaders[['symbol', 'close', 'price_change_pct', 'rs_score', 'ma_alignment']].to_string(index=False))

print("\n--- LOW VOL INTEGRATION / SQUEEZE (CẠN CUNG TÍCH LŨY) ---")
if len(cung_can) > 0:
    print(cung_can[['symbol', 'close', 'vol_ratio', 'bb_width', 'ma_alignment']].head(10).to_string(index=False))
else:
    # If no strict is_cung_can, just show narrowest BB width
    narrow_bb = df[df['ma_alignment'] != 'Strong Downtrend'].sort_values(by='bb_width').head(10)
    print(narrow_bb[['symbol', 'close', 'vol_ratio', 'bb_width', 'ma_alignment']].to_string(index=False))

print("\n--- POCKET PIVOT (DÒNG TIỀN LỚN KÍCH HOẠT) ---")
if len(pocket_pivots) > 0:
    print(pocket_pivots[['symbol', 'close', 'price_change_pct', 'vol_ratio', 'rsi']].to_string(index=False))
else:
    # Fallback to high vol gainers
    high_vol = df[(df['price_change_pct'] > 1.5) & (df['vol_ratio'] > 1.3)].sort_values(by='vol_ratio', ascending=False).head(5)
    print(high_vol[['symbol', 'close', 'price_change_pct', 'vol_ratio', 'rsi']].to_string(index=False))
