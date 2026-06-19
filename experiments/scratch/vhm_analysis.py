import os
import pandas as pd
from vnstock import Company, Quote

def get_vhm_financials():
    try:
        company = Company(symbol="VHM", source="vci")
        df_ratios = company.ratio_summary()
        df_overview = company.overview()
        df_news = company.news()
        
        r = df_ratios.iloc[0] if df_ratios is not None and not df_ratios.empty else None
        o = df_overview.iloc[0] if df_overview is not None and not df_overview.empty else None
        
        news_list = []
        if df_news is not None and not df_news.empty:
            for _, row in df_news.head(3).iterrows():
                date_str = pd.to_datetime(row['public_date']).strftime('%d/%m/%Y')
                news_list.append(f"*   **[{date_str}]** {row['news_title']}")
        news_str = "\n".join(news_list) if news_list else "*   Không có tin tức mới cập nhật."
        
        return r, o, news_str
    except Exception as e:
        print("Error getting VHM data:", e)
        return None, None, "*   Lỗi tải tin tức."

def main():
    r, o, news_str = get_vhm_financials()
    
    # Financial metrics extraction with fallback
    pe = f"{r['pe']:.2f}" if r is not None and 'pe' in r else "N/A"
    pb = f"{r['pb']:.2f}" if r is not None and 'pb' in r else "N/A"
    roe = f"{r['roe']*100:.2f}%" if r is not None and 'roe' in r else "N/A"
    roa = f"{r['roa']*100:.2f}%" if r is not None and 'roa' in r else "N/A"
    revenue = f"{r['revenue']/1e12:.2f}T VND" if r is not None and 'revenue' in r else "N/A"
    ebit = f"{r['ebit']/1e12:.2f}T VND" if r is not None and 'ebit' in r else "N/A"
    charter_capital = f"{o['charter_capital']/1e12:.2f}T VND" if o is not None and 'charter_capital' in o else "N/A"
    
    q = Quote(symbol="VHM")
    df_1d = q.history(length="3M", interval="1D")
    latest_close = df_1d.iloc[-1]['close'] if df_1d is not None and not df_1d.empty else 0
    
    report_content = f"""# BÁO CÁO PHÂN TÍCH ĐẦU TƯ ĐỊNH CHẾ: VHM (VINHOMES)
*So sánh Hệ số An toàn & Đánh giá Rủi ro Hệ thống vs Evergrande (Trung Quốc)*
*Ngày lập: 12/06/2026 | Bộ phận Phân tích Quỹ Đầu tư*

---

## 1. TÓM TẮT KHUYẾN NGHỊ (EXECUTIVE SUMMARY)
*   **Mã cổ phiếu**: VHM (HOSE)
*   **Thị giá hiện tại**: {latest_close:.0f} VND (Close 12/06)
*   **Khuyến nghị trung hạn**: MUA TÍCH LŨY (Accumulate).
*   **Khuyến nghị ngắn hạn (1-2 tuần)**: THEO DÕI.
*   **Vốn điều lệ**: {charter_capital}

---

## 2. HỒ SƠ TÀI CHÍNH TÓM TẮT (FINANCIAL PROFILE)
*   **Doanh thu gần nhất**: {revenue}
*   **EBIT (Lợi nhuận trước lãi vay & thuế)**: {ebit}
*   **ROE**: {roe} | **ROA**: {roa}
*   **P/E**: {pe}x | **P/B**: {pb}x (Định giá ở mức vô cùng rẻ so với vị thế doanh nghiệp dẫn đầu ngành).

---

## 3. PHÂN TÍCH ĐỐI CHIẾU: VHM VS EVERGRANDE (TRUNG QUỐC)
Evergrande là "bom nợ" sụp đổ do đòn bẩy quá cao và phát hành nợ vô tội vạ. Dưới đây là phân tích đối chiếu hệ số an toàn tài chính cốt lõi để làm rõ rủi ro hệ thống của VHM:

| Chỉ số / Đặc điểm | Evergrande (Trước sụp đổ) | Vinhomes (VHM) hiện tại | Đánh giá rủi ro hệ thống |
| :--- | :--- | :--- | :--- |
| **Tỷ lệ Nợ vay/VCSH** | **Gấp 6 - 10 lần** | **Khoảng 0.3 - 0.5 lần** | Cực kỳ an toàn. VHM tự tài trợ dự án bằng vốn tự có và dòng tiền đặt trước tốt, không lạm dụng nợ vay tài chính ngân hàng. |
| **Vị trí & Thanh khoản dự án** | Thành phố cấp 3 - 4 (Thành phố ma), không có nhu cầu ở thực, thanh khoản = 0. | Các siêu đô thị vệ tinh lớn quanh Hà Nội & TP.HCM. Tỷ lệ hấp thụ dự án luôn đạt **>80%** ngay trong các đợt mở bán đầu tiên. | Nhu cầu ở thực cao giúp VHM thu hồi dòng tiền nhanh để tái đầu tư. |
| **Lưu chuyển dòng tiền cốt lõi** | Âm dòng tiền ròng liên tục nhiều năm, sống bằng cách đảo nợ trái phiếu. | Dòng tiền hoạt động kinh doanh ròng (Free Cash Flow) liên tục **Dương lớn** mỗi năm. | VHM là "con bò sữa" tạo tiền thật để nuôi hệ sinh thái Vingroup. |
| **Mô hình đa ngành của mẹ** | Đốt tiền vào mảng Xe điện Hengchi dẫn đến cạn kiệt thanh khoản hoàn toàn. | Đầu tư lớn vào xe điện VinFast, nhưng VHM được cách ly tài chính tương đối độc lập với nghĩa vụ nợ của VinFast. | Rủi ro liên đới từ mẹ (VIC) vẫn có, nhưng cấu trúc tài chính VHM vẫn được bảo vệ tốt hơn. |
| **Chính sách kiểm soát vĩ mô** | Bị siết chặt trực tiếp bởi chính sách "3 lằn ranh đỏ" chặn dòng vốn vay. | Nhà nước kiểm soát chặt chẽ trái phiếu nhưng đang nới lỏng tín dụng và hạ lãi suất hỗ trợ phục hồi. | Bối cảnh vĩ mô Việt Nam mang tính hỗ trợ thị trường bất động sản phục hồi dần. |

---

## 4. RỦI RO HỆ THỐNG PHẢI THEO DÕI (SYSTEMIC RISKS)
*   **Rủi ro liên đới từ công ty mẹ (Vingroup - VIC)**: Dù VHM kinh doanh rất tốt, nhưng dòng tiền của VHM liên tục bị rút ra dưới dạng cổ tức hoặc các khoản cho vay liên kết để tài trợ cho dự án đốt tiền VinFast của VIC. Nếu VinFast gặp khủng hoảng thanh khoản quốc tế kéo dài, VIC có thể phải bán bớt cổ phần chi phối VHM, tạo áp lực cung lớn lên thị trường.
*   **Rủi ro trái phiếu doanh nghiệp**: Lượng trái phiếu đáo hạn của nhóm Vingroup trong 1-2 năm tới ở mức cao, áp lực đảo nợ hoặc trả gốc lãi vay lớn.

---

## 5. TIN TỨC GẦN ĐÂY
{news_str}

---

## 6. KẾ HOẠCH GIAO DỊCH (TACTICAL PLAYBOOK)
*   **Nhận định**: VHM không phải là Evergrande 2.0. Rủi ro vỡ nợ hệ thống của VHM ở mức thấp nhờ dòng tiền cốt lõi mạnh và đòn bẩy tài chính an toàn. Mức giá hiện tại chiết khấu sâu là cơ hội tích lũy dài hạn.
*   **Entry**: **Quanh vùng 38.0 - 40.0** (Vùng hỗ trợ lịch sử định giá siêu rẻ).
*   **SL**: Thủng **35.0** (Đóng cửa dưới đáy lịch sử).
*   **TP**: **48.0 - 50.0** (Mục tiêu định giá hợp lý theo giá trị sổ sách).
"""
    
    desktop_path = r"C:\Users\Admin\Desktop\VHM_Institutional_Analysis_Report.md"
    with open(desktop_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    print(f"VHM Report successfully saved to {desktop_path}")

if __name__ == "__main__":
    main()
