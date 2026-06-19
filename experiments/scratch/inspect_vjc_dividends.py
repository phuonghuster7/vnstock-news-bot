from vnstock import Company
company = Company(symbol="VJC", source="vci")
df = company.events()
df_div = df[df['category'] == 'DIVIDEND']
print(df_div[['event_title_vi', 'exright_date', 'record_date', 'exercise_ratio', 'event_name_en']].head(10))
