import pickle
import pandas as pd
import numpy as np
import qlib
from qlib.data import D
import os

def calc_ic_stats(pred_path: str, label_expr: str = "Ref($close,-5)/$close-1") -> dict:
    with open(pred_path, "rb") as f:
        pred = pickle.load(f)
    
    # pred index: (datetime, instrument), columns: ['score']
    # Get unique instruments and date range
    instruments = pred.index.get_level_values("instrument").unique().tolist()
    start_time = pred.index.get_level_values("datetime").min()
    end_time = pred.index.get_level_values("datetime").max()
    
    # Fetch labels
    labels = D.features(instruments, [label_expr], start_time=start_time, end_time=end_time)
    labels.columns = ["label"]
    
    # Merge
    merged = pred.join(labels, how="inner")
    
    daily_ic = (
        merged.groupby(level="datetime")
        .apply(lambda g: g["score"].corr(g["label"], method="spearman"))
        .dropna()
    )
    
    return {
        "IC_mean":  round(daily_ic.mean(), 4),
        "IC_std":   round(daily_ic.std(), 4),
        "ICIR":     round(daily_ic.mean() / daily_ic.std(), 4),
        "IC>0_pct": round((daily_ic > 0).mean(), 3),
        "IC_monthly": daily_ic.resample("M").mean().to_dict(),
    }


if __name__ == "__main__":
    qlib.init(provider_uri=os.path.expanduser("~/.qlib/qlib_data/vn_data"))
    
    v3 = calc_ic_stats("results/v3/pred.pkl")
    v4 = calc_ic_stats("results/v4/pred.pkl")

    print(f"{'Metric':<15} {'v3':>10} {'v4 (rank)':>10} {'Delta':>10}")
    print("-" * 48)
    for k in ["IC_mean", "IC_std", "ICIR", "IC>0_pct"]:
        delta = v4[k] - v3[k]
        sign = "+" if delta > 0 else ""
        print(f"{k:<15} {v3[k]:>10.4f} {v4[k]:>10.4f} {sign+str(round(delta,4)):>10}")
