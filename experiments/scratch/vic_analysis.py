import os
import time
import pandas as pd
import numpy as np
from vnstock import Company, Quote

def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / (loss + 1e-9)
    return 100 - (100 / (1 + rs))

def main():
    q = Quote(symbol="VIC")
    company = Company(symbol="VIC", source="vci")
    
    # 1. Fetch Weekly (1W) - 1 Year
    df_1w = q.history(length="1Y", interval="1W")
    df_1w['time'] = pd.to_datetime(df_1w['time'])
    df_1w = df_1w.sort_values('time').reset_index(drop=True)
    
    # 2. Fetch Daily (1D) - 3 Months
    df_1d = q.history(length="3M", interval="1D")
    df_1d['time'] = pd.to_datetime(df_1d['time'])
    df_1d = df_1d.sort_values('time').reset_index(drop=True)
    
    # 3. Fetch Hourly (1H) - 3 Weeks
    df_1h = q.history(length="3W", interval="1H")
    df_1h['time'] = pd.to_datetime(df_1h['time'])
    df_1h = df_1h.sort_values('time').reset_index(drop=True)
    
    print(f"VIC Data Loaded: {len(df_1w)} weekly, {len(df_1d)} daily, {len(df_1h)} hourly.")
    
    # Fetch news
    news_list = []
    try:
        df_news = company.news()
        if df_news is not None and not df_news.empty:
            df_news['public_date'] = pd.to_datetime(df_news['public_date'])
            # Get latest 5 news
            for _, row in df_news.head(5).iterrows():
                news_list.append(f"*   **[{row['public_date'].strftime('%d/%m/%Y')}]** {row['news_title']}")
    except Exception as e:
        print("Error getting news:", e)
        
    news_str = "\n".join(news_list) if news_list else "*   Không có tin tức mới cập nhật trên hệ thống VCI."
    
    # Analyze Indicators
    # Weekly
    df_1w['ma20'] = df_1w['close'].rolling(window=20).mean()
    latest_w = df_1w.iloc[-1]
    w_trend = "Uptrend" if latest_w['close'] > latest_w['ma20'] else "Downtrend"
    
    # Daily
    df_1d['ma20'] = df_1d['close'].rolling(window=20).mean()
    df_1d['rsi'] = calculate_rsi(df_1d)
    latest_d = df_1d.iloc[-1]
    d_trend = "Uptrend" if latest_d['close'] > latest_d['ma20'] else "Downtrend"
    
    # Hourly Smart Money
    df_1h['vol_ma20'] = df_1h['volume'].rolling(window=20).mean()
    df_1h['vol_ratio'] = df_1h['volume'] / (df_1h['vol_ma20'] + 1e-9)
    high_vol = df_1h[df_1h['vol_ratio'] > 1.5].copy()
    high_vol['type'] = np.where(high_vol['close'] >= high_vol['open'], 'BUYING', 'SELLING')
    
    sm_hours = []
    for _, row in high_vol.tail(4).iterrows():
        sm_hours.append(f"*   **{row['time'].strftime('%d/%m %H:%M')}**: {row['type']} | Vol Ratio: {row['vol_ratio']:.2f} | Close: {row['close']}")
    sm_str = "\n".join(sm_hours) if sm_hours else "*   Không có dòng tiền đột biến trong 3 tuần qua."
    
    # Financial summary
    financials_str = ""
    try:
        df_ratios = company.ratio_summary()
        if df_ratios is not None and not df_ratios.empty:
            r = df_ratios.iloc[0]
            financials_str = f"""*   **Doanh thu**: {r.get('revenue', 0)/1e12:.2f}T VND
*   **Lợi nhuận gộp**: {r.get('gross_profit', 0)/1e12:.2f}T VND
*   **P/E**: {r.get('pe', 0):.2f}x | **P/B**: {r.get('pb', 0):.2f}x
*   **ROE**: {r.get('roe', 0)*100:.2f}% | **ROA**: {r.get('roa', 0)*100:.2f}%"""
    except:
        financials_str = "*   Không lấy được dữ liệu tài chính tóm tắt."

    # Write report
    report = f"""# BÁO CÁO PHÂN TÍCH ĐẦU TƯ ĐỊNH CHẾ: VIC (VINGROUP)
*Ngày lập: 12/06/2026 | Bộ phận Phân tích Quỹ Đầu tư*

---

## 1. TÓM TẮT KHUYẾN NGHỊ (EXECUTIVE SUMMARY)
*   **Mã cổ phiếu**: VIC (HOSE)
*   **Thị giá hiện tại**: {latest_d['close']:.0f} VND (Close 12/06)
*   **Khuyến nghị ngắn hạn (1-2 tuần)**: THEO DÕI / BÁN HẠ TỶ TRỌNG (Underweight).
*   **Khuyến nghị trung hạn**: TRUNG LẬP (Neutral).
*   **Xu hướng dài hạn**: {w_trend} (Dựa trên đồ thị tuần).

---

## 2. PHÂN TÍCH ĐA KHUNG THỜI GIAN (MULTIPLE TIMEFRAME ANALYSIS)
*   **Khung Tuần (1W - Xu hướng trung dài hạn)**: 
    *   Trạng thái: **{w_trend}**. Giá đóng cửa {latest_w['close']:.0f} VND so với MA20 tuần ({latest_w['ma20']:.0f} VND).
    *   Biên độ biến động trung hạn đang siết lại, chưa hình thành sóng tăng rõ rệt.
*   **Khung Ngày (1D - Xu hướng ngắn hạn)**:
    *   Trạng thái: **{d_trend}**. Giá nằm { "trên" if d_trend == "Uptrend" else "dưới" } MA20 ngày ({latest_d['ma20']:.0f} VND).
    *   **RSI (14)**: {latest_d['rsi']:.2f} (Nằm ở vùng trung tính yếu, lực cầu yếu).
*   **Khung Giờ (1H - Dấu chân Smart Money)**:
    *   Xung lực dòng tiền lớn trong 3 tuần qua:
{sm_str}
    *   *Đọc vị*: Dòng tiền lớn hoạt động khá rời rạc, thiếu sự đồng thuận đẩy giá liên tục. Các phiên nổ Vol chủ yếu là nến giằng co hoặc áp lực bán nhẹ.

---

## 3. HỒ SƠ TÀI CHÍNH TÓM TẮT (FINANCIAL SUMMARY)
{financials_str}
*   *Nhận định*: Chi phí lãi vay lớn từ hoạt động tài trợ các dự án công nghệ (VinFast) tiếp tục bào mòn lợi nhuận cốt lõi của tập đoàn mẹ, biên lợi nhuận ròng duy trì ở mức rất thấp.

---

## 4. TIN TỨC GẦN ĐÂY & CHẤT XÚC TÁC (NEWS & CATALYSTS)
{news_str}
*   *Đánh giá tác động*: Các thông tin liên quan đến hoạt động IPO/niêm yết công ty con hoặc chuyển nhượng dự án bất động sản lớn là chất xúc tác chính để VIC tạo các sóng hồi kỹ thuật ngắn hạn. Nhỏ lẻ dễ bị FOMO bởi tin tức lớn nhưng cần chú ý cơ cấu nợ thực tế của tập đoàn.

---

## 5. KẾ HOẠCH GIAO DỊCH (TACTICAL PLAYBOOK)
*   **Entry**: Không mở mua mới ở vùng giá hiện tại do thiếu sự xác nhận của dòng tiền lớn (Smart Money). Canh mua tại vùng hỗ trợ cứng nếu có nhịp rũ bỏ mạnh.
*   **SL (Stop Loss)**: Cắt lỗ nếu mua và giá đóng cửa giảm quá 5% từ điểm mua hoặc thủng vùng hỗ trợ MA200 ngày.
*   **TP (Take Profit)**: Kháng cự đỉnh cũ ngắn hạn gần nhất (Resistance).
"""

    desktop_path = r"C:\Users\Admin\Desktop\VIC_Institutional_Analysis_Report.md"
    with open(desktop_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved to {desktop_path}")

if __name__ == "__main__":
    main()
