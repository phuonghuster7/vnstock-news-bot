import vnstock
q = vnstock.Quote(symbol="VCB", source="KBS")
# Let's inspect q._provider
print("q._provider class:", q._provider.__class__.__name__)
print("q._provider methods:", dir(q._provider))
try:
    df_his = q._provider.history(start="2026-05-01", end="2026-06-01")
    print("q._provider history columns:", df_his.columns.tolist())
    print(df_his.head(2))
except Exception as e:
    print("q._provider history failed:", e)
