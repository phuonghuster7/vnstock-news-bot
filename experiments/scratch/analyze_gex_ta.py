import sys
import pandas as pd
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')

from vnstock import Quote

symbols = ['GEX', 'GEE', 'VGC']

def calculate_ta(df):
    if df.empty or len(df) < 50:
        return None
    
    df = df.copy()
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    
    # MA
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma50'] = df['close'].rolling(window=50).mean()
    df['ma200'] = df['close'].rolling(window=200).mean() if len(df) >= 200 else df['close'].rolling(window=len(df)).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Support & Resistance (Pivot Points / Min Max 60 days)
    recent_60 = df.iloc[-60:]
    support = recent_60['low'].min()
    resistance = recent_60['high'].max()
    
    # Latest values
    latest = df.iloc[-1]
    
    return {
        'symbol': latest.get('ticker', 'N/A'),
        'close': latest['close'],
        'ma20': latest['ma20'],
        'ma50': latest['ma50'],
        'ma200': latest['ma200'],
        'rsi': latest['rsi'],
        'support': support,
        'resistance': resistance,
        'volume_ma20': df['volume'].rolling(window=20).mean().iloc[-1],
        'volume_latest': latest['volume']
    }

print("--- PHAN TICH KY THUAT SAU ---")
for sym in symbols:
    try:
        q = Quote(symbol=sym, source='vci')
        # Lay 250 phien (1 nam) de tinh MA200
        df = q.history(start='2025-06-01', end='2026-06-16', interval='1D')
        ta = calculate_ta(df)
        if ta:
            print(f"\n===== {sym} =====")
            print(f"Giá hiện tại: {ta['close']:.2f}")
            print(f"MA20: {ta['ma20']:.2f} | MA50: {ta['ma50']:.2f} | MA200: {ta['ma200']:.2f}")
            
            # Xu huong
            trend_short = "TĂNG" if ta['close'] > ta['ma20'] else "GIẢM"
            trend_mid = "TĂNG" if ta['close'] > ta['ma50'] else "GIẢM"
            trend_long = "TĂNG" if ta['close'] > ta['ma200'] else "GIẢM"
            print(f"Xu hướng: Ngắn hạn ({trend_short}) | Trung hạn ({trend_mid}) | Dài hạn ({trend_long})")
            
            print(f"RSI (14): {ta['rsi']:.2f}")
            print(f"Support (60d): {ta['support']:.2f} | Resistance (60d): {ta['resistance']:.2f}")
            print(f"Volume phiên cuối: {ta['volume_latest']:,} (MA20 Vol: {ta['volume_ma20']:.0f})")
            
            # Tinh toan Entry, SL, TP de xuat khuyen nghi
            # Entry gan support hoac break resistance
            entry = ta['close']
            sl = ta['support'] * 0.95  # Stoploss duoi support 5%
            tp = ta['resistance']  # Target cu la resistance
            print(f"Gợi ý Kỹ thuật: Entry: {entry:.2f} | SL: {sl:.2f} | TP: {tp:.2f}")
        else:
            print(f"[{sym}] Khong du du lieu de phan tich.")
    except Exception as e:
        print(f" Lỗi phân tích {sym}: {e}")
