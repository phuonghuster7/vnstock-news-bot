"""
Calculate and compare IC/ICIR statistics between Model V4 (baseline) and Model V8 (with sector momentum features).
"""
import os
import pickle
import pandas as pd
import numpy as np
import qlib
from qlib.data import D

def calc_ic_stats(pred: pd.DataFrame, label: pd.DataFrame) -> dict:
    if isinstance(pred, pd.Series):
        pred = pred.to_frame("score")
    elif "score" not in pred.columns:
        pred.columns = ["score"]
        
    merged = pred.join(label, how="inner")
    daily_ic = (
        merged.groupby(level="datetime")
        .apply(lambda g: g["score"].corr(g["label"], method="spearman"))
        .dropna()
    )
    return {
        "IC_mean":  daily_ic.mean(),
        "IC_std":   daily_ic.std(),
        "ICIR":     daily_ic.mean() / daily_ic.std() if daily_ic.std() > 0 else 0,
        "IC>0_pct": (daily_ic > 0).mean(),
        "N_days":   len(daily_ic)
    }

def main():
    # 1. Initialize Qlib
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/vn_data")
    qlib.init(provider_uri=provider_uri)
    
    # 2. Load predictions
    v4_path = "results/v4/pred.pkl"
    v8_path = "results/v8/pred.pkl"
    
    if not os.path.exists(v4_path):
        print(f"Error: {v4_path} not found. Run baseline comparison first.")
        return
    if not os.path.exists(v8_path):
        print(f"Error: {v8_path} not found. Train V8 first.")
        return
        
    with open(v4_path, "rb") as f:
        pred_v4 = pickle.load(f)
    with open(v8_path, "rb") as f:
        pred_v8 = pickle.load(f)
        
    # Get common index parameters
    instruments = pred_v8.index.get_level_values("instrument").unique().tolist()
    start_time = pred_v8.index.get_level_values("datetime").min()
    end_time = pred_v8.index.get_level_values("datetime").max()
    
    # 3. Load actual forward returns (label)
    label_expr = "Ref($close,-5)/$close-1"
    print(f"Fetching actual labels using: {label_expr}")
    labels = D.features(instruments, [label_expr], start_time=start_time, end_time=end_time)
    labels.columns = ["label"]
    
    # 4. Calculate Stats
    v4_stats = calc_ic_stats(pred_v4, labels)
    v8_stats = calc_ic_stats(pred_v8, labels)
    
    # 5. Output comparison
    print("\n" + "=" * 55)
    print("      IC / ICIR COMPARISON: MODEL V4 vs MODEL V8 (Sector Momentum)")
    print("=" * 55)
    print(f"{'Metric':<18} {'V4 (Baseline)':>15} {'V8 (Sector Mom)':>15} {'Delta':>10}")
    print("-" * 55)
    for k in ["IC_mean", "IC_std", "ICIR", "IC>0_pct"]:
        val4 = v4_stats[k]
        val8 = v8_stats[k]
        delta = val8 - val4
        sign = "+" if delta > 0 else ""
        print(f"{k:<18} {val4:>15.6f} {val8:>15.6f} {sign+str(round(delta,6)):>10}")
    print("-" * 55)
    print(f"Trading days: V4={v4_stats['N_days']}, V8={v8_stats['N_days']}")
    print("=" * 55)
    
    # Check if target met (>0.005 increase in IC mean)
    ic_delta = v8_stats["IC_mean"] - v4_stats["IC_mean"]
    if ic_delta >= 0.005:
        print(f"🎉 SUCCESS: IC Mean increased by {ic_delta:.6f} (>= 0.005).")
    else:
        print(f"⚠️  WARNING: IC Mean delta is {ic_delta:.6f} (< 0.005).")

if __name__ == "__main__":
    main()
