"""Quick debug: kiểm tra price_map lookup trong compute_daily_ic"""
import os, pickle
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
import shutil; shutil.copy2 = shutil.copyfile; shutil.copy = shutil.copyfile
import pandas as pd
import numpy as np
import qlib
from qlib.data import D

qlib.init(provider_uri=os.path.expanduser("~/.qlib/qlib_data/vn_data"))

with open("results/v9_vn100/pred.pkl", "rb") as f:
    pred = pickle.load(f)
pred = pred.reset_index()
pred.columns = ["datetime", "instrument", "score"]
pred["datetime"] = pd.to_datetime(pred["datetime"])

w5 = pred[(pred["datetime"] >= "2024-09-01") & (pred["datetime"] <= "2024-12-31")]
syms = w5["instrument"].unique().tolist()[:10]
print("Sample syms:", syms)
dates = sorted(w5["datetime"].unique())
print("W5 dates count:", len(dates), "First:", dates[0])

# Check price fetch
raw = D.features(syms, ["$close", "$volume"], start_time="2024-09-01", end_time="2024-12-31")
raw.columns = ["close", "volume"]
raw = raw.reset_index()
raw["datetime"] = pd.to_datetime(raw["datetime"])
print("Price rows:", len(raw))
print("Price columns:", raw.columns.tolist())
print("Price dtypes:", raw.dtypes.to_dict())
print(raw.head(3))

# Build price_map như trong script
price_map = {(row.datetime, row.instrument): row.close for row in raw.itertuples(index=False)}
print("Price map size:", len(price_map))

# Test lookup
d0 = dates[0]
sym0 = syms[0]
key = (d0, sym0)
print(f"Test key type: {type(d0)}, {type(sym0)}")
print(f"Test lookup {key} -> {price_map.get(key, 'NOT FOUND')}")

# Check map key types
sample_key = list(price_map.keys())[0]
print(f"Map key types: {type(sample_key[0])}, {type(sample_key[1])}")
