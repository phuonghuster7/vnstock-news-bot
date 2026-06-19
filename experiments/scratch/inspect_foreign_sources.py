import vnstock
print("Trading methods:", dir(vnstock.Trading))
t = vnstock.Trading(symbol="VCB", source="VCI")
try:
    print("VCI foreign_trade:")
    print(t.foreign_trade().head(2))
except Exception as e:
    print("VCI failed:", e)

t_ssi = vnstock.Trading(symbol="VCB", source="SSI")
try:
    print("SSI foreign_trade:")
    print(t_ssi.foreign_trade().head(2))
except Exception as e:
    print("SSI failed:", e)
