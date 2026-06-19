import vnstock
print("vnstock modules:")
print(dir(vnstock))
print("explorer modules:")
try:
    import vnstock.explorer
    print(dir(vnstock.explorer))
except Exception as e:
    print(e)
