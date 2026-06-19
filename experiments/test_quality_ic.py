import qlib
from qlib.data import D
import pandas as pd
import numpy as np
from vnstock_qlib.features.quality_factor import compute_quality_score
import os
from datetime import datetime, timedelta

# Initialize Qlib
QLIB_DIR = os.path.expanduser("~/.qlib/qlib_data/vn_data")
qlib.init(provider_uri=QLIB_DIR)

def main():
    # Lấy danh sách symbols từ vn100_clean.txt để đồng bộ
    with open("instruments/vn100_clean.txt", "r") as f:
        symbols = [line.strip() for line in f if line.strip()]
        
    print(f"Loaded {len(symbols)} symbols from vn100_clean.txt")
    
    # Định nghĩa các mốc kiểm tra IC (lấy ngày thứ Hai hàng tuần trong segment test 2024-01-01 đến 2026-06-01)
    start_date = pd.Timestamp("2024-01-01")
    end_date = pd.Timestamp("2026-04-01")  # Để trống 2 tháng cuối tính forward return 5 ngày
    
    dates = []
    curr = start_date
    while curr <= end_date:
        if curr.weekday() == 0:  # Thứ Hai
            dates.append(curr.strftime("%Y-%m-%d"))
        curr += timedelta(days=1)
        
    print(f"Generated {len(dates)} weekly test dates from {dates[0]} to {dates[-1]}")
    
    # 1. Fetch forward 5-day return from Qlib
    print("Fetching forward returns from Qlib...")
    # Ref($close,-5)/$close - 1
    raw_close = D.features(symbols, ["$close"], start_time="2024-01-01", end_time="2026-06-01")
    raw_close.columns = ["close"]
    raw_close = raw_close.reset_index()
    raw_close["datetime"] = pd.to_datetime(raw_close["datetime"])
    
    # Tính forward return 5 ngày cho mỗi ngày giao dịch
    # Sắp xếp theo instrument và datetime
    raw_close = raw_close.sort_values(["instrument", "datetime"])
    raw_close["fwd_ret_5d"] = raw_close.groupby("instrument")["close"].shift(-5) / raw_close["close"] - 1
    
    # Đưa về dạng index để query nhanh
    fwd_ret_df = raw_close.set_index(["datetime", "instrument"])["fwd_ret_5d"]
    
    # 2. Xây dựng quality scores matrix và tính IC
    records = []
    cache_dir = "cache/quality"
    os.makedirs(cache_dir, exist_ok=True)
    
    total_dates = len(dates)
    print("Computing quality factor scores...")
    for i, date_str in enumerate(dates):
        dt = pd.Timestamp(date_str)
        date_records = []
        for sym in symbols:
            cache_file = f"{cache_dir}/{sym}_{date_str}.pkl"
            if os.path.exists(cache_file):
                try:
                    score = pd.read_pickle(cache_file)
                except:
                    score = compute_quality_score(sym, date_str)
                    pd.to_pickle(score, cache_file)
            else:
                score = compute_quality_score(sym, date_str)
                pd.to_pickle(score, cache_file)
                
            date_records.append({
                "datetime": dt,
                "instrument": sym,
                "quality_score": score
            })
        
        # Rank normalize cross-sectionally
        df_date = pd.DataFrame(date_records)
        valid_scores = df_date["quality_score"].dropna()
        if len(valid_scores) >= 2:
            # Scale sang [-1, 1]
            df_date.loc[valid_scores.index, "quality_score"] = (valid_scores.rank(pct=True) * 2 - 1)
        df_date["quality_score"] = df_date["quality_score"].fillna(0.0)
        
        # Map forward return
        for _, row in df_date.iterrows():
            fwd = fwd_ret_df.get((row["datetime"], row["instrument"]), np.nan)
            records.append({
                "datetime": row["datetime"],
                "instrument": row["instrument"],
                "quality_score": row["quality_score"],
                "fwd_ret_5d": fwd
            })
            
        if (i + 1) % 10 == 0:
            print(f"  Processed {i + 1}/{total_dates} dates")
            
    df_factor = pd.DataFrame(records).dropna(subset=["fwd_ret_5d"])
    
    # 3. Tính toán Spearman IC
    daily_ic = df_factor.groupby("datetime").apply(
        lambda g: g["quality_score"].corr(g["fwd_ret_5d"], method="spearman")
    )
    
    mean_ic = daily_ic.mean()
    std_ic = daily_ic.std()
    ir = mean_ic / std_ic if std_ic > 0 else 0
    
    print("\n" + "="*50)
    print("📈 QUALITY FACTOR INDEPENDENT IC TEST RESULTS")
    print("="*50)
    print(f"Mean IC (Spearman) : {mean_ic:.4f}")
    print(f"Std IC             : {std_ic:.4f}")
    print(f"Information Ratio  : {ir:.4f}")
    print(f"Total Weeks Tested : {len(daily_ic)}")
    print(f"Positive IC Weeks  : {(daily_ic > 0).mean():.1%}")
    print("="*50)

if __name__ == "__main__":
    main()
