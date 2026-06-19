import pandas as pd
from vnstock import Quote

q = Quote(symbol='VHM')
df = q.history(length="90D", interval="1D")
df['time'] = pd.to_datetime(df['time'])
df = df.sort_values('time', ascending=False)
print("--- VHM Latest 30 Days Price and Volume ---")
print(df[['time', 'open', 'high', 'low', 'close', 'volume']].head(30).to_string(index=False))
