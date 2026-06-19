import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timezone
import dateutil.parser as date_parser
import html
import re

# Danh sách các RSS feeds tin tức tài chính, kinh doanh, chứng khoán
RSS_FEEDS = {
    "VnExpress - Kinh doanh": "https://vnexpress.net/rss/kinh-doanh.rss",
    "CafeF - Thị trường chứng khoán": "https://cafef.vn/thi-truong-chung-khoan.rss",
    "CafeF - Thời sự": "https://cafef.vn/thoi-su.rss",
    "VnEconomy - Chứng khoán": "https://vneconomy.vn/chung-khoan.rss",
    "VnEconomy - Tài chính - Ngân hàng": "https://vneconomy.vn/tai-chinh-ngan-hang.rss",
    "Vietstock - Tài chính": "https://vietstock.vn/rss/tai-chinh.rss",
    "Vietstock - Doanh nghiệp": "https://vietstock.vn/rss/doanh-nghiep.rss"
}

def fix_encoding(text):
    if not text:
        return ""
    try:
        # Giải mã các ký tự unicode dạng #123; hoặc #123 (thiếu &) của VnEconomy
        # Khớp cả dấu chấm phẩy tuỳ chọn ở sau
        return re.sub(r'#([0-9]+);?', lambda m: chr(int(m.group(1))), text)
    except Exception:
        return text

def parse_rss_feed(source_name, url):
    articles = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch {source_name}: HTTP {response.status_code}")
            return articles
            
        root = ET.fromstring(response.content)
        for item in root.findall(".//item"):
            title_raw = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            pub_date_raw = item.find("pubDate").text if item.find("pubDate") is not None else ""
            description_raw = item.find("description").text if item.find("description") is not None else ""
            
            # Giải mã HTML Entities trước, sau đó fix lỗi định dạng unicode thiếu & của VnEconomy
            title = fix_encoding(html.unescape(title_raw))
            description_decoded = fix_encoding(html.unescape(description_raw))
            
            # Clean các tag HTML trong mô tả
            desc_soup = BeautifulSoup(description_decoded, "html.parser")
            description = desc_soup.get_text().strip()
            
            # Parse ngày
            pub_date = None
            if pub_date_raw:
                try:
                    pub_date = date_parser.parse(pub_date_raw)
                except Exception:
                    pass
            
            articles.append({
                "source": source_name,
                "title": title.strip(),
                "link": link.strip(),
                "pub_date": pub_date,
                "description": description
            })
    except Exception as e:
        print(f"Error parsing {source_name}: {e}")
    return articles

def main():
    all_articles = []
    for source, url in RSS_FEEDS.items():
        print(f"Fetching from {source}...")
        all_articles.extend(parse_rss_feed(source, url))
        
    df = pd.DataFrame(all_articles)
    if df.empty:
        print("Không tìm thấy tin tức nào.")
        return
        
    today_str = "2026-06-16"
    now = datetime.now(timezone.utc)
    
    today_articles = []
    for _, row in df.iterrows():
        pub_date = row["pub_date"]
        if pub_date is None:
            today_articles.append(row)
            continue
            
        time_diff = now - pub_date
        is_today = pub_date.strftime("%Y-%m-%d") == today_str
        
        if is_today or time_diff.total_seconds() < 86400:
            today_articles.append(row)
            
    df_today = pd.DataFrame(today_articles)
    if df_today.empty:
        print("Không có tin tức nào xuất bản hôm nay.")
        return
        
    df_today = df_today.drop_duplicates(subset=["title"])
    df_today = df_today.sort_values(by="pub_date", ascending=False)
    
    print(f"\n# TỔNG HỢP TIN TỨC THỊ TRƯỜNG NGÀY {today_str}\n")
    for idx, row in df_today.iterrows():
        time_str = row["pub_date"].strftime("%H:%M") if row["pub_date"] else "N/A"
        print(f"### [{row['source']}] {row['title']} ({time_str})")
        print(f"- **Mô tả**: {row['description']}")
        print(f"- **Chi tiết**: {row['link']}")
        print()

if __name__ == "__main__":
    main()
