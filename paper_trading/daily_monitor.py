"""
paper_trading/daily_monitor.py
─────────────────────────────
Chạy mỗi sáng khi khởi động máy.
Output: ghi đè file duy nhất trên Desktop (morning_brief.md).

Logic:
  - Đọc portfolio tuần hiện tại từ weekly_log.csv
  - Fetch giá từ Qlib (không cần vnstock API)
  - Tính return từ entry + return hôm nay / ngày gần nhất
  - So sánh với VN100 benchmark
  - Ghi đè Desktop/morning_brief.md

Tự chạy khi startup → xem file trên Desktop mỗi sáng.
"""
import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
import shutil
shutil.copy2 = shutil.copyfile
shutil.copy  = shutil.copyfile

import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────
QLIB_DIR    = os.path.expanduser("~/.qlib/qlib_data/vn_data")
PAPER_DIR   = Path(__file__).parent
LOG_FILE    = PAPER_DIR / "weekly_log.csv"
NAV_FILE    = PAPER_DIR / "nav_tracking.csv"

# Output file: Windows Desktop (qua WSL mount /mnt/c)
_win_user = os.environ.get("WSLENV", "")
_username = os.popen("cmd.exe /c echo %USERNAME% 2>/dev/null").read().strip()
if not _username:
    # Fallback: lấy từ /mnt/c/Users
    import glob as _glob
    _users = [p for p in _glob.glob("/mnt/c/Users/*/Desktop") if "Public" not in p]
    _desktop = _users[0] if _users else str(Path.home() / "Desktop")
else:
    _desktop = f"/mnt/c/Users/{_username}/Desktop"

OUTPUT_FILE = Path(_desktop) / "morning_brief.md"

# ─── Khởi tạo Qlib ────────────────────────────────────────────────────────────
import qlib
from qlib.data import D

qlib.init(provider_uri=QLIB_DIR)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def fetch_prices(symbols: list, start: str, end: str) -> pd.DataFrame:
    """Fetch close + volume từ Qlib."""
    extra_end = (pd.Timestamp(end) + timedelta(days=5)).strftime("%Y-%m-%d")
    raw = D.features(symbols, ["$close", "$volume"], start_time=start, end_time=extra_end)
    if raw.empty:
        return pd.DataFrame()
    raw.columns = ["close", "volume"]
    raw = raw.reset_index()
    raw["datetime"] = pd.to_datetime(raw["datetime"])
    # Chỉ lấy đến ngày có data (không tương lai)
    raw = raw[raw["datetime"] <= pd.Timestamp(end)]
    return raw


def get_latest_trading_date(price_df: pd.DataFrame) -> pd.Timestamp:
    """Ngày giao dịch gần nhất trong data."""
    if price_df.empty:
        return None
    return price_df["datetime"].max()


def calc_return(price_df: pd.DataFrame, sym: str,
                entry_date: str) -> dict:
    """
    Entry: close ngày gần nhất <= entry_date có data thực (không NaN)
    Current: close ngày mới nhất có data thực
    """
    s = price_df[(price_df["instrument"] == sym)].sort_values("datetime")
    # Chỉ giữ rows có close thực (loại NaN placeholder)
    s = s.dropna(subset=["close"])
    if s.empty or len(s) < 1:
        return None

    entry_dt = pd.Timestamp(entry_date)

    # Entry: ngày cuối cùng <= entry_date có data thực
    s_before = s[s["datetime"] <= entry_dt]
    if s_before.empty:
        s_entry_row = s.iloc[[0]]
    else:
        s_entry_row = s_before.iloc[[-1]]

    # Current: ngày mới nhất có data thực
    s_current_row = s.iloc[[-1]]

    p_entry   = float(s_entry_row.iloc[0]["close"])
    p_current = float(s_current_row.iloc[0]["close"])
    date_entry   = s_entry_row.iloc[0]["datetime"]
    date_current = s_current_row.iloc[0]["datetime"]

    ret_total = p_current / p_entry - 1 if p_entry > 0 else np.nan

    # Return ngày cuối vs ngày trước
    ret_today = np.nan
    if len(s) >= 2:
        p_prev    = float(s.iloc[-2]["close"])
        ret_today = p_current / p_prev - 1 if p_prev > 0 else np.nan

    avg_vol_5d = float(s.tail(5)["volume"].mean())

    return {
        "symbol":      sym,
        "entry_date":  date_entry.strftime("%Y-%m-%d"),
        "last_date":   date_current.strftime("%Y-%m-%d"),
        "p_entry":     round(p_entry, 2),
        "p_current":   round(p_current, 2),
        "ret_total":   ret_total,
        "ret_today":   ret_today,
        "avg_vol_5d":  avg_vol_5d,
    }


# ─── Core logic ───────────────────────────────────────────────────────────────

def run_daily_monitor() -> str:
    """
    Chạy daily monitor, trả về nội dung markdown.
    """
    now   = datetime.now()
    today = now.strftime("%Y-%m-%d")
    ts    = now.strftime("%Y-%m-%d %H:%M")
    dow   = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"][now.weekday()]

    lines = []
    lines.append(f"# 📊 Morning Brief — {dow} {today}")
    lines.append(f"*Generated: {ts}*\n")

    # ── Đọc portfolio ──────────────────────────────────────────────────────
    if not LOG_FILE.exists():
        lines.append("⚠️ **Chưa có weekly_log.csv. Chạy live_ranking.py --rank trước.**")
        return "\n".join(lines)

    log = pd.read_csv(LOG_FILE)
    if log.empty:
        lines.append("⚠️ weekly_log.csv trống.")
        return "\n".join(lines)

    log["week_of"] = pd.to_datetime(log["week_of"])
    latest_week_ts = log["week_of"].max()
    latest_week    = latest_week_ts.strftime("%Y-%m-%d")
    portfolio_rows = log[log["week_of"] == latest_week_ts]
    portfolio      = portfolio_rows["symbol"].tolist()
    scores         = dict(zip(portfolio_rows["symbol"], portfolio_rows["score"]))

    lines.append(f"## 📅 Portfolio tuần {latest_week} ({len(portfolio)} mã)")
    lines.append("")

    # ── Fetch prices ───────────────────────────────────────────────────────
    # Lấy thêm VN30 để làm benchmark proxy
    vn30_benchmark = ["ACB", "BID", "CTG", "FPT", "GAS", "HPG", "MBB",
                       "TCB", "VCB", "VHM", "VIC", "VNM", "VPB", "SSI", "VJC"]
    all_syms = list(set(portfolio + vn30_benchmark))

    # Fetch từ ngày entry (tuần đó)
    price_df = fetch_prices(all_syms, 
                            (pd.Timestamp(latest_week) - timedelta(days=10)).strftime("%Y-%m-%d"),
                            today)

    if price_df.empty:
        lines.append("⚠️ **Không fetch được giá từ Qlib. Kiểm tra kết nối data.**")
        return "\n".join(lines)

    last_data_date = get_latest_trading_date(price_df)
    lines.append(f"*Giá cập nhật đến: **{last_data_date.strftime('%Y-%m-%d')}***\n")

    # ── Tính return từng mã ────────────────────────────────────────────────
    results = []
    for sym in portfolio:
        r = calc_return(price_df, sym, latest_week)
        if r:
            r["score"] = scores.get(sym, 0)
            results.append(r)

    if not results:
        lines.append("⚠️ Không đủ data để tính return.")
        return "\n".join(lines)

    df = pd.DataFrame(results).sort_values("ret_total", ascending=False)

    # ── Portfolio summary ──────────────────────────────────────────────────
    port_ret_total = df["ret_total"].mean()
    port_ret_today = df["ret_today"].dropna().mean()
    winners        = (df["ret_total"] > 0).sum()
    losers         = (df["ret_total"] < 0).sum()

    # VN100 benchmark (dùng VN30 proxy)
    bench_rets = []
    for sym in vn30_benchmark:
        r = calc_return(price_df, sym, latest_week)
        if r and not np.isnan(r["ret_total"]):
            bench_rets.append(r["ret_total"])
    bench_ret   = np.mean(bench_rets) if bench_rets else np.nan
    alpha       = port_ret_total - bench_ret if not np.isnan(bench_ret) else np.nan

    # NAV indicator
    nav_indicator = ""
    if NAV_FILE.exists():
        nav_df = pd.read_csv(NAV_FILE)
        if not nav_df.empty and "cum_portfolio_nav" in nav_df.columns:
            last_nav = nav_df["cum_portfolio_nav"].iloc[-1]
            nav_indicator = f" | NAV: {last_nav:,.0f} VND"

    # Summary box
    alpha_str = f"{alpha:+.2%}" if not np.isnan(alpha) else "N/A"
    today_str = f"{port_ret_today:+.2%}" if not np.isnan(port_ret_today) else "N/A"
    bench_str = f"{bench_ret:+.2%}" if not np.isnan(bench_ret) else "N/A"

    lines.append("## 📈 Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Portfolio từ entry | **{port_ret_total:+.2%}** |")
    lines.append(f"| Hôm nay (avg) | {today_str} |")
    lines.append(f"| VN30 proxy từ entry | {bench_str} |")
    lines.append(f"| Alpha | **{alpha_str}** |")
    lines.append(f"| Lãi/Lỗ ({len(df)} mã) | 🟢{winners} 🔴{losers} |")
    if nav_indicator:
        lines.append(f"| {nav_indicator.strip()} | |")
    lines.append("")

    # ── Per-stock table ────────────────────────────────────────────────────
    lines.append("## 📋 Chi tiết từng mã")
    lines.append("")
    lines.append("| # | Symbol | Entry | Hiện tại | Từ Entry | Hôm nay | Vol 5d (M) |")
    lines.append("|---|--------|-------|----------|----------|---------|------------|")

    warnings = []
    for i, row in df.iterrows():
        flag      = "🟢" if row["ret_total"] > 0 else "🔴"
        today_ret = f"{row['ret_today']:+.2%}" if not np.isnan(row["ret_today"]) else "—"
        vol_m     = f"{row['avg_vol_5d']/1e6:.2f}M"
        lines.append(
            f"| {flag} | **{row['symbol']}** "
            f"| {row['p_entry']:.1f} "
            f"| {row['p_current']:.1f} "
            f"| **{row['ret_total']:+.2%}** "
            f"| {today_ret} "
            f"| {vol_m} |"
        )
        # Warning nếu giảm > 5% từ entry
        if row["ret_total"] < -0.05:
            warnings.append(f"⚠️ **{row['symbol']}** giảm {row['ret_total']:.1%} từ entry")
        # Warning nếu hôm nay giảm > 3%
        if not np.isnan(row["ret_today"]) and row["ret_today"] < -0.03:
            warnings.append(f"🔴 **{row['symbol']}** hôm nay {row['ret_today']:+.1%}")

    lines.append("")

    # ── Cảnh báo ──────────────────────────────────────────────────────────
    if warnings:
        lines.append("## ⚠️ Cảnh báo")
        lines.append("")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")
    else:
        lines.append("## ✅ Không có cảnh báo")
        lines.append("")

    # ── Thống kê lịch sử NAV (nếu có) ────────────────────────────────────
    if NAV_FILE.exists():
        nav_df = pd.read_csv(NAV_FILE)
        if len(nav_df) >= 1:
            lines.append("## 📊 Lịch sử NAV (paper trading)")
            lines.append("")
            lines.append("| Tuần | Port | VN100 | Alpha | IC |")
            lines.append("|------|------|-------|-------|----|")
            for _, row in nav_df.tail(6).iterrows():
                a_flag = "🟢" if row.get("alpha", 0) > 0 else "🔴"
                port_r = f"{float(row['portfolio_ret'])*100:+.2f}%" if pd.notna(row.get("portfolio_ret")) else "—"
                vn_r   = f"{float(row['vn100_ret'])*100:+.2f}%" if pd.notna(row.get("vn100_ret")) else "—"
                al_r   = f"{float(row['alpha'])*100:+.2f}%" if pd.notna(row.get("alpha")) else "—"
                ic_r   = f"{float(row['realized_ic']):.3f}" if pd.notna(row.get("realized_ic")) else "—"
                lines.append(f"| {str(row['week_of'])[:10]} | {port_r} | {vn_r} | {a_flag}{al_r} | {ic_r} |")
            lines.append("")

    # ── Footer ────────────────────────────────────────────────────────────
    lines.append("---")
    lines.append(f"*Model: VN100 V9 LightGBM | Rebalance: Thứ Hai hàng tuần*")
    lines.append(f"*Chạy lại: `python paper_trading/daily_monitor.py`*")

    return "\n".join(lines)


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Generating morning brief ...")

    try:
        content = run_daily_monitor()
    except Exception as e:
        content = f"# Morning Brief — ERROR\n\n```\n{e}\n```\n"
        import traceback
        content += f"\n```\n{traceback.format_exc()}\n```"

    # Ghi đè Desktop file
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(content, encoding="utf-8")

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Done → {OUTPUT_FILE}")
    print(f"\n{'─'*50}")
    # In preview ra terminal
    for line in content.split("\n")[:30]:
        print(line)
    if content.count("\n") > 30:
        print(f"... (xem đầy đủ tại {OUTPUT_FILE})")


if __name__ == "__main__":
    main()
