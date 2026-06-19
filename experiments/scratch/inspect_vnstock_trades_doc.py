import vnstock
try:
    print("Market show_doc:")
    vnstock.show_doc("Market.equity.trades")
except Exception as e:
    print("show_doc failed:", e)
