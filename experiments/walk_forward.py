"""
Walk-Forward Validation — 3 windows using V4 dataset configuration (CSRankNorm + RobustZScoreNorm)
and Tuned LightGBM hyperparameters (if available).

W1: train 2018-2020, valid 2021, predict 2022-Q1
W2: train 2018-2021, valid 2022, predict 2023-Q1
W3: train 2018-2022, valid 2023, predict 2024-Q1
"""
import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
import shutil
shutil.copy2 = shutil.copyfile
shutil.copy = shutil.copyfile

import yaml
import pandas as pd
import numpy as np
import qlib
from qlib.data import D
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord
from vnstock_qlib.features.alpha101 import VN_PRICE_FEATURES

QLIB_DIR   = os.path.expanduser("~/.qlib/qlib_data/vn_data")
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "configs")
TOPK       = 8
COMMISSION = 0.0015
T_PLUS     = 2
LOT_SIZE   = 100
INIT_CAP   = 1_000_000_000

WINDOWS = [
    {"name": "W1_2021H2", "train_s": "2018-01-01", "train_e": "2021-06-30",
                          "valid_s": "2021-07-01", "valid_e": "2021-08-31",
                          "pred_s":  "2021-09-01", "pred_e":  "2021-12-31"},
    {"name": "W2_2022H1", "train_s": "2018-01-01", "train_e": "2021-12-31",
                          "valid_s": "2022-01-01", "valid_e": "2022-02-28",
                          "pred_s":  "2022-03-01", "pred_e":  "2022-06-30"},
    {"name": "W3_2023H1", "train_s": "2018-01-01", "train_e": "2022-12-31",
                          "valid_s": "2023-01-01", "valid_e": "2023-02-28",
                          "pred_s":  "2023-03-01", "pred_e":  "2023-06-30"},
    {"name": "W4_2024H1", "train_s": "2018-01-01", "train_e": "2023-12-31",
                          "valid_s": "2024-01-01", "valid_e": "2024-02-29",
                          "pred_s":  "2024-03-01", "pred_e":  "2024-06-30"},
    {"name": "W5_2024H2", "train_s": "2018-01-01", "train_e": "2024-06-30",
                          "valid_s": "2024-07-01", "valid_e": "2024-08-31",
                          "pred_s":  "2024-09-01", "pred_e":  "2024-12-31"},
]


def build_dataset_config(train_s, train_e, valid_s, valid_e, pred_s, pred_e):
    """Tạo DatasetH config cho từng window dựa trên dataset_vn100_v9.yaml."""
    with open(os.path.join(CONFIG_DIR, "dataset_vn100_v9.yaml"), "r") as f:
        dataset_config = yaml.safe_load(f)
        
    # Check for tuned model, if not available use baseline
    tuned_model_path = os.path.join(CONFIG_DIR, "lgbm_vn30_tuned.yaml")
    model_path = tuned_model_path if os.path.exists(tuned_model_path) else os.path.join(CONFIG_DIR, "lgbm_vn30.yaml")
    print(f"  Using model config: {os.path.basename(model_path)}")
    with open(model_path, "r") as f:
        model_config = yaml.safe_load(f)

    features = [f[0] for f in VN_PRICE_FEATURES]
    names    = [f[1] for f in VN_PRICE_FEATURES]

    # Explicitly append sector momentum features
    features.extend(["$sector_ret_5d", "$sector_rel_ret"])
    names.extend(["sector_ret_5d", "sector_rel_ret"])

    # Inject features dynamic
    dataset_config["kwargs"]["handler"]["kwargs"]["data_loader"] = {
        "class": "QlibDataLoader",
        "kwargs": {
            "config": {
                "feature": (features, names),
                "label": (dataset_config["kwargs"]["handler"]["kwargs"].pop("label"), ["LABEL0"])
            }
        }
    }
    
    # Update dates
    dataset_config["kwargs"]["handler"]["kwargs"]["start_time"] = train_s
    dataset_config["kwargs"]["handler"]["kwargs"]["end_time"] = pred_e
    dataset_config["kwargs"]["segments"] = {
        "train": [train_s, train_e],
        "valid": [valid_s, valid_e],
        "test":  [pred_s,  pred_e],
    }
    
    # Adjust RobustZScoreNorm fit times to avoid look-ahead bias
    # Inject SectorMomentumProcessor in infer_processors list
    has_sector_momentum = False
    for proc in dataset_config["kwargs"]["handler"]["kwargs"].get("infer_processors", []):
        if proc.get("class") == "RobustZScoreNorm":
            proc["kwargs"]["fit_start_time"] = train_s
            proc["kwargs"]["fit_end_time"] = train_e
        if proc.get("class") == "SectorMomentumProcessor":
            has_sector_momentum = True
            
    if not has_sector_momentum:
        processors = dataset_config["kwargs"]["handler"]["kwargs"].get("infer_processors", [])
        sector_proc = {
            "class": "SectorMomentumProcessor",
            "module_path": "vnstock_qlib.processors.sector_momentum_proc",
            "kwargs": {
                "feature_col": "ret_5d"
            }
        }
        # Insert after RobustZScoreNorm and before CSRankNorm
        processors.insert(1, sector_proc)

    return dataset_config, model_config





def load_price_map(symbols, start, end):
    raw = D.features(symbols, ["$close"], start_time=start, end_time=end)
    raw.columns = ["close"]
    raw = raw.reset_index()
    raw["datetime"] = pd.to_datetime(raw["datetime"])
    return {(row.datetime, row.instrument): row.close
            for row in raw.itertuples(index=False)}


def run_backtest(pred_df: pd.DataFrame, price_map: dict, test_dates: list):
    holdings     = {}
    cash         = float(INIT_CAP)
    pending_cash = []
    equity_curve = []
    trade_log    = []
    
    # Track daily Spearman IC for rolling confidence calculation (Track B)
    # Start with baseline TOPK = 5
    daily_ic_history = []
    
    # For Track C: ETF short tracking
    # VFMVN30 ETF proxy is represented by VN30 market average return
    # If market trend is Bear (5-day rolling index return is negative & VN-Index drop), we short ETF by 50% NAV
    etf_short_units = 0.0
    etf_entry_price = 0.0

    def get_price(ts, sym):
        return price_map.get((ts, sym), np.nan)

    def flush_pending(today):
        nonlocal cash
        remaining = []
        for sd, amt in pending_cash:
            if sd <= today:
                cash += amt
            else:
                remaining.append((sd, amt))
        pending_cash.clear()
        pending_cash.extend(remaining)
        return remaining

    for i, date in enumerate(test_dates):
        flush_pending(date)
        mask       = pred_df["datetime"] == date
        day_scores = pred_df.loc[mask].set_index("instrument")["score"]

        # Calculate daily IC for rolling IC calculation (Track B)
        # We look back at last 5 days realized return if possible
        if i >= 5:
            past_date = test_dates[i-5]
            past_day = pred_df[pred_df["datetime"] == past_date]
            ic_records = []
            for _, row in past_day.iterrows():
                sym = row["instrument"]
                t0_past = get_price(past_date, sym)
                t5_past = get_price(date, sym)
                if not np.isnan(t0_past) and not np.isnan(t5_past) and t0_past > 0:
                    ic_records.append({"score": row["score"], "ret": t5_past / t0_past - 1})
            if len(ic_records) >= 5:
                tmp = pd.DataFrame(ic_records)
                daily_ic_history.append(tmp["score"].corr(tmp["ret"], method="spearman"))
        
        # Calculate Rolling 30-day IC (Track B)
        # Use simple mean of last 30 daily ICs (or all available if < 30)
        rolling_ic_30d = np.mean(daily_ic_history[-30:]) if daily_ic_history else 0.03 # Default to baseline V4 mean
        
        # Dynamic exposure scaling: select TOPK based on model confidence (scaled up for VN100, max TOPK = 8)
        if rolling_ic_30d > 0.05:
            current_topk = 8
        elif rolling_ic_30d > 0.03:
            current_topk = 6
        elif rolling_ic_30d > 0.01:
            current_topk = 4
        elif rolling_ic_30d > 0.00:
            current_topk = 2
        else:
            current_topk = 1 # Cash proxy, trade only 1 highest-conviction stock

        if day_scores.empty:
            hv = sum(shares * p for sym, shares in holdings.items()
                     if not np.isnan(p := get_price(date, sym)))
            pending_total = sum(a for _, a in pending_cash)
            # Add ETF short value to equity (Track C)
            etf_val = 0.0
            if etf_short_units > 0:
                # Estimate current VFMVN30 price by proxying index price (market mean)
                mkt_mean_price = np.mean([p for sym in holdings.keys() if not np.isnan(p := get_price(date, sym))]) if holdings else 1.0
                # Short profit/loss: entry_price - current_price
                etf_val = etf_short_units * (etf_entry_price - mkt_mean_price)
            equity_curve.append((date, cash + hv + pending_total + etf_val))
            continue

        valid        = day_scores.dropna().sort_values(ascending=False)
        target_syms  = set(valid.index[:current_topk].tolist())
        current_syms = set(holdings.keys())

        # Bán các cổ phiếu không còn trong TOPK
        for sym in list(current_syms - target_syms):
            price = get_price(date, sym)
            if np.isnan(price) or price <= 0:
                continue
            shares   = holdings.pop(sym)
            proceeds = shares * price * (1 - COMMISSION)
            si = min(i + T_PLUS, len(test_dates) - 1)
            pending_cash.append((test_dates[si], proceeds))
            trade_log.append((date, "SELL", sym, shares, price, proceeds))

        # Mua các cổ phiếu mới vào TOPK
        buy_syms = list(target_syms - set(holdings.keys()))
        if buy_syms:
            per_sym = cash / len(buy_syms)
            for sym in buy_syms:
                price = get_price(date, sym)
                if np.isnan(price) or price <= 0:
                    continue
                cps    = price * (1 + COMMISSION)
                shares = int((per_sym / cps) // LOT_SIZE) * LOT_SIZE
                if shares <= 0:
                    continue
                cost = shares * cps
                if cost > cash:
                    shares = int((cash / cps) // LOT_SIZE) * LOT_SIZE
                    cost   = shares * cps
                if shares <= 0:
                    continue
                cash -= cost
                holdings[sym] = holdings.get(sym, 0) + shares
                trade_log.append((date, "BUY", sym, shares, price, cost))

        # Track C: ETF Hedge Simulation
        # Estimate market index return of current day (using 20-day trend to avoid whipsaw)
        day_prices = [get_price(date, sym) for sym in day_scores.index]
        day_prices_past_20d = [get_price(test_dates[max(0, i-20)], sym) for sym in day_scores.index]
        valid_pairs_20d = [(p0, p20) for p0, p20 in zip(day_prices_past_20d, day_prices) if not np.isnan(p0) and not np.isnan(p20) and p0 > 0]
        mkt_ret_20d = np.mean([p20 / p0 - 1 for p0, p20 in valid_pairs_20d]) if valid_pairs_20d else 0.0
        
        # Current simulated VFMVN30 ETF price proxy (market average price)
        curr_etf_price = np.mean([p for p in day_prices if not np.isnan(p)]) if day_prices else 1.0
        
        # Calculate current net asset value (before ETF position)
        hv = sum(shares * p for sym, shares in holdings.items()
                 if not np.isnan(p := get_price(date, sym)))
        pending_total = sum(a for _, a in pending_cash)
        raw_nav = cash + hv + pending_total
        
        # Regime is Bear if 20-day market return trend is negative enough to avoid daily noise
        is_bear = mkt_ret_20d < -0.05
        
        if is_bear:
            if etf_short_units == 0:
                # Open short ETF hedge position using 50% of NAV
                etf_entry_price = curr_etf_price
                etf_short_units = (raw_nav * 0.5) / curr_etf_price
                trade_log.append((date, "SHORT_ETF_OPEN", "VFMVN30", etf_short_units, curr_etf_price, raw_nav * 0.5))
        else:
            if etf_short_units > 0:
                # Close short position (cover short)
                gain_loss = etf_short_units * (etf_entry_price - curr_etf_price)
                cash += gain_loss
                trade_log.append((date, "SHORT_ETF_CLOSE", "VFMVN30", etf_short_units, curr_etf_price, gain_loss))
                etf_short_units = 0.0
                
        # Calculate final equity curve value including ETF hedge profit/loss
        etf_val = 0.0
        if etf_short_units > 0:
            etf_val = etf_short_units * (etf_entry_price - curr_etf_price)
            
        equity_curve.append((date, cash + hv + pending_total + etf_val))

    # Close any remaining ETF positions at final date
    if etf_short_units > 0:
        final_date = test_dates[-1]
        final_price = np.mean([get_price(final_date, sym) for sym in holdings.keys() if not np.isnan(get_price(final_date, sym))]) if holdings else etf_entry_price
        gain_loss = etf_short_units * (etf_entry_price - final_price)
        cash += gain_loss
        equity_curve[-1] = (final_date, cash + sum(shares * get_price(final_date, sym) for sym, shares in holdings.items() if not np.isnan(get_price(final_date, sym))) + sum(a for _, a in pending_cash))

    return equity_curve, trade_log



def compute_metrics(equity_curve):
    df = pd.DataFrame(equity_curve, columns=["date", "nav"]).set_index("date")
    df["ret"] = df["nav"].pct_change()
    total   = df["nav"].iloc[-1] / df["nav"].iloc[0] - 1
    n       = len(df)
    ann_ret = (1 + total) ** (252 / n) - 1
    ann_vol = df["ret"].std() * np.sqrt(252)
    sharpe  = (ann_ret - 0.045) / ann_vol if ann_vol > 0 else 0
    peak    = df["nav"].cummax()
    max_dd  = ((df["nav"] - peak) / peak).min()
    calmar  = ann_ret / abs(max_dd) if max_dd != 0 else 0
    wr      = (df["ret"].dropna() > 0).mean()
    return {
        "Total Return":  f"{total:+.2%}",
        "Ann. Return":   f"{ann_ret:+.2%}",
        "Volatility":    f"{ann_vol:.2%}",
        "Sharpe":        f"{sharpe:.3f}",
        "Max Drawdown":  f"{max_dd:.2%}",
        "Calmar":        f"{calmar:.3f}",
        "Win Rate":      f"{wr:.2%}",
        "Days":          str(n),
    }, df


def compute_ic(pred_df, price_map, pred_s, pred_e):
    """
    Tính IC (Information Coefficient) = Spearman corr(score, realized return) cho từng ngày.
    Đồng thời phân loại và in ra IC mean theo từng Market Regime:
    - Bull (VN30 index return > 0.5% & positive trend)
    - Bear (VN30 index return < -0.5% & negative trend)
    - Sideways (Low volatility, abs return <= 0.5%)
    - Recovery (Rising trend after sharp drop)
    """
    dates = sorted([pd.Timestamp(d) for d in
                    pred_df[(pred_df["datetime"] >= pred_s) &
                            (pred_df["datetime"] <= pred_e)]["datetime"].unique()])
    ic_list = []
    regime_ic = {"Bull": [], "Bear": [], "Sideways": [], "Recovery": []}
    
    # Precompute market returns to assign daily regime
    # We estimate daily market return by average of raw returns
    daily_returns = {}
    for date in dates:
        day = pred_df[pred_df["datetime"] == date]
        day_rets = []
        for _, row in day.iterrows():
            sym = row["instrument"]
            t0  = price_map.get((date, sym), np.nan)
            # Find next day price to compute daily return
            fidx = dates.index(date) + 1
            if fidx < len(dates):
                t1 = price_map.get((dates[fidx], sym), np.nan)
                if not np.isnan(t0) and not np.isnan(t1) and t0 > 0:
                    day_rets.append(t1 / t0 - 1)
        daily_returns[date] = np.mean(day_rets) if day_rets else 0.0

    for idx_date, date in enumerate(dates):
        day = pred_df[pred_df["datetime"] == date]
        records = []
        for _, row in day.iterrows():
            sym = row["instrument"]
            t0  = price_map.get((date, sym), np.nan)
            fidx = dates.index(date) + 5
            if fidx >= len(dates):
                continue
            fdate = dates[fidx]
            t5    = price_map.get((fdate, sym), np.nan)
            if np.isnan(t0) or np.isnan(t5) or t0 == 0:
                continue
            fwd_ret = t5 / t0 - 1
            records.append({"score": row["score"], "fwd_ret": fwd_ret})
            
        if len(records) >= 5:
            tmp = pd.DataFrame(records)
            ic  = tmp["score"].corr(tmp["fwd_ret"], method="spearman")
            if not np.isnan(ic):
                ic_list.append(ic)
                
                # Simple Regime Classifier:
                # Calculate rolling 5-day market return trend
                mkt_ret_5d = sum(daily_returns.get(dates[max(0, idx_date-k)], 0.0) for k in range(5))
                mkt_ret_1d = daily_returns.get(date, 0.0)
                
                if mkt_ret_1d > 0.005 and mkt_ret_5d > 0:
                    regime = "Bull"
                elif mkt_ret_1d < -0.005 and mkt_ret_5d < 0:
                    regime = "Bear"
                elif mkt_ret_1d > 0.005 and mkt_ret_5d <= 0:
                    regime = "Recovery"
                else:
                    regime = "Sideways"
                    
                regime_ic[regime].append(ic)
                
    # Print IC per Regime
    print("\n    IC per Market Regime:")
    for regime, ics in regime_ic.items():
        mean_reg = np.mean(ics) if ics else np.nan
        count_reg = len(ics)
        print(f"      - {regime:<10}: Mean IC = {mean_reg:+.4f} (Count: {count_reg})")
        
    if ic_list:
        ic_s = pd.Series(ic_list)
        return ic_s.mean(), ic_s.mean() / ic_s.std() if ic_s.std() > 0 else 0
    return np.nan, np.nan



def main():
    qlib.init(provider_uri=QLIB_DIR)

    all_results = []

    for w in WINDOWS:
        print(f"\n{'='*60}")
        print(f"  {w['name']}: Train {w['train_s']}→{w['train_e']} | "
              f"Valid {w['valid_s']}→{w['valid_e']} | "
              f"Predict {w['pred_s']}→{w['pred_e']}")
        print(f"{'='*60}")

        dataset_config, model_config = build_dataset_config(
            w["train_s"], w["train_e"],
            w["valid_s"], w["valid_e"],
            w["pred_s"],  w["pred_e"]
        )
        dataset = init_instance_by_config(dataset_config, default_module="qlib.data.dataset")
        model   = init_instance_by_config(model_config,   default_module="qlib.contrib.model")

        exp_name = f"wf_{w['name']}"
        with R.start(experiment_name=exp_name):
            print(f"  Training ...")
            model.fit(dataset)
            R.save_objects(trained_model=model)
            rec     = SignalRecord(model=model, dataset=dataset, recorder=R.get_recorder())
            rec.generate()
            pred_df = rec.recorder.load_object("pred.pkl")

        # Chuẩn hoá pred_df
        if isinstance(pred_df.index, pd.MultiIndex):
            pred_df = pred_df.reset_index()
            pred_df.columns = ["datetime", "instrument", "score"]
        pred_df["datetime"] = pd.to_datetime(pred_df["datetime"])

        # Filter predict period
        pred_test = pred_df[
            (pred_df["datetime"] >= w["pred_s"]) &
            (pred_df["datetime"] <= w["pred_e"])
        ].copy()

        if pred_test.empty:
            print(f"  [WARN] No predictions for {w['name']} predict period!")
            continue

        symbols    = pred_test["instrument"].unique().tolist()
        test_dates = sorted([pd.Timestamp(d) for d in pred_test["datetime"].unique()])

        price_map = load_price_map(symbols, w["pred_s"], w["pred_e"])
        print(f"  Running backtest on {len(test_dates)} days ...")
        equity_curve, trade_log = run_backtest(pred_test, price_map, test_dates)
        metrics, nav_df = compute_metrics(equity_curve)

        # IC / ICIR (Spearman)
        ic_mean, ic_ir = compute_ic(pred_test, price_map, w["pred_s"], w["pred_e"])

        print(f"\n  Backtest Result:")
        for k, v in metrics.items():
            print(f"    {k:<14}: {v}")
        print(f"    IC Mean      : {ic_mean:.4f}" if not np.isnan(ic_mean) else "    IC Mean      : N/A")
        print(f"    IC IR        : {ic_ir:.4f}"   if not np.isnan(ic_ir)   else "    IC IR        : N/A")

        all_results.append({
            "Window":    w["name"],
            "Period":    f"{w['pred_s']}→{w['pred_e']}",
            **metrics,
            "IC Mean":   f"{ic_mean:.4f}" if not np.isnan(ic_mean) else "N/A",
            "IC IR":     f"{ic_ir:.4f}"   if not np.isnan(ic_ir)   else "N/A",
        })

        # Save per-window NAV
        out_dir = os.path.join(os.path.dirname(__file__), "..", "results")
        os.makedirs(out_dir, exist_ok=True)
        nav_df.to_csv(os.path.join(out_dir, f"wf_{w['name']}_nav.csv"))

    # Tổng hợp
    print(f"\n{'='*60}")
    print("  WALK-FORWARD SUMMARY")
    print(f"{'='*60}")
    summary = pd.DataFrame(all_results).set_index("Window")
    cols = ["Period", "Total Return", "Ann. Return", "Sharpe", "Max Drawdown",
            "Calmar", "Win Rate", "IC Mean", "IC IR"]
    print(summary[cols].to_string())
    print(f"{'='*60}")

    # Save summary
    summary.to_csv(os.path.join(out_dir, "walk_forward_summary.csv"))
    print(f"\nResults → {os.path.abspath(out_dir)}")


if __name__ == "__main__":
    main()
