import pandas as pd
from vnstock import Quote

q = Quote(symbol='VHM')

# Hourly history
df_1h = q.history(length="15D", interval="1H")
df_1h['time'] = pd.to_datetime(df_1h['time'])
df_1h = df_1h.sort_values('time', ascending=False)
print("\n--- VHM Hourly Price History (Latest 15 periods) ---")
print(df_1h[['time', 'open', 'high', 'low', 'close', 'volume']].head(15).to_string(index=False))

# 15M history
try:
    df_15m = q.history(length="5D", interval="15M")
    df_15m['time'] = pd.to_datetime(df_15m['time'])
    df_15m = df_15m.sort_values('time', ascending=False)
    print("\n--- VHM 15-Minute Price History (Latest 15 periods) ---")
    print(df_15m[['time', 'open', 'high', 'low', 'close', 'volume']].head(15).to_string(index=False))
except Exception as e:
    print(f"\nCould not fetch 15M interval: {e}")
