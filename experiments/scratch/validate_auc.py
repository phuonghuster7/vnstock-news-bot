import pandas as pd
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import roc_auc_score
import pickle

# --- CODE TỪ ĐỀ XUẤT CỦA USER ---

def build_market_features(vnindex: pd.DataFrame) -> pd.DataFrame:
    df = pd.DataFrame(index=vnindex.index)
    c = vnindex["close"]
    v = vnindex["volume"]

    # Trend features
    df["ret_5d"]      = c.pct_change(5)
    df["ret_20d"]     = c.pct_change(20)
    df["ret_60d"]     = c.pct_change(60)
    df["ma20_ratio"]  = c / c.rolling(20).mean() - 1
    df["ma60_ratio"]  = c / c.rolling(60).mean() - 1

    # Volatility features
    df["vol_5d"]      = c.pct_change().rolling(5).std()
    df["vol_20d"]     = c.pct_change().rolling(20).std()
    df["vol_ratio"]   = df["vol_5d"] / (df["vol_20d"] + 1e-8)

    # Breadth proxy
    df["range_ratio"] = (vnindex["high"] - vnindex["low"]) / (c + 1e-8)

    # Volume signal
    df["vol_ma_ratio"] = v / (v.rolling(20).mean() + 1e-8)

    # Momentum curvature
    ema12 = c.ewm(span=12).mean()
    ema26 = c.ewm(span=26).mean()
    df["macd_norm"]   = (ema12 - ema26) / (c + 1e-8)

    return df.dropna()


def build_ic_labels(pred_pkl: str, forward_window: int = 10) -> tuple:
    with open(pred_pkl, "rb") as f:
        pred = pickle.load(f)

    # pred_df reset index if needed
    if isinstance(pred.index, pd.MultiIndex):
        pred = pred.reset_index()
        pred.columns = ["datetime", "instrument", "score"]
    pred["datetime"] = pd.to_datetime(pred["datetime"])

    # Load realized returns from Qlib or proxy. 
    # Nhưng vì ta cần label = corr(score, realized return). 
    # Trong database Qlib có label sẵn không? V8 pred.pkl có cột label không? 
    # Hãy check columns của pred.pkl trước. 
    # À, debug_pkl.py in ra Columns: Index(['score'], dtype='object'). Nó không có cột 'label'!
    # Chúng ta phải tự tính realized return 5d của từng cổ phiếu trong pred.pkl để làm label.
    # Hãy tự tính realized return cho từng cổ phiếu từ dữ liệu đóng cửa trong Qlib.
    return pred


class ICRegimeClassifier:
    def __init__(self,
                 n_estimators: int = 100,
                 max_depth: int = 3,
                 forward_window: int = 10,
                 ic_threshold: float = 0.03):
        self.forward_window = forward_window
        self.ic_threshold   = ic_threshold
        base = GradientBoostingClassifier(
            n_estimators  = n_estimators,
            max_depth     = max_depth,
            learning_rate = 0.05,
            subsample     = 0.8,
            random_state  = 42,
        )
        self.model = CalibratedClassifierCV(base, cv=5, method="isotonic")
        self.feature_names = None

    def fit(self, market_features: pd.DataFrame,
            ic_labels: pd.Series,
            train_end: str = "2022-12-31"):
        X = market_features.loc[:train_end]
        y = ic_labels.reindex(X.index).dropna()
        X = X.loc[y.index]

        self.feature_names = X.columns.tolist()
        self.model.fit(X, y)
        print(f"Train samples: {len(y)}, IC-good days: {y.sum()} ({y.mean():.1%})")
        return self


# --- SCRIPT RUNNER ---
import os
import qlib
from qlib.data import D

QLIB_DIR = os.path.expanduser("~/.qlib/qlib_data/vn_data")
qlib.init(provider_uri=QLIB_DIR)

print("Đọc VNINDEX...")
vnindex = pd.read_csv("cache/VNINDEX_price.csv", index_col=0, parse_dates=True)
# Loại bỏ thông tin múi giờ timezone nếu có, đưa về timezone naive
if vnindex.index.tz is not None:
    vnindex.index = vnindex.index.tz_localize(None)
else:
    vnindex.index = vnindex.index.tz_localize(None).tz_localize(None) # Đảm bảo naive
# Hoặc đơn giản là chuẩn hóa giờ thành 00:00:00
vnindex.index = pd.to_datetime(vnindex.index).normalize()
mkt_feat = build_market_features(vnindex)

print("Đọc predictions...")
with open("results/v8/pred.pkl", "rb") as f:
    pred = pickle.load(f)
if isinstance(pred.index, pd.MultiIndex):
    pred = pred.reset_index()
    pred.columns = ["datetime", "instrument", "score"]
pred["datetime"] = pd.to_datetime(pred["datetime"])

# Tự tính realized return 5d của từng cổ phiếu trong pred để tính IC
symbols = pred["instrument"].unique().tolist()
start_date = pred["datetime"].min().strftime("%Y-%m-%d")
end_date = pred["datetime"].max().strftime("%Y-%m-%d")

print(f"Tải giá đóng cửa cho {len(symbols)} cổ phiếu từ {start_date} đến {end_date}...")
price_df = D.features(symbols, ["$close"], start_time=start_date, end_time=end_date)
price_df.columns = ["close"]
price_df = price_df.reset_index()
price_df["datetime"] = pd.to_datetime(price_df["datetime"])

# Tạo mapping để tính return nhanh
price_map = {(row.datetime, row.instrument): row.close for row in price_df.itertuples(index=False)}

# Tính realized 5d return của từng instrument
records = []
dates = sorted(pred["datetime"].unique())
print("Dates count:", len(dates))
# Chuyển đổi keys của price_map và dates sang pd.Timestamp để đồng bộ hoàn toàn
price_map = {(pd.Timestamp(k[0]), k[1]): v for k, v in price_map.items()}

for idx, dt in enumerate(dates):
    dt_ts = pd.Timestamp(dt)
    if idx + 5 >= len(dates):
        continue
    fwd_dt_ts = pd.Timestamp(dates[idx+5])
    day_pred = pred[pred["datetime"] == dt]
    for _, row in day_pred.iterrows():
        sym = row["instrument"]
        p0 = price_map.get((dt_ts, sym), np.nan)
        p5 = price_map.get((fwd_dt_ts, sym), np.nan)
        if not np.isnan(p0) and not np.isnan(p5) and p0 > 0:
            records.append({
                "datetime": dt_ts,
                "instrument": sym,
                "score": row["score"],
                "fwd_ret": p5 / p0 - 1
            })

processed_df = pd.DataFrame(records)
print("Records created:", len(records))
print("processed_df columns:", processed_df.columns)
print(processed_df.head())
# Groupby bằng cách sử dụng pd.Grouper hoặc chỉ rõ cột 'datetime'
daily_ic = processed_df.groupby(processed_df["datetime"]).apply(lambda g: g["score"].corr(g["fwd_ret"], method="spearman")).dropna()

print("Mô tả Daily IC:")
print(daily_ic.describe())

# Rolling IC 10 ngày -> label cho hôm nay (shift forward)
forward_window = 10
rolling_ic = daily_ic.rolling(forward_window).mean()
labels = (rolling_ic.shift(-forward_window) > 0.03).astype(int)

print("Class balance của label toàn bộ:")
print(labels.value_counts(normalize=True))

# validate_classifier_auc
# validate_classifier_auc
val_start = "2025-07-01"
val_end = "2026-06-01"

clf = ICRegimeClassifier()
clf.fit(mkt_feat, labels, train_end="2025-06-30")

X_val = mkt_feat.loc[val_start:val_end]
y_val = labels.reindex(X_val.index).dropna()
X_val = X_val.loc[y_val.index]

if len(y_val) > 0:
    proba = clf.model.predict_proba(X_val)[:, 1]
    auc = roc_auc_score(y_val, proba)
    print(f"\nClassifier AUC on validation ({val_start} to {val_end}): {auc:.4f}")
    print(f"{'✅ Proceed to 9B' if auc > 0.55 else '❌ Classifier too weak — do not use'}")
else:
    print("Không có đủ mẫu validation để tính AUC.")
