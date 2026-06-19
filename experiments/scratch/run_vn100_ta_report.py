import os
import sys
import time
import socket
socket.setdefaulttimeout(10) # Timeout 10s cho ket noi socket

import pandas as pd
import numpy as np
from datetime import datetime
sys.stdout.reconfigure(encoding='utf-8')

from vnstock import Quote

def get_desktop_path():
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, 
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        )
        path, _ = winreg.QueryValueEx(key, "Desktop")
        return os.path.expandvars(path)
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Desktop")

def calculate_ta(df, sym):
    if df is None or df.empty or len(df) < 50:
        return None
    
    df = df.copy()
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['volume'] = df['volume'].astype(float)
    
    # MAs
    df['ma20'] = df['close'].rolling(window=20).mean()
    df['ma50'] = df['close'].rolling(window=50).mean()
    df['vol_ma20'] = df['volume'].rolling(window=20).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # Bollinger Bands
    std20 = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['ma20'] + (2 * std20)
    df['bb_lower'] = df['ma20'] - (2 * std20)
    
    # Support & Resistance (60 days)
    recent_60 = df.iloc[-60:]
    support = recent_60['low'].min()
    resistance = recent_60['high'].max()
    
    latest = df.iloc[-1]
    close = latest['close']
    ma20 = latest['ma20']
    ma50 = latest['ma50']
    rsi = latest['rsi']
    bb_upper = latest['bb_upper']
    bb_lower = latest['bb_lower']
    
    # Trend Classification (Khong can MA200)
    if close > ma20 and close > ma50:
        trend = "Uptrend Mạnh"
        trend_class = "trend-uptrend"
    elif close < ma20 and close < ma50:
        trend = "Downtrend Mạnh"
        trend_class = "trend-downtrend"
    elif close > ma20:
        trend = "Uptrend Ngắn hạn"
        trend_class = "trend-weak-up"
    else:
        trend = "Tích lũy / Sideways"
        trend_class = "trend-sideways"
        
    # RSI Status
    if rsi >= 70:
        rsi_status = "Quá mua"
        rsi_class = "rsi-overbought"
    elif rsi <= 30:
        rsi_status = "Quá bán"
        rsi_class = "rsi-oversold"
    else:
        rsi_status = "Trung tính"
        rsi_class = ""
        
    # Volume Status
    vol_ratio = latest['volume'] / (latest['vol_ma20'] + 1e-9)
    if vol_ratio >= 1.5:
        vol_status = "Đột biến"
        vol_class = "vol-breakout"
    elif vol_ratio <= 0.6:
        vol_status = "Cạn kiệt"
        vol_class = "vol-low"
    else:
        vol_status = "Bình thường"
        vol_class = ""
        
    # Entry, SL, TP Recommendation
    entry = close
    sl = support * 0.95
    tp = resistance
    
    return {
        'symbol': sym,
        'close': close,
        'ma20': ma20,
        'ma50': ma50,
        'rsi': rsi,
        'rsi_status': rsi_status,
        'rsi_class': rsi_class,
        'bb_upper': bb_upper,
        'bb_lower': bb_lower,
        'support': support,
        'resistance': resistance,
        'trend': trend,
        'trend_class': trend_class,
        'volume': latest['volume'],
        'vol_ratio': vol_ratio,
        'vol_status': vol_status,
        'vol_class': vol_class,
        'entry': entry,
        'sl': sl,
        'tp': tp
    }

def main():
    txt_path = "d:/Qlib-Vnstock/instruments/vn100_clean.txt"
    if not os.path.exists(txt_path):
        print(f"Error: {txt_path} không tìm thấy.")
        sys.exit(1)
        
    with open(txt_path, "r", encoding="utf-8") as f:
        symbols = [line.strip() for line in f if line.strip()]
        
    print(f"Đã tải {len(symbols)} mã VN100. Tiến hành quét qua nguồn KBS (tốc độ cao)...")
    
    ta_results = []
    
    for idx, sym in enumerate(symbols):
        print(f"[{idx+1}/{len(symbols)}] Đang xử lý {sym}...", flush=True)
        retries = 2
        while retries > 0:
            try:
                # Dung nguon kbs cho on dinh va nhanh
                q = Quote(symbol=sym, source='kbs')
                # Lay ngan tu 2026-03-01 de tinh MA50 va tranh treo bang thong
                df = q.history(start='2026-03-01', end='2026-06-17', interval='1D')
                
                ta_data = calculate_ta(df, sym)
                if ta_data:
                    ta_results.append(ta_data)
                
                time.sleep(1.2)  # Tránh Rate Limit 60req/min
                break
            except Exception as e:
                err_msg = str(e)
                if "Rate Limit" in err_msg or "GIỚI HẠN API" in err_msg or "rate" in err_msg.lower():
                    print(f" Bị giới hạn tại {sym}. Chờ 60s...", flush=True)
                    time.sleep(60)
                    retries -= 1
                else:
                    print(f" Lỗi xử lý {sym}: {err_msg}", flush=True)
                    time.sleep(1.2)
                    break
                    
    if not ta_results:
        print("❌ Không thu thập được dữ liệu kỹ thuật nào!")
        return
        
    # Tạo HTML Report chuyên nghiệp
    today_str = datetime.now().strftime("%d/%m/%Y")
    desktop = get_desktop_path()
    output_html = os.path.join(desktop, f"bao_cao_ta_vn100_{datetime.now().strftime('%Y%m%d')}.html")
    
    html_rows = ""
    for r in ta_results:
        html_rows += f"""
        <tr>
            <td style="font-weight: 700; color: #60a5fa;">{r['symbol']}</td>
            <td style="font-weight: 600;">{r['close']:,}</td>
            <td class="{r['trend_class']}">{r['trend']}</td>
            <td>{r['ma20']:.2f}</td>
            <td>{r['ma50']:.2f}</td>
            <td class="{r['rsi_class']}">{r['rsi']:.1f} ({r['rsi_status']})</td>
            <td>{r['bb_lower']:.1f} - {r['bb_upper']:.1f}</td>
            <td class="{r['vol_class']}">{r['vol_ratio']:.2f}x ({r['vol_status']})</td>
            <td style="color: #34d399;">{r['support']:,}</td>
            <td style="color: #f87171;">{r['resistance']:,}</td>
            <td style="font-size: 0.85rem;">
                Entry: <strong>{r['entry']:,}</strong><br>
                SL: <strong style="color: #f87171;">{r['sl']:.1f}</strong><br>
                TP: <strong style="color: #34d399;">{r['tp']:,}</strong>
            </td>
        </tr>
        """
        
    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Báo Cáo Phân Tích Kỹ Thuật VN100 - {today_str}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{
            background-color: #0f172a;
            color: #f8fafc;
            font-family: 'Inter', sans-serif;
            margin: 0;
            padding: 30px;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        header {{
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 1px solid #334155;
            padding-bottom: 20px;
        }}
        h1 {{
            font-size: 2.2rem;
            margin: 0 0 10px 0;
            background: linear-gradient(to right, #60a5fa, #3b82f6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .meta {{
            color: #94a3b8;
            font-size: 0.95rem;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background-color: #1e293b;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #334155;
        }}
        th, td {{
            padding: 14px 16px;
            text-align: left;
            border-bottom: 1px solid #334155;
            font-size: 0.9rem;
        }}
        th {{
            background-color: #0f172a;
            color: #94a3b8;
            font-weight: 600;
            cursor: pointer;
        }}
        th:hover {{
            background-color: #1e293b;
        }}
        tr:hover {{
            background-color: #334155;
        }}
        /* Colors for trends */
        .trend-uptrend {{
            color: #34d399;
            font-weight: 600;
            background-color: rgba(52, 211, 153, 0.1);
            border-radius: 4px;
            padding: 4px 8px;
            display: inline-block;
        }}
        .trend-downtrend {{
            color: #f87171;
            font-weight: 600;
            background-color: rgba(248, 113, 113, 0.1);
            border-radius: 4px;
            padding: 4px 8px;
            display: inline-block;
        }}
        .trend-weak-up {{
            color: #6ee7b7;
        }}
        .trend-weak-down {{
            color: #fca5a5;
        }}
        .trend-sideways {{
            color: #cbd5e1;
        }}
        /* Colors for RSI */
        .rsi-overbought {{
            background-color: rgba(245, 158, 11, 0.2);
            color: #fbbf24;
            font-weight: 600;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        .rsi-oversold {{
            background-color: rgba(139, 92, 246, 0.2);
            color: #a78bfa;
            font-weight: 600;
            padding: 2px 6px;
            border-radius: 4px;
        }}
        /* Vol */
        .vol-breakout {{
            color: #34d399;
            font-weight: 600;
        }}
        .vol-low {{
            color: #64748b;
        }}
    </style>
    <script>
        function sortTable(n) {{
            var table, rows, switching, i, x, y, shouldSwitch, dir, switchcount = 0;
            table = document.getElementById("taTable");
            switching = true;
            dir = "asc";
            while (switching) {{
                switching = false;
                rows = table.rows;
                for (i = 1; i < (rows.length - 1); i++) {{
                    shouldSwitch = false;
                    x = rows[i].getElementsByTagName("TD")[n];
                    y = rows[i+1].getElementsByTagName("TD")[n];
                    
                    var xVal = x.innerHTML.toLowerCase().replace(/[^a-z0-9.-]/g, "");
                    var yVal = y.innerHTML.toLowerCase().replace(/[^a-z0-9.-]/g, "");
                    
                    if (!isNaN(parseFloat(xVal)) && !isNaN(parseFloat(yVal))) {{
                        xVal = parseFloat(xVal);
                        yVal = parseFloat(yVal);
                    }}
                    
                    if (dir == "asc") {{
                        if (xVal > yVal) {{
                            shouldSwitch = true;
                            break;
                        }}
                    }} else if (dir == "desc") {{
                        if (xVal < yVal) {{
                            shouldSwitch = true;
                            break;
                        }}
                    }}
                }}
                if (shouldSwitch) {{
                    rows[i].parentNode.insertBefore(rows[i + 1], rows[i]);
                    switching = true;
                    switchcount ++;
                }} else {{
                    if (switchcount == 0 && dir == "asc") {{
                        dir = "desc";
                        switching = true;
                    }}
                }}
            }}
        }}
    </script>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 BÁO CÁO PHÂN TÍCH KỸ THUẬT TOÀN BỘ VN100</h1>
            <div class="meta">Ngày cập nhật: {today_str} | Báo cáo chi tiết đa chỉ báo (MA20, MA50, RSI, BB, Hỗ trợ/Kháng cự, Vol)</div>
            <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 5px;">* Nhấp vào tiêu đề cột để sắp xếp dữ liệu</div>
        </header>
        <table id="taTable">
            <thead>
                <tr>
                    <th onclick="sortTable(0)">Mã CP</th>
                    <th onclick="sortTable(1)">Giá</th>
                    <th onclick="sortTable(2)">Xu hướng</th>
                    <th onclick="sortTable(3)">MA20</th>
                    <th onclick="sortTable(4)">MA50</th>
                    <th onclick="sortTable(5)">RSI (14)</th>
                    <th onclick="sortTable(6)">Bollinger Bands</th>
                    <th onclick="sortTable(7)">Vol/MA20 Vol</th>
                    <th onclick="sortTable(8)">Hỗ trợ (60d)</th>
                    <th onclick="sortTable(9)">Kháng cự (60d)</th>
                    <th>Gợi ý Kỹ thuật</th>
                </tr>
            </thead>
            <tbody>
                {html_rows}
            </tbody>
        </table>
    </div>
</body>
</html>
"""
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"\n✅ Đã xuất báo cáo phân tích kỹ thuật VN100 ra Desktop thành công: {output_html}")

if __name__ == "__main__":
    main()
