import vnstock
print("vnstock version:", getattr(vnstock, "__version__", "unknown"))
q = vnstock.Quote(symbol="VCB", source="KBS")
print("Quote methods/attributes:", dir(q))
try:
    print("Trying q.intraday():")
    df = q.intraday()
    print("Intraday columns:", df.columns.tolist() if df is not None else "None")
except Exception as e:
    print("Intraday failed:", e)

# Test if we have vnstock_data
try:
    import vnstock_data
    print("vnstock_data version:", getattr(vnstock_data, "__version__", "unknown"))
except Exception as e:
    print("vnstock_data import failed:", e)
