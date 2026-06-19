from vnstock import Company
company = Company(symbol="VJC", source="vci")
try:
    df = company.events()
    print("Columns:", df.columns.tolist())
    print(df.head(2))
except Exception as e:
    print("Error:", e)
