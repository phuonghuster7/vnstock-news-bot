"""
Calculate Information Coefficient (IC) and IC Information Ratio (ICIR) for predictions.
"""
import os
import pandas as pd
import numpy as np
import qlib
from qlib.data import D

def main():
    # 1. Initialize Qlib
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/vn_data")
    qlib.init(provider_uri=provider_uri)
    
    # 2. Load V4 predictions
    pred_path = "results/v4/pred.pkl"
    if not os.path.exists(pred_path):
        print(f"Error: {pred_path} does not exist.")
        return
        
    pred = pd.read_pickle(pred_path)
    # Ensure standard index and column
    if "score" not in pred.columns:
        print("Error: 'score' column not found in predictions.")
        return
        
    # Get instruments and dates from predictions
    pred = pred.sort_index()
    instruments = list(pred.index.get_level_values("instrument").unique())
    start_date = pred.index.get_level_values("datetime").min().strftime("%Y-%m-%d")
    end_date = pred.index.get_level_values("datetime").max().strftime("%Y-%m-%d")
    
    print(f"Loaded predictions for {len(instruments)} instruments from {start_date} to {end_date}")
    
    # 3. Load actual forward returns (label)
    # The label used during training was Ref($close, -5)/$close - 1
    label_expr = "Ref($close, -5)/$close - 1"
    print(f"Loading actual labels using expression: {label_expr}")
    
    actual = D.features(instruments, [label_expr], start_time=start_date, end_time=end_date)
    actual.columns = ["label"]
    
    # 4. Merge predictions and labels
    merged = pred.join(actual, how="inner")
    print(f"Merged dataset has {len(merged)} rows.")
    
    # 5. Compute Daily IC
    def compute_daily_ic(df):
        # Calculate Spearman correlation
        if len(df) < 2:
            return np.nan
        return df["score"].corr(df["label"], method="spearman")
        
    daily_ic = merged.groupby("datetime").apply(compute_daily_ic)
    daily_ic = daily_ic.dropna()
    
    # 6. Calculate statistics
    ic_mean = daily_ic.mean()
    ic_std = daily_ic.std()
    ic_ir = ic_mean / ic_std if ic_std > 0 else 0
    ic_pos_rate = (daily_ic > 0).mean() * 100
    
    print("\n" + "=" * 50)
    print("           IC / ICIR ANALYSIS (V4 Baseline)")
    print("=" * 50)
    print(f"Number of trading days: {len(daily_ic)}")
    print(f"Mean IC:                 {ic_mean:.6f}")
    print(f"IC Std:                  {ic_std:.6f}")
    print(f"ICIR (Information Ratio): {ic_ir:.6f}")
    print(f"IC > 0 Rate:             {ic_pos_rate:.2f}%")
    print("=" * 50)
    
    # Save daily IC to csv for reference
    out_dir = "results/v4"
    os.makedirs(out_dir, exist_ok=True)
    daily_ic.to_csv(os.path.join(out_dir, "daily_ic.csv"), header=["ic"])
    print(f"Saved daily IC to {out_dir}/daily_ic.csv")

if __name__ == "__main__":
    main()
