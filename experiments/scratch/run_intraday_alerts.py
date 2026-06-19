import os
import sys
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import html
import re
import pandas as pd
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
import dateutil.parser as date_parser

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# RSS Feeds
GOOGLE_NEWS_MACRO_URL = "https://news.google.com/rss/search?q=" + quote("lãi suất OR lạm phát OR chứng khoán OR vĩ mô OR tỷ giá OR doanh nghiệp") + "&hl=vi&gl=VN&ceid=VN:vi"
GOOGLE_NEWS_GEOPOLITICS_URL = "https://news.google.com/rss/search?q=" + quote("địa chính trị OR chiến tranh OR xung đột OR thuế quan OR chính trị OR bầu cử OR ngoại giao") + "&hl=vi&gl=VN&ceid=VN:vi"

RSS_FEEDS = {
    "Google News - Tài chính vĩ mô": GOOGLE_NEWS_MACRO_URL,
    "Google News - Địa chính trị": GOOGLE_NEWS_GEOPOLITICS_URL,
    "CafeF - Thị trường": "https://cafef.vn/thi-truong-chung-khoan.rss",
    "CafeF - Vĩ mô": "https://cafef.vn/thoi-su.rss",
    "CafeF - Doanh nghiệp": "https://cafef.vn/doanh-nghiep.rss",
    "Vietstock - Vĩ mô": "https://vietstock.vn/rss/tai-chinh.rss",
    "Vietstock - Doanh nghiệp": "https://vietstock.vn/rss/doanh-nghiep.rss"
}

def fix_encoding(text):
    if not text: return ""
    try: return re.sub(r'#([0-9]+);?', lambda m: chr(int(m.group(1))), text)
    except Exception: return text

def parse_rss(source_name, url):
    articles = []
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code != 200: return articles
        root = ET.fromstring(response.content)
        for item in root.findall(".//item"):
            title_raw = item.find("title").text or ""
            pub_date_raw = item.find("pubDate").text or ""
            title = fix_encoding(html.unescape(title_raw)).strip()
            
            pub_date = None
            if pub_date_raw:
                try: pub_date = date_parser.parse(pub_date_raw)
                except: pass
            
            articles.append({"title": title, "pub_date": pub_date})
    except Exception:
        pass
    return articles

def call_llm_fallback(prompt):
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
            if response.text: return response.text.strip()
        except: pass

    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    if deepseek_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}]
            )
            if response.choices: return response.choices[0].message.content.strip()
        except: pass
        
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}]
            )
            if response.choices: return response.choices[0].message.content.strip()
        except: pass

    return "KHÔNG"

def main():
    print("🤖 Bắt đầu quét tin tức ĐỘT BIẾN (Intraday)...")
    all_articles = []
    for source, url in RSS_FEEDS.items():
        all_articles.extend(parse_rss(source, url))
        
    df = pd.DataFrame(all_articles)
    now = datetime.now(timezone.utc)
    thirty_mins_ago = now - timedelta(minutes=35)
    
    recent_articles = []
    if not df.empty:
        for _, row in df.iterrows():
            pub_date = row.get("pub_date")
            if pd.notnull(pub_date) and pub_date >= thirty_mins_ago:
                recent_articles.append(row["title"])
                
    if not recent_articles:
        print("❌ Không có tin mới trong 30 phút qua.")
        return
        
    titles_text = "\n- ".join(list(set(recent_articles)))
    prompt = f"Bạn là một chuyên gia giao dịch chứng khoán. Đây là các tin tức vừa ra trong 30 phút qua:\n{titles_text}\n\nHỏi: Có tin tức nào mang tính ĐỘT BIẾN, BẤT NGỜ (High Impact) ảnh hưởng mạnh đến một cổ phiếu cụ thể hoặc toàn thị trường không (ví dụ bắt bớ, doanh thu lợi nhuận khủng, trúng thầu tỷ đô, chiến tranh, chính sách mới)? Nếu KHÔNG có gì đột biến, hãy trả lời chính xác chữ 'KHÔNG'. Nếu CÓ, hãy tóm tắt tin đó trong 1-2 câu ngắn gọn kèm tên mã cổ phiếu liên quan (nếu có). Lưu ý: Chỉ chọn tin thực sự rất quan trọng."
    
    print("Đang phân tích LLM...")
    result = call_llm_fallback(prompt)
    if result and "KHÔNG" not in result[:10].upper():
        print(f"🔥 CÓ TIN NÓNG: {result}")
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if token and chat_id:
            msg = f"🚨 <b>TIN NÓNG INTRADAY</b> 🚨\n\n{result}"
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={
                "chat_id": chat_id,
                "text": msg,
                "parse_mode": "HTML"
            })
            print("Đã gửi Telegram.")
    else:
        print("Trạng thái: Bình thường, không có tin giật gân.")

if __name__ == "__main__":
    main()
