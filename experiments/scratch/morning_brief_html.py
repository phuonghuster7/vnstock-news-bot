import os
import sys
import winreg
import html
import re
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timezone, timedelta
import dateutil.parser as date_parser
import json

# Thiết lập encoding UTF-8 cho stdout trên Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# API Key cho Gemini
GEMINI_API_KEY = "AIzaSyC78asTmCdjgNeBGB3Oi2ihoXGZ93n7VPE"

# File lưu vết chạy tránh trùng lặp
LAST_RUN_FILE = os.path.join("paper_trading", "reports", ".last_run")
RAW_DATA_FILE = os.path.join("paper_trading", "reports", ".raw_news_data.json")

def check_already_run_today():
    today_str = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(LAST_RUN_FILE):
        try:
            with open(LAST_RUN_FILE, "r") as f:
                last_run = f.read().strip()
                if last_run == today_str:
                    return True
        except Exception:
            pass
    return False

def get_desktop_path():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, 
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        )
        path, _ = winreg.QueryValueEx(key, "Desktop")
        return os.path.expandvars(path)
    except Exception:
        return os.path.join(os.path.expanduser("~"), "Desktop")

# --- DANH SÁCH NGUỒN QUÉT RSS RỘNG LỚN (VIỆT NAM + QUỐC TẾ) ---
from urllib.parse import quote
GOOGLE_NEWS_MACRO_VI = "https://news.google.com/rss/search?q=" + quote("lãi suất OR lạm phát OR chứng khoán OR vĩ mô OR tỷ giá OR doanh nghiệp OR kinh tế") + "&hl=vi&gl=VN&ceid=VN:vi"
GOOGLE_NEWS_GEOPOLITICS_VI = "https://news.google.com/rss/search?q=" + quote("địa chính trị OR chiến tranh OR xung đột OR thuế quan OR lệnh trừng phạt") + "&hl=vi&gl=VN&ceid=VN:vi"

# Yahoo Finance & Google News Quốc Tế (Tiếng Anh) để lấy thông tin toàn cầu sớm nhất
YAHOO_FINANCE_WORLD = "https://finance.yahoo.com/news/rssindex"
GOOGLE_NEWS_MACRO_EN = "https://news.google.com/rss/search?q=" + quote("interest rates OR inflation OR FED OR macroeconomics OR central bank OR geopolitical") + "&hl=en-US&gl=US&ceid=US:en"

RSS_FEEDS = {
    "VnExpress": "https://vnexpress.net/rss/kinh-doanh.rss",
    "CafeF - Thị trường": "https://cafef.vn/thi-truong-chung-khoan.rss",
    "CafeF - Vĩ mô": "https://cafef.vn/thoi-su.rss",
    "VnEconomy - Tài chính": "https://vneconomy.vn/tai-chinh-ngan-hang.rss",
    "VnEconomy - Chứng khoán": "https://vneconomy.vn/chung-khoan.rss",
    "Vietstock - Vĩ mô": "https://vietstock.vn/rss/tai-chinh.rss",
    "Vietstock - Doanh nghiệp": "https://vietstock.vn/rss/doanh-nghiep.rss",
    "Tuổi Trẻ - Kinh tế": "https://tuoitre.vn/rss/kinh-doanh.rss",
    "Thanh Niên - Tài chính": "https://thanhnien.vn/rss/tai-chinh-kinh-doanh.rss",
    "Google News VN - Vĩ mô": GOOGLE_NEWS_MACRO_VI,
    "Google News VN - Địa chính trị": GOOGLE_NEWS_GEOPOLITICS_VI,
    "Google News Quốc tế - Tài chính": GOOGLE_NEWS_MACRO_EN,
    "Yahoo Finance": YAHOO_FINANCE_WORLD
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

def clean_words(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text)
    words = set(text.split())
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
    sorted_articles = sorted(articles, key=lambda x: x["pub_date"] or datetime.min, reverse=True)
    for art in sorted_articles:
        found_cluster = False
        for cluster in clustered:
            sim = calculate_similarity(art["title"], cluster["representative"]["title"])
            if sim > 0.35:
                cluster["sources"].append({
                    "source": art["source"],
                    "title": art["title"],
                    "link": art["link"]
                })
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

# --- VNSTOCK MARKET DATA & EVENTS ---
def get_vn100_watchlist_details():
    try:
        from vnstock import Listing, Market
        l = Listing()
        vn100_series = l.symbols_by_group('VN100')
        if vn100_series.empty:
            return [], [], []
        
        vn100_symbols = vn100_series.tolist()
        mkt = Market()
        vn100_data = []
        
        print("🤖 Đang tải bảng giá VN100 (tối đa 15 mã lớn)...")
        sample_symbols = vn100_symbols[:15]
        
        for sym in sample_symbols:
            try:
                price_df = mkt.equity(sym).quote()
                if not price_df.empty:
                    row = price_df.iloc[0]
                    fb = row.get('foreign_buy_volume', 0)
                    fs = row.get('foreign_sell_volume', 0)
                    
                    raw_pct = row.get('percent_change', 0)
                    if -1.0 < raw_pct < 1.0 and raw_pct != 0:
                        change_pct = raw_pct * 100
                    else:
                        change_pct = raw_pct
                        
                    vn100_data.append({
                        'symbol': sym,
                        'close': row.get('close_price', 0),
                        'change_pct': change_pct,
                        'volume': row.get('volume_accumulated', 0),
                        'foreign_net_vol': fb - fs
                    })
            except Exception:
                pass
        
        if vn100_data:
            df_res = pd.DataFrame(vn100_data)
            top_up = df_res[df_res['change_pct'] > 0].sort_values(by='change_pct', ascending=False).head(5).to_dict(orient="records")
            top_down = df_res[df_res['change_pct'] < 0].sort_values(by='change_pct', ascending=True).head(5).to_dict(orient="records")
            return vn100_data, top_up, top_down
    except Exception as e:
        print(f"Lỗi khi lấy dữ liệu VN100: {e}")
    return [], [], []

def get_corporate_events():
    events_list = []
    try:
        from vnstock import Listing, Company
        l = Listing()
        vn100_series = l.symbols_by_group('VN100')
        if vn100_series.empty:
            return []
        
        # Chỉ quét top 15 mã lớn để tối ưu thời gian chạy
        sample_symbols = vn100_series.head(15).tolist()
        current_year = datetime.now().year
        
        for sym in sample_symbols:
            try:
                comp = Company(symbol=sym, source='vci')
                df_ev = comp.events()
                if df_ev is not None and not df_ev.empty:
                    div_ev = df_ev[df_ev['event_name_vi'].str.contains('cổ tức|phát hành|thưởng|quyền', case=False, na=False)]
                    for _, row in div_ev.iterrows():
                        exright_date = row.get('exright_date')
                        if exright_date and not pd.isna(exright_date):
                            try:
                                dt = date_parser.parse(str(exright_date))
                                if dt.year != current_year:
                                    continue
                            except Exception:
                                continue
                                
                        events_list.append({
                            'symbol': sym,
                            'title': row.get('event_title_vi') or row.get('event_name_vi'),
                            'exright_date': str(exright_date) if exright_date else '',
                            'ratio': row.get('exercise_ratio') or 'N/A',
                            'value': float(row.get('value_per_share', 0)) if not pd.isna(row.get('value_per_share')) else 0
                        })
            except Exception:
                pass
    except Exception as e:
        print(f"Lỗi khi quét sự kiện doanh nghiệp: {e}")
    return events_list[:12]

def main():
    if check_already_run_today():
        print("Bot đã chạy hôm nay rồi. Tự động thoát để tránh trùng lặp.")
        sys.exit(0)
        
    print("🤖 Bắt đầu cào dữ liệu từ hàng loạt nguồn Việt Nam, Yahoo Finance, Google News...")
    all_articles = []
    for source, url in RSS_FEEDS.items():
        all_articles.extend(parse_rss(source, url))
        
    if not all_articles:
        print("Không có tin tức nào được tìm thấy.")
        return
        
    df = pd.DataFrame(all_articles)
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(hours=24)
    
    recent_articles = []
    for _, row in df.iterrows():
        pub_date = row["pub_date"]
        if pub_date is not None and pub_date >= twenty_four_hours_ago:
            title = row["title"]
            source = row["source"]
            if " - " in title and "Google News" in source:
                parts = title.rsplit(" - ", 1)
                title = parts[0]
                source = parts[1]
                row["title"] = title
                row["source"] = source
            
            row_dict = row.to_dict()
            row_dict["pub_date"] = row_dict["pub_date"].isoformat() if row_dict["pub_date"] else None
            recent_articles.append(row_dict)
            
    clustered_data = cluster_articles(pd.DataFrame(recent_articles).assign(pub_date=lambda d: pd.to_datetime(d['pub_date'])).to_dict(orient="records"))
    
    print("🤖 Lấy dữ liệu VN100...")
    vn100_data, movers_up, movers_down = get_vn100_watchlist_details()
    
    print("🤖 Quét sự kiện cổ tức/phát hành...")
    corporate_events = get_corporate_events()
    
    os.makedirs(os.path.dirname(RAW_DATA_FILE), exist_ok=True)
    
    for c in clustered_data:
        if c["representative"]["pub_date"] and hasattr(c["representative"]["pub_date"], "isoformat"):
            c["representative"]["pub_date"] = c["representative"]["pub_date"].isoformat()
            
    raw_payload = {
        "clustered_data": clustered_data,
        "movers_up": movers_up,
        "movers_down": movers_down,
        "corporate_events": corporate_events
    }
    
    with open(RAW_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(raw_payload, f, ensure_ascii=False, indent=2)
        
    print(f"✅ Đã ghi nhận dữ liệu thô tích hợp nguồn quốc tế thành công.")

if __name__ == "__main__":
    main()
