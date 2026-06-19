"""
IC/ICIR per feature analysis — tính trước để biết feature nào predict được.
Output: bảng IC Mean, IC IR, IC > 0 rate cho từng feature.
"""
import os, sys
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"

import pandas as pd
import numpy as np
import qlib
from qlib.data import D

QLIB_DIR  = os.path.expanduser("~/.qlib/qlib_data/vn_data")
UNIVERSE  = ["ACB","BID","BSR","CTG","FPT","GAS","GVR","HDB","HPG","LPB",
             "MBB","MSN","MWG","PLX","SAB","SHB","SSB","SSI","STB","TCB",
             "TPB","VCB","VHM","VIB","VIC","VJC","VNM","VPB","VPL","VRE"]
START     = "2018-01-01"
END       = "2026-06-01"
FWD_DAYS  = 5      # IC tính với 5-day forward return

# ── Tất cả features cần test ─────────────────────────────────────────────────
CANDIDATE_FEATURES = [
    # === Existing features ===
    ("Ref($close,1)/$close-1",                          "ret_1d"),
    ("Ref($close,5)/$close-1",                          "ret_5d"),
    ("Ref($close,20)/$close-1",                         "ret_20d"),
    ("Ref($close,60)/$close-1",                         "ret_60d"),
    ("Log($volume+1)",                                  "log_vol"),
    ("$volume/Mean($volume,20)",                        "vol_ratio_20d"),
    ("$close/Mean($close,5)-1",                         "vs_ma5"),
    ("$close/Mean($close,20)-1",                        "vs_ma20"),
    ("$close/Mean($close,60)-1",                        "vs_ma60"),
    ("($close-Min($low,20))/(Max($high,20)-Min($low,20)+1e-8)", "pct_k_20d"),
    ("Std(Ref($close,1)/$close-1,20)",                  "ret_vol_20d"),
    ("Std(($high-$low)/$close,20)",                     "intraday_vol_20d"),
    ("EMA($close,12)/EMA($close,26)-1",                 "macd_proxy"),

    # === Market microstructure ===
    ("($high-$low)/$vwap",                              "hl_spread"),      # bid-ask proxy
    ("($close-$open)/$open",                            "intraday_ret"),   # open-to-close
    ("($high-$close)/($high-$low+1e-8)",                "upper_shadow"),   # upper wick ratio
    ("($close-$low)/($high-$low+1e-8)",                 "lower_shadow"),   # lower wick ratio
    ("$volume/Mean($volume,5)",                         "vol_ratio_5d"),   # short-term vol spike
    ("$volume/Mean($volume,60)",                        "vol_ratio_60d"),  # long-term vol spike

    # === Cross-sectional rank proxies (Qlib không có Rank() native → dùng zscore trick) ===
    # Qlib hỗ trợ: ta sẽ tính rank ngoài hoặc dùng biểu thức chuẩn hoá
    ("Ref($close,5)/$close-1",                          "ret_5d_raw"),     # duplicate để so sánh
    ("($close-Mean($close,20))/Std($close,20)",         "price_zscore_20"), # z-score thay rank

    # === Reversal ===
    ("Ref($close,1)/$close-1",                          "ret_1d_rev"),     # short reversal
]

# Loại bỏ duplicate name
seen = set()
CANDIDATE_FEATURES = [(e, n) for e, n in CANDIDATE_FEATURES
                      if n not in seen and not seen.add(n)]


def load_features_and_label():
    """Load tất cả features + forward return (label) từ Qlib."""
    exprs = [e for e, _ in CANDIDATE_FEATURES]
    names = [n for _, n in CANDIDATE_FEATURES]
    label_expr = f"Ref($close,-{FWD_DAYS})/$close-1"

    all_exprs = exprs + [label_expr]
    all_names = names + ["fwd_ret"]

    print(f"Loading {len(all_exprs)} fields for {len(UNIVERSE)} symbols ...")
    df = D.features(UNIVERSE, all_exprs, start_time=START, end_time=END)
    df.columns = all_names
    return df


def compute_ic_per_feature(df: pd.DataFrame):
    """
    Với mỗi feature, tính IC hàng ngày = Spearman corr(feature, fwd_ret)
    cross-sectional (across symbols cho mỗi ngày).
    """
    feature_names = [n for _, n in CANDIDATE_FEATURES]
    results = []

    # df có MultiIndex (instrument, datetime) → cần pivot để tính cross-sectional
    df_reset = df.reset_index()
    # Sau reset: columns = [instrument, datetime, feat1, feat2, ..., fwd_ret]
    df_reset.columns = ["instrument", "datetime"] + feature_names + ["fwd_ret"]
    df_reset["datetime"] = pd.to_datetime(df_reset["datetime"])

    dates = sorted(df_reset["datetime"].unique())
    print(f"Computing IC across {len(dates)} dates ...")

    for fname in feature_names:
        ic_daily = []
        for date in dates:
            day = df_reset[df_reset["datetime"] == date][[fname, "fwd_ret"]].dropna()
            if len(day) < 5:
                continue
            # Spearman rank IC
            ic = day[fname].rank().corr(day["fwd_ret"].rank())
            if not np.isnan(ic):
                ic_daily.append(ic)

        if ic_daily:
            s = pd.Series(ic_daily)
            results.append({
                "Feature":    fname,
                "IC Mean":    s.mean(),
                "IC Std":     s.std(),
                "IC IR":      s.mean() / s.std() if s.std() > 0 else 0,
                "IC > 0 (%)": (s > 0).mean() * 100,
                "|IC| > 0.02 (%)": (s.abs() > 0.02).mean() * 100,
                "N days":     len(ic_daily),
            })

    return pd.DataFrame(results).sort_values("IC IR", ascending=False)


def main():
    qlib.init(provider_uri=QLIB_DIR)
    df = load_features_and_label()
    ic_table = compute_ic_per_feature(df)

    print("\n" + "=" * 75)
    print("  IC / ICIR PER FEATURE  (5-day forward return, cross-sectional Spearman)")
    print("=" * 75)
    print(ic_table.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print("=" * 75)

    # Phân loại
    strong  = ic_table[ic_table["IC IR"].abs() > 0.1]
    moderate = ic_table[(ic_table["IC IR"].abs() >= 0.05) & (ic_table["IC IR"].abs() <= 0.1)]
    weak    = ic_table[ic_table["IC IR"].abs() < 0.05]

    print(f"\n✅ Strong (|ICIR| > 0.10): {len(strong)} features")
    print(f"   {strong['Feature'].tolist()}")
    print(f"⚠️  Moderate (0.05–0.10): {len(moderate)} features")
    print(f"   {moderate['Feature'].tolist()}")
    print(f"❌ Weak (|ICIR| < 0.05):  {len(weak)} features → consider dropping")
    print(f"   {weak['Feature'].tolist()}")

    # Save
    out = os.path.join(os.path.dirname(__file__), "..", "results", "ic_analysis.csv")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    ic_table.to_csv(out, index=False)
    print(f"\nSaved → {os.path.abspath(out)}")

    return ic_table


if __name__ == "__main__":
    main()
