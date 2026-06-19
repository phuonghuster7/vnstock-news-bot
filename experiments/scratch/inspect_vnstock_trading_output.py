import vnstock
t = vnstock.Trading(symbol="VCB", source="KBS")
try:
    df_ft = t.foreign_trade()
    print("foreign_trade columns:", df_ft.columns.tolist() if df_ft is not None else "None")
    print("foreign_trade head:\n", df_ft.head(2) if df_ft is not None else "None")
except Exception as e:
    print("foreign_trade failed:", e)

try:
    df_ts = t.trading_stats()
    print("\ntrading_stats columns:", df_ts.columns.tolist() if df_ts is not None else "None")
    print("trading_stats head:\n", df_ts.head(2) if df_ts is not None else "None")
except Exception as e:
    print("trading_stats failed:", e)
