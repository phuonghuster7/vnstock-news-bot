import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timezone, timedelta
import dateutil.parser as date_parser
import html
import re
import os
from urllib.parse import quote

# 1. Các nguồn RSS chính thống hiện tại kết hợp các kênh Google News Aggregator để bao phủ hàng nghìn báo
# Google News giúp tổng hợp tất cả các bài viết về một chủ đề vĩ mô từ hàng nghìn nguồn báo chí Việt Nam
GOOGLE_NEWS_MACRO_URL = "https://news.google.com/rss/search?q=" + quote("lãi suất OR lạm phát OR chứng khoán OR vĩ mô OR tỷ giá OR doanh nghiệp") + "&hl=vi&gl=VN&ceid=VN:vi"
GOOGLE_NEWS_GEOPOLITICS_URL = "https://news.google.com/rss/search?q=" + quote("địa chính trị OR chiến tranh OR xung đột OR thuế quan") + "&hl=vi&gl=VN&ceid=VN:vi"

RSS_FEEDS = {
    # Cổng tổng hợp toàn bộ báo chí Việt Nam (Google News)
    "Google News - Tài chính vĩ mô": GOOGLE_NEWS_MACRO_URL,
    "Google News - Địa chính trị": GOOGLE_NEWS_GEOPOLITICS_URL,
    # Các báo chuyên ngành tài chính cốt lõi làm mốc đối chiếu
    "CafeF - Thị trường": "https://cafef.vn/thi-truong-chung-khoan.rss",
    "CafeF - Vĩ mô": "https://cafef.vn/thoi-su.rss",
    "VnEconomy - Tài chính": "https://vneconomy.vn/tai-chinh-ngan-hang.rss",
    "Vietstock - Vĩ mô": "https://vietstock.vn/rss/tai-chinh.rss"
}

THEMATIC_KEYWORDS = {
    "Lãi suất & Tiền tệ (Rates & Inflation)": [
        "lãi suất", "lạm phát", "tỷ giá", "usd", "vnd", "tiền tệ", "fed", "nhnn", 
        "ngân hàng trung ương", "hạ lãi suất", "tăng lãi suất", "hút tiền", "vàng", "sjc", "gold"
    ],
    "Địa chính trị & Chiến tranh (Geopolitics & Macro Impact)": [
        "chiến tranh", "xung đột", "địa chính trị", "tấn công", "quân sự", "tên lửa", 
        "giao tranh", "leo thang", "nổ súng", "biên giới", "trừng phạt", "mỹ - trung",
        "israel", "iran", "nga", "ukraine", "gaza", "houthi", "hormuz", "thỏa thuận hòa bình"
    ],
    "Kinh tế Thế giới (Global Economy)": [
        "kinh tế thế giới", "kinh tế toàn cầu", "gdp mỹ", "lạm phát mỹ", "wall street",
        "chứng khoán mỹ", "indonesia", "trung quốc", "nhật bản", "châu âu", "rupiah", "yen",
        "thuế quan", "thương mại", "xuất khẩu"
    ],
    "Vĩ mô Việt Nam & Chính sách (VN Macro & Policies)": [
        "vĩ mô", "gdp", "cpi", "đầu tư công", "fdi", "thuế", "chính sách", "nghị quyết",
        "thông tư", "bộ tài chính", "chính phủ", "thủ tướng", "thanh tra", "quy hoạch"
    ],
    "Chứng khoán & Doanh nghiệp nổi bật (Market & Corporate)": [
        "chứng khoán", "cổ phiếu", "vn-index", "tự doanh", "khối ngoại", "bán ròng",
        "mua ròng", "khớp lệnh", "thanh khoản", "cổ tức", "lợi nhuận", "doanh thu",
        "chủ tịch", "khởi tố", "bắt giam", "tạm giam", "thâu tóm", "sáp nhập",
        "coteccons", "masan", "vinfast", "spacex", "tesla", "apple", "nvidia"
    ]
}

def fix_encoding(text):
    if not text:
        return ""
    try:
        return re.sub(r'#([0-9]+);?', lambda m: chr(int(m.group(1))), text)
    except Exception:
        return text

def parse_rss(source_name, url):
    articles = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code != 200:
            return articles
            
        root = ET.fromstring(response.content)
        for item in root.findall(".//item"):
            title_raw = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            pub_date_raw = item.find("pubDate").text if item.find("pubDate") is not None else ""
            description_raw = item.find("description").text if item.find("description") is not None else ""
            
            title = fix_encoding(html.unescape(title_raw)).strip()
            desc_decoded = fix_encoding(html.unescape(description_raw)).strip()
            
            desc_soup = BeautifulSoup(desc_decoded, "html.parser")
            description = desc_soup.get_text().strip()
            
            pub_date = None
            if pub_date_raw:
                try:
                    pub_date = date_parser.parse(pub_date_raw)
                except Exception:
                    pass
            
            articles.append({
                "source": source_name,
                "title": title,
                "link": link.strip(),
                "pub_date": pub_date,
                "description": description
            })
    except Exception:
        pass
    return articles

def classify_article(title, description):
    combined_text = (title + " " + description).lower()
    for category, keywords in THEMATIC_KEYWORDS.items():
        for kw in keywords:
            if kw in combined_text:
                return category
    return None

# Thuật toán gom cụm (Clustering) đơn giản dựa trên tỷ lệ trùng lặp từ khóa trong tiêu đề
def clean_words(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    words = set(text.split())
    # Loại bỏ các từ dừng cơ bản trong tiếng Việt
    stop_words = {"và", "của", "đã", "đang", "sẽ", "được", "bị", "có", "cho", "lên", "xuống", "tại", "trong", "về", "những", "các", "ngày", "năm"}
    return words - stop_words

def calculate_similarity(title1, title2):
    w1 = clean_words(title1)
    w2 = clean_words(title2)
    if not w1 or not w2:
        return 0.0
    intersection = w1.intersection(w2)
    union = w1.union(w2)
    return len(intersection) / len(union)

def cluster_articles(articles):
    clustered = []
    # Sắp xếp bài viết theo thời gian giảm dần trước khi gom cụm
    sorted_articles = sorted(articles, key=lambda x: x["pub_date"] or datetime.min, reverse=True)
    
    for art in sorted_articles:
        found_cluster = False
        for cluster in clustered:
            # So sánh với bài viết đại diện của cụm
            sim = calculate_similarity(art["title"], cluster["representative"]["title"])
            if sim > 0.35:  # Ngưỡng tương đồng 35% từ khóa (đủ để nhận diện cùng một sự kiện)
                cluster["sources"].append({
                    "source": art["source"],
                    "title": art["title"],
                    "link": art["link"]
                })
                # Giữ pub_date mới nhất cho cụm
                if art["pub_date"] and (not cluster["representative"]["pub_date"] or art["pub_date"] > cluster["representative"]["pub_date"]):
                    cluster["representative"]["pub_date"] = art["pub_date"]
                found_cluster = True
                break
        if not found_cluster:
            clustered.append({
                "representative": art,
                "sources": [{
                    "source": art["source"],
                    "title": art["title"],
                    "link": art["link"]
                }]
            })
    return clustered

def main():
    print("🤖 Con bot Morning Brief thông minh đang quét hàng nghìn nguồn báo song song qua Google Aggregator...")
    all_articles = []
    
    for source, url in RSS_FEEDS.items():
        print(f"-> Kết nối & Quét: {source}")
        all_articles.extend(parse_rss(source, url))
        
    if not all_articles:
        print("❌ Không thu thập được tin tức!")
        return
        
    df = pd.DataFrame(all_articles)
    
    # Lọc tin 24h qua
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(hours=24)
    
    recent_articles = []
    for _, row in df.iterrows():
        pub_date = row["pub_date"]
        if pub_date is None or pub_date >= twenty_four_hours_ago:
            # Chuẩn hóa tên nguồn từ Google News nếu có
            title = row["title"]
            source = row["source"]
            # Tiêu đề Google News thường có đuôi " - Tên Báo"
            if " - " in title and "Google News" in source:
                parts = title.rsplit(" - ", 1)
                title = parts[0]
                source = parts[1]
                row["title"] = title
                row["source"] = source
            recent_articles.append(row.to_dict())
            
    if not recent_articles:
        print("❌ Không có tin tức mới trong 24h qua.")
        return
        
    # Phân loại và lọc rác vĩ mô
    filtered_articles = []
    for art in recent_articles:
        cat = classify_article(art["title"], art["description"])
        if cat:
            art["category"] = cat
            filtered_articles.append(art)
            
    if not filtered_articles:
        print("❌ Sau khi lọc, không có tin tức tài chính vĩ mô quan trọng nào.")
        return
        
    # Áp dụng thuật toán Gom Cụm (Clustering) tránh tin trùng lặp giữa các báo
    clustered_data = cluster_articles(filtered_articles)
    
    # Xuất báo cáo Markdown rút gọn thông minh
    today_str = datetime.now().strftime("%d/%m/%Y")
    report_lines = []
    report_lines.append(f"# 📰 BẢN TIN SÁNG SỚM THÔNG MINH (AGGREGATED & CLUSTERED) - NGÀY {today_str}")
    report_lines.append(f"*Thời gian cập nhật: {datetime.now().strftime('%H:%M:%S')}*")
    report_lines.append(f"*Đã quét hàng nghìn tờ báo qua Google News & lọc sạch tin trùng lặp bằng thuật toán Clustering.*\n")
    report_lines.append("---")
    
    categories_order = [
        "Lãi suất & Tiền tệ (Rates & Inflation)",
        "Địa chính trị & Chiến tranh (Geopolitics & Macro Impact)",
        "Kinh tế Thế giới (Global Economy)",
        "Vĩ mô Việt Nam & Chính sách (VN Macro & Policies)",
        "Chứng khoán & Doanh nghiệp nổi bật (Market & Corporate)"
    ]
    
    for cat in categories_order:
        # Lọc các cụm thuộc category này
        cat_clusters = [c for c in clustered_data if c["representative"]["category"] == cat]
        if not cat_clusters:
            continue
            
        report_lines.append(f"\n## 📌 {cat}")
        # Chỉ in ra tối đa 8 sự kiện lớn nhất mỗi chủ đề
        for cluster in cat_clusters[:8]:
            rep = cluster["representative"]
            time_str = rep["pub_date"].strftime("%H:%M") if rep["pub_date"] else "N/A"
            report_lines.append(f"* **{rep['title']}** *(lúc {time_str})*")
            # Liệt kê các nguồn báo đưa tin về sự kiện này
            source_links = []
            for src in cluster["sources"][:3]: # Giới hạn tối đa 3 nguồn tiêu biểu nhất
                source_links.append(f"[{src['source']}]({src['link']})")
            report_lines.append(f"  * Nguồn đưa tin: {', '.join(source_links)}")
            
    # Lưu file
    output_dir = "paper_trading/reports"
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, "morning_brief_news.md")
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
        
    print(f"\n✅ Đã xuất báo cáo Morning Brief thông minh thành công tại: {report_path}")
    
    # In kết quả terminal
    print("\n" + "="*50)
    print(f"📊 BẢN TIN VĨ MÔ THÔNG MINH - {today_str}")
    print("="*50)
    for cat in categories_order:
        cat_clusters = [c for c in clustered_data if c["representative"]["category"] == cat]
        if cat_clusters:
            print(f"\n▶ {cat.upper()}:")
            for cluster in cat_clusters[:4]:
                rep = cluster["representative"]
                sources_str = ", ".join([s["source"] for s in cluster["sources"][:3]])
                print(f"  • {rep['title']} ({sources_str})")
                print(f"    Nguồn đại diện: {rep['link']}")
                
if __name__ == "__main__":
    main()
