import pandas as pd
from vnstock import Quote

for sym in ['CII', 'NLG']:
    q = Quote(symbol=sym)
    df = q.history(length="15D", interval="1D")
    df['time'] = pd.to_datetime(df['time'])
    df = df.sort_values('time', ascending=False)
    print(f"\n--- {sym} Price History (Latest 10 Days) ---")
    print(df[['time', 'open', 'high', 'low', 'close', 'volume']].head(10).to_string(index=False))
