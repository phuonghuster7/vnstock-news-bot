import pandas as pd
from vnstock import Company

company = Company(symbol="VJC", source="vci")
df = company.events()
# Show unique values of event_code, category, action_type_en if they exist
for col in ['event_code', 'category', 'action_type_en', 'event_name_en']:
    if col in df.columns:
        print(f"Unique values in {col}:")
        print(df[col].unique())
