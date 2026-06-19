import os
import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    with open(".env", "r") as f:
        for line in f:
            if "TELEGRAM_BOT_TOKEN" in line:
                TOKEN = line.split("=")[1].strip().strip("\"'")
                break

if TOKEN:
    url = f"https://api.telegram.org/bot{TOKEN}/setMyCommands"
    commands = [
        {"command": "tin", "description": "Xem nhanh tin tức của cổ phiếu (VD: /tin VCB)"},
        {"command": "soi", "description": "Nhờ AI soi kỹ thuật & khuyến nghị (VD: /soi FPT)"},
        {"command": "chart", "description": "Vẽ biểu đồ phân tích kỹ thuật (VD: /chart HPG)"}
    ]
    
    # Đăng ký cho toàn bộ các Group Chat
    requests.post(url, json={"commands": commands, "scope": {"type": "default"}})
    requests.post(url, json={"commands": commands, "scope": {"type": "all_group_chats"}})
    requests.post(url, json={"commands": commands, "scope": {"type": "all_chat_administrators"}})
    
    print("Xong!")
else:
    print("No token")
