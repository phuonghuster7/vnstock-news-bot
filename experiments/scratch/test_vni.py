from vnstock import Quote
try:
    q = Quote(symbol="VNINDEX")
    df = q.history(length="1M", interval="1D")
    print("VNINDEX loaded successfully!")
    print(df.head())
except Exception as e:
    print("Error loading VNINDEX:", e)
