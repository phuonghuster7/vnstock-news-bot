import pickle
import pandas as pd
import numpy as np

with open("results/v8/pred.pkl", "rb") as f:
    pred = pickle.load(f)
if isinstance(pred.index, pd.MultiIndex):
    pred = pred.reset_index()
    pred.columns = ["datetime", "instrument", "score"]
pred["datetime"] = pd.to_datetime(pred["datetime"])

print("Pred dates range:", pred["datetime"].min(), "to", pred["datetime"].max())
print("Pred head symbols:", pred["instrument"].head(5).tolist())

import qlib
from qlib.data import D
qlib.init(provider_uri="/home/losbancos/.qlib/qlib_data/vn_data")
price_df = D.features(["ACB"], ["$close"], start_time="2024-01-01", end_time="2026-06-01")
print("Price dates range for ACB:", price_df.index.get_level_values("datetime").min() if price_df is not None else "None")
