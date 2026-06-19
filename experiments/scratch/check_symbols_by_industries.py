from vnstock import Listing
listing = Listing()
try:
    df = listing.symbols_by_industries()
    print("symbols_by_industries columns:", df.columns.tolist())
    print(df.head(10))
except Exception as e:
    print("Error:", e)
