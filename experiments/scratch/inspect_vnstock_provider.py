import vnstock
q = vnstock.Quote(symbol="VCB", source="KBS")
# Let's check history and other methods on q.provider
print("Provider class:", q.provider.__class__.__name__)
print("Provider methods:", dir(q.provider))
try:
    df_his = q.provider.history(symbol="VCB", start="2026-05-01", end="2026-06-01")
    print("Provider history columns:", df_his.columns.tolist())
    print(df_his.head(2))
except Exception as e:
    print("Provider history failed:", e)
