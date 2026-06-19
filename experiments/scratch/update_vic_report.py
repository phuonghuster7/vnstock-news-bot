import os

def main():
    report_path = r"C:\Users\Admin\Desktop\VIC_Institutional_Analysis_Report.md"
    if not os.path.exists(report_path):
        print("Report not found.")
        return
        
    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Expand Financial and Debt structure
    old_financial = """## 3. HỒ SƠ TÀI CHÍNH TÓM TẮT (FINANCIAL SUMMARY)
*   **Doanh thu**: 0.00T VND
*   **Lợi nhuận gộp**: 0.00T VND
*   **P/E**: 79.33x | **P/B**: 8.45x
*   **ROE**: 8.36% | **ROA**: 2.05%
*   *Nhận định*: Chi phí lãi vay lớn từ hoạt động tài trợ các dự án công nghệ (VinFast) tiếp tục bào mòn lợi nhuận cốt lõi của tập đoàn mẹ, biên lợi nhuận ròng duy trì ở mức rất thấp."""

    new_financial_debt = """## 3. THUYẾT MINH BÁO CÁO TÀI CHÍNH & CHỈ SỐ DOANH NGHIỆP
*   **Hiệu quả kinh doanh (Q1/2026)**: Doanh thu thuần hợp nhất đạt **104.352 tỷ VND**, Lợi nhuận sau thuế đạt **5.610 tỷ VND** (gấp 2.5 lần cùng kỳ năm 2025). Doanh thu năm 2025 đạt kỷ lục **332.808 tỷ VND**.
*   **Định giá tài sản**: P/E: **79.33x** | P/B: **8.45x**. Định giá ở mức Premium rất cao, phản ánh kỳ vọng rủi ro của dòng tiền định chế đối với mảng công nghệ.
*   **Hiệu quả sử dụng vốn**: ROE: **8.36%** | ROA: **2.05%**. Khả năng sinh lời trên tổng tài sản rất mỏng do quy mô tài sản phình to nhưng hiệu quả sinh lời cốt lõi chưa tương xứng.

---

## 4. PHÂN TÍCH CHUYÊN SÂU CƠ CẤU NỢ (DEBT PROFILE ANALYSIS)
*   **Quy mô nợ**: Tổng nợ phải trả vượt mốc **1.000.000 tỷ VND** (1 triệu tỷ VND) đầu năm 2026.
*   **Chất lượng cơ cấu nợ**: 
    *   *Nợ vay tài chính thực tế* (ngân hàng + trái phiếu) chỉ chiếm khoảng **35%** tổng nợ phải trả (tương đương khoảng **350.000 tỷ VND**).
    *   *Nợ phi tài chính* (người mua trả tiền trước của Vinhomes, đặt cọc mua nhà) chiếm phần lớn còn lại. Đây không phải nợ xấu mà là nguồn lực doanh thu tích lũy sẽ được ghi nhận dần khi bàn giao dự án.
*   **Áp lực lãi vay**: Chi phí tài chính (lãi vay và chênh lệch tỷ giá) năm 2025 tăng gấp đôi so với 2024. Dòng tiền kinh doanh từ Vinhomes (VHM) đang gánh toàn bộ nghĩa vụ trả nợ và tài trợ vốn R&D/Capex cho VinFast.

---

## 5. RỦI RO VĨ MÔ ĐỐI VỚI VINGROUP (MACRO RISKS)
*   **Rủi ro Tỷ giá (VND/USD)**: VIC có lượng nợ vay bằng ngoại tệ (USD) rất lớn từ các định chế quốc tế tài trợ cho VinFast. Xu hướng thắt chặt tiền tệ toàn cầu và tỷ giá biến động gây áp lực chênh lệch tỷ giá lớn lên chi phí tài chính (dù đã sử dụng các hợp đồng hoán đổi tiền tệ - Swap).
*   **Rủi ro Lãi suất**: Mặt bằng lãi suất huy động trong nước có xu hướng tăng vào năm 2026 (một số bank lớn neo lãi suất tiền gửi lớn lên tới 10%/năm) sẽ gián tiếp đẩy chi phí vay nợ mới của VIC lên cao, làm giảm biên lợi nhuận ròng vốn đã mỏng.
*   **Rủi ro Thanh khoản Bất động sản**: Dòng tiền của VIC phụ thuộc hoàn toàn vào tốc độ bán hàng và bàn giao dự án của Vinhomes. Bất kỳ sự đóng băng hay thắt chặt pháp lý nào của thị trường Bất động sản trong nước sẽ lập tức làm nghẽn mạch máu dòng tiền của toàn bộ hệ sinh thái Vingroup.
*   **Rủi ro Cạnh tranh mảng Xe điện**: Sự bành trướng của các hãng xe điện Trung Quốc giá rẻ tiến vào thị trường Việt Nam và quốc tế đe dọa trực tiếp đến thị phần và tốc độ hòa vốn của VinFast."""

    # Replace in content
    updated_content = content.replace(old_financial, new_financial_debt)
    
    # Update section numbering for the rest of the file
    updated_content = updated_content.replace("## 4. TIN TỨC GẦN ĐÂY", "## 6. TIN TỨC GẦN ĐÂY")
    updated_content = updated_content.replace("## 5. KẾ HOẠCH GIAO DỊCH", "## 7. KẾ HOẠCH GIAO DỊCH")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(updated_content)
        
    print("Report updated successfully.")

if __name__ == "__main__":
    main()
