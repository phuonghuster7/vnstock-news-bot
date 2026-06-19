#!/bin/bash
# run_morning_brief.sh
# Wrapper chạy trong WSL Ubuntu.
# Được gọi bởi Windows Task Scheduler khi startup.

cd /mnt/d/Qlib-Vnstock
source ~/.venv_linux/bin/activate
export PYTHONPATH=/mnt/d/Qlib-Vnstock

LOG_DIR="/mnt/d/Qlib-Vnstock/paper_trading/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/daily_monitor.log"

# 1. Tự động cập nhật dữ liệu Qlib từ vnstock (Cập nhật các ngày trống)
echo "$(date '+%Y-%m-%d %H:%M:%S') — Cập nhật dữ liệu Qlib..." >> "$LOG_FILE"
python3 -m vnstock_qlib.build_data --universe vn100 >> "$LOG_FILE" 2>&1

# 2. Tự động Rebalance (Chỉ chạy vào Thứ Hai, hoặc chạy bù nếu dữ liệu tuần này chưa được chấm điểm)
TODAY_MON=$(date -d "last monday" +%Y-%m-%d)
if [ "$(date +%u)" -eq 1 ]; then
    TODAY_MON=$(date +%Y-%m-%d)
fi

# Kiểm tra xem log tuần này đã tồn tại trong weekly_log.csv chưa
if [ -f "paper_trading/weekly_log.csv" ]; then
    HAS_WEEK=$(grep -c "$TODAY_MON" "paper_trading/weekly_log.csv")
else
    HAS_WEEK=0
fi

if [ "$HAS_WEEK" -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') — Phát hiện thiếu log tuần $TODAY_MON. Tự động chạy Rebalance..." >> "$LOG_FILE"
    python3 experiments/live_ranking.py --rank >> "$LOG_FILE" 2>&1
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') — Đã có dữ liệu Rebalance cho tuần $TODAY_MON. Bỏ qua ranking..." >> "$LOG_FILE"
fi

# 3. Chạy báo cáo hàng ngày morning brief
echo "$(date '+%Y-%m-%d %H:%M:%S') — Quét tin tức Morning Brief..." >> "$LOG_FILE"
python3 /mnt/d/Qlib-Vnstock/experiments/scratch/morning_brief_bot.py >> "$LOG_FILE" 2>&1

echo "$(date '+%Y-%m-%d %H:%M:%S') — Khởi chạy Daily Monitor..." >> "$LOG_FILE"
python3 /mnt/d/Qlib-Vnstock/paper_trading/daily_monitor.py >> "$LOG_FILE" 2>&1

EXIT_CODE=$?
echo "$(date '+%Y-%m-%d %H:%M:%S') — EXIT $EXIT_CODE" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
