import os
import sys
import html
import re
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timezone, timedelta
import dateutil.parser as date_parser
from urllib.parse import quote
import json
from vnstock import Quote
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Thiết lập encoding UTF-8 cho stdout trên Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

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

# RSS Feeds
GOOGLE_NEWS_MACRO_URL = "https://news.google.com/rss/search?q=" + quote("lãi suất OR lạm phát OR chứng khoán OR vĩ mô OR tỷ giá OR doanh nghiệp") + "&hl=vi&gl=VN&ceid=VN:vi"
GOOGLE_NEWS_GEOPOLITICS_URL = "https://news.google.com/rss/search?q=" + quote("địa chính trị OR chiến tranh OR xung đột OR thuế quan OR chính trị OR bầu cử OR ngoại giao") + "&hl=vi&gl=VN&ceid=VN:vi"

RSS_FEEDS = {
    "Google News - Tài chính vĩ mô": GOOGLE_NEWS_MACRO_URL,
    "Google News - Địa chính trị": GOOGLE_NEWS_GEOPOLITICS_URL,
    "CafeF - Thị trường": "https://cafef.vn/thi-truong-chung-khoan.rss",
    "CafeF - Vĩ mô": "https://cafef.vn/thoi-su.rss",
    "CafeF - Doanh nghiệp": "https://cafef.vn/doanh-nghiep.rss",
    "VnEconomy - Tài chính": "https://vneconomy.vn/tai-chinh-ngan-hang.rss",
    "VnEconomy - Kinh tế số": "https://vneconomy.vn/cong-nghe.rss",
    "Vietstock - Vĩ mô": "https://vietstock.vn/rss/tai-chinh.rss",
    "Vietstock - Doanh nghiệp": "https://vietstock.vn/rss/doanh-nghiep.rss"
}

THEMATIC_KEYWORDS = {
    "Lãi suất & Tiền tệ": [
        "lãi suất", "lạm phát", "tỷ giá", "usd", "vnd", "tiền tệ", "fed", "nhnn", 
        "ngân hàng trung ương", "hạ lãi suất", "tăng lãi suất", "hút tiền", "vàng", "sjc", "gold"
    ],
    "Địa chính trị & Vĩ mô Toàn cầu": [
        "chiến tranh", "xung đột", "địa chính trị", "tấn công", "quân sự", "tên lửa", 
        "giao tranh", "leo thang", "nổ súng", "biên giới", "trừng phạt", "mỹ - trung",
        "israel", "iran", "nga", "ukraine", "gaza", "houthi", "hormuz", "thỏa thuận hòa bình",
        "bầu cử", "tổng thống", "ngoại giao", "nguyên thủ"
    ],
    "Kinh tế Thế giới": [
        "kinh tế thế giới", "kinh tế toàn cầu", "gdp mỹ", "lạm phát mỹ", "wall street",
        "chứng khoán mỹ", "indonesia", "trung quốc", "nhật bản", "châu âu", "rupiah", "yen",
        "thuế quan", "thương mại", "xuất khẩu"
    ],
    "Vĩ mô Việt Nam & Chính sách": [
        "vĩ mô", "gdp", "cpi", "đầu tư công", "fdi", "thuế", "chính sách", "nghị quyết",
        "thông tư", "bộ tài chính", "chính phủ", "thủ tướng", "thanh tra", "quy hoạch"
    ],
    "Chứng khoán & Doanh nghiệp nổi bật": [
        "chứng khoán", "cổ phiếu", "vn-index", "tự doanh", "khối ngoại", "bán ròng",
        "mua ròng", "khớp lệnh", "thanh khoản", "cổ tức", "lợi nhuận", "doanh thu",
        "chủ tịch", "khởi tố", "bắt giam", "tạm giam", "thâu tóm", "sáp nhập"
    ]
}

COMPANY_NAME_MAPPING = {
    "hòa phát": "HPG", "vietcombank": "VCB", "vingroup": "VIC", "vinhomes": "VHM",
    "novaland": "NVL", "đất xanh": "DXG", "masan": "MSN", "fpt": "FPT",
    "vietinbank": "CTG", "bidv": "BID", "sacombank": "STB", "vinamilk": "VNM",
    "vietjet": "VJC", "thế giới di động": "MWG", "vpbank": "VPB", "techcombank": "TCB",
    "mbbank": "MBB", "hdbank": "HDB", "vndirect": "VND",
    "khang điền": "KDH", "phát đạt": "PDR", "nam long": "NLG", 
    "hoàng anh gia lai": "HAG", "bảo việt": "BVH", "vietjet air": "VJC", 
    "sabeco": "SAB", "habeco": "BHN", "chứng khoán hsc": "HCM", 
    "tập đoàn ceo": "CEO", "ceo group": "CEO"
}

POSITIVE_WORDS = [
    "lãi", "lợi nhuận", "tăng", "kỳ vọng", "khởi sắc", "chấp thuận", "phục hồi", 
    "trúng thầu", "cổ tức", "vượt", "đỉnh", "tăng trưởng", "bứt phá"
]

NEGATIVE_WORDS = [
    "lỗ", "giảm", "bị phạt", "hủy niêm yết", "bắt giam", "khởi tố", "phá sản", 
    "thanh tra", "vi phạm", "cảnh báo", "lao dốc", "thủng", "thua lỗ", "sụt giảm", "rơi"
]

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

def find_tickers_in_text(text, target_tickers):
    # Tìm các từ viết hoa dài 3 ký tự khớp với danh sách mã
    found = re.findall(r'\b([A-Z]{3})\b', text)
    matched = [sym for sym in found if sym in target_tickers]
    
    # Tìm theo tên công ty phổ biến
    text_lower = text.lower()
    for name, ticker in COMPANY_NAME_MAPPING.items():
        if name in text_lower:
            matched.append(ticker)
            
    return list(set(matched))

def to_symbol_list(obj):
    if obj is None:
        return []
    import pandas as pd
    if isinstance(obj, pd.DataFrame):
        if 'symbol' in obj.columns:
            return obj['symbol'].tolist()
        return []
    elif isinstance(obj, pd.Series):
        return obj.tolist()
    elif isinstance(obj, (list, set)):
        return list(obj)
    try:
        return list(obj)
    except Exception:
        return []

def get_target_tickers():
    cache_file = "vn100_hnx_tickers.json"
    tickers = set()
    exclusions = {'USD', 'VND', 'EUR', 'SJC', 'HKD', 'SGD', 'JPY', 'HCM', 'CEO', 'FDI', 'GDP', 'CPI', 'FED', 'UBND', 'HNX', 'VNX', 'BCA', 'BCT', 'VNI'}
    
    # 1. Thử tải qua API vnstock (VCI source)
    try:
        from vnstock import Listing
        listing = Listing(source="vci")
        vn100 = listing.symbols_by_group(group_name="VN100", to_df=False)
        hnx = listing.symbols_by_exchange(exchange="HNX", to_df=False)
        
        vn100_list = to_symbol_list(vn100)
        hnx_list = to_symbol_list(hnx)
        
        if vn100_list or hnx_list:
            combined = set(vn100_list + hnx_list)
            # Lọc chỉ giữ mã cổ phiếu hợp lệ (3 chữ cái hoa)
            tickers = ({t for t in combined if len(t) == 3 and t.isalpha()}) - exclusions
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(list(tickers), f)
            print(f"-> Đã tải {len(tickers)} mã VN100 & HNX từ API.")
            return tickers
    except Exception as e:
        print(f"⚠️ Không tải được mã từ API vnstock: {e}. Thử dùng cache...")

    # 2. Thử đọc từ cache
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached_list = json.load(f)
                if cached_list:
                    tickers = set(cached_list) - exclusions
                    print(f"-> Đã tải {len(tickers)} mã VN100 & HNX từ cache.")
                    return tickers
        except Exception:
            pass

    # 3. Danh sách cứng fallback (HOSE VN100 & HNX30)
    fallback = {
        # VN30
        'ACB', 'BCM', 'BID', 'CTG', 'DGC', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 
        'LPB', 'MBB', 'MSN', 'MWG', 'PLX', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 
        'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE',
        # HNX30
        'BVS', 'CAP', 'CEO', 'DHT', 'DP3', 'DTD', 'DVM', 'DXP', 'HGM', 'HUT', 
        'IDC', 'IDV', 'L14', 'L18', 'LAS', 'LHC', 'MBS', 'NTP', 'PLC', 'PSD', 
        'PVB', 'PVC', 'PVI', 'PVS', 'SHS', 'SLS', 'TMB', 'TNG', 'VC3', 'VCS',
        # VN100 khác & HNX lớn
        'VCI', 'HCM', 'DXG', 'NLG', 'KBC', 'DIG', 'PDR', 'GEX', 'REE',
        'EIB', 'VGC', 'HDG', 'DPM', 'DCM', 'SBT', 'PNJ', 'FRT', 'DGW', 'MSB',
        'OCB', 'TCH', 'GEG', 'PC1', 'NT2', 'POW', 'ANV', 'VHC', 'IDI', 'FMC',
        'PAN', 'HSG', 'NKG', 'SMC', 'VOS', 'HAH', 'GMD', 'PVT', 'HHV', 'VCG',
        'LCG', 'FCN', 'KSB', 'HT1', 'BCC', 'C4G', 'CTD', 'HBC'
    }
    tickers = fallback - exclusions
    print(f"-> Sử dụng {len(tickers)} mã fallback sàn HOSE/HNX.")
    return tickers

def analyze_sentiment(text):
    text_lower = text.lower()
    pos_score = sum(1 for word in POSITIVE_WORDS if word in text_lower)
    neg_score = sum(1 for word in NEGATIVE_WORDS if word in text_lower)
    
    score = pos_score - neg_score
    if score > 0:
        return "Tích cực"
    elif score < 0:
        return "Tiêu cực"
    return "Trung lập"

def classify_article(title, description, target_tickers):
    combined_text = title + " " + (description or "")
    matched_tickers = find_tickers_in_text(combined_text, target_tickers)
    sentiment = analyze_sentiment(combined_text)
    
    # Nếu bài viết chứa mã VN100/HNX hoặc map được tên công ty, gom vào danh mục Doanh nghiệp & Cổ phiếu
    if matched_tickers:
        return "Tin Doanh nghiệp & Cổ phiếu", matched_tickers, sentiment
        
    combined_lower = combined_text.lower()
    for category, keywords in THEMATIC_KEYWORDS.items():
        for kw in keywords:
            if kw in combined_lower:
                return category, [], sentiment
    return "Thời sự & Tin tức khác", [], sentiment

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
    
    # Fallback timezone-aware comparison để tránh lỗi mix naive/aware
    _tz_min = datetime.min.replace(tzinfo=timezone.utc)
    def _pub_key(x):
        d = x["pub_date"]
        if d is None:
            return _tz_min
        if d.tzinfo is None:
            return d.replace(tzinfo=timezone.utc)
        return d

    sorted_articles = sorted(articles, key=_pub_key, reverse=True)
    
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
                # Gộp danh sách tickers
                cluster["tickers"] = list(set(cluster.get("tickers", []) + art.get("tickers", [])))
                
                # Update sentiment (lấy theo sentiment của bài mới nhất)
                cluster["sentiment"] = art.get("sentiment", cluster.get("sentiment", "Trung lập"))
                
                # Cập nhật ngày đăng mới nhất
                art_pub = art["pub_date"]
                rep_pub = cluster["representative"]["pub_date"]
                if art_pub:
                    if not rep_pub or art_pub.replace(tzinfo=timezone.utc) > rep_pub.replace(tzinfo=timezone.utc):
                        cluster["representative"]["pub_date"] = art_pub
                found_cluster = True
                break
        if not found_cluster:
            clustered.append({
                "representative": art,
                "tickers": art.get("tickers", []),
                "sentiment": art.get("sentiment", "Trung lập"),
                "sources": [{
                    "source": art["source"],
                    "title": art["title"],
                    "link": art["link"]
                }]
            })
    return clustered

CATEGORY_META = {
    "Tin Doanh nghiệp & Cổ phiếu": {
        "icon": "fa-building-columns",
        "color": "#06b6d4",
        "glow": "rgba(6,182,212,0.12)",
        "border": "rgba(6,182,212,0.35)",
        "badge_bg": "rgba(6,182,212,0.15)",
        "badge_text": "#22d3ee",
    },
    "Lãi suất & Tiền tệ": {
        "icon": "fa-coins",
        "color": "#f59e0b",
        "glow": "rgba(245,158,11,0.15)",
        "border": "rgba(245,158,11,0.35)",
        "badge_bg": "rgba(245,158,11,0.15)",
        "badge_text": "#fbbf24",
    },
    "Địa chính trị & Vĩ mô Toàn cầu": {
        "icon": "fa-globe",
        "color": "#ef4444",
        "glow": "rgba(239,68,68,0.15)",
        "border": "rgba(239,68,68,0.35)",
        "badge_bg": "rgba(239,68,68,0.15)",
        "badge_text": "#f87171",
    },
    "Kinh tế Thế giới": {
        "icon": "fa-earth-americas",
        "color": "#8b5cf6",
        "glow": "rgba(139,92,246,0.15)",
        "border": "rgba(139,92,246,0.35)",
        "badge_bg": "rgba(139,92,246,0.15)",
        "badge_text": "#a78bfa",
    },
    "Vĩ mô Việt Nam & Chính sách": {
        "icon": "fa-landmark",
        "color": "#10b981",
        "glow": "rgba(16,185,129,0.15)",
        "border": "rgba(16,185,129,0.35)",
        "badge_bg": "rgba(16,185,129,0.15)",
        "badge_text": "#34d399",
    },
    "Chứng khoán & Doanh nghiệp nổi bật": {
        "icon": "fa-chart-line",
        "color": "#3b82f6",
        "glow": "rgba(59,130,246,0.15)",
        "border": "rgba(59,130,246,0.35)",
        "badge_bg": "rgba(59,130,246,0.15)",
        "badge_text": "#60a5fa",
    },
    "Thời sự & Tin tức khác": {
        "icon": "fa-newspaper",
        "color": "#64748b",
        "glow": "rgba(100,116,139,0.10)",
        "border": "rgba(100,116,139,0.30)",
        "badge_bg": "rgba(100,116,139,0.15)",
        "badge_text": "#94a3b8",
    },
}

def fetch_stock_prices(tickers):
    """Lấy dữ liệu giá của danh sách mã chứng khoán trong 7 ngày qua để tính % thay đổi"""
    prices = {}
    if not tickers:
        return prices
    today = datetime.now()
    start_date = (today - timedelta(days=10)).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    
    print(f"Đang lấy dữ liệu giá cho {len(tickers)} mã: {', '.join(tickers)}")
    for ticker in tickers:
        try:
            df = Quote("kbs", ticker).history(start=start_date, end=end_date)
            if df is not None and not df.empty and len(df) >= 2:
                current_price = df.iloc[-1]['close']
                prev_price = df.iloc[-2]['close']
                pct_change = ((current_price - prev_price) / prev_price) * 100
                prices[ticker] = {
                    "price": current_price,
                    "change": pct_change
                }
            # Ngủ 1.2s để tránh Rate Limit (60 req/min) của vnstock bản Community
            time.sleep(1.2)
        except Exception as e:
            time.sleep(1.2) # Bỏ qua nếu lỗi (mã không tồn tại, v.v.)
    return prices

def call_llm_fallback(prompt):
    # Try Gemini
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            if response.text:
                return response.text.strip().replace("\n", " ")
        except Exception as e:
            print(f"  [Gemini Lỗi] {e} -> Chuyển sang DeepSeek")
            
    # Try DeepSeek
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    if deepseek_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Bạn là trợ lý tài chính ngắn gọn. Viết đúng 1 câu duy nhất, không in đậm, không format."},
                    {"role": "user", "content": prompt}
                ]
            )
            if response.choices:
                return response.choices[0].message.content.strip().replace("\n", " ")
        except Exception as e:
            print(f"  [DeepSeek Lỗi] {e} -> Chuyển sang OpenAI")
            
    # Try OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "Bạn là trợ lý tài chính ngắn gọn. Viết đúng 1 câu duy nhất, không in đậm, không format."},
                    {"role": "user", "content": prompt}
                ]
            )
            if response.choices:
                return response.choices[0].message.content.strip().replace("\n", " ")
        except Exception as e:
            print(f"  [OpenAI Lỗi] {e}")

    return ""

def load_watchlist():
    """Sử dụng toàn bộ mã trong rổ VN100 làm Watchlist"""
    watchlist = []
    print("Đang lấy danh mục VN100 làm Watchlist...")
    try:
        from vnstock import Listing
        listing = Listing(source="kbs")
        vn100_df = listing.indices(index="VN100")
        if vn100_df is not None and not vn100_df.empty:
            if 'ticker' in vn100_df.columns:
                watchlist = vn100_df['ticker'].tolist()
    except Exception as e:
        print("Lỗi lấy danh mục VN100:", e)
    return watchlist

def send_telegram_alerts(clustered_data, stock_prices, ai_summaries, watchlist):
    """Gửi cảnh báo Telegram cho các cụm tin nóng hoặc thuộc danh mục quan tâm"""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
        
    print("📲 Đang gửi tin nóng qua Telegram...")
    
    messages_to_send = []
    
    for idx, cluster in enumerate(clustered_data):
        rep = cluster["representative"]
        tickers = cluster.get("tickers", [])
        
        # Kiểm tra xem tin có thuộc watchlist không
        in_watchlist = any(t in watchlist for t in tickers)
        
        # Chỉ gửi tin thuộc watchlist HOẶC là tin rất nóng (nhiều báo đăng)
        if in_watchlist or len(cluster["sources"]) >= 3:
            title = rep["title"]
            ai_sum = ai_summaries.get(idx, "")
            
            # Format Price Tags
            price_text = ""
            for t in tickers:
                if t in stock_prices:
                    p = stock_prices[t]
                    icon = "🟢" if p["change"] > 0 else "🔴" if p["change"] < 0 else "🟡"
                    price_text += f"\n{icon} {t}: {p['price']:,.1f} ({p['change']:.1f}%)"
            
            # Xây dựng nội dung tin nhắn
            msg = ""
            if in_watchlist:
                msg += "⭐ <b>TIN DANH MỤC CỦA BẠN</b>\n"
            else:
                msg += "🔥 <b>TIN NÓNG THỊ TRƯỜNG</b>\n"
                
            msg += f"<b>{html.escape(title)}</b>\n"
            if ai_sum:
                msg += f"\n🪄 <i>{html.escape(ai_sum)}</i>\n"
                
            if price_text:
                msg += f"\n📈 <b>Biến động giá:</b>{price_text}\n"
                
            msg += f"\n🔗 <a href='{cluster['sources'][0]['link']}'>Đọc chi tiết</a>"
            messages_to_send.append(msg)
            
    # Gửi lần lượt qua Telegram API
    for msg in messages_to_send[:10]: # Tối đa 10 tin để tránh spam
        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            requests.post(url, json=payload, timeout=5)
        except Exception as e:
            print("Lỗi gửi Telegram:", e)

def summarize_clusters_with_ai(clustered_data):
    """Sử dụng cơ chế Fallback (Gemini -> DeepSeek -> OpenAI) để tóm tắt các cụm tin"""
    summaries = {}
    
    if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        print("⚠️ Không tìm thấy API Key nào, bỏ qua bước AI tóm tắt.")
        return summaries

    print("🤖 Đang nhờ AI tóm tắt các cụm tin chính...")
    for idx, cluster in enumerate(clustered_data):
        if len(cluster["sources"]) >= 2 or cluster["representative"].get("category") == "Tin Doanh nghiệp & Cổ phiếu":
            titles = [s["title"] for s in cluster["sources"]]
            titles_text = "\n- ".join(titles[:5]) # Lấy tối đa 5 bài
            prompt = f"Dựa vào các tiêu đề bài báo sau đây về cùng một sự kiện, hãy viết ĐÚNG 1 CÂU tóm tắt ngắn gọn nhất bản chất sự kiện và đánh giá tác động (nếu có). Không in đậm, không format, không xuống dòng.\n\nTiêu đề:\n- {titles_text}"
            
            result = call_llm_fallback(prompt)
            if result:
                summaries[idx] = result
                
    return summaries

def build_html_report(clustered_data, output_path, stock_prices=None, ai_summaries=None, watchlist=None):
    if stock_prices is None:
        stock_prices = {}
    if ai_summaries is None:
        ai_summaries = {}
    if watchlist is None:
        watchlist = []

    today_str = datetime.now().strftime("%d/%m/%Y")
    now_str = datetime.now().strftime("%H:%M:%S")
    weekday_names = ["Thứ Hai","Thứ Ba","Thứ Tư","Thứ Năm","Thứ Sáu","Thứ Bảy","Chủ Nhật"]
    weekday_str = weekday_names[datetime.now().weekday()]

    # Phân loại thêm "⭐ Danh mục Của Tôi"
    for cluster in clustered_data:
        tickers = cluster.get("tickers", [])
        if any(t in watchlist for t in tickers):
            cluster["representative"]["category"] = "⭐ Danh mục Của Tôi"

    categories_order = ["⭐ Danh mục Của Tôi", "Tin Doanh nghiệp & Cổ phiếu"] + list(THEMATIC_KEYWORDS.keys()) + ["Thời sự & Tin tức khác"]
    
    # Định nghĩa màu sắc cho Danh mục của Tôi
    CATEGORY_META["⭐ Danh mục Của Tôi"] = {
        "icon": "fa-star",
        "color": "#f59e0b",
        "glow": "rgba(245,158,11,0.15)",
        "border": "rgba(245,158,11,0.35)",
        "badge_bg": "rgba(245,158,11,0.15)",
        "badge_text": "#fbbf24",
    }

    # Chỉ giữ category có tin
    active_cats = [c for c in categories_order if any(
        cl["representative"].get("category") == c for cl in clustered_data
    )]

    # Tính tổng thống kê
    total_clusters = len(clustered_data)
    total_articles = sum(len(c["sources"]) for c in clustered_data)
    cat_counts = {}
    for cat in categories_order:
        cat_counts[cat] = len([c for c in clustered_data if c["representative"].get("category") == cat])

    # ── Build sidebar nav items ──
    sidebar_items_html = ""
    for idx, cat in enumerate(active_cats):
        meta = CATEGORY_META.get(cat, CATEGORY_META["Thời sự & Tin tức khác"])
        count = cat_counts.get(cat, 0)
        active_class = " active" if idx == 0 else ""
        cat_id = f"cat_{idx}"
        sidebar_items_html += f"""
        <div class="nav-item{active_class}" data-target="{cat_id}"
             style="--cat-color:{meta['color']};--cat-glow:{meta['glow']};--cat-border:{meta['border']};">
            <div class="nav-num">{idx+1}</div>
            <div class="nav-icon-wrap" style="background:{meta['badge_bg']};">
                <i class="fa-solid {meta['icon']}" style="color:{meta['color']};"></i>
            </div>
            <div class="nav-text">
                <div class="nav-name">{cat}</div>
                <div class="nav-count">{count} tin</div>
            </div>
            <div class="nav-arrow"><i class="fa-solid fa-chevron-right"></i></div>
        </div>"""

    # ── Build content panels ──
    panels_html = ""
    for idx, cat in enumerate(active_cats):
        # Fallback timezone-aware để sort đúng real-time
        _tz_min = datetime.min.replace(tzinfo=timezone.utc)
        def _pub_key(c):
            d = c["representative"]["pub_date"]
            if d is None:
                return _tz_min
            if d.tzinfo is None:
                return d.replace(tzinfo=timezone.utc)
            return d

        cat_clusters = sorted(
            [c for c in clustered_data if c["representative"].get("category") == cat],
            key=_pub_key,
            reverse=True
        )

        meta = CATEGORY_META.get(cat, CATEGORY_META["Thời sự & Tin tức khác"])
        color = meta["color"]
        glow = meta["glow"]
        border = meta["border"]
        badge_bg = meta["badge_bg"]
        badge_text = meta["badge_text"]
        icon = meta["icon"]
        cat_id = f"cat_{idx}"
        active_class = " active" if idx == 0 else ""

        # build news cards
        cards_html = ""
        for cluster in cat_clusters[:15]:
            rep = cluster["representative"]
            time_str = rep["pub_date"].strftime("%H:%M %d/%m") if rep["pub_date"] else "--:--"
            title_safe = rep["title"].replace("'", "&#39;").replace("<", "&lt;").replace(">", "&gt;")
            desc_safe = (rep["description"] or "").replace("'", "&#39;").replace("<", "&lt;").replace(">", "&gt;")
            main_link = cluster["sources"][0]["link"] if cluster["sources"] else "#"

            chips_html = ""
            for src in cluster["sources"][:4]:
                src_name = src["source"].split(" - ")[-1] if " - " in src["source"] else src["source"]
                chips_html += f'<a href="{src["link"]}" target="_blank" class="src-chip">{src_name}</a>'
            if len(cluster["sources"]) > 4:
                chips_html += f'<span class="multi-badge">+{len(cluster["sources"])-4}</span>'

            # Dựng HTML cho mã cổ phiếu liên quan và thẻ giá
            tickers_html = ""
            for t in cluster.get("tickers", []):
                price_html = ""
                if stock_prices and t in stock_prices:
                    p_data = stock_prices[t]
                    p_val = p_data["price"]
                    c_val = p_data["change"]
                    if c_val > 0:
                        price_html = f'<span class="price-tag pos">{p_val:,.1f} (+{c_val:.1f}%)</span>'
                    elif c_val < 0:
                        price_html = f'<span class="price-tag neg">{p_val:,.1f} ({c_val:.1f}%)</span>'
                    else:
                        price_html = f'<span class="price-tag neu">{p_val:,.1f} (0.0%)</span>'
                
                tickers_html += f'<span class="ticker-badge">{t} {price_html}</span>'

            # Dựng HTML cho Sentiment badge
            sentiment = cluster.get("sentiment", "Trung lập")
            sentiment_html = ""
            if cat == "Tin Doanh nghiệp & Cổ phiếu":
                if sentiment == "Tích cực":
                    sentiment_html = '<span class="sentiment-badge pos">🟢 Tích cực</span>'
                elif sentiment == "Tiêu cực":
                    sentiment_html = '<span class="sentiment-badge neg">🔴 Tiêu cực</span>'
                else:
                    sentiment_html = '<span class="sentiment-badge neu">⚪ Trung lập</span>'

            # Dựng HTML cho AI Summary (nếu có)
            # index của cluster trong clustered_data (cần map đúng, ở đây ta sẽ dùng logic tìm lại index gốc hoặc gán id)
            # Thay vì truyền id, ta sẽ so sánh reference
            cluster_idx = clustered_data.index(cluster)
            ai_summary_text = ai_summaries.get(cluster_idx, "")
            
            ai_html = ""
            if ai_summary_text:
                ai_html = f'<div class="ai-summary"><i class="fa-solid fa-wand-magic-sparkles"></i> <strong>AI Tóm tắt:</strong> {html.escape(ai_summary_text)}</div>'

            cards_html += f"""
            <div class="news-card">
                <div class="news-content-inline">
                    {tickers_html} {sentiment_html}
                    <a href="{main_link}" target="_blank" class="news-headline-link">{title_safe}</a>
                    {ai_html}
                    <span class="news-meta">
                        <i class="fa-regular fa-clock"></i>
                        <span class="meta-time">{time_str}</span>
                        <span class="meta-sep">·</span>
                        {chips_html}
                    </span>
                </div>
            </div>"""

        panels_html += f"""
        <div class="content-panel{active_class}" id="{cat_id}">
            <div class="panel-header" style="border-left:4px solid {color};background:{glow};">
                <div class="panel-header-left">
                    <div class="panel-icon" style="background:{badge_bg};">
                        <i class="fa-solid {icon}" style="color:{color};font-size:1.1rem;"></i>
                    </div>
                    <div>
                        <div class="panel-title" style="color:{color};">{cat}</div>
                        <div class="panel-subtitle">{len(cat_clusters)} cụm tin · {sum(len(c['sources']) for c in cat_clusters)} bài gốc</div>
                    </div>
                </div>
                <span class="panel-badge" style="background:{badge_bg};color:{badge_text};border:1px solid {border};">
                    <i class="fa-solid fa-layer-group"></i> {len(cat_clusters)} tin
                </span>
            </div>
            <div class="cards-grid">
                {cards_html}
            </div>
        </div>"""

    # ── Full HTML ──
    html_content = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bảng Tin Tài Chính - {today_str}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
    <style>
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        :root {{
            --bg:        #f0f2f7;
            --surface:   #ffffff;
            --surface2:  #f7f8fc;
            --border:    #dde3ee;
            --text:      #1e2535;
            --muted:     #6b7a99;
            --muted2:    #9aa3b8;
            --sb-bg:     #1c2140;
            --sb-border: #2a3160;
            --sb-text:   #c8d0ec;
            --sb-muted:  #6b78a8;
            --sidebar-w: 265px;
            --header-h:  60px;
            --radius:    12px;
        }}
        html, body {{ height: 100%; overflow: hidden; }}
        body {{
            background: var(--bg);
            color: var(--text);
            font-family: 'Inter', sans-serif;
            display: flex;
            flex-direction: column;
        }}

        /* ══ TOP HEADER ══ */
        .top-header {{
            height: var(--header-h);
            min-height: var(--header-h);
            background: var(--sb-bg);
            border-bottom: 1px solid var(--sb-border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 20px;
            flex-shrink: 0;
        }}
        .brand {{ display: flex; align-items: center; gap: 10px; }}
        .brand-logo {{
            width: 34px; height: 34px;
            background: linear-gradient(135deg, #5b7fff, #9b5cf6);
            border-radius: 9px;
            display: flex; align-items: center; justify-content: center;
            font-size: 0.9rem; flex-shrink: 0;
        }}
        .brand-title {{ font-size: 0.9rem; font-weight: 700; color: #e8edf8; letter-spacing: -0.1px; }}
        .brand-sub {{ font-size: 0.62rem; color: var(--sb-muted); margin-top: 1px; }}
        .header-meta {{
            display: flex; align-items: center;
            gap: 14px; font-size: 0.7rem; color: var(--sb-muted);
        }}
        .header-meta span {{ display: flex; align-items: center; gap: 4px; }}
        .header-meta i {{ color: #7b9fff; font-size: 0.68rem; }}
        .live-pill {{
            display: flex; align-items: center; gap: 5px;
            background: rgba(34,197,94,0.15);
            border: 1px solid rgba(34,197,94,0.3);
            border-radius: 20px; padding: 3px 9px;
            font-size: 0.65rem; color: #4ade80;
            font-weight: 700; letter-spacing: 0.05em;
        }}
        .live-dot {{
            width: 5px; height: 5px; background: #22c55e;
            border-radius: 50%; animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity:1; transform:scale(1); }}
            50%        {{ opacity:0.3; transform:scale(0.6); }}
        }}
        
        /* PRICE TAGS */
        .price-tag {{
            font-size: 0.65rem;
            margin-left: 4px;
            padding: 1px 4px;
            border-radius: 4px;
            font-weight: 600;
        }}
        .price-tag.pos {{ background: rgba(34,197,94,0.15); color: #4ade80; }}
        .price-tag.neg {{ background: rgba(239,68,68,0.15); color: #f87171; }}
        .price-tag.neu {{ background: rgba(234,179,8,0.15); color: #facc15; }}
        
        /* AI SUMMARY */
        .ai-summary {{
            font-size: 0.72rem;
            color: #475569;
            background: rgba(139,92,246,0.05);
            border-left: 3px solid #8b5cf6;
            padding: 6px 10px;
            margin-top: 8px;
            margin-bottom: 4px;
            border-radius: 0 6px 6px 0;
            line-height: 1.4;
        }}
        .ai-summary i {{ color: #8b5cf6; margin-right: 4px; }}

        /* ══ APP BODY ══ */
        .app-body {{ display: flex; flex: 1; overflow: hidden; }}

        /* ══ SIDEBAR ══ */
        .sidebar {{
            width: var(--sidebar-w);
            min-width: var(--sidebar-w);
            background: var(--sb-bg);
            border-right: 1px solid var(--sb-border);
            display: flex; flex-direction: column; overflow: hidden;
        }}
        .sidebar-header {{
            padding: 14px 14px 10px;
            border-bottom: 1px solid var(--sb-border);
            flex-shrink: 0;
        }}
        .sidebar-label {{
            font-size: 0.58rem; text-transform: uppercase;
            letter-spacing: 0.12em; color: var(--sb-muted);
            font-weight: 700; margin-bottom: 2px;
        }}
        .sidebar-total {{ font-size: 0.73rem; color: var(--sb-muted); }}
        .sidebar-total strong {{ color: #7b9fff; font-weight: 700; }}
        .nav-list {{ flex: 1; overflow-y: auto; padding: 6px; }}
        .nav-list::-webkit-scrollbar {{ width: 3px; }}
        .nav-list::-webkit-scrollbar-thumb {{ background: var(--sb-border); border-radius: 3px; }}

        .nav-item {{
            display: flex; align-items: center;
            gap: 9px; padding: 10px 11px;
            border-radius: 10px; cursor: pointer;
            border: 1px solid transparent;
            margin-bottom: 3px;
            transition: background 0.15s, border-color 0.15s;
        }}
        .nav-item:hover {{
            background: rgba(255,255,255,0.05);
            border-color: rgba(255,255,255,0.1);
        }}
        .nav-item.active {{
            background: var(--cat-glow, rgba(91,127,255,0.18));
            border-color: var(--cat-border, rgba(91,127,255,0.4));
        }}
        .nav-item.active .nav-name {{ color: var(--cat-color, #7b9fff); font-weight: 700; }}
        .nav-item.active .nav-arrow {{ opacity: 1; color: var(--cat-color); }}

        .nav-num {{ font-size: 0.58rem; font-weight: 800; color: var(--sb-muted); width: 14px; text-align: center; flex-shrink: 0; }}
        .nav-icon-wrap {{ width: 30px; height: 30px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 0.75rem; flex-shrink: 0; }}
        .nav-text {{ flex: 1; min-width: 0; }}
        .nav-name {{ font-size: 0.8rem; font-weight: 500; color: var(--sb-text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .nav-count {{ font-size: 0.63rem; color: var(--sb-muted); margin-top: 1px; }}
        .nav-arrow {{ font-size: 0.55rem; color: var(--sb-muted); opacity: 0; transition: opacity 0.15s; flex-shrink: 0; }}
        .nav-item:hover .nav-arrow {{ opacity: 0.5; }}
        .sidebar-footer {{
            padding: 10px 14px; border-top: 1px solid var(--sb-border);
            font-size: 0.6rem; color: var(--sb-muted); flex-shrink: 0;
        }}

        /* ══ CONTENT AREA ══ */
        .content-area {{ flex: 1; overflow-y: auto; background: var(--bg); }}
        .content-area::-webkit-scrollbar {{ width: 5px; }}
        .content-area::-webkit-scrollbar-thumb {{ background: #c8d0e0; border-radius: 5px; }}

        .content-panel {{ display: none; padding: 20px 24px; }}
        .content-panel.active {{ display: block; animation: fadeIn 0.18s ease; }}
        @keyframes fadeIn {{ from {{ opacity:0; transform:translateY(4px); }} to {{ opacity:1; transform:translateY(0); }} }}

        /* ── Panel header ── */
        .panel-header {{
            display: flex; align-items: center; justify-content: space-between;
            padding: 14px 18px;
            background: var(--surface);
            border-radius: var(--radius);
            border: 1px solid var(--border);
            margin-bottom: 16px; gap: 12px;
            border-left: 4px solid;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        }}
        .panel-header-left {{ display: flex; align-items: center; gap: 12px; }}
        .panel-icon {{ width: 38px; height: 38px; border-radius: 10px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }}
        .panel-title {{ font-size: 0.95rem; font-weight: 700; color: var(--text); letter-spacing: -0.1px; }}
        .panel-subtitle {{ font-size: 0.67rem; color: var(--muted); margin-top: 2px; }}
        .panel-badge {{
            display: flex; align-items: center; gap: 5px;
            font-size: 0.68rem; font-weight: 700;
            padding: 4px 10px; border-radius: 20px; flex-shrink: 0;
        }}

        /* ══ NEWS CARD LIST - Headline only ══ */
        .cards-grid {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .news-card {{
            background: var(--surface);
            border: 1px solid var(--border);
            border-left: 3px solid var(--border);
            border-radius: 6px;
            padding: 8px 12px;
            transition: border-left-color 0.15s, background 0.12s;
        }}
        .news-card:hover {{
            border-left-color: #5b7fff;
            background: #f5f7fd;
        }}
        .news-content-inline {{
            font-size: 0.88rem;
            line-height: 1.45;
        }}
        .news-headline-link {{
            font-weight: 700;
            color: #111827;
            text-decoration: none;
        }}
        .news-headline-link:hover {{
            color: #2563eb;
            text-decoration: underline;
        }}
        .news-meta {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            font-size: 0.7rem;
            color: var(--muted2);
            margin-left: 8px;
            white-space: nowrap;
        }}
        .ticker-badge {{
            display: inline-block;
            background: rgba(6,182,212,0.12);
            color: #0891b2;
            font-size: 0.72rem;
            font-weight: 800;
            padding: 1px 5px;
            border-radius: 4px;
            margin-right: 6px;
            border: 1px solid rgba(6,182,212,0.25);
            vertical-align: middle;
        }}
        .sentiment-badge {{
            display: inline-block;
            font-size: 0.72rem;
            font-weight: 700;
            padding: 1px 6px;
            border-radius: 4px;
            margin-right: 6px;
            vertical-align: middle;
        }}
        .sentiment-badge.pos {{
            background: rgba(34,197,94,0.12);
            color: #166534;
            border: 1px solid rgba(34,197,94,0.3);
        }}
        .sentiment-badge.neg {{
            background: rgba(239,68,68,0.12);
            color: #991b1b;
            border: 1px solid rgba(239,68,68,0.3);
        }}
        .sentiment-badge.neu {{
            background: rgba(100,116,139,0.12);
            color: #475569;
            border: 1px solid rgba(100,116,139,0.3);
        }}
        .news-meta i {{ font-size: 0.65rem; }}
        .meta-time {{ color: var(--muted2); font-weight: 500; }}
        .meta-sep {{ color: #c4ccd8; }}
        .src-chip {{
            color: #4f6dc8;
            text-decoration: none;
            font-weight: 600;
            transition: color 0.12s;
        }}
        .src-chip:hover {{ color: #2d4ea8; text-decoration: underline; }}
        .multi-badge {{ font-size: 0.62rem; color: var(--muted2); }}
    </style>
</head>
<body>

<!-- TOP HEADER -->
<div class="top-header">
    <div class="brand">
        <div class="brand-logo"><i class="fa-solid fa-chart-mixed" style="color:#fff;"></i></div>
        <div>
            <div class="brand-title">BẢN TIN TÀI CHÍNH THÔNG MINH</div>
            <div class="brand-sub">Tổng hợp đa nguồn · Khử trùng lặp · Phân loại tự động</div>
        </div>
    </div>
    <div class="header-meta">
        <span><i class="fa-regular fa-calendar"></i> {weekday_str}, {today_str}</span>
        <span><i class="fa-regular fa-clock"></i> {now_str}</span>
        <span><i class="fa-solid fa-database"></i> {total_articles} bài · {total_clusters} cụm</span>
        <div class="live-pill"><span class="live-dot"></span>LIVE</div>
    </div>
</div>

<!-- APP BODY -->
<div class="app-body">

    <!-- SIDEBAR -->
    <div class="sidebar">
        <div class="sidebar-header">
            <div class="sidebar-label"><i class="fa-solid fa-list-ul"></i> &nbsp;Danh mục</div>
            <div class="sidebar-total">
                <strong>{len(active_cats)}</strong> nhóm · <strong>{total_clusters}</strong> tin
            </div>
        </div>
        <div class="nav-list">
            {sidebar_items_html}
        </div>
        <div class="sidebar-footer">
            <i class="fa-solid fa-rss"></i> {len(RSS_FEEDS)} nguồn RSS · {today_str}
        </div>
    </div>

    <!-- CONTENT AREA -->
    <div class="content-area">
        {panels_html}
    </div>
</div>

<script>
    const navItems = document.querySelectorAll('.nav-item');
    const panels   = document.querySelectorAll('.content-panel');

    navItems.forEach(function(item) {{
        item.addEventListener('click', function() {{
            const target = this.getAttribute('data-target');

            navItems.forEach(function(n) {{ n.classList.remove('active'); }});
            panels.forEach(function(p) {{ p.classList.remove('active'); }});

            this.classList.add('active');
            const panel = document.getElementById(target);
            if (panel) {{
                panel.classList.add('active');
                // scroll content area về đầu khi chuyển tab
                panel.parentElement.scrollTop = 0;
            }}
        }});
    }});
</script>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

def main():
    print("🤖 Bắt đầu cào dữ liệu tin tức vĩ mô ngày hôm nay...")
    all_articles = []
    
    for source, url in RSS_FEEDS.items():
        print(f"-> Quét nguồn: {source}")
        all_articles.extend(parse_rss(source, url))
        
    if not all_articles:
        print("❌ Không thu thập được tin tức!")
        sys.exit(1)
        
    df = pd.DataFrame(all_articles)
    
    # Lọc tin trong 24h qua
    now = datetime.now(timezone.utc)
    twenty_four_hours_ago = now - timedelta(hours=24)
    
    recent_articles = []
    for _, row in df.iterrows():
        pub_date = row["pub_date"]
        if pub_date is None or pub_date >= twenty_four_hours_ago:
            title = row["title"]
            source = row["source"]
            if " - " in title and "Google News" in source:
                parts = title.rsplit(" - ", 1)
                title = parts[0]
                source = parts[1]
                row["title"] = title
                row["source"] = source
            recent_articles.append(row.to_dict())
            
    if not recent_articles:
        print("❌ Không có tin tức mới trong 24h qua.")
        sys.exit(0)
        
    # Phân loại và lọc
    target_tickers = get_target_tickers()
    filtered_articles = []
    for art in recent_articles:
        cat, tickers, sentiment = classify_article(art["title"], art["description"], target_tickers)
        if cat:
            art["category"] = cat
            art["tickers"] = tickers
            art["sentiment"] = sentiment
            filtered_articles.append(art)
            
    if not filtered_articles:
        print("❌ Sau khi lọc phân loại, không còn tin tức vĩ mô quan trọng nào.")
        sys.exit(0)
        
    # Gom cụm tin trùng
    clustered_data = cluster_articles(filtered_articles)
    
    # Lấy dữ liệu giá cho các mã xuất hiện trong tin tức
    all_tickers = set()
    for cluster in clustered_data:
        all_tickers.update(cluster.get("tickers", []))
    stock_prices = fetch_stock_prices(list(all_tickers))
    
    # AI Tóm tắt
    ai_summaries = summarize_clusters_with_ai(clustered_data)
    
    # Đọc Watchlist
    watchlist = load_watchlist()
    
    # Gửi Telegram Alert
    send_telegram_alerts(clustered_data, stock_prices, ai_summaries, watchlist)
    
    # Cấu hình xuất file HTML
    if os.environ.get("GITHUB_ACTIONS"):
        # Chạy trên GitHub Actions -> lưu vào thư mục docs/ để serve GitHub Pages
        docs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
        if not os.path.exists(docs_dir):
            os.makedirs(docs_dir)
        output_file = os.path.join(docs_dir, "index.html")
        build_html_report(clustered_data, output_file, stock_prices, ai_summaries, watchlist)
        print(f"\n✅ Đã xuất báo cáo tự động cho GitHub Pages: {output_file}")
    else:
        # Chạy cục bộ ở máy tính -> lưu ra Desktop
        desktop = get_desktop_path()
        output_file = os.path.join(desktop, "ban_tin_tai_chinh_hang_ngay.html")
        build_html_report(clustered_data, output_file, stock_prices, ai_summaries, watchlist)
        print(f"\n✅ Đã xuất báo cáo thành công ra Desktop: {output_file}")

if __name__ == "__main__":
    main()
