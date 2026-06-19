import sys
import time
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')

from vnstock import Listing, Company

print("Đang lấy danh sách mã cổ phiếu VN30...", flush=True)
try:
    listing = Listing(source='kbs')
    symbols = listing.indices(index='VN30')
    if not symbols or len(symbols) == 0:
        # Danh sách VN30 phổ biến đề phòng API lỗi
        symbols = [
            'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG',
            'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB',
            'TCB', 'TPB', 'VCB', 'VJC', 'VHM', 'VIC', 'VNM', 'VPB', 'VRE', 'HDB'
        ]
except Exception:
    symbols = [
        'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG',
        'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB',
        'TCB', 'TPB', 'VCB', 'VJC', 'VHM', 'VIC', 'VNM', 'VPB', 'VRE', 'HDB'
    ]

symbols = list(set(symbols))
print(f"Tổng số mã VN30 cần quét: {len(symbols)}", flush=True)

upcoming_events = []
current_date = '2026-06-16'

for idx, sym in enumerate(symbols):
    print(f"[{idx+1}/{len(symbols)}] Đang quét {sym}...", flush=True)
    retries = 2
    while retries > 0:
        try:
            c = Company(symbol=sym, source='vci')
            df = c.events()
            
            if df is not None and not df.empty:
                df['exright_date_dt'] = pd.to_datetime(df['exright_date'], errors='coerce')
                df_filtered = df[df['exright_date_dt'] >= current_date]
                
                # Lọc các sự kiện liên quan đến cổ tức/phát hành
                df_div = df_filtered[df_filtered['event_code'].isin(['DIV', 'BONUS', 'RIGHTS', 'SPLIT']) | 
                                     df_filtered['event_name_vi'].str.contains('cổ tức|phát hành|thưởng', case=False, na=False)]
                
                if not df_div.empty:
                    for _, row in df_div.iterrows():
                        title = row['event_title_vi']
                        event_type = "Tiền mặt" if "tiền mặt" in title.lower() else ("Cổ phiếu" if "cổ phiếu" in title.lower() or "thưởng" in title.lower() else "Khác")
                        
                        upcoming_events.append({
                            'Ticker': sym,
                            'Event': title,
                            'Exright Date': row['exright_date_dt'].strftime('%Y-%m-%d'),
                            'Type': event_type,
                            'Value': row.get('value_per_share', 'N/A'),
                            'Ratio': row.get('exercise_ratio', 'N/A')
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

# Tạo DataFrame kết quả và in ra
if upcoming_events:
    df_res = pd.DataFrame(upcoming_events)
    df_res = df_res.sort_values(by='Exright Date')
    print("\n--- KẾT QUẢ QUÉT CỔ TỨC SẮP TỚI VN30 (TỪ 16/06/2026) ---", flush=True)
    print(df_res.to_string(index=False), flush=True)
else:
    print("\nKhông tìm thấy cổ phiếu nào chuẩn bị chia cổ tức/phát hành từ ngày 16/06/2026 trong VN30.", flush=True)
