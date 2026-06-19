from vnstock import Company
company = Company(symbol="VHM", source="vci")
try:
    df = company.ratio_summary()
    print("VHM Ratio columns:", df.columns.tolist())
    print(df.iloc[0].to_dict())
except Exception as e:
    print("Error:", e)
