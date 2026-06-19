import pickle
import pandas as pd
import numpy as np
import qlib
from qlib.data import D
import os

qlib.init(provider_uri="/home/losbancos/.qlib/qlib_data/vn_data")

# 1. Đọc pred VN30 (V8) và VN100 (V9)
with open("results/v8/pred.pkl", "rb") as f:
    pred_v8 = pickle.load(f)
with open("results/v9_vn100/pred.pkl", "rb") as f:
    pred_v9 = pickle.load(f)

# Chuẩn hoá
for df in [pred_v8, pred_v9]:
    if isinstance(df.index, pd.MultiIndex):
        df.reset_index(inplace=True)
        df.columns = ["datetime", "instrument", "score"]
    df["datetime"] = pd.to_datetime(df["datetime"])

# Khoảng thời gian so sánh (Test: 2024-01-02 -> 2026-06-01)
TEST_START = "2024-01-02"
TEST_END = "2026-06-01"

pred_v8 = pred_v8[(pred_v8["datetime"] >= TEST_START) & (pred_v8["datetime"] <= TEST_END)].copy()
pred_v9 = pred_v9[(pred_v9["datetime"] >= TEST_START) & (pred_v9["datetime"] <= TEST_END)].copy()

# Lấy close price để tính realised return
all_symbols = list(set(pred_v8["instrument"].unique()) | set(pred_v9["instrument"].unique()))
price_df = D.features(all_symbols, ["$close"], start_time=TEST_START, end_time=TEST_END)
price_df.columns = ["close"]
price_df = price_df.reset_index()
price_df["datetime"] = pd.to_datetime(price_df["datetime"])
price_map = {(pd.Timestamp(row.datetime), row.instrument): row.close for row in price_df.itertuples(index=False)}

# Tải VNINDEX để phân loại market regime
vnindex = pd.read_csv("cache/VNINDEX_price.csv", index_col=0, parse_dates=True)
vnindex.index = pd.to_datetime(vnindex.index).normalize()
vnindex["ret_1d"] = vnindex["close"].pct_change()
vnindex["ret_5d"] = vnindex["close"].pct_change(5)

def calculate_ic_and_regimes(pred_df, name):
    dates = sorted(pred_df["datetime"].unique())
    ic_list = []
    regime_ic = {"Bull": [], "Bear": [], "Sideways": [], "Recovery": []}
    
    # Tính return 5d của từng cp
    records = []
    for idx, dt in enumerate(dates):
        if idx + 5 >= len(dates):
            continue
        fwd_dt = dates[idx+5]
        day_pred = pred_df[pred_df["datetime"] == dt]
        for _, row in day_pred.iterrows():
            sym = row["instrument"]
            p0 = price_map.get((pd.Timestamp(dt), sym), np.nan)
            p5 = price_map.get((pd.Timestamp(fwd_dt), sym), np.nan)
            if not np.isnan(p0) and not np.isnan(p5) and p0 > 0:
                records.append({
                    "datetime": dt,
                    "instrument": sym,
                    "score": row["score"],
                    "fwd_ret": p5 / p0 - 1
                })
    
    df_rec = pd.DataFrame(records)
    daily_ic = df_rec.groupby("datetime").apply(lambda g: g["score"].corr(g["fwd_ret"], method="spearman")).dropna()
    
    # Phân loại regime
    for dt, ic in daily_ic.items():
        dt_ts = pd.Timestamp(dt)
        try:
            mkt_ret_1d = vnindex.loc[dt_ts, "ret_1d"]
            mkt_ret_5d = vnindex.loc[dt_ts, "ret_5d"]
        except KeyError:
            mkt_ret_1d = 0.0
            mkt_ret_5d = 0.0
            
        if mkt_ret_1d > 0.005 and mkt_ret_5d > 0:
            regime = "Bull"
        elif mkt_ret_1d < -0.005 and mkt_ret_5d < 0:
            regime = "Bear"
        elif mkt_ret_1d > 0.005 and mkt_ret_5d <= 0:
            regime = "Recovery"
        else:
            regime = "Sideways"
            
        regime_ic[regime].append(ic)
        ic_list.append(ic)
        
    ic_s = pd.Series(ic_list)
    mean_ic = ic_s.mean()
    icir = ic_s.mean() / ic_s.std() if ic_s.std() > 0 else 0
    
    print(f"\n===== KẾT QUẢ IC CHO {name} =====")
    print(f"IC Mean : {mean_ic:.4f}")
    print(f"ICIR    : {icir:.4f}")
    print("IC per Regime:")
    for regime, ics in regime_ic.items():
        print(f"  - {regime:<10}: {np.mean(ics):+.4f} (Count: {len(ics)})")
        
    return mean_ic, icir, regime_ic

print("Đang tính toán IC...")
calculate_ic_and_regimes(pred_v8, "VN30 (Model V8)")
calculate_ic_and_regimes(pred_v9, "VN100 (Model V9)")
