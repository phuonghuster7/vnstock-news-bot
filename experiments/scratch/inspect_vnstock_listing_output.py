import vnstock
l = vnstock.Listing(source="KBS")
try:
    print(l.all_symbols().head())
except Exception as e:
    print("all_symbols failed:", e)
try:
    print(l.info().head())
except Exception as e:
    print("info failed:", e)
