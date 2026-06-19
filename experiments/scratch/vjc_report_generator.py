import os
import pandas as pd
from vnstock import Company, Quote

def get_vjc_financials():
    try:
        company = Company(symbol="VJC", source="vci")
        # Get financial ratios
        df_ratios = company.ratio_summary()
        # Get overview
        df_overview = company.overview()
        
        ratios = df_ratios.iloc[0] if df_ratios is not None and not df_ratios.empty else None
        overview = df_overview.iloc[0] if df_overview is not None and not df_overview.empty else None
        
        return ratios, overview
    except Exception as e:
        print("Error getting financials:", e)
        return None, None

def main():
    ratios, overview = get_vjc_financials()
    
    # Financial metrics extraction with fallback
    charter_capital = f"{overview['charter_capital']/1e12:.2f}T VND" if overview is not None and 'charter_capital' in overview else "N/A"
    
    pe = f"{ratios['pe']:.2f}" if ratios is not None and 'pe' in ratios else "N/A"
    pb = f"{ratios['pb']:.2f}" if ratios is not None and 'pb' in ratios else "N/A"
    roe = f"{ratios['roe']*100:.2f}%" if ratios is not None and 'roe' in ratios else "N/A"
    roa = f"{ratios['roa']*100:.2f}%" if ratios is not None and 'roa' in ratios else "N/A"
    revenue = f"{ratios['revenue']/1e12:.2f}T VND" if ratios is not None and 'revenue' in ratios else "N/A"
    ebit = f"{ratios['ebit']/1e12:.2f}T VND" if ratios is not None and 'ebit' in ratios else "N/A"
    
    # Report Markdown content
    report_content = f"""# BÁO CÁO PHÂN TÍCH ĐẦU TƯ ĐỊNH CHẾ: VJC (VIETJET AIR)
*Ngày lập: 12/06/2026 | Bộ phận Phân tích Quỹ Đầu tư*

---

## 1. TÓM TẮT KHUYẾN NGHỊ (EXECUTIVE SUMMARY)
*   **Mã cổ phiếu**: VJC (HOSE)
*   **Thị giá hiện tại (12/06/2026)**: 180.600 VND
*   **Khuyến nghị ngắn hạn (1-2 tuần)**: BÁN trước ngày chốt quyền (16/06) - CANH MUA lại sau chia.
*   **Khuyến nghị trung hạn (3-6 tháng)**: THEO DÕI (Neutral).
*   **Vốn điều lệ**: {charter_capital}

---

## 2. HỒ SƠ TÀI CHÍNH & HIỆU QUẢ HOẠT ĐỘNG (FINANCIAL PROFILE)
*   **Doanh thu gần nhất**: {revenue}
*   **EBIT (Lợi nhuận trước lãi vay & thuế)**: {ebit}
*   **ROE (Tỷ suất LN trên vốn CSH)**: {roe}
*   **ROA (Tỷ suất LN trên tổng tài sản)**: {roa}
*   **Định giá**:
    *   **P/E**: {pe}x (Mức định giá tương đối cao so với trung bình ngành hàng không khu vực).
    *   **P/B**: {pb}x.
*   **Đánh giá sức khỏe tài chính**: 
    *   Nợ vay dài hạn lớn do đặc thù ngành thuê mua tàu bay. Lãi suất neo cao gây áp lực chi phí tài chính.
    *   Lợi nhuận cốt lõi phục hồi nhờ mảng vận chuyển quốc tế và bán & thuê lại tàu bay (Sale & Leaseback), tuy nhiên biên lợi nhuận thuần vẫn mỏng.

---

## 3. PHÂN TÍCH TÁC ĐỘNG PHÁ LOÃNG CỔ PHIẾU (30% STOCK DIVIDEND)
*   **Sự kiện**: Chia cổ tức năm 2025 bằng cổ phiếu tỷ lệ 30% (Ngày GDKHQ: 16/06/2026).
*   **Tác động kỹ thuật**: 
    *   Thị giá giảm từ ~180.000 VND về khoảng ~138.000 VND.
    *   Số lượng cổ phiếu lưu hành tăng 30%. EPS và Buchwert (P/B) bị pha loãng tương ứng.
*   **Tác động thanh khoản**: Tăng tính hấp dẫn với dòng tiền Retail nhờ giá cổ phiếu "mềm" hơn. VJC thuộc nhóm thanh khoản trung bình thấp trong VN30, việc pha loãng sẽ giúp cải thiện thanh khoản khớp lệnh hàng ngày.
*   **Rủi ro chôn vốn**: 30% lượng cổ phiếu thưởng cần 1.5 - 2 tháng để niêm yết bổ sung. Nhà đầu tư chịu rủi ro kẹt vốn và biến động thị trường trong thời gian này.

---

## 4. CHIẾN LƯỢC HÀNH ĐỘNG CHO QUỸ (TACTICAL PLAYBOOK)

### Kịch bản ngắn hạn (1-2 tuần):
*   **Hành động**: **BÁN** toàn bộ vị thế sẵn có trước ngày **16/06/2026** (Khuyến nghị thực hiện trong phiên 12/06 hoặc 15/06).
*   **Lý do**: Tránh kẹt vốn 30% vào cổ phiếu thưởng dài hạn. Thị giá trước chia thường có xu hướng kéo rướn nhẹ để chốt quyền, là cơ hội bán giá tốt.

### Kịch bản sau chia (Sau ngày 16/06/2026):
*   **Hành động**: **Mở mua lại** sau khi giá đã điều chỉnh kỹ thuật chiết khấu 30%.
*   **Chi tiết giao dịch**:
    *   **Entry**: Vùng giá đã điều chỉnh kỹ thuật (quanh 138.000đ/cp).
    *   **SL (Stop Loss)**: Thủng vùng hỗ trợ đáy cũ sau điều chỉnh (tương đương giảm 5% từ điểm mua).
    *   **TP (Take Profit)**: 148.000 VND (Mục tiêu hồi phục kỹ thuật lấp gap ngắn hạn, hiệu suất dự kiến ~7%).

---
*Báo cáo được thực hiện cho mục đích tham khảo nội bộ định chế. Nhà đầu tư tự chịu trách nhiệm quyết định.*
"""
    
    # Save to desktop
    desktop_path = r"C:\Users\Admin\Desktop\VJC_Institutional_Analysis_Report.md"
    try:
        with open(desktop_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"Report successfully written to {desktop_path}")
    except Exception as e:
        print("Error writing report to desktop:", e)

if __name__ == "__main__":
    main()
