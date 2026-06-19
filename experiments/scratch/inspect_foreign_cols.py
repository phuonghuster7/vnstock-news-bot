import vnstock
q = vnstock.Quote(symbol="VCB", source="KBS")
try:
    df_his = q.history(start="2026-05-01", end="2026-06-01", interval="1D")
    print("KBS History Columns:", df_his.columns.tolist())
    print("Head:\n", df_his.head(2))
except Exception as e:
    print("KBS History failed:", e)

try:
    print("\nTrying VCI source...")
    q2 = vnstock.Quote(symbol="VCB", source="VCI")
    df_his2 = q2.history(start="2026-05-01", end="2026-06-01", interval="1D")
    print("VCI History Columns:", df_his2.columns.tolist())
    print("Head:\n", df_his2.head(2))
except Exception as e:
    print("VCI History failed:", e)
