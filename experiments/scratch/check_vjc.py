from vnstock import Quote
import pandas as pd

q = Quote(symbol="VJC")
df = q.history(length="15D", interval="1D")
df['time'] = pd.to_datetime(df['time'])
df = df.sort_values('time', ascending=False)
print("--- VJC Price History (Latest 10 Days) ---")
print(df[['time', 'open', 'high', 'low', 'close', 'volume']].head(10).to_string(index=False))
