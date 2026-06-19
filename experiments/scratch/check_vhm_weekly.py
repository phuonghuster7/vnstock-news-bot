import pandas as pd
from vnstock import Quote

q = Quote(symbol='VHM')
df_w = q.history(length="90D", interval="1W")
df_w['time'] = pd.to_datetime(df_w['time'])
df_w = df_w.sort_values('time', ascending=False)
print("\n--- VHM Weekly Price History (Latest 10 Weeks) ---")
print(df_w[['time', 'open', 'high', 'low', 'close', 'volume']].head(10).to_string(index=False))
