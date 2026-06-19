"""
live_ranking.py — Weekly paper trading ranker (Phase 10 Track A)

Workflow:
  1. Load V9 model (trained on full VN100, Walk-Forward W5 window)
  2. Fetch giá VN100 từ Qlib / vnstock (trailing 60 ngày để tính features)
  3. Tính features giống walk_forward.py (CSRankNorm + SectorMomentum)
  4. Predict score, output top-8
  5. Log vào paper_trading/weekly_log.csv
  6. Track realized IC và NAV paper portfolio vs VN100 benchmark

Usage:
  python experiments/live_ranking.py              # Rank tuần này
  python experiments/live_ranking.py --track      # Tính realized IC của tuần trước
  python experiments/live_ranking.py --report     # In báo cáo tổng hợp
"""
import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
import shutil
shutil.copy2 = shutil.copyfile
shutil.copy  = shutil.copyfile

import argparse
import pickle
import yaml
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

import qlib
from qlib.data import D
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord
from vnstock_qlib.features.alpha101 import VN_PRICE_FEATURES
from vnstock_qlib.processors.sector_momentum_proc import SECTOR_MAP
from vnstock_qlib.features.foreign_room import fetch_foreign_room, apply_room_filter

# ─── Cấu hình ──────────────────────────────────────────────────────────────
QLIB_DIR     = os.path.expanduser("~/.qlib/qlib_data/vn_data")
CONFIG_DIR   = os.path.join(os.path.dirname(__file__), "configs")
PAPER_DIR    = os.path.join(os.path.dirname(__file__), "..", "paper_trading")
RESULTS_DIR  = os.path.join(os.path.dirname(__file__), "..", "results")
MODEL_PICKLE = os.path.join(RESULTS_DIR, "v9_vn100", "live_model.pkl")

TOPK                = 8
COMMISSION          = 0.0015
INIT_NAV            = 1_000_000_000   # 1 tỷ VND giả định
LIQUIDITY_MIN_VOL   = 500_000         # cổ/ngày tối thiểu
LIQUIDITY_DAYS      = 20              # lookback để tính avg volume

# TopK scaling theo rolling IC thực tế của model
# IC avg = 0.0604, W4 = 0.0941 → baseline full = 8
IC_TOPK_TABLE = [(0.06, 8), (0.04, 6), (0.02, 4), (0.00, 2)]

LOG_FILE    = os.path.join(PAPER_DIR, "weekly_log.csv")
NAV_FILE    = os.path.join(PAPER_DIR, "nav_tracking.csv")
REPORT_FILE = os.path.join(PAPER_DIR, "performance_report.md")


# ─── Helpers ────────────────────────────────────────────────────────────────

def ensure_dirs():
    Path(PAPER_DIR).mkdir(parents=True, exist_ok=True)
    Path(RESULTS_DIR + "/v9_vn100").mkdir(parents=True, exist_ok=True)


def last_monday(ref: datetime = None) -> str:
    """Trả về ngày thứ Hai gần nhất (hoặc hôm nay nếu là thứ Hai)."""
    ref = ref or datetime.today()
    days_back = ref.weekday()          # 0=Mon … 6=Sun
    monday = ref - timedelta(days=days_back)
    return monday.strftime("%Y-%m-%d")


def ic_to_topk(ic: float) -> int:
    for threshold, k in IC_TOPK_TABLE:
        if ic > threshold:
            return k
    return 1


def get_universe() -> list[str]:
    """Lấy danh sách VN100 từ Qlib instrument list."""
    df = D.list_instruments(D.instruments("vn100"), as_list=True)
    return sorted(df)


def load_or_train_model() -> object:
    """
    Load live model pkl theo thứ tự ưu tiên:
    1. live_model.pkl (đã save từ lần trước)
    2. Walk-forward W5 model từ Qlib MLflow recorder
    3. Retrain từ đầu (chậm, chỉ khi không có model nào)
    """
    if os.path.exists(MODEL_PICKLE):
        print(f"  Loaded model from {MODEL_PICKLE}")
        with open(MODEL_PICKLE, "rb") as f:
            return pickle.load(f)

    # Fallback: extract model từ walk-forward W5 experiment
    wf_model = _try_load_wf_model()
    if wf_model is not None:
        with open(MODEL_PICKLE, "wb") as f:
            pickle.dump(wf_model, f)
        print(f"  Model saved (from WF) → {MODEL_PICKLE}")
        return wf_model

    print("  Model pkl not found → training fresh on full VN100 data ...")
    return _train_fresh_model()


def _try_load_wf_model() -> object:
    """Thử load model từ walk-forward W5 Qlib experiment."""
    try:
        from qlib.workflow import R
        exp = R.get_exp(experiment_name="wf_W5_2024H2")
        recorders = list(exp.list_recorders().values())
        if not recorders:
            return None
        rec = sorted(recorders, key=lambda r: r.info.get('start_time', ''))[-1]
        model = rec.load_object("trained_model")
        print("  Loaded model from WF W5 experiment recorder.")
        return model
    except Exception as e:
        print(f"  Could not load WF model: {e}")
        return None


def _train_fresh_model() -> object:
    """Train model mới trên full VN100 data đến cuối tháng trước."""
    today = datetime.today()
    # Train trên data đến cuối tháng trước để tránh look-ahead
    train_end = (today.replace(day=1) - timedelta(days=1)).strftime("%Y-%m-%d")
    # Valid: 2 tháng trước đó
    valid_end_dt = today.replace(day=1) - timedelta(days=1)
    valid_start_dt = (valid_end_dt.replace(day=1) - timedelta(days=1)).replace(day=1)
    valid_start = valid_start_dt.strftime("%Y-%m-%d")
    real_train_end = (valid_start_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    predict_start = train_end   # predict từ tháng này
    predict_end   = today.strftime("%Y-%m-%d")

    with open(os.path.join(CONFIG_DIR, "dataset_vn100_v9.yaml")) as f:
        dataset_config = yaml.safe_load(f)

    tuned = os.path.join(CONFIG_DIR, "lgbm_vn30_tuned.yaml")
    mpath = tuned if os.path.exists(tuned) else os.path.join(CONFIG_DIR, "lgbm_vn30.yaml")
    with open(mpath) as f:
        model_config = yaml.safe_load(f)

    features = [f[0] for f in VN_PRICE_FEATURES]
    names    = [f[1] for f in VN_PRICE_FEATURES]
    features.extend(["$sector_ret_5d", "$sector_rel_ret"])
    names.extend(["sector_ret_5d", "sector_rel_ret"])

    label_expr = dataset_config["kwargs"]["handler"]["kwargs"].pop("label")
    dataset_config["kwargs"]["handler"]["kwargs"]["data_loader"] = {
        "class": "QlibDataLoader",
        "kwargs": {"config": {
            "feature": (features, names),
            "label":   (label_expr, ["LABEL0"]),
        }},
    }
    dataset_config["kwargs"]["handler"]["kwargs"]["start_time"] = "2018-01-01"
    dataset_config["kwargs"]["handler"]["kwargs"]["end_time"]   = predict_end
    dataset_config["kwargs"]["segments"] = {
        "train": ["2018-01-01", real_train_end],
        "valid": [valid_start,  train_end],
        "test":  [predict_start, predict_end],
    }
    print(f"  Training: 2018-01-01 → {real_train_end}")
    print(f"  Valid:    {valid_start} → {train_end}")
    print(f"  Test:     {predict_start} → {predict_end}")

    dataset = init_instance_by_config(dataset_config, default_module="qlib.data.dataset")
    model   = init_instance_by_config(model_config,   default_module="qlib.contrib.model")

    with R.start(experiment_name="live_ranking_retrain"):
        model.fit(dataset)
        R.save_objects(trained_model=model)

    with open(MODEL_PICKLE, "wb") as f:
        pickle.dump(model, f)
    print(f"  Model saved → {MODEL_PICKLE}")
    return model


def fetch_features(symbols: list[str], lookback_days: int = 90) -> pd.DataFrame:
    """
    Fetch raw features từ Qlib cho trailing `lookback_days` ngày.
    Xử lý đủ pipeline: RobustZScore → SectorMomentum → CSRankNorm → Fillna
    Trả về DataFrame (instrument, feature_name) chỉ cho ngày cuối cùng.
    """
    end   = datetime.today().strftime("%Y-%m-%d")
    start = (datetime.today() - timedelta(days=lookback_days + 30)).strftime("%Y-%m-%d")

    feature_exprs = [f[0] for f in VN_PRICE_FEATURES]
    feature_names = [f[1] for f in VN_PRICE_FEATURES]

    raw = D.features(symbols, feature_exprs, start_time=start, end_time=end)
    if raw.empty:
        raise RuntimeError("Không fetch được features từ Qlib. Kiểm tra dữ liệu.")

    raw.columns = feature_names
    raw = raw.reset_index()
    raw["datetime"] = pd.to_datetime(raw["datetime"])

    # Lấy ngày giao dịch cuối cùng
    last_date = raw["datetime"].max()
    print(f"  Last available date in Qlib: {last_date.date()}")

    # ── Sector Momentum (add sector_ret_5d, sector_rel_ret) ──────────────
    # Tính ret_5d trước
    if "ret_5d" in raw.columns:
        raw["sector"] = raw["instrument"].map(SECTOR_MAP).fillna("Other")
        sector_mean  = raw.groupby(["datetime", "sector"])["ret_5d"].transform("mean")
        raw["sector_ret_5d"] = sector_mean
        raw["sector_rel_ret"] = raw["ret_5d"] - sector_mean
    else:
        raw["sector_ret_5d"] = 0.0
        raw["sector_rel_ret"] = 0.0

    # ── Giữ chỉ ngày cuối ───────────────────────────────────────────────
    latest = raw[raw["datetime"] == last_date].copy()
    latest = latest.set_index("instrument")

    feature_cols = feature_names + ["sector_ret_5d", "sector_rel_ret"]
    X = latest[feature_cols].copy()

    # ── CSRankNorm cross-sectional ───────────────────────────────────────
    # Rank → [0,1] → z-score
    for col in X.columns:
        r = X[col].rank(pct=True, na_option="keep")
        X[col] = (r - 0.5) / 0.5        # map [0,1] → [-1, 1]

    X = X.fillna(0.0)
    return X, last_date


def compute_rolling_ic(n_weeks: int = 4) -> float:
    """
    Tính rolling IC từ weekly_log.csv: corr(score, realized_1w_return).
    Dùng n_weeks gần nhất.
    Nếu chưa đủ data → trả về IC backtest avg (0.06) thay vì 0.03 conservative.
    """
    if not os.path.exists(LOG_FILE):
        return 0.06   # backtest IC avg → TopK=8 full

    log = pd.read_csv(LOG_FILE, parse_dates=["week_of", "realized_date"])
    log = log.dropna(subset=["realized_ret"])
    if len(log) < 5:
        return 0.06   # chưa đủ live data → dùng backtest prior

    recent = log.sort_values("week_of").tail(n_weeks * TOPK)
    ic = recent["score"].corr(recent["realized_ret"], method="spearman")
    return ic if not np.isnan(ic) else 0.06


def apply_liquidity_filter(ranking: pd.DataFrame,
                            price_df_vol: pd.Series = None) -> pd.DataFrame:
    """
    Loại mã có avg volume Qlib (20 ngày) < LIQUIDITY_MIN_VOL cổ/ngày.
    Dùng dữ liệu volume đã fetch từ Qlib — không cần call API ngoài.

    Args:
        ranking   : DataFrame có cột 'symbol'
        price_df_vol: Series (index=instrument, value=avg_volume_20d) từ Qlib
    """
    if price_df_vol is None or price_df_vol.empty:
        return ranking   # không có data → không filter

    liquid_mask = []
    removed     = []
    for sym in ranking["symbol"]:
        avg_vol = price_df_vol.get(sym, 0)
        ok = avg_vol >= LIQUIDITY_MIN_VOL
        liquid_mask.append(ok)
        if not ok:
            removed.append(f"{sym}({avg_vol/1e3:.0f}K)")

    filtered = ranking[liquid_mask].reset_index(drop=True)
    filtered["rank"] = range(1, len(filtered) + 1)

    if removed:
        print(f"  ⚠ Loại {len(removed)} mã low-liquidity: {', '.join(removed)}")
    else:
        print(f"  ✓ Tất cả {len(ranking)} mã pass liquidity filter")

    return filtered


def compute_position_weights(ranking: pd.DataFrame,
                              max_weight: float = 0.25) -> pd.DataFrame:
    """
    Dùng softmax thay vì linear normalize.
    Softmax giữ được rank ordering nhưng không extreme.
    max_weight: cap tối đa per mã, mặc định 25%
    """
    import numpy as np
    
    scores = ranking["score"].values
    
    # Sử dụng Linear Weighting thay cho Softmax để tránh việc 1 mã có score đột biến chiếm 100% weight.
    # Scale scores về khoảng dương để tính tỷ trọng tuyến tính
    min_s = scores.min()
    max_s = scores.max()
    if abs(max_s - min_s) < 1e-6:
        # Nếu các score bằng nhau → phân bổ đều
        weights = np.full(len(scores), 1.0 / len(scores))
    else:
        # Shift dịch chuyển tuyến tính (score cao nhất có giá trị dương, thấp nhất không bằng 0 hoàn toàn để tránh weight = 0%)
        shifted_scores = (scores - min_s) + (max_s - min_s) * 0.2
        weights = shifted_scores / shifted_scores.sum()
    
    # Cap max weight 25% mỗi mã để tránh concentration
    for _ in range(5):  # Lặp tối đa 5 lần để hội tụ sau khi cap và renormalize
        weights = np.minimum(weights, max_weight)
        weights = weights / weights.sum()
    
    ranking = ranking.copy()
    ranking["weight_pct"] = (weights * 100).round(1)
    
    return ranking


def format_output(ranking: pd.DataFrame, 
                  total_capital: float = None,
                  avg_vol_series: pd.Series = None) -> pd.DataFrame:
    """
    Output cuối với weight và allocation cụ thể.
    """
    ranking = compute_position_weights(ranking)
    
    if total_capital:
        ranking["alloc_vnd"] = (
            ranking["weight_pct"] / 100 * total_capital
        ).round(-6)  # làm tròn triệu
    
    print(f"\n📊 VN100 Portfolio — {ranking['week_of'].iloc[0]}")
    if total_capital:
        print(f"{'Rank':<5} {'Symbol':<8} {'Sector':<15} {'Score':<8} {'Weight':>7} {'Allocation':>15} {'Volume':>10}")
        print("-" * 85)
        for _, row in ranking.iterrows():
            avg_vol = avg_vol_series.get(row["symbol"], 0) / 1e6 if avg_vol_series is not None else 0.0
            print(f"{int(row['rank']):<5} {row['symbol']:<8} "
                  f"{row['sector']:<15} {row['score']:.4f}   "
                  f"{row['weight_pct']:>5.1f}%  "
                  f"{row['alloc_vnd']:>13,.0f}đ  "
                  f"{avg_vol:.2f}M")
    else:
        print(f"{'Rank':<5} {'Symbol':<8} {'Sector':<15} {'Score':<8} {'Weight':>7} {'Volume':>10}")
        print("-" * 58)
        for _, row in ranking.iterrows():
            avg_vol = avg_vol_series.get(row["symbol"], 0) / 1e6 if avg_vol_series is not None else 0.0
            print(f"{int(row['rank']):<5} {row['symbol']:<8} "
                  f"{row['sector']:<15} {row['score']:.4f}   "
                  f"{row['weight_pct']:>5.1f}%  "
                  f"{avg_vol:.2f}M")
    
    return ranking


# ─── Track A: Weekly Ranking ─────────────────────────────────────────────────

def run_weekly_ranking(week_of: str = None):
    """
    Core function: predict top-8 VN100 cho tuần `week_of`.
    """
    ensure_dirs()
    qlib.init(provider_uri=QLIB_DIR)

    week_of = week_of or last_monday()
    print(f"\n{'='*55}")
    print(f"  VN100 Weekly Ranking — Tuần bắt đầu {week_of}")
    print(f"{'='*55}")

    # 1. Rolling IC → dynamic topk
    rolling_ic = compute_rolling_ic(n_weeks=4)
    current_topk = ic_to_topk(rolling_ic)
    print(f"  Rolling IC (4w): {rolling_ic:.4f}  →  TopK = {current_topk}")

    # 2. Load model
    model = load_or_train_model()

    # 3. Fetch features + volume cho liquidity filter
    symbols = get_universe()
    print(f"  Universe: {len(symbols)} symbols")
    X, last_date = fetch_features(symbols)

    # Fetch avg volume 20 ngày từ Qlib để dùng cho liquidity filter
    avg_vol_series = pd.Series(dtype=float)
    try:
        vol_start = (datetime.today() - timedelta(days=LIQUIDITY_DAYS + 5)).strftime("%Y-%m-%d")
        vol_end   = datetime.today().strftime("%Y-%m-%d")
        vol_raw = D.features(symbols, ["$volume"], start_time=vol_start, end_time=vol_end)
        vol_raw.columns = ["volume"]
        vol_raw = vol_raw.reset_index()
        vol_raw["datetime"] = pd.to_datetime(vol_raw["datetime"])
        cutoff = vol_raw["datetime"].max() - pd.Timedelta(days=LIQUIDITY_DAYS)
        vol_recent = vol_raw[vol_raw["datetime"] >= cutoff]
        avg_vol_series = vol_recent.groupby("instrument")["volume"].mean()
        print(f"  Volume data: {len(avg_vol_series)} symbols, {LIQUIDITY_DAYS}d lookback")
    except Exception as e:
        print(f"  ⚠ Không lấy được volume: {e} → bỏ qua liquidity filter")

    # 4. Predict — dùng LightGBM booster trực tiếp (model.model = lgb.Booster)
    try:
        scores_raw = model.model.predict(X.values)
    except AttributeError:
        try:
            scores_raw = model.predict(X.values)
        except Exception:
            scores_raw = model.predict(X)

    scores = pd.Series(scores_raw, index=X.index, name="score")
    scores = scores.dropna().sort_values(ascending=False)

    # 5a. Lấy top buffer (2x để có đủ sau filter)
    buffer_k   = min(current_topk * 2, len(scores))
    candidates = scores.head(buffer_k).reset_index()
    candidates.columns = ["symbol", "score"]
    candidates["sector"] = candidates["symbol"].map(SECTOR_MAP).fillna("Other")

    # 5b. Liquidity filter
    print(f"\n  Checking liquidity (min {LIQUIDITY_MIN_VOL/1e3:.0f}K vol/day) ...")
    candidates = apply_liquidity_filter(candidates, avg_vol_series)

    # 5c. Foreign room filter
    print(f"  Checking foreign room (min {5}% room remaining) ...")
    try:
        room_df = fetch_foreign_room(symbols, use_cache=True, cache_ttl_hours=8)
        candidates = apply_room_filter(candidates, room_df=room_df, threshold=5.0)
    except Exception as e:
        print(f"  ⚠ Room filter skipped: {e}")

    # 5c. Final top-K
    top_k = candidates.head(current_topk).copy()
    top_k["rank"]          = range(1, len(top_k) + 1)
    top_k["week_of"]       = week_of
    top_k["data_date"]     = last_date.strftime("%Y-%m-%d")
    top_k["rolling_ic"]    = round(rolling_ic, 4)
    top_k["topk_used"]     = current_topk
    # 6. Format and Print
    top_k = format_output(top_k, total_capital=None, avg_vol_series=avg_vol_series)

    # 7. Log
    existing = pd.read_csv(LOG_FILE) if os.path.exists(LOG_FILE) else pd.DataFrame()
    if not existing.empty and "week_of" in existing.columns:
        existing = existing[existing["week_of"] != week_of]
    updated = pd.concat([existing, top_k], ignore_index=True)
    updated.to_csv(LOG_FILE, index=False)
    print(f"\n  ✅ Logged → {LOG_FILE}")

    # 8. Concentration warning
    sector_counts = top_k["sector"].value_counts()
    concentrated  = sector_counts[sector_counts >= 4]
    if not concentrated.empty:
        print(f"  ⚠️  Concentration risk: {concentrated.to_dict()}")

    return top_k



# ─── Track A: Realized IC Tracking ──────────────────────────────────────────

def track_realized_performance(fill_week: str = None):
    """
    Điền realized_ret cho tuần `fill_week` (default: tuần trước).
    Tính toán realized IC, hit rate, alpha vs VN100.
    """
    ensure_dirs()
    qlib.init(provider_uri=QLIB_DIR)

    if not os.path.exists(LOG_FILE):
        print("Chưa có weekly_log.csv. Chạy --rank trước.")
        return

    log = pd.read_csv(LOG_FILE, parse_dates=["week_of"])

    # Xác định tuần cần fill
    if fill_week is None:
        today = datetime.today()
        fill_week = (today - timedelta(weeks=1))
        fill_week = (fill_week - timedelta(days=fill_week.weekday())).strftime("%Y-%m-%d")

    mask = (log["week_of"].astype(str) == fill_week) & log["realized_ret"].isna()
    if mask.sum() == 0:
        print(f"Không có entry nào cần fill cho tuần {fill_week}.")
        return

    symbols = log.loc[mask, "symbol"].tolist()
    entry_date = fill_week
    exit_date  = (pd.Timestamp(fill_week) + timedelta(days=7)).strftime("%Y-%m-%d")

    print(f"\n  Fetching prices: {entry_date} → {exit_date} ...")
    raw = D.features(
        symbols,
        ["$close"],
        start_time=entry_date,
        end_time=(pd.Timestamp(exit_date) + timedelta(days=5)).strftime("%Y-%m-%d")
    )
    if raw.empty:
        print("  Không lấy được giá. Thử lại sau.")
        return
    raw.columns = ["close"]
    raw = raw.reset_index()
    raw["datetime"] = pd.to_datetime(raw["datetime"])

    # Entry price (close ngày đầu tuần hoặc gần nhất)
    entry_prices = {}
    for sym in symbols:
        s = raw[(raw["instrument"] == sym) & (raw["datetime"] >= entry_date)].sort_values("datetime")
        if not s.empty:
            entry_prices[sym] = s.iloc[0]["close"]

    # Exit price (close ngày cuối tuần hoặc gần nhất trước exit_date)
    exit_prices = {}
    for sym in symbols:
        s = raw[(raw["instrument"] == sym) & (raw["datetime"] <= exit_date)].sort_values("datetime")
        if not s.empty:
            exit_prices[sym] = s.iloc[-1]["close"]
            realized_date    = s.iloc[-1]["datetime"]
            exit_prices[sym + "_date"] = realized_date

    # Fill log
    for idx in log[mask].index:
        sym = log.at[idx, "symbol"]
        p0  = entry_prices.get(sym, np.nan)
        p1  = exit_prices.get(sym, np.nan)
        if not np.isnan(p0) and not np.isnan(p1) and p0 > 0:
            log.at[idx, "realized_ret"]  = p1 / p0 - 1
            log.at[idx, "realized_date"] = exit_prices.get(sym + "_date", pd.NaT)

    log.to_csv(LOG_FILE, index=False)

    # ── Metrics cho tuần vừa fill ──────────────────────────────────────
    week_data = log[log["week_of"].astype(str) == fill_week].dropna(subset=["realized_ret"])
    if week_data.empty:
        print("  Không đủ data để tính metrics.")
        return

    realized_ic  = week_data["score"].corr(week_data["realized_ret"], method="spearman")
    hit_rate     = (week_data["realized_ret"] > 0).mean()
    avg_ret      = week_data["realized_ret"].mean()

    # VN100 benchmark: trung bình tất cả symbols trong universe
    all_syms = get_universe()
    bench_raw = D.features(all_syms, ["$close"], start_time=entry_date,
                           end_time=(pd.Timestamp(exit_date) + timedelta(days=5)).strftime("%Y-%m-%d"))
    bench_rets = []
    if not bench_raw.empty:
        bench_raw.columns = ["close"]
        bench_raw = bench_raw.reset_index()
        bench_raw["datetime"] = pd.to_datetime(bench_raw["datetime"])
        for sym in all_syms:
            s = bench_raw[bench_raw["instrument"] == sym].sort_values("datetime")
            s_entry = s[s["datetime"] >= entry_date]
            s_exit  = s[s["datetime"] <= exit_date]
            if not s_entry.empty and not s_exit.empty:
                bench_rets.append(s_exit.iloc[-1]["close"] / s_entry.iloc[0]["close"] - 1)
    vn100_ret = np.mean(bench_rets) if bench_rets else np.nan
    alpha     = avg_ret - vn100_ret if not np.isnan(vn100_ret) else np.nan

    print(f"\n  📈 Realized Performance — Tuần {fill_week}")
    print(f"  {'Realized IC':<22}: {realized_ic:+.4f}")
    print(f"  {'Hit Rate':<22}: {hit_rate:.1%}")
    print(f"  {'Portfolio Return':<22}: {avg_ret:+.2%}")
    print(f"  {'VN100 Return':<22}: {vn100_ret:+.2%}" if not np.isnan(vn100_ret) else "  VN100 Return          : N/A")
    print(f"  {'Alpha':<22}: {alpha:+.2%}" if not np.isnan(alpha) else "  Alpha                 : N/A")

    # ── Append NAV tracking ─────────────────────────────────────────────
    nav_entry = {
        "week_of":        fill_week,
        "realized_ic":    round(realized_ic, 4),
        "hit_rate":       round(hit_rate, 4),
        "portfolio_ret":  round(avg_ret, 4),
        "vn100_ret":      round(vn100_ret, 4) if not np.isnan(vn100_ret) else np.nan,
        "alpha":          round(alpha, 4) if not np.isnan(alpha) else np.nan,
    }
    nav_df = pd.read_csv(NAV_FILE) if os.path.exists(NAV_FILE) else pd.DataFrame()
    nav_df = pd.concat([nav_df, pd.DataFrame([nav_entry])], ignore_index=True)

    # Cumulative NAV
    nav_df = nav_df.sort_values("week_of").reset_index(drop=True)
    cum_port  = (1 + nav_df["portfolio_ret"].fillna(0)).cumprod()
    cum_bench = (1 + nav_df["vn100_ret"].fillna(0)).cumprod()
    nav_df["cum_portfolio_nav"]  = (INIT_NAV * cum_port).round(0)
    nav_df["cum_benchmark_nav"]  = (INIT_NAV * cum_bench).round(0)

    nav_df.to_csv(NAV_FILE, index=False)
    print(f"\n  ✅ NAV logged → {NAV_FILE}")

    return nav_entry


# ─── Track B: Báo cáo tổng hợp ──────────────────────────────────────────────

def generate_report():
    """In báo cáo performance tổng hợp ra markdown."""
    ensure_dirs()

    if not os.path.exists(NAV_FILE):
        print("Chưa có dữ liệu. Chạy --rank và --track trước.")
        return

    nav = pd.read_csv(NAV_FILE, parse_dates=["week_of"])
    nav = nav.sort_values("week_of")

    if nav.empty:
        print("Không có dữ liệu NAV.")
        return

    n_weeks       = len(nav)
    avg_ic        = nav["realized_ic"].mean()
    avg_hit       = nav["hit_rate"].mean()
    total_port    = nav["portfolio_ret"].add(1).prod() - 1
    total_bench   = nav["vn100_ret"].add(1).prod() - 1
    total_alpha   = total_port - total_bench
    cum_nav_last  = nav["cum_portfolio_nav"].iloc[-1]
    winning_weeks = (nav["portfolio_ret"] > 0).sum()

    sharpe_weekly = (nav["portfolio_ret"].mean() / nav["portfolio_ret"].std() * np.sqrt(52)
                     if nav["portfolio_ret"].std() > 0 else 0)

    report = f"""# Paper Trading Performance Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Summary ({n_weeks} weeks)

| Metric              | Value          |
|---------------------|----------------|
| Avg Realized IC     | {avg_ic:+.4f}       |
| Avg Hit Rate        | {avg_hit:.1%}        |
| Total Portfolio Ret | {total_port:+.2%}      |
| Total VN100 Ret     | {total_bench:+.2%}      |
| Total Alpha         | {total_alpha:+.2%}      |
| Winning Weeks       | {winning_weeks}/{n_weeks}         |
| Ann. Sharpe (weekly)| {sharpe_weekly:.3f}        |
| Current NAV         | {cum_nav_last:,.0f} VND |

## Weekly Breakdown

{nav[['week_of','realized_ic','hit_rate','portfolio_ret','vn100_ret','alpha']].to_markdown(index=False, floatfmt='.4f')}

## IC Trend
{"🟢 IC > 0.04 (good edge)" if avg_ic > 0.04 else "🟡 IC 0.02-0.04 (moderate)" if avg_ic > 0.02 else "🔴 IC < 0.02 (weak — review model)"}

## Decision Rule (4-week checkpoint)
- Realized IC > 0.03 consistently → model has live edge ✅
- Realized IC 0.01-0.03 → monitor 4 more weeks
- Realized IC < 0.01 → debug model, review W5 anomaly
"""

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"\n  ✅ Report saved → {REPORT_FILE}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VN100 Paper Trading Ranker")
    parser.add_argument("--rank",    action="store_true", help="Rank top-K tuần này")
    parser.add_argument("--track",   action="store_true", help="Fill realized return tuần trước")
    parser.add_argument("--report",  action="store_true", help="Báo cáo tổng hợp")
    parser.add_argument("--week",    type=str, default=None,
                        help="Override tuần (YYYY-MM-DD, ngày thứ Hai)")
    parser.add_argument("--fill-week", type=str, default=None, dest="fill_week",
                        help="Tuần cần fill realized return (YYYY-MM-DD)")
    args = parser.parse_args()

    # Default: nếu không có flag nào → chạy rank
    if not any([args.rank, args.track, args.report]):
        args.rank = True

    if args.rank:
        run_weekly_ranking(week_of=args.week)

    if args.track:
        track_realized_performance(fill_week=args.fill_week)

    if args.report:
        generate_report()


if __name__ == "__main__":
    main()
