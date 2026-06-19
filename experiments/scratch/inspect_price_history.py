import vnstock
t = vnstock.Trading(symbol="VCB", source="KBS")
try:
    print("KBS price_history columns:", t.price_history().columns.tolist())
    print(t.price_history().head(2))
except Exception as e:
    print("price_history failed:", e)

t_vci = vnstock.Trading(symbol="VCB", source="VCI")
try:
    print("\nVCI price_history columns:", t_vci.price_history().columns.tolist())
    print(t_vci.price_history().head(2))
except Exception as e:
    print("price_history failed:", e)
