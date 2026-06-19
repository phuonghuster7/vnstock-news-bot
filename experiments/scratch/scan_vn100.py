import os
import time
import pandas as pd
import numpy as np
from vnstock import Quote

def calculate_rsi(df, period=14):
    if len(df) < period:
        period = len(df) - 1
    if period <= 0:
        return pd.Series([50.0] * len(df))
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def main():
    # Read VN100 clean symbols
    txt_path = "d:/Qlib-Vnstock/instruments/vn100_clean.txt"
    if not os.path.exists(txt_path):
        print(f"Error: {txt_path} not found.")
        return
        
    with open(txt_path, "r", encoding="utf-8") as f:
        symbols = [line.strip() for line in f if line.strip()]
        
    print(f"Loaded {len(symbols)} symbols from vn100_clean.txt")
    
    # Download data for all symbols
    data_dict = {}
    print("Downloading historical data...")
    for i, sym in enumerate(symbols):
        try:
            q = Quote(symbol=sym)
            df = q.history(length="6M", interval="1D")
            if df is not None and len(df) >= 10:
                df['time'] = pd.to_datetime(df['time'])
                df = df.sort_values('time').reset_index(drop=True)
                data_dict[sym] = df
        except Exception as e:
            pass
        time.sleep(0.02)
        if (i+1) % 20 == 0:
            print(f"Downloaded {i+1}/{len(symbols)}...")
            
    print(f"Successfully downloaded data for {len(data_dict)} stocks.")
    
    # Construct market benchmark from VN100 average
    all_dates = sorted(list(set([t for df in data_dict.values() for t in df['time']])))
    df_market = pd.DataFrame({'time': all_dates})
    
    returns_list = []
    for sym, df in data_dict.items():
        df_ret = df[['time', 'close']].copy()
        df_ret[f'{sym}_ret'] = df_ret['close'].pct_change()
        returns_list.append(df_ret[['time', f'{sym}_ret']])
        
    for ret_df in returns_list:
        df_market = pd.merge(df_market, ret_df, on='time', how='left')
        
    ret_cols = [c for c in df_market.columns if c.endswith('_ret')]
    df_market['market_ret'] = df_market[ret_cols].mean(axis=1).fillna(0)
    
    market_index = [100.0]
    for r in df_market['market_ret'].iloc[1:]:
        market_index.append(market_index[-1] * (1.0 + r))
    df_market['close'] = market_index
    
    print("Market benchmark constructed. Analyzing individual stocks...")
    
    results = []
    for sym, df in data_dict.items():
        try:
            n = len(df)
            # Use adaptive windows based on available length
            w5 = min(5, n)
            w10 = min(10, n)
            w20 = min(20, n)
            
            df['ma5'] = df['close'].rolling(window=w5).mean()
            df['ma10'] = df['close'].rolling(window=w10).mean()
            df['ma20'] = df['close'].rolling(window=w20).mean()
            df['vol_ma10'] = df['volume'].rolling(window=w10).mean()
            df['rsi'] = calculate_rsi(df, period=10)
            
            # Bollinger Bands (using 15 periods to ensure stability on 22 days of data)
            w_bb = min(15, n)
            std_bb = df['close'].rolling(window=w_bb).std()
            df['bb_upper'] = df['ma10'] + (2 * std_bb)
            df['bb_lower'] = df['ma10'] - (2 * std_bb)
            df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / (df['ma10'] + 1e-9)
            
            latest = df.iloc[-1]
            prev = df.iloc[-2] if n > 1 else latest
            
            close = latest['close']
            vol = latest['volume']
            vol_ma = latest['vol_ma10']
            
            # Trend based on MA5, MA10, MA20
            above_ma5 = close > latest['ma5']
            above_ma10 = close > latest['ma10']
            above_ma20 = close > latest['ma20']
            
            if above_ma5 and above_ma10 and above_ma20:
                ma_alignment = "Strong Uptrend"
            elif not above_ma5 and not above_ma10 and not above_ma20:
                ma_alignment = "Strong Downtrend"
            else:
                ma_alignment = "Sideways/Reversing"
                
            # Low vol squeeze (cung cạn kiệt): Vol < 75% trung bình 10 phiên, giá tích lũy quanh MA10
            vol_ratio = vol / (vol_ma + 1e-9)
            is_cung_can = (vol_ratio < 0.75) and (abs(close - latest['ma10'])/latest['ma10'] < 0.02)
            
            # Pocket pivot (Dòng tiền lớn kích hoạt): Giá tăng > 1.5% với Vol > 1.4x Vol MA10
            price_change = (close - prev['close']) / (prev['close'] + 1e-9)
            is_pocket_pivot = (price_change > 0.015) and (vol_ratio > 1.4)
            
            # Calculate RS vs Market Benchmark (using 10 days performance comparison)
            merged = pd.merge(df[['time', 'close']], df_market[['time', 'close']], on='time', suffixes=('_stock', '_market'))
            w_rs = min(10, len(merged))
            if w_rs > 1:
                stock_perf = (merged['close_stock'].iloc[-1] - merged['close_stock'].iloc[-w_rs]) / (merged['close_stock'].iloc[-w_rs] + 1e-9)
                mkt_perf = (merged['close_market'].iloc[-1] - merged['close_market'].iloc[-w_rs]) / (merged['close_market'].iloc[-w_rs] + 1e-9)
                rs_score = stock_perf - mkt_perf
            else:
                rs_score = 0
                stock_perf = 0
                
            results.append({
                'symbol': sym,
                'close': close,
                'price_change_pct': price_change * 100,
                'volume': vol,
                'vol_ma10': vol_ma,
                'vol_ratio': vol_ratio,
                'rsi': latest['rsi'],
                'bb_width': latest['bb_width'],
                'ma_alignment': ma_alignment,
                'is_cung_can': is_cung_can,
                'is_pocket_pivot': is_pocket_pivot,
                'rs_score': rs_score * 100,
                'stock_perf': stock_perf * 100
            })
        except Exception as e:
            pass
            
    df_results = pd.DataFrame(results)
    output_path = "d:/Qlib-Vnstock/experiments/scratch/vn100_scan_results.csv"
    df_results.to_csv(output_path, index=False)
    print(f"Scan complete. Analyzed {len(df_results)} symbols. Saved to {output_path}")

if __name__ == "__main__":
    main()
