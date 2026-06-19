import sys
import pandas as pd
sys.stdout.reconfigure(encoding='utf-8')

from vnstock import Company, Quote

symbols = ['GEX', 'GEE', 'VGC']

print("--- CO TUC VA SU KIEN GAN DAY (2025-2026) ---")
for sym in symbols:
    try:
        c = Company(symbol=sym, source='vci')
        df = c.events()
        # Chuyển đổi exright_date sang datetime để lọc
        df['exright_date'] = pd.to_datetime(df['exright_date'])
        # Lọc các sự kiện từ năm 2025 trở đi
        df_recent = df[df['exright_date'] >= '2025-01-01'].sort_values('exright_date', ascending=False)
        print(f"\n[{sym}] Các sự kiện gần đây:")
        if not df_recent.empty:
            for idx, row in df_recent.iterrows():
                print(f" - Ngày GDKHQ: {row['exright_date'].strftime('%Y-%m-%d')} | Sự kiện: {row['event_title_vi']} | Giá trị: {row.get('value_per_share', 'N/A')} | Tỷ lệ: {row.get('exercise_ratio', 'N/A')}")
        else:
            print(" Không có sự kiện nào từ 2025 đến nay.")
    except Exception as e:
        print(f" Lỗi lấy sự kiện cho {sym}: {e}")

print("\n--- GIA CO PHIEU HIEN TAI ---")
for sym in symbols:
    try:
        q = Quote(symbol=sym, source='vci')
        # Lấy lịch sử giá 30 ngày gần đây
        df_price = q.history(start='2026-05-01', end='2026-06-16', interval='1D')
        if not df_price.empty:
            latest = df_price.iloc[-1]
            print(f"[{sym}] Ngày: {latest['time']} | Đóng cửa: {latest['close']:,} | Khối lượng: {latest['volume']:,}")
        else:
            print(f"[{sym}] Không có dữ liệu giá.")
    except Exception as e:
        print(f" Lỗi lấy giá cho {sym}: {e}")
