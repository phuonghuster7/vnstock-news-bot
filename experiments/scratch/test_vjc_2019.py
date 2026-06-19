from vnstock import Quote
try:
    q = Quote(symbol="VJC")
    df = q.history(start="2019-10-01", end="2019-11-15", interval="1D")
    print("History 2019 loaded successfully! Length:", len(df))
    print(df.head())
except Exception as e:
    print("Error:", e)
