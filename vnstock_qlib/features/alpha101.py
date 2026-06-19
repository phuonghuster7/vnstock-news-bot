"""
VN Price Features — v2 (IC-ranked, data-driven selection)
Chỉ giữ features có |ICIR| >= 0.05 từ ic_analysis.py
Kết quả IC analysis (5-day forward Spearman, 2018-2026):

Strong  (|ICIR| > 0.10): upper_shadow(+0.143), lower_shadow(-0.149), vs_ma5(-0.102)
Moderate(0.05-0.10):     log_vol, ret_5d, macd_proxy, vol_ratio_5d, vol_ratio_20d,
                         ret_1d, intraday_ret
Dropped (<0.05):         ret_20d, ret_60d, vs_ma20, vs_ma60, pct_k_20d,
                         intraday_vol_20d, ret_vol_20d, hl_spread, price_zscore_20
"""

VN_PRICE_FEATURES = [
    # ── Strong signals (|ICIR| > 0.10) ──────────────────────────────────────
    # Candlestick structure — VN market retail-driven, nến pattern hiệu quả
    ("($high-$close)/($high-$low+1e-8)",    "upper_shadow"),   # ICIR=+0.143
    ("($close-$low)/($high-$low+1e-8)",     "lower_shadow"),   # ICIR=-0.149 (mean-rev signal)
    ("$close/Mean($close,5)-1",             "vs_ma5"),         # ICIR=-0.102 (mean-rev)

    # ── Moderate signals (|ICIR| 0.05-0.10) ─────────────────────────────────
    # Momentum short-term (5d, 1d work — long-term 20d/60d dropped)
    ("Ref($close,5)/$close-1",              "ret_5d"),         # ICIR=+0.083
    ("Ref($close,1)/$close-1",              "ret_1d"),         # ICIR=+0.052

    # Volume signals
    ("Log($volume+1)",                      "log_vol"),        # ICIR=+0.086
    ("$volume/Mean($volume,5)",             "vol_ratio_5d"),   # ICIR=+0.062
    ("$volume/Mean($volume,20)",            "vol_ratio_20d"),  # ICIR=+0.055

    # Trend
    ("EMA($close,12)/EMA($close,26)-1",    "macd_proxy"),     # ICIR=+0.076

    # Intraday reversal (negative predictor — gap-up đảo chiều)
    ("($close-$open)/$open",               "intraday_ret"),   # ICIR=-0.091

    # ── Fundamental Features (with 45-day lag to prevent look-ahead bias) ──
    ("$pe",                                "pe"),             # Price to Earnings
    ("$pb",                                "pb"),             # Price to Book
    ("$roe",                               "roe"),            # Return on Equity
    ("$eps",                               "eps"),            # Earnings Per Share

    # ── EXTRA FEATURES (Vol-adjusted Momentum & Acceleration) ──
    # ⚠️ DISABLED: V7/V8 tests showed degradation in VN30 small universe due to noise.
    # ("(Ref($close,5)/$close-1) / (Std(Ref($close,1)/$close-1, 20) + 1e-8)",     "sharpe_momentum_5d"),
    # ("(Ref($close,20)/$close-1) / (Std(Ref($close,1)/$close-1, 60) + 1e-8)",    "sharpe_momentum_20d"),
    # ("(Ref($close,5)/$close-1) - (Ref($close,10)/Ref($close,5)-1)",             "momentum_accel_5d"),
    # ("($volume/Mean($volume,20)) * (Ref($close,5)/$close-1)",                  "vol_weighted_mom_5d"),
]

# ── Cross-sectional rank versions (thêm sau) ─────────────────────────────────
# Qlib không có Rank() native trong D.features expression
# → tính rank trong DataHandler bằng processor, xem vnstock_qlib/processors.py
