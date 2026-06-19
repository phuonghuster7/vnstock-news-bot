from vnstock import Company
company = Company(symbol="VHM", source="vci")
df = company.ratio_summary()
# Sort by year_report and ratio_year_id to get the latest
df_sorted = df.sort_values(by=['year_report', 'quarter'], ascending=False)
print("Latest ratio row:")
latest = df_sorted.dropna(subset=['pe']).iloc[0]
print(latest[['year_report', 'quarter', 'pe', 'pb', 'roe', 'roa']])
