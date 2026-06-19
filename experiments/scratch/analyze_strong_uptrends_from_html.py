import os
import sys
import time
from datetime import datetime
from bs4 import BeautifulSoup
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

def main():
    desktop = get_desktop_path()
    # Đường dẫn file HTML đã sinh trong ngày hôm nay 17/06/2026
    html_path = os.path.join(desktop, f"bao_cao_ta_vn100_{datetime.now().strftime('%Y%m%d')}.html")
    
    if not os.path.exists(html_path):
        print(f"Error: Không tìm thấy file báo cáo vĩ mô {html_path} trên Desktop.")
        sys.exit(1)
        
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")
        
    table = soup.find("table")
    if not table:
        print("Error: Không tìm thấy bảng dữ liệu trong file HTML.")
        sys.exit(1)
        
    rows = table.find("tbody").find_all("tr")
    
    strong_uptrends = []
    
    for r in rows:
        cells = r.find_all("td")
        if len(cells) >= 11:
            sym = cells[0].get_text().strip()
            close_val = float(cells[1].get_text().strip().replace(",", ""))
            trend = cells[2].get_text().strip()
            ma20 = float(cells[3].get_text().strip().replace(",", ""))
            ma50 = float(cells[4].get_text().strip().replace(",", ""))
            
            # Lấy RSI (cắt chuỗi chỉ lấy phần số)
            rsi_text = cells[5].get_text().strip()
            rsi_val = float(rsi_text.split()[0])
            
            vol_ratio_text = cells[7].get_text().strip()
            vol_ratio = float(vol_ratio_text.split("x")[0])
            
            support = float(cells[8].get_text().strip().replace(",", ""))
            resistance = float(cells[9].get_text().strip().replace(",", ""))
            
            if "Uptrend" in trend:
                strong_uptrends.append({
                    'symbol': sym,
                    'close': close_val,
                    'trend': trend,
                    'ma20': ma20,
                    'ma50': ma50,
                    'rsi': rsi_val,
                    'vol_ratio': vol_ratio,
                    'support': support,
                    'resistance': resistance
                })
                
    if not strong_uptrends:
        print("Không tìm thấy mã nào có trạng thái Uptrend trong báo cáo.")
        return
        
    # Lọc ra top 5 mã mạnh nhất (Ưu tiên những mã có RSI cao nhưng chưa quá mua > 70, hoặc có dòng tiền đột biến nhất)
    # Sắp xếp theo vol_ratio giảm dần (dòng tiền đột phá nhất)
    strong_uptrends = sorted(strong_uptrends, key=lambda x: x['vol_ratio'], reverse=True)
    
    print(f"=== PHÂN TÍCH CHUYÊN SÂU TOP 5 MÃ UPTREND MẠNH NHẤT THỊ TRƯỜNG ===")
    print(f"Dữ liệu nguồn trích xuất từ báo cáo ngày: {datetime.now().strftime('%d/%m/%Y')}")
    
    for idx, cand in enumerate(strong_uptrends[:5]):
        sym = cand['symbol']
        print(f"\n------------------------------------------------------------")
        print(f"🔥 [{idx+1}/5] PHÂN TÍCH OHLCV & CHỈ BÁO KỸ THUẬT: {sym}")
        print(f"------------------------------------------------------------")
        print(f" - Giá hiện tại: {cand['close']:,} VND | Xu hướng: {cand['trend']}")
        print(f" - MA20: {cand['ma20']:.2f} | MA50: {cand['ma50']:.2f} | RSI (14): {cand['rsi']:.1f}")
        print(f" - Tỷ lệ Vol/MA20 Vol: {cand['vol_ratio']:.2f}x")
        print(f" - Hỗ trợ (60d): {cand['support']:,} | Kháng cự (60d): {cand['resistance']:,}")
        
        # Tải dữ liệu OHLCV 10 phiên gần nhất để phân tích cấu trúc giá và khối lượng chi tiết
        try:
            q = Quote(symbol=sym, source='kbs')
            df = q.history(start='2026-05-25', end='2026-06-17', interval='1D')
            if df is not None and not df.empty:
                recent_5 = df.tail(5)
                print("\n   * Diễn biến OHLCV 5 phiên gần nhất:")
                for i, row in recent_5.iterrows():
                    prev_close = df.loc[i-1, 'close'] if i > 0 else row['close']
                    change = ((row['close'] - prev_close) / prev_close) * 100
                    print(f"     Ngày {row['time'].strftime('%Y-%m-%d')} | O: {row['open']:.1f} | H: {row['high']:.1f} | L: {row['low']:.1f} | C: {row['close']:.1f} | Vol: {row['volume']:,.0f} ({change:+.2f}%)")
                
                # Logic phân tích khối lượng & giá (Price Action)
                last_row = recent_5.iloc[-1]
                prev_row = recent_5.iloc[-2]
                last_change = ((last_row['close'] - prev_row['close']) / prev_row['close']) * 100
                
                print("\n   * Đánh giá Cấu trúc và Dòng tiền:")
                if last_change > 1.5 and cand['vol_ratio'] > 1.3:
                    print("     👉 BREAKOUT xác nhận: Giá tăng mạnh kèm khối lượng vượt trội. Dòng tiền thông minh (Smart Money) đang đẩy giá quyết liệt khỏi nền tích lũy.")
                elif abs(last_change) < 1.0 and cand['vol_ratio'] < 0.7:
                    print("     👉 TÍCH LŨY CUNG CẠN: Giá đi ngang biên độ hẹp với thanh khoản thấp dần. Đây là trạng thái tích lũy lành mạnh, lực bán đã cạn kiệt, chuẩn bị có biến động mạnh.")
                elif last_change < -1.5 and cand['vol_ratio'] > 1.3:
                    print("     👉 ÁP LỰC CHỐT LỜI: Xuất hiện nến giảm mạnh kèm Vol lớn. Cần thận trọng nhịp phân phối ngắn hạn.")
                else:
                    print("     👉 XU HƯỚNG BỀN VỮNG: Giá tăng đều đặn với thanh khoản duy trì quanh mức trung bình. Xu hướng tăng tự nhiên chưa có dấu hiệu suy yếu.")
                
                # Chiến lược giao dịch logic chuyên nghiệp
                if cand['rsi'] > 70:
                    entry_strategy = f"Chờ mua khi điều chỉnh về vùng hỗ trợ động MA20 ({cand['ma20']:.1f} - {cand['ma20']*1.02:.1f} VND). Tránh mua đuổi vì rủi ro rung lắc ngắn hạn do RSI ở vùng quá mua ({cand['rsi']:.1f})."
                else:
                    entry_strategy = f"Vùng mua (Entry) tối ưu quanh {cand['close']:,} VND (vùng tích lũy hiện tại) hoặc gom dần khi rung lắc về sát đường MA20 ({cand['ma20']:.1f} VND)."
                    
                sl_price = cand['support'] * 0.95
                tp_price = cand['resistance'] if cand['close'] < cand['resistance'] else cand['close'] * 1.15
                
                print("\n   * Khuyến nghị Giao dịch chi tiết:")
                print(f"     - Entry: {entry_strategy}")
                print(f"     - Stop Loss (SL): {sl_price:.1f} VND (Dưới đáy 60 ngày 5% để quản trị rủi ro chặt chẽ)")
                print(f"     - Take Profit (TP): {tp_price:.1f} VND (Mục tiêu đỉnh cũ hoặc tỷ lệ tăng trưởng kỳ vọng 15%)")
            time.sleep(1.0)
        except Exception as e:
            print(f"   [Lỗi khi tải lịch sử OHLCV cho {sym}]: {e}")
            
if __name__ == "__main__":
    main()
