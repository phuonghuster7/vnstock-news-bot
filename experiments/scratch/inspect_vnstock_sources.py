import vnstock
print("Listing sources:")
# Let's inspect Listing class sources
print("Reference sources:")
try:
    print(vnstock.Reference().show_sources())
except Exception as e:
    print(e)
print("Trading sources:")
try:
    t = vnstock.Trading(symbol="VCB")
    print(t.show_sources())
except Exception as e:
    print(e)
