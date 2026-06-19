import os
import sys
import requests
import json
import time

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
OFFSET_FILE = "experiments/scratch/telegram_offset.txt"

def get_offset():
    if os.path.exists(OFFSET_FILE):
        try:
            with open(OFFSET_FILE, "r") as f:
                return int(f.read().strip())
        except:
            pass
    return None

def save_offset(offset):
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    requests.post(url, json=payload)

def handle_tin(chat_id, symbol):
    # Dùng LLM hoặc lấy dữ liệu giả lập (thực tế sẽ gọi vnstock_news)
    send_message(chat_id, f"🔍 Đang tìm kiếm tin tức cho mã <b>{symbol.upper()}</b>...")
    # Tích hợp logic tìm tin (giả lập trả về tạm thời)
    from experiments.scratch.run_intraday_alerts import call_llm_fallback
    prompt = f"Viết 1 nhận định siêu ngắn về cổ phiếu {symbol.upper()} hôm nay dựa trên những gì bạn biết."
    res = call_llm_fallback(prompt)
    send_message(chat_id, f"📰 <b>TIN TỨC {symbol.upper()}</b>\n{res}")

def handle_soi(chat_id, symbol):
    send_message(chat_id, f"🧠 AI đang soi mã <b>{symbol.upper()}</b>...")
    from experiments.scratch.run_intraday_alerts import call_llm_fallback
    prompt = f"Đóng vai chuyên gia phân tích kỹ thuật và cơ bản, đưa ra lời khuyên MUA/BÁN cho cổ phiếu {symbol.upper()}."
    res = call_llm_fallback(prompt)
    send_message(chat_id, f"🎯 <b>KHUYẾN NGHỊ {symbol.upper()}</b>\n{res}")

def handle_chart(chat_id, symbol):
    send_message(chat_id, f"📊 Đang vẽ biểu đồ cho mã <b>{symbol.upper()}</b> (tính năng đang được xây dựng...).")

def main():
    if not TOKEN:
        print("Thiếu TELEGRAM_BOT_TOKEN")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"timeout": 10}
    offset = get_offset()
    if offset:
        params["offset"] = offset

    try:
        res = requests.get(url, params=params).json()
        if not res.get("ok"):
            print("Lỗi Telegram:", res)
            return
            
        updates = res.get("result", [])
        if not updates:
            print("Không có tin nhắn mới.")
            return

        highest_offset = offset or 0
        for upd in updates:
            upd_id = upd["update_id"]
            highest_offset = max(highest_offset, upd_id + 1)
            
            msg = upd.get("message", {})
            text = msg.get("text", "")
            chat_id = msg.get("chat", {}).get("id")
            
            if not text or not chat_id:
                continue
                
            text = text.strip()
            if text.startswith("/tin"):
                parts = text.split(" ")
                if len(parts) > 1 and parts[1].strip():
                    handle_tin(chat_id, parts[1].strip())
                else:
                    send_message(chat_id, "Sếp hãy gõ thêm mã cổ phiếu nhé! Ví dụ: /tin VCB")
            elif text.startswith("/soi"):
                parts = text.split(" ")
                if len(parts) > 1 and parts[1].strip():
                    handle_soi(chat_id, parts[1].strip())
                else:
                    send_message(chat_id, "Sếp hãy gõ thêm mã cổ phiếu nhé! Ví dụ: /soi FPT")
            elif text.startswith("/chart"):
                parts = text.split(" ")
                if len(parts) > 1 and parts[1].strip():
                    handle_chart(chat_id, parts[1].strip())
                else:
                    send_message(chat_id, "Sếp hãy gõ thêm mã cổ phiếu nhé! Ví dụ: /chart HPG")
                
        # Lưu offset để không xử lý lại
        save_offset(highest_offset)
        print(f"Đã xử lý {len(updates)} tin nhắn. Cập nhật offset: {highest_offset}")
        
    except Exception as e:
        print("Lỗi xử lý:", e)

if __name__ == "__main__":
    main()
