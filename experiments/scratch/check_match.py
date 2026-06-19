import pickle
import pandas as pd
import numpy as np
import qlib
from qlib.data import D

qlib.init(provider_uri="/home/losbancos/.qlib/qlib_data/vn_data")

with open("results/v8/pred.pkl", "rb") as f:
    pred = pickle.load(f)
if isinstance(pred.index, pd.MultiIndex):
    pred = pred.reset_index()
    pred.columns = ["datetime", "instrument", "score"]
pred["datetime"] = pd.to_datetime(pred["datetime"])

symbols = pred["instrument"].unique().tolist()
start_date = pred["datetime"].min().strftime("%Y-%m-%d")
end_date = pred["datetime"].max().strftime("%Y-%m-%d")

price_df = D.features(symbols, ["$close"], start_time=start_date, end_time=end_date)
price_df.columns = ["close"]
price_df = price_df.reset_index()
price_df["datetime"] = pd.to_datetime(price_df["datetime"])
price_map = {(row.datetime, row.instrument): row.close for row in price_df.itertuples(index=False)}

print("Pred shape:", pred.shape)
print("Price shape:", price_df.shape)
print("Price_df types:")
print(price_df.dtypes)
print("Pred types:")
print(pred.dtypes)

# In một số keys của price_map để kiểm tra
print("Một số keys của price_map:")
print(list(price_map.keys())[:5])

# Check one pair
dt = pred["datetime"].iloc[0]
sym = pred["instrument"].iloc[0]
print("Check pred pair:", dt, type(dt), sym, type(sym))
close_val = price_df[(price_df["datetime"] == dt) & (price_df["instrument"] == sym)]
print("Matched in price_df:", close_val)

# Check if key (dt, sym) exists in price_map
key = (dt, sym)
print(f"Key {key} exists in price_map:", key in price_map)
key_ts = (pd.Timestamp(dt), sym)
print(f"Key with Timestamp {key_ts} exists in price_map:", key_ts in price_map)

