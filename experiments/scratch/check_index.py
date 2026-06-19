import pandas as pd
import numpy as np

# Đọc VNINDEX
vnindex = pd.read_csv("cache/VNINDEX_price.csv", index_col=0, parse_dates=True)
print("vnindex index type:", type(vnindex.index), vnindex.index[0])

# Tính features
c = vnindex["close"]
mkt_feat = pd.DataFrame(index=vnindex.index)
mkt_feat["ret_5d"] = c.pct_change(5)
mkt_feat = mkt_feat.dropna()
print("mkt_feat index range:", mkt_feat.index.min(), "to", mkt_feat.index.max())

# Đọc labels giả lập từ validate_auc
# (Chúng ta biết labels có index từ daily_ic)
# Hãy in ra index của labels
import pickle
with open("results/v8/pred.pkl", "rb") as f:
    pred = pickle.load(f)
if isinstance(pred.index, pd.MultiIndex):
    pred = pred.reset_index()
    pred.columns = ["datetime", "instrument", "score"]
pred["datetime"] = pd.to_datetime(pred["datetime"])

dates = sorted(pred["datetime"].unique())
print("pred dates type:", type(dates[0]), dates[0])

# Match index
overlap = mkt_feat.index.intersection(dates)
print("Overlap size:", len(overlap))
if len(overlap) > 0:
    print("Example overlap:", overlap[0])
