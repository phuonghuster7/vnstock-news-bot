"""
Test scrape tự doanh CTCK từ HSX.
Thử nhiều URL pattern và parse format.
"""
import requests
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.hsx.vn",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
}

def test_url(url: str, label: str):
    print(f"\n{'─'*55}")
    print(f"  Testing: {label}")
    print(f"  URL: {url[:80]}...")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        print(f"  Status: {resp.status_code}")
        print(f"  Content-Type: {resp.headers.get('Content-Type', 'unknown')}")
        print(f"  Content-Length: {len(resp.content)} bytes")
        ct = resp.headers.get("Content-Type", "")
        if "html" in ct:
            # Thử parse HTML table
            try:
                tables = pd.read_html(StringIO(resp.text))
                print(f"  Tables found: {len(tables)}")
                for i, t in enumerate(tables[:2]):
                    print(f"  Table {i}: shape={t.shape}, cols={t.columns[:5].tolist()}")
            except Exception as e:
                print(f"  HTML parse error: {e}")
                # Print first 500 chars
                print(f"  Response preview: {resp.text[:300]}")
        elif "json" in ct:
            data = resp.json()
            print(f"  JSON keys: {list(data.keys())[:10] if isinstance(data, dict) else 'list'}")
        elif "excel" in ct or "spreadsheet" in ct or "octet" in ct:
            print(f"  Excel/binary response — download successful")
        else:
            print(f"  Unknown format preview: {resp.text[:200]}")
    except Exception as e:
        print(f"  Error: {e}")

# Ngày hôm qua (ngày giao dịch)
yesterday = datetime.today() - timedelta(days=1)
if yesterday.weekday() >= 5:
    yesterday = datetime.today() - timedelta(days=yesterday.weekday() - 4)
date_slash = yesterday.strftime("%d/%m/%Y")
date_dash  = yesterday.strftime("%Y-%m-%d")
date_compact = yesterday.strftime("%d%m%Y")

print(f"Testing date: {date_slash}")

# URL patterns cần test
urls = [
    (f"https://www.hsx.vn/Modules/Listed/Web/Proprietary?date={date_slash}",
     "HSX Proprietary (slash date)"),
    
    (f"https://www.hsx.vn/Modules/Listed/Web/Proprietary",
     "HSX Proprietary (no date)"),
    
    ("https://www.hsx.vn/Modules/Listed/Web/Proprietary/ExportExcel",
     "HSX Proprietary Excel Export"),
     
    (f"https://api.hsx.vn/api/proprietary?date={date_dash}",
     "HSX API v1"),
]

for url, label in urls:
    test_url(url, label)

# Cũng thử vnstock Trading.prop_trade nếu có
print(f"\n{'─'*55}")
print(f"  Testing: vnstock Trading.prop_trade()")
try:
    from vnstock import Trading
    t = Trading(symbol="VCB", source="VCI")
    if hasattr(t, "prop_trade"):
        result = t.prop_trade()
        print(f"  Type: {type(result)}")
        if result is not None:
            print(f"  Shape: {result.shape}")
            print(f"  Columns: {result.columns.tolist()[:10]}")
            print(result.head(5).to_string())
    else:
        print("  Method prop_trade không tồn tại")
except Exception as e:
    print(f"  Error: {e}")
