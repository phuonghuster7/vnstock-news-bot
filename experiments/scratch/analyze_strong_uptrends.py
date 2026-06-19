import os
import sys
import time
import socket
socket.setdefaulttimeout(15)

import pandas as pd
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')

from vnstock import Quote

# Danh sách 40 mã chất lượng cao nhất VN100 (VN30 + Top Midcaps thanh khoản lớn)
SELECTED_SYMBOLS = [
    # VN30
    'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG',
    'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB',
    'TCB', 'TPB', 'VCB', 'VJC', 'VHM', 'VIC', 'VNM', 'VPB', 'VRE',
    # Midcaps hàng đầu dòng tiền lớn
    'GEX', 'VGC', 'VND', 'VCI', 'DGC', 'NKG', 'HSG', 'DXG', 'DIG', 'PDR', 'KBC'
]

def get_strong_uptrends():
    symbols = list(set(SELECTED_SYMBOLS))
    print(f"Đang quét tìm các mã Uptrend mạnh nhất trong danh sách {len(symbols)} mã tiêu biểu...")
    
    candidates = []
    
    for idx, sym in enumerate(symbols):
        print(f"[{idx+1}/{len(symbols)}] Đang xử lý {sym}...", flush=True)
        retries = 2
        while retries > 0:
            try:
                q = Quote(symbol=sym, source='kbs')
                # Lấy 200 phiên giao dịch để tính MA200 chính xác
                df = q.history(start='2025-08-01', end='2026-06-17', interval='1D')
                if df is not None and len(df) >= 200:
                    df = df.copy()
                    df['close'] = df['close'].astype(float)
                    df['high'] = df['high'].astype(float)
                    df['low'] = df['low'].astype(float)
                    df['volume'] = df['volume'].astype(float)
                    
                    # Tính toán chỉ báo
                    df['ma20'] = df['close'].rolling(window=20).mean()
                    df['ma50'] = df['close'].rolling(window=50).mean()
                    df['ma200'] = df['close'].rolling(window=200).mean()
                    df['vol_ma20'] = df['volume'].rolling(window=20).mean()
                    
                    latest = df.iloc[-1]
                    close = latest['close']
                    ma20 = latest['ma20']
                    ma50 = latest['ma50']
                    ma200 = latest['ma200']
                    
                    # Điều kiện Uptrend Dài hạn thực sự: Price > MA20 > MA50 > MA200
                    if close > ma20 and ma20 > ma50 and ma50 > ma200:
                        # Tính thêm RSI
                        delta = df['close'].diff()
                        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                        rs = gain / (loss + 1e-9)
                        rsi = 100 - (100 / (1 + rs))
                        
                        distance_ma200 = ((close - ma200) / ma200) * 100
                        
                        candidates.append({
                            'symbol': sym,
                            'close': close,
                            'ma20': ma20,
                            'ma50': ma50,
                            'ma200': ma200,
                            'rsi': rsi.iloc[-1],
                            'vol_latest': latest['volume'],
                            'vol_ma20': latest['vol_ma20'],
                            'distance_ma200': distance_ma200,
                            'df': df
                        })
                time.sleep(1.2)
                break
            except Exception as e:
                err_msg = str(e)
                if "Rate Limit" in err_msg or "GIỚI HẠN API" in err_msg or "rate" in err_msg.lower():
                    print(f" Bị giới hạn tại {sym}. Chờ 60s...", flush=True)
                    time.sleep(60)
                    retries -= 1
                else:
                    time.sleep(1.2)
                    break
                    
    candidates = sorted(candidates, key=lambda x: x['distance_ma200'], reverse=True)
    return candidates

def analyze_candidate(cand):
    df = cand['df']
    sym = cand['symbol']
    recent_5 = df.iloc[-5:]
    
    print(f"\n========================================")
    print(f"🔥 PHÂN TÍCH CHUYÊN SÂU: {sym}")
    print(f"========================================")
    print(f"- Giá đóng cửa hiện tại: {cand['close']:,} VND")
    print(f"- Chỉ số xu hướng: MA20={cand['ma20']:.2f} | MA50={cand['ma50']:.2f} | MA200={cand['ma200']:.2f}")
    print(f"- Giá nằm trên MA200: +{cand['distance_ma200']:.1f}% (Xu hướng dài hạn rất mạnh)")
    print(f"- RSI (14): {cand['rsi']:.1f}")
    
    vol_latest = cand['vol_latest']
    vol_ma20 = cand['vol_ma20']
    vol_ratio = vol_latest / (vol_ma20 + 1e-9)
    print(f"- Volume phiên cuối: {vol_latest:,.0f} vs MA20 Vol: {vol_ma20:,.0f} ({vol_ratio:.2f}x)")
    
    print("\n* Diễn biến OHLCV 5 phiên gần nhất:")
    for idx, row in recent_5.iterrows():
        change = ((row['close'] - df.loc[idx-1, 'close']) / df.loc[idx-1, 'close'] * 100) if idx > 0 else 0.0
        print(f"  Ngày {row['time'].strftime('%Y-%m-%d')} | O: {row['open']:.1f} | H: {row['high']:.1f} | L: {row['low']:.1f} | C: {row['close']:.1f} | Vol: {row['volume']:,.0f} ({change:+.2f}%)")
        
    last_change = ((recent_5.iloc[-1]['close'] - recent_5.iloc[-2]['close']) / recent_5.iloc[-2]['close'] * 100)
    if last_change > 1.5 and vol_ratio > 1.3:
        print("  👉 Tín hiệu: BREAKOUT nền giá đi kèm dòng tiền lớn xác nhận tham gia mạnh mẽ.")
    elif abs(last_change) < 1.0 and vol_ratio < 0.7:
        print("  👉 Tín hiệu: TÍCH LŨY CUNG CẠN (Lực bán cạn kiệt, đang nén chặt chờ bùng nổ).")
    else:
        print("  👉 Trạng thái: Tiếp tục duy trì đà tăng trưởng tự nhiên bền vững.")

    recent_60 = df.iloc[-60:]
    support = recent_60['low'].min()
    resistance = recent_60['high'].max()
    
    if cand['rsi'] > 70:
        entry_desc = f"RSI đang Quá mua ({cand['rsi']:.1f}). Hạn chế mua đuổi. Chờ nhịp chỉnh hoặc tích lũy test lại MA20 quanh vùng {cand['ma20']:.1f}."
    else:
        entry_desc = f"RSI trung tính ({cand['rsi']:.1f}). Điểm mua (Entry) tối ưu ngay tại vùng giá hiện tại quanh {cand['close']:,} hoặc khi rung lắc nhẹ."
        
    sl = support * 0.95
    tp = resistance if cand['close'] < resistance else cand['close'] * 1.15
    
    print(f"\n* KHUYẾN NGHỊ GIAO DỊCH LOGIC:")
    print(f"  - Điểm mua (Entry): {entry_desc}")
    print(f"  - Cắt lỗ (Stop Loss): {sl:.1f} (Dưới hỗ trợ cứng 60 ngày 5%)")
    print(f"  - Chốt lời (Take Profit): {tp:.1f} (Mục tiêu đỉnh cũ hoặc Fibonacci mở rộng +15%)")

def main():
    candidates = get_strong_uptrends()
    if not candidates:
        print("Không tìm thấy mã nào đạt điều kiện Uptrend Dài hạn mạnh mẽ (Price > MA20 > MA50 > MA200).")
        return
        
    print(f"\nTìm thấy {len(candidates)} mã đạt tiêu chuẩn. Tiến hành phân tích top 5 mã mạnh nhất:")
    for cand in candidates[:5]:
        analyze_candidate(cand)

if __name__ == "__main__":
    main()
