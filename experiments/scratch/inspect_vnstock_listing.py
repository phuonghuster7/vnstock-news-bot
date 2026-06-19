import vnstock
print("Listing show_doc:")
try:
    vnstock.show_doc("Listing.symbols")
except Exception as e:
    print(e)
print("Listing API methods:")
print(dir(vnstock.Listing))
