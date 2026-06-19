import pandas as pd
import numpy as np
from vnstock import Quote

def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def main():
    q = Quote(symbol="CII")
    
    # 1. Fetch Daily (1D)
    df_1d = q.history(length="3M", interval="1D")
    df_1d['time'] = pd.to_datetime(df_1d['time'])
    df_1d = df_1d.sort_values('time').reset_index(drop=True)
    
    # 2. Fetch Hourly (1H)
    df_1h = q.history(length="3W", interval="1H")
    df_1h['time'] = pd.to_datetime(df_1h['time'])
    df_1h = df_1h.sort_values('time').reset_index(drop=True)
    
    # Analyze Daily
    df_1d['ma20'] = df_1d['close'].rolling(window=20).mean()
    df_1d['vol_ma20'] = df_1d['volume'].rolling(window=20).mean()
    df_1d['rsi'] = calculate_rsi(df_1d)
    
    # Analyze Hourly
    df_1h['ma20'] = df_1h['close'].rolling(window=20).mean()
    df_1h['vol_ma20'] = df_1h['volume'].rolling(window=20).mean()
    df_1h['rsi'] = calculate_rsi(df_1h)
    
    # Smart Money detection on Hourly
    df_1h['vol_ratio'] = df_1h['volume'] / (df_1h['vol_ma20'] + 1e-9)
    high_vol_hours = df_1h[df_1h['vol_ratio'] > 1.5].copy()
    high_vol_hours['type'] = np.where(high_vol_hours['close'] >= high_vol_hours['open'], 'BUYING', 'SELLING')
    
    print("\nCII High Volume Hours (Smart Money Action):")
    latest_hours = high_vol_hours.tail(7)
    for _, row in latest_hours.iterrows():
        print(f"Time: {row['time'].strftime('%Y-%m-%d %H:%M')}, Type: {row['type']}, Vol Ratio: {row['vol_ratio']:.2f}, Close: {row['close']}")

if __name__ == "__main__":
    main()
