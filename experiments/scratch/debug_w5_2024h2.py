"""
debug_w5_2024h2.py — Track B: Điều tra W5 (Sep-Dec 2024) failure

Câu hỏi cần trả lời:
  1. IC âm chỉ tháng nào? (event-driven hay structural?)
  2. Mã nào gây lỗ nhiều nhất (top losers)?
  3. Low-liquidity stocks có chiếm top predictions không?
  4. Sector nào underperform nhất H2 2024?
  5. Feature importance thay đổi ra sao trong W5 vs W4?

Usage:
  python experiments/scratch/debug_w5_2024h2.py
"""
import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
import shutil
shutil.copy2 = shutil.copyfile
shutil.copy  = shutil.copyfile

import pickle
import numpy as np
import pandas as pd
from pathlib import Path

import qlib
from qlib.data import D
from vnstock_qlib.processors.sector_momentum_proc import SECTOR_MAP

# VN30 list để phân biệt blue-chip vs mid-cap
VN30_LIST = [
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB",
    "HPG", "MBB", "MSN", "MWG", "NVL", "PDR", "PLX", "PNJ", "POW",
    "SAB", "SHB", "SSB", "SSI", "STB", "TCB", "TPB", "VCB", "VHM",
    "VIB", "VIC", "VJC", "VNM", "VPB", "VRE", "VTO",
]

QLIB_DIR  = os.path.expanduser("~/.qlib/qlib_data/vn_data")
PRED_PKL  = "results/v9_vn100/pred.pkl"
RESULTS   = "results"

W5_START  = "2024-09-01"
W5_END    = "2024-12-31"
W4_START  = "2024-03-01"
W4_END    = "2024-06-30"

TOPK = 8


def load_pred() -> pd.DataFrame:
    """
    Load predictions. Ưu tiên static pred.pkl (full period bao gồm W5).
    Fallback: WF W5 experiment recorder.
    """
    # Primary: static pred.pkl từ train_v9.py (có full 2024 data)
    if os.path.exists(PRED_PKL):
        print(f"  Loading from static {PRED_PKL}")
        with open(PRED_PKL, "rb") as f:
            pred = pickle.load(f)
        if isinstance(pred.index, pd.MultiIndex):
            pred = pred.reset_index()
            pred.columns = ["datetime", "instrument", "score"]
        pred["datetime"] = pd.to_datetime(pred["datetime"])
        print(f"  Pred: {len(pred)} rows, {pred['datetime'].min().date()} → {pred['datetime'].max().date()}")
        return pred

    # Fallback: WF recorder
    try:
        from qlib.workflow import R
        exp = R.get_exp(experiment_name="wf_W5_2024H2")
        recorders = list(exp.list_recorders().values())
        if recorders:
            rec = sorted(recorders, key=lambda r: r.info.get('start_time', ''))[-1]
            pred = rec.load_object("pred.pkl")
            print("  Loaded W5 pred from WF experiment recorder.")
            if isinstance(pred.index, pd.MultiIndex):
                pred = pred.reset_index()
                pred.columns = ["datetime", "instrument", "score"]
            pred["datetime"] = pd.to_datetime(pred["datetime"])
            return pred
    except Exception as e:
        print(f"  Could not load from WF recorder: {e}")
    raise RuntimeError(f"Cannot load pred. Run train_v9.py first.")


def load_prices(symbols: list, start: str, end: str) -> pd.DataFrame:
    """Fetch close prices từ Qlib."""
    raw = D.features(symbols, ["$close", "$volume"],
                     start_time=start,
                     end_time=(pd.Timestamp(end) + pd.Timedelta(days=10)).strftime("%Y-%m-%d"))
    raw.columns = ["close", "volume"]
    raw = raw.reset_index()
    raw["datetime"] = pd.to_datetime(raw["datetime"])
    return raw


def compute_daily_ic(pred_df: pd.DataFrame, price_df: pd.DataFrame,
                     start: str, end: str, horizon: int = 5) -> pd.Series:
    """
    Tính Spearman IC mỗi ngày: corr(score, forward_5d_return).
    """
    dates = sorted(pred_df[
        (pred_df["datetime"] >= start) & (pred_df["datetime"] <= end)
    ]["datetime"].unique())

    price_map = {(row.datetime, row.instrument): row.close
                 for row in price_df.itertuples(index=False)}

    ic_list = []
    # Convert dates sang Timestamp để match price_map keys
    dates = [pd.Timestamp(d) for d in dates]
    for i, date in enumerate(dates):
        if i + horizon >= len(dates):
            break
        fdate = dates[i + horizon]
        day   = pred_df[pred_df["datetime"] == date]
        recs  = []
        for _, row in day.iterrows():
            sym = row["instrument"]
            p0  = price_map.get((date, sym), np.nan)
            p5  = price_map.get((fdate, sym), np.nan)
            if not np.isnan(p0) and not np.isnan(p5) and p0 > 0:
                recs.append({"score": row["score"], "fwd_ret": p5 / p0 - 1})
        if len(recs) >= 5:
            tmp = pd.DataFrame(recs)
            ic  = tmp["score"].corr(tmp["fwd_ret"], method="spearman")
            ic_list.append((date, ic))

    ic_series = pd.Series(
        {pd.Timestamp(d): ic for d, ic in ic_list},
        name="daily_ic",
        dtype=float
    )
    ic_series.index = pd.DatetimeIndex(ic_series.index)
    return ic_series


def compute_stock_pnl(pred_df: pd.DataFrame, price_df: pd.DataFrame,
                      start: str, end: str) -> pd.DataFrame:
    """
    Mô phỏng lại portfolio top-K mỗi ngày, tính P&L theo từng mã.
    error = score * realized_5d_ret (dương = đúng hướng)
    """
    dates = sorted(pred_df[
        (pred_df["datetime"] >= start) & (pred_df["datetime"] <= end)
    ]["datetime"].unique())

    price_map = {(row.datetime, row.instrument): row.close
                 for row in price_df.itertuples(index=False)}

    vol_map = {(row.datetime, row.instrument): row.volume
               for row in price_df.itertuples(index=False)}

    records = []
    # Convert dates sang Timestamp để match price_map keys
    dates = [pd.Timestamp(d) for d in dates]
    for i, date in enumerate(dates):
        if i + 5 >= len(dates):
            break
        fdate = dates[i + 5]
        day   = pred_df[pred_df["datetime"] == date].sort_values("score", ascending=False)
        top_k = day.head(TOPK)

        for _, row in top_k.iterrows():
            sym = row["instrument"]
            p0  = price_map.get((date, sym), np.nan)
            p5  = price_map.get((fdate, sym), np.nan)
            vol = vol_map.get((date, sym), np.nan)
            if np.isnan(p0) or np.isnan(p5) or p0 <= 0:
                continue
            fwd_ret = p5 / p0 - 1
            records.append({
                "date":     date,
                "symbol":   sym,
                "score":    row["score"],
                "rank":     list(day["instrument"]).index(sym) + 1,
                "fwd_ret":  fwd_ret,
                "error":    row["score"] * fwd_ret,   # + đúng hướng, - sai hướng
                "in_vn30":  sym in VN30_LIST,
                "sector":   SECTOR_MAP.get(sym, "Other"),
                "volume":   vol,
                "price":    p0,
            })

    return pd.DataFrame(records)


def liquidity_analysis(pnl: pd.DataFrame, price_df: pd.DataFrame,
                       start: str, end: str):
    """
    Tính avg daily volume (triệu VND) cho mỗi mã trong W5.
    Cờ báo mã có volume < 1M cổ/ngày.
    """
    syms = pnl["symbol"].unique()
    liq  = price_df[
        (price_df["datetime"] >= start) &
        (price_df["datetime"] <= end) &
        (price_df["instrument"].isin(syms))
    ].groupby("instrument").agg(
        avg_volume=("volume", "mean"),
        avg_price=("close", "mean")
    )
    liq["avg_value_bn"]  = liq["avg_volume"] * liq["avg_price"] / 1e9
    liq["low_liquidity"] = liq["avg_volume"] < 1_000_000
    return liq


def run_debug():
    print("="*60)
    print("  DEBUG W5 (Sep–Dec 2024) — VN100 Failure Analysis")
    print("="*60)

    qlib.init(provider_uri=QLIB_DIR)
    pred = load_pred()

    # Lấy symbols
    syms_w5 = pred[
        (pred["datetime"] >= W5_START) & (pred["datetime"] <= W5_END)
    ]["instrument"].unique().tolist()
    syms_w4 = pred[
        (pred["datetime"] >= W4_START) & (pred["datetime"] <= W4_END)
    ]["instrument"].unique().tolist()
    all_syms = list(set(syms_w5 + syms_w4))

    # Fetch prices
    print("\n  Fetching prices ...")
    price_df = load_prices(all_syms, W4_START, W5_END)

    # ── 1. Monthly IC Breakdown ─────────────────────────────────────────
    print("\n" + "─"*55)
    print("  [1] MONTHLY IC — W5 vs W4")
    print("─"*55)

    daily_ic_w5 = compute_daily_ic(pred, price_df, W5_START, W5_END)
    daily_ic_w4 = compute_daily_ic(pred, price_df, W4_START, W4_END)

    print("\n  W5 Monthly IC (2024 H2):")
    _freq = "ME" if pd.__version__ >= "2.2" else "M"
    monthly_w5 = daily_ic_w5.groupby(pd.Grouper(freq=_freq)).agg(
        ic_mean="mean", ic_std="std", count="count"
    )
    for month, row in monthly_w5.iterrows():
        print(f"    {month.strftime('%Y-%m')}: IC={row['ic_mean']:+.4f}  std={row['ic_std']:.4f}  n={int(row['count'])}")

    print("\n  W4 Monthly IC (2024 H1) [benchmark]:")
    monthly_w4 = daily_ic_w4.groupby(pd.Grouper(freq=_freq)).agg(
        ic_mean="mean", ic_std="std", count="count"
    )
    for month, row in monthly_w4.iterrows():
        print(f"    {month.strftime('%Y-%m')}: IC={row['ic_mean']:+.4f}  std={row['ic_std']:.4f}  n={int(row['count'])}")

    # ── Diagnosis ──────────────────────────────────────────────────────
    neg_months = monthly_w5[monthly_w5["ic_mean"] < 0]
    pos_months = monthly_w5[monthly_w5["ic_mean"] > 0]
    print(f"\n  Diagnosis:")
    print(f"    Tháng IC âm:  {len(neg_months)}/4 tháng → ", end="")
    if len(neg_months) <= 1:
        print("Event-driven anomaly (1-2 tháng) — không cần fix model")
    elif len(neg_months) >= 3:
        print("⚠️  Structural break — model fail toàn W5")
    else:
        print("Mixed — cần xem thêm sector breakdown")

    # ── 2. Stock-Level PnL ─────────────────────────────────────────────
    print("\n" + "─"*55)
    print("  [2] STOCK-LEVEL PnL — TOP LOSERS (W5)")
    print("─"*55)

    pnl_w5 = compute_stock_pnl(pred, price_df, W5_START, W5_END)
    if pnl_w5.empty:
        print("  Không đủ dữ liệu PnL.")
    else:
        # Tổng hợp theo mã
        by_sym = pnl_w5.groupby("symbol").agg(
            mean_error=("error", "mean"),
            mean_fwd_ret=("fwd_ret", "mean"),
            n_appearances=("date", "count"),
            in_vn30=("in_vn30", "first"),
            sector=("sector", "first"),
        ).sort_values("mean_error")

        print("\n  Top 10 mã gây nhiễu nhất (error âm = dự đoán sai hướng):")
        print(f"  {'Symbol':<8} {'Sector':<22} {'VN30':<6} {'Error':>8} {'FwdRet':>8} {'N':>5}")
        print(f"  {'-'*60}")
        for sym, row in by_sym.head(10).iterrows():
            vn30_flag = "✓" if row["in_vn30"] else "✗"
            print(f"  {sym:<8} {row['sector']:<22} {vn30_flag:<6} "
                  f"{row['mean_error']:>8.4f} {row['mean_fwd_ret']:>8.4f} {int(row['n_appearances']):>5}")

        print("\n  Top 5 mã contribute tốt nhất (error dương):")
        for sym, row in by_sym.tail(5)[::-1].iterrows():
            vn30_flag = "✓" if row["in_vn30"] else "✗"
            print(f"  {sym:<8} {row['sector']:<22} {vn30_flag:<6} "
                  f"{row['mean_error']:>8.4f} {row['mean_fwd_ret']:>8.4f}")

        # ── 3. Sector Breakdown ────────────────────────────────────────
        print("\n" + "─"*55)
        print("  [3] SECTOR BREAKDOWN — W5")
        print("─"*55)
        by_sector = pnl_w5.groupby("sector").agg(
            mean_fwd_ret=("fwd_ret", "mean"),
            mean_error=("error", "mean"),
            count=("date", "count")
        ).sort_values("mean_fwd_ret")

        print(f"\n  {'Sector':<25} {'AvgRet':>8} {'Error':>8} {'N':>5}")
        print(f"  {'-'*50}")
        for sector, row in by_sector.iterrows():
            flag = "🔴" if row["mean_fwd_ret"] < -0.01 else "🟡" if row["mean_fwd_ret"] < 0.005 else "🟢"
            print(f"  {flag} {sector:<23} {row['mean_fwd_ret']:>8.4f} {row['mean_error']:>8.4f} {int(row['count']):>5}")

        # ── 4. Liquidity Check ─────────────────────────────────────────
        print("\n" + "─"*55)
        print("  [4] LIQUIDITY CHECK — W5 Top Losers")
        print("─"*55)
        liq = liquidity_analysis(pnl_w5, price_df, W5_START, W5_END)
        liq = liq.join(by_sym[["mean_error", "in_vn30", "sector"]]).sort_values("mean_error")

        print(f"\n  {'Symbol':<8} {'VN30':<6} {'AvgVol(M)':>10} {'AvgVal(Bn)':>11} {'LowLiq':>7} {'Error':>8}")
        print(f"  {'-'*60}")
        for sym, row in liq.head(15).iterrows():
            vn30_flag  = "✓" if row.get("in_vn30", False) else "✗"
            liq_flag   = "⚠️" if row["low_liquidity"] else "  "
            avg_vol_m  = row["avg_volume"] / 1e6
            print(f"  {sym:<8} {vn30_flag:<6} {avg_vol_m:>10.2f} {row['avg_value_bn']:>11.2f} "
                  f"  {liq_flag} {row.get('mean_error', 0):>8.4f}")

        low_liq_losers = liq[liq["low_liquidity"] & (liq.get("mean_error", 0) < -0.01)]
        if not low_liq_losers.empty:
            print(f"\n  ⚠️  {len(low_liq_losers)} mã có low liquidity VÀ error âm cao:")
            print(f"  → Cân nhắc filter: volume > 1M cổ/ngày")

        # ── 5. VN30 vs Non-VN30 ───────────────────────────────────────
        print("\n" + "─"*55)
        print("  [5] VN30 vs NON-VN30 TRONG TOP PREDICTIONS")
        print("─"*55)
        vn30_pnl    = pnl_w5[pnl_w5["in_vn30"]]
        non_vn30_pnl = pnl_w5[~pnl_w5["in_vn30"]]
        print(f"\n  VN30    : N={len(vn30_pnl):>4}  AvgFwdRet={vn30_pnl['fwd_ret'].mean():+.4f}  "
              f"AvgError={vn30_pnl['error'].mean():+.4f}")
        print(f"  Non-VN30: N={len(non_vn30_pnl):>4}  AvgFwdRet={non_vn30_pnl['fwd_ret'].mean():+.4f}  "
              f"AvgError={non_vn30_pnl['error'].mean():+.4f}")

        vn30_in_top = pnl_w5.groupby("date").apply(
            lambda g: g.nsmallest(TOPK, "rank")["in_vn30"].mean()
        )
        print(f"  % VN30 trong Top-{TOPK} mỗi ngày: avg={vn30_in_top.mean():.1%}, "
              f"min={vn30_in_top.min():.1%}, max={vn30_in_top.max():.1%}")

    # ── 6. Kết luận & Khuyến nghị ──────────────────────────────────────
    print("\n" + "="*55)
    print("  [6] KẾT LUẬN VÀ KHUYẾN NGHỊ")
    print("="*55)
    print("""
  Xem kết quả trên và đối chiếu:

  A. Nếu IC âm tập trung 1-2 tháng:
     → Market event (VD: tháng 10/2024 VN-Index crash)
     → Không cần fix model — chỉ cần live trading chấp nhận
       drawdown ngắn hạn. Paper trading sẽ confirm.

  B. Nếu Non-VN30 chiếm nhiều top-K VÀ có error âm cao:
     → Thêm liquidity filter trong live_ranking.py:
       chỉ giữ mã avg_volume > 500K cổ/ngày
       (ước tính ~50 tỷ/ngày với P=100k)

  C. Nếu sector cụ thể chiếm phần lớn lỗ:
     → Thêm sector concentration cap: tối đa 3 mã/sector
       (đã có warning trong live_ranking.py)

  D. Nếu IC âm toàn bộ 4 tháng:
     → Structural break — cần re-examine features
     → Ưu tiên debug trước khi paper trade
    """)

    # Save summary
    out_path = "results/debug_w5_summary.txt"
    print(f"  Phân tích hoàn tất. Lưu output vào {out_path}")


if __name__ == "__main__":
    run_debug()
