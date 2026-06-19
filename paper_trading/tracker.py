"""
paper_trading/tracker.py — PaperTradingTracker

Track NAV paper portfolio vs VN100 Index benchmark.
Cập nhật mỗi thứ Hai khi có ranking mới.

Usage:
    from paper_trading.tracker import PaperTradingTracker
    tracker = PaperTradingTracker()
    tracker.update_nav()          # Tính tuần vừa kết thúc
    tracker.monthly_report()      # In báo cáo tháng
    tracker.decision_check()      # Kiểm tra 3 KPI để quyết định live capital
"""
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Qlib
try:
    import qlib
    from qlib.data import D
    QLIB_AVAILABLE = True
except ImportError:
    QLIB_AVAILABLE = False

QLIB_DIR   = os.path.expanduser("~/.qlib/qlib_data/vn_data")
BASE_DIR   = Path(__file__).parent
LOG_PATH   = BASE_DIR / "weekly_log.csv"
NAV_PATH   = BASE_DIR / "nav_tracking.csv"
REPORT_MD  = BASE_DIR / "performance_report.md"
INIT_NAV   = 1_000_000_000   # 1 tỷ VND giả định

# ── KPI thresholds để quyết định live capital ──────────────────────────────
KPI_REALIZED_IC_MIN  = 0.025   # IC thực tế tối thiểu
KPI_ALPHA_MIN        = 0.0     # alpha dương vs VN100
KPI_WIN_RATE_MIN     = 0.55    # win rate vs benchmark


class PaperTradingTracker:
    """
    Track NAV tuần từ weekly_log.csv → nav_tracking.csv.

    Workflow mỗi thứ Hai:
      1. tracker.update_nav()  → điền realized return tuần trước
      2. tracker.monthly_report() → sau 4 tuần
      3. tracker.decision_check() → sau 6 tuần
    """

    def __init__(self, qlib_dir: str = QLIB_DIR):
        self.qlib_dir = qlib_dir
        self._qlib_init = False

    def _ensure_qlib(self):
        if not self._qlib_init and QLIB_AVAILABLE:
            os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
            import shutil
            shutil.copy2 = shutil.copyfile
            shutil.copy  = shutil.copyfile
            qlib.init(provider_uri=self.qlib_dir)
            self._qlib_init = True

    # ── Core: update tuần trước ───────────────────────────────────────────

    def update_nav(self, prev_week: str = None, curr_week: str = None):
        """
        Tính realized return của portfolio tuần `prev_week`.
        Entry: close ngày đầu tiên của prev_week (thứ Hai)
        Exit:  close ngày cuối cùng trước curr_week (thứ Sáu)
        So sánh với avg return VN100 universe cùng kỳ.

        Args:
            prev_week: YYYY-MM-DD (mặc định: tuần trước)
            curr_week: YYYY-MM-DD (mặc định: tuần này = hôm nay)
        """
        self._ensure_qlib()

        today = datetime.today()
        if curr_week is None:
            # Thứ Hai tuần này
            curr_week = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        if prev_week is None:
            prev_week = (pd.Timestamp(curr_week) - timedelta(weeks=1)).strftime("%Y-%m-%d")

        print(f"\n{'='*50}")
        print(f"  NAV Update: {prev_week} → {curr_week}")
        print(f"{'='*50}")

        if not LOG_PATH.exists():
            print("  Chưa có weekly_log.csv. Chạy live_ranking.py --rank trước.")
            return None

        log = pd.read_csv(LOG_PATH)
        portfolio = log[log["week_of"] == prev_week]["symbol"].tolist()

        if not portfolio:
            print(f"  Không tìm thấy portfolio cho tuần {prev_week}.")
            return None

        print(f"  Portfolio ({len(portfolio)} mã): {portfolio}")

        # ── Fetch prices từ Qlib ─────────────────────────────────────────
        all_syms = list(set(portfolio + self._get_vn100_sample()))
        fetch_start = prev_week
        fetch_end   = (pd.Timestamp(curr_week) + timedelta(days=3)).strftime("%Y-%m-%d")

        price_df = self._fetch_prices(all_syms, fetch_start, fetch_end)
        if price_df is None:
            return None

        # ── Portfolio return ─────────────────────────────────────────────
        port_rets = []
        for sym in portfolio:
            ret = self._calc_weekly_return(price_df, sym, prev_week, curr_week)
            if ret is not None:
                port_rets.append({"symbol": sym, "return": ret})

        if not port_rets:
            print("  Không đủ price data để tính return.")
            return None

        port_df      = pd.DataFrame(port_rets)
        port_return  = port_df["return"].mean()

        # ── Realized IC ──────────────────────────────────────────────────
        log_week = log[log["week_of"] == prev_week].copy()
        log_week = log_week.merge(port_df, on="symbol", how="inner")
        realized_ic = (log_week["score"].corr(log_week["return"], method="spearman")
                       if len(log_week) >= 3 else np.nan)

        # ── VN100 benchmark return ───────────────────────────────────────
        vn100_syms = self._get_universe()
        bench_rets = []
        for sym in vn100_syms:
            ret = self._calc_weekly_return(price_df, sym, prev_week, curr_week)
            if ret is not None:
                bench_rets.append(ret)
        vn100_ret = np.mean(bench_rets) if bench_rets else np.nan
        alpha     = port_return - vn100_ret if not np.isnan(vn100_ret) else np.nan
        hit_rate  = (port_df["return"] > 0).mean()

        # ── Print ────────────────────────────────────────────────────────
        print(f"\n  Stock-level returns:")
        for _, row in port_df.sort_values("return", ascending=False).iterrows():
            flag = "🟢" if row["return"] > 0 else "🔴"
            print(f"    {flag} {row['symbol']:<8} {row['return']:+.2%}")

        print(f"\n  {'Portfolio Return':<22}: {port_return:+.2%}")
        print(f"  {'VN100 Return':<22}: {vn100_ret:+.2%}" if not np.isnan(vn100_ret)
              else f"  {'VN100 Return':<22}: N/A")
        print(f"  {'Alpha':<22}: {alpha:+.2%}" if not np.isnan(alpha)
              else f"  {'Alpha':<22}: N/A")
        print(f"  {'Hit Rate':<22}: {hit_rate:.0%}")
        print(f"  {'Realized IC':<22}: {realized_ic:+.4f}" if not np.isnan(realized_ic)
              else f"  {'Realized IC':<22}: N/A")

        # ── Append NAV ──────────────────────────────────────────────────
        nav_row = {
            "week_of":        curr_week,
            "portfolio_ret":  round(port_return, 6),
            "vn100_ret":      round(vn100_ret, 6) if not np.isnan(vn100_ret) else np.nan,
            "alpha":          round(alpha, 6) if not np.isnan(alpha) else np.nan,
            "hit_rate":       round(hit_rate, 4),
            "realized_ic":    round(realized_ic, 4) if not np.isnan(realized_ic) else np.nan,
            "n_stocks":       len(port_rets),
        }
        self._append_nav(nav_row)
        print(f"\n  ✅ NAV logged → {NAV_PATH}")

        return nav_row

    # ── Reporting ─────────────────────────────────────────────────────────

    def monthly_report(self):
        """In báo cáo performance khi có ≥ 4 tuần data."""
        if not NAV_PATH.exists():
            print("Chưa có dữ liệu. Chạy update_nav() trước.")
            return

        nav = pd.read_csv(NAV_PATH, parse_dates=["week_of"])
        nav = nav.sort_values("week_of").reset_index(drop=True)
        n   = len(nav)

        if n < 2:
            print(f"Mới có {n} tuần, cần ≥ 4 tuần để báo cáo có ý nghĩa.")
            return

        total_port  = nav["portfolio_ret"].add(1).prod() - 1
        total_bench = nav["vn100_ret"].fillna(0).add(1).prod() - 1
        total_alpha = total_port - total_bench
        avg_ic      = nav["realized_ic"].mean()
        avg_alpha   = nav["alpha"].mean()
        win_rate    = (nav["alpha"] > 0).mean()
        sharpe      = (nav["portfolio_ret"].mean() / nav["portfolio_ret"].std() * np.sqrt(52)
                       if nav["portfolio_ret"].std() > 0 else 0)

        # Cumulative NAV
        nav["cum_port"]  = INIT_NAV * nav["portfolio_ret"].add(1).cumprod()
        nav["cum_bench"] = INIT_NAV * nav["vn100_ret"].fillna(0).add(1).cumprod()

        print(f"\n{'='*50}")
        print(f"  Paper Trading Report ({n} tuần)")
        print(f"{'='*50}")
        print(f"\n  {'Metric':<25} {'Value':>12}")
        print(f"  {'-'*38}")
        print(f"  {'Total Portfolio Ret':<25} {total_port:>+12.2%}")
        print(f"  {'Total VN100 Ret':<25} {total_bench:>+12.2%}")
        print(f"  {'Total Alpha':<25} {total_alpha:>+12.2%}")
        print(f"  {'Avg Weekly Alpha':<25} {avg_alpha:>+12.2%}")
        print(f"  {'Avg Realized IC':<25} {avg_ic:>+12.4f}")
        print(f"  {'Win Rate vs VN100':<25} {win_rate:>12.0%}")
        print(f"  {'Ann. Sharpe (weekly)':<25} {sharpe:>12.3f}")

        print(f"\n  Weekly breakdown:")
        cols = ["week_of", "portfolio_ret", "vn100_ret", "alpha", "realized_ic"]
        for _, row in nav[cols].iterrows():
            alpha_flag = "🟢" if row["alpha"] > 0 else "🔴"
            print(f"  {alpha_flag} {str(row['week_of'])[:10]}  "
                  f"Port={row['portfolio_ret']:+.2%}  "
                  f"VN100={row['vn100_ret']:+.2%}  "
                  f"Alpha={row['alpha']:+.2%}  "
                  f"IC={row['realized_ic']:+.3f}")

        # Save markdown report
        self._save_report_md(nav, total_port, total_bench, total_alpha,
                             avg_ic, avg_alpha, win_rate, sharpe, n)

    def decision_check(self):
        """
        Kiểm tra 3 KPI để quyết định có nên live capital không.
        Gọi sau ≥ 6 tuần paper trading.
        """
        if not NAV_PATH.exists():
            print("Chưa có dữ liệu nav_tracking.csv.")
            return

        nav = pd.read_csv(NAV_PATH)
        n   = len(nav)

        avg_ic     = nav["realized_ic"].mean()
        avg_alpha  = nav["alpha"].mean()
        win_rate   = (nav["alpha"] > 0).mean()

        kpi_ic_ok  = avg_ic > KPI_REALIZED_IC_MIN
        kpi_al_ok  = avg_alpha > KPI_ALPHA_MIN
        kpi_wr_ok  = win_rate > KPI_WIN_RATE_MIN
        kpis_met   = sum([kpi_ic_ok, kpi_al_ok, kpi_wr_ok])

        print(f"\n{'='*50}")
        print(f"  Decision Check ({n} tuần paper trading)")
        print(f"{'='*50}")
        print(f"\n  KPI 1: Realized IC > {KPI_REALIZED_IC_MIN:.3f}  "
              f"→ {avg_ic:+.4f}  {'✅' if kpi_ic_ok else '❌'}")
        print(f"  KPI 2: Avg Alpha  > {KPI_ALPHA_MIN:.0%}      "
              f"→ {avg_alpha:+.2%}  {'✅' if kpi_al_ok else '❌'}")
        print(f"  KPI 3: Win Rate   > {KPI_WIN_RATE_MIN:.0%}      "
              f"→ {win_rate:.0%}    {'✅' if kpi_wr_ok else '❌'}")

        print(f"\n  {'─'*45}")
        if kpis_met == 3:
            print(f"  🟢 CẢ 3 KPI ĐẠT — Xem xét live capital (5-10 triệu VND)")
            print(f"  → Bắt đầu với position size = 1/8 của target allocation")
            print(f"  → Scale up sau 4 tuần live nếu realized IC tiếp tục > 0.025")
        elif kpis_met == 2:
            print(f"  🟡 2/3 KPI ĐẠT — Tiếp tục paper thêm 4 tuần")
            if not kpi_ic_ok:
                print(f"  → IC thấp: kiểm tra feature drift")
            if not kpi_al_ok:
                print(f"  → Alpha âm: xem sector rotation")
            if not kpi_wr_ok:
                print(f"  → Win rate thấp: portfolio quá concentrated?")
        else:
            print(f"  🔴 < 2/3 KPI — Debug model trước khi live")
            print(f"  → Xem lại debug_w5_2024h2.py cho pattern tương tự")

    # ── Private helpers ───────────────────────────────────────────────────

    def _fetch_prices(self, symbols: list, start: str, end: str):
        """Fetch close prices từ Qlib."""
        if not QLIB_AVAILABLE:
            print("  Qlib không available.")
            return None
        try:
            raw = D.features(symbols, ["$close"], start_time=start, end_time=end)
            raw.columns = ["close"]
            raw = raw.reset_index()
            raw["datetime"] = pd.to_datetime(raw["datetime"])
            return raw
        except Exception as e:
            print(f"  Lỗi fetch prices: {e}")
            return None

    def _calc_weekly_return(self, price_df: pd.DataFrame,
                             sym: str, entry_week: str, exit_week: str) -> float:
        """
        Entry: close ngày đầu tiên >= entry_week
        Exit:  close ngày cuối cùng < exit_week
        """
        s = price_df[price_df["instrument"] == sym].sort_values("datetime")
        s_entry = s[s["datetime"] >= entry_week]
        s_exit  = s[s["datetime"] < exit_week]
        if s_entry.empty or s_exit.empty:
            return None
        p0 = s_entry.iloc[0]["close"]
        p1 = s_exit.iloc[-1]["close"]
        if p0 <= 0:
            return None
        return float(p1 / p0 - 1)

    def _get_universe(self) -> list:
        """Lấy VN100 universe từ Qlib."""
        if not QLIB_AVAILABLE:
            return []
        try:
            return D.list_instruments(D.instruments("vn100"), as_list=True)
        except Exception:
            return []

    def _get_vn100_sample(self) -> list:
        """Sample VN100 cho benchmark nếu Qlib không available."""
        return [
            "ACB", "BID", "CTG", "FPT", "GAS", "HPG", "MBB", "MSN",
            "MWG", "TCB", "VCB", "VHM", "VIC", "VNM", "VPB",
        ]

    def _append_nav(self, row: dict):
        """Append 1 row vào nav_tracking.csv, recalculate cumulative NAV."""
        existing = pd.read_csv(NAV_PATH) if NAV_PATH.exists() else pd.DataFrame()
        # Dedup theo week_of
        if not existing.empty and "week_of" in existing.columns:
            existing = existing[existing["week_of"] != row["week_of"]]
        updated = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
        updated = updated.sort_values("week_of").reset_index(drop=True)
        # Tính cumulative NAV
        updated["cum_portfolio_nav"] = (
            INIT_NAV * updated["portfolio_ret"].fillna(0).add(1).cumprod()
        ).round(0)
        updated["cum_benchmark_nav"] = (
            INIT_NAV * updated["vn100_ret"].fillna(0).add(1).cumprod()
        ).round(0)
        updated.to_csv(NAV_PATH, index=False)

    def _save_report_md(self, nav, total_port, total_bench, total_alpha,
                         avg_ic, avg_alpha, win_rate, sharpe, n_weeks):
        """Save markdown report."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        ic_status = ("🟢 IC > 0.04 (good edge)" if avg_ic > 0.04
                     else "🟡 IC 0.02-0.04 (moderate)" if avg_ic > 0.02
                     else "🔴 IC < 0.02 (weak — review model)")

        md = f"""# Paper Trading Report
Generated: {ts} | {n_weeks} weeks

## Performance Summary

| Metric                | Value           |
|-----------------------|-----------------|
| Total Portfolio Ret   | {total_port:+.2%}        |
| Total VN100 Ret       | {total_bench:+.2%}        |
| Total Alpha           | {total_alpha:+.2%}        |
| Avg Weekly Alpha      | {avg_alpha:+.2%}        |
| Avg Realized IC       | {avg_ic:+.4f}       |
| Win Rate vs VN100     | {win_rate:.0%}           |
| Ann. Sharpe (weekly)  | {sharpe:.3f}          |

## Weekly Breakdown

{nav[['week_of','portfolio_ret','vn100_ret','alpha','realized_ic','hit_rate']].to_markdown(index=False, floatfmt='.4f')}

## IC Status
{ic_status}

## KPI Check
| KPI                         | Threshold | Actual    | Status |
|-----------------------------|-----------|-----------|--------|
| Realized IC per week        | > 0.025   | {avg_ic:+.4f}    | {"✅" if avg_ic > 0.025 else "❌"} |
| Avg Alpha vs VN100          | > 0%      | {avg_alpha:+.2%}    | {"✅" if avg_alpha > 0 else "❌"} |
| Win Rate vs benchmark       | > 55%     | {win_rate:.0%}       | {"✅" if win_rate > 0.55 else "❌"} |
"""
        REPORT_MD.write_text(md, encoding="utf-8")
        print(f"\n  📄 Report saved → {REPORT_MD}")


# ── CLI shortcut ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Paper Trading Tracker")
    parser.add_argument("--update",   action="store_true", help="Tính NAV tuần trước")
    parser.add_argument("--report",   action="store_true", help="In báo cáo")
    parser.add_argument("--decision", action="store_true", help="Kiểm tra 3 KPI")
    parser.add_argument("--prev-week", type=str, default=None, dest="prev_week")
    parser.add_argument("--curr-week", type=str, default=None, dest="curr_week")
    args = parser.parse_args()

    tracker = PaperTradingTracker()

    if args.update or not any([args.report, args.decision]):
        tracker.update_nav(prev_week=args.prev_week, curr_week=args.curr_week)

    if args.report:
        tracker.monthly_report()

    if args.decision:
        tracker.decision_check()
