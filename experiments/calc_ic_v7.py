"""
Calculate and compare IC/ICIR statistics between Model V4 (baseline) and Model V7 (with extra features).
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
    v7_path = "results/v7/pred.pkl"
    
    if not os.path.exists(v4_path):
        print(f"Error: {v4_path} not found. Run baseline comparison first.")
        return
    if not os.path.exists(v7_path):
        print(f"Error: {v7_path} not found. Train V7 first.")
        return
        
    with open(v4_path, "rb") as f:
        pred_v4 = pickle.load(f)
    with open(v7_path, "rb") as f:
        pred_v7 = pickle.load(f)
        
    # Get common index parameters
    instruments = pred_v7.index.get_level_values("instrument").unique().tolist()
    start_time = pred_v7.index.get_level_values("datetime").min()
    end_time = pred_v7.index.get_level_values("datetime").max()
    
    # 3. Load actual forward returns (label)
    label_expr = "Ref($close,-5)/$close-1"
    print(f"Fetching actual labels using: {label_expr}")
    labels = D.features(instruments, [label_expr], start_time=start_time, end_time=end_time)
    labels.columns = ["label"]
    
    # 4. Calculate Stats
    v4_stats = calc_ic_stats(pred_v4, labels)
    v7_stats = calc_ic_stats(pred_v7, labels)
    
    # 5. Output comparison
    print("\n" + "=" * 55)
    print("      IC / ICIR COMPARISON: MODEL V4 vs MODEL V7")
    print("=" * 55)
    print(f"{'Metric':<18} {'V4 (Baseline)':>15} {'V7 (Extra Feats)':>15} {'Delta':>10}")
    print("-" * 55)
    for k in ["IC_mean", "IC_std", "ICIR", "IC>0_pct"]:
        val4 = v4_stats[k]
        val7 = v7_stats[k]
        delta = val7 - val4
        sign = "+" if delta > 0 else ""
        print(f"{k:<18} {val4:>15.6f} {val7:>15.6f} {sign+str(round(delta,6)):>10}")
    print("-" * 55)
    print(f"Trading days: V4={v4_stats['N_days']}, V7={v7_stats['N_days']}")
    print("=" * 55)
    
    # Check if target met (>0.005 increase in IC mean)
    ic_delta = v7_stats["IC_mean"] - v4_stats["IC_mean"]
    if ic_delta >= 0.005:
        print(f"🎉 SUCCESS: IC Mean increased by {ic_delta:.6f} (>= 0.005). Proceed to Sector Momentum.")
    else:
        print(f"⚠️  WARNING: IC Mean delta is {ic_delta:.6f} (< 0.005). Extra features alone are insufficient.")

if __name__ == "__main__":
    main()
