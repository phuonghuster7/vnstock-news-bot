import os
from vnstock import Listing

def build_instruments(output_dir: str):
    """
    Tạo danh sách mã cho Qlib instruments: VN30 và VN100.
    Ghi ra dạng: SYMBOL\tSTART_DATE\tEND_DATE
    """
    listing = Listing(source="kbs")
    
    os.makedirs(output_dir, exist_ok=True)
    
    groups = {
        "VN30": "vn30.txt",
        "VN100": "vn100.txt"
    }
    
    for group, filename in groups.items():
        try:
            # Lấy list symbols
            symbols = listing.symbols_by_group(group).tolist()
            
            output_path = os.path.join(output_dir, filename)
            with open(output_path, 'w', encoding='utf-8') as f:
                for symbol in symbols:
                    f.write(f"{symbol}\t2015-01-01\t2099-12-31\n")
            print(f"Written {len(symbols)} symbols to {output_path}")
        except Exception as e:
            print(f"Error fetching {group}: {e}")

if __name__ == '__main__':
    output_dir = os.path.expanduser('~/.qlib/qlib_data/vn_data/instruments')
    build_instruments(output_dir)
