"""Quick check: xem price data có fetch được cho W5 period không"""
import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
import shutil; shutil.copy2 = shutil.copyfile; shutil.copy = shutil.copyfile
import qlib
import pandas as pd
from qlib.data import D

qlib.init(provider_uri=os.path.expanduser("~/.qlib/qlib_data/vn_data"))

symbols = ["ACB", "VCB", "FPT", "MSN", "HPG"]
raw = D.features(symbols, ["$close", "$volume"],
                 start_time="2024-09-01",
                 end_time="2024-12-31")
raw.columns = ["close", "volume"]
raw = raw.reset_index()
raw["datetime"] = pd.to_datetime(raw["datetime"])
print("Price rows:", len(raw))
print("Date range:", raw["datetime"].min(), "->", raw["datetime"].max())
print(raw.head(10))

# Check pred dates
import pickle
with open("results/v9_vn100/pred.pkl", "rb") as f:
    pred = pickle.load(f)
pred = pred.reset_index()
pred.columns = ["datetime", "instrument", "score"]
pred["datetime"] = pd.to_datetime(pred["datetime"])
w5 = pred[(pred["datetime"] >= "2024-09-01") & (pred["datetime"] <= "2024-12-31")]
print("\nPred W5 rows:", len(w5))
print("W5 date range:", w5["datetime"].min(), "->", w5["datetime"].max())
print(w5.head())
