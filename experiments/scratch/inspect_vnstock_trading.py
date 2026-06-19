import vnstock
print("Trading methods:", dir(vnstock.Trading))
try:
    t = vnstock.Trading(symbol="VCB", source="KBS")
    print("Trading object methods:", dir(t))
except Exception as e:
    print(e)
