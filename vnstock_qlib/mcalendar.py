import os
from datetime import datetime
from vnstock import Quote

def build_calendar(output_path: str) -> list[str]:
    """Trả về list ngày giao dịch VN, đồng thời ghi ra day.txt"""
    # Khởi tạo API
    quote = Quote(source="kbs", symbol="HPG")
    
    # Fetch từ 2015 đến hôm nay
    today_str = datetime.today().strftime('%Y-%m-%d')
    df = quote.history(
        start="2015-01-01",
        end=today_str,
        interval="1D"
    )
    
    if df is None or df.empty:
        raise ValueError("Lỗi: Không lấy được dữ liệu HPG.")
        
    # Lấy ngày định dạng YYYY-MM-DD
    dates = df['time'].dt.strftime('%Y-%m-%d').tolist()

    # Đảm bảo thư mục tồn tại
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Ghi ra file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(dates))
        
    print(f"Written {len(dates)} days to {output_path}")
    return dates

if __name__ == '__main__':
    output_dir = os.path.expanduser('~/.qlib/qlib_data/vn_data/calendars')
    output_path = os.path.join(output_dir, 'day.txt')
    build_calendar(output_path)
