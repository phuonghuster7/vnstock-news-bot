from vnstock import Quote
try:
    q = Quote(symbol="VCB", source="KBS")
    df = q.history(start="2026-05-01", end="2026-06-01", interval="1D")
    print("Columns:")
    print(df.columns.tolist())
    print("Head:")
    print(df.head(2))
except Exception as e:
    print("Error:", e)
