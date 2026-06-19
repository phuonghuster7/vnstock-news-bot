"""Debug backtest: kiểm tra pred_df và price_map có dữ liệu không."""
import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
import shutil
shutil.copy2 = shutil.copyfile
shutil.copy = shutil.copyfile

import yaml
import pandas as pd
import numpy as np
import qlib
from qlib.data import D
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord
from vnstock_qlib.features.alpha101 import VN_PRICE_FEATURES

QLIB_DIR   = os.path.expanduser("~/.qlib/qlib_data/vn_data")
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "configs")
TEST_START = "2024-01-02"
TEST_END   = "2026-06-01"

qlib.init(provider_uri=QLIB_DIR)

with open(os.path.join(CONFIG_DIR, "dataset_vn30.yaml"), "r") as f:
    dataset_config = yaml.safe_load(f)
with open(os.path.join(CONFIG_DIR, "lgbm_vn30.yaml"), "r") as f:
    model_config = yaml.safe_load(f)

features = [f[0] for f in VN_PRICE_FEATURES]
names    = [f[1] for f in VN_PRICE_FEATURES]
dataset_config["kwargs"]["handler"]["kwargs"]["data_loader"] = {
    "class": "QlibDataLoader",
    "kwargs": {"config": {
        "feature": (features, names),
        "label": (dataset_config["kwargs"]["handler"]["kwargs"].pop("label"), ["LABEL0"])
    }}
}

dataset = init_instance_by_config(dataset_config, default_module="qlib.data.dataset")
model   = init_instance_by_config(model_config,   default_module="qlib.contrib.model")

with R.start(experiment_name="debug_backtest"):
    model.fit(dataset)
    rec = SignalRecord(model=model, dataset=dataset, recorder=R.get_recorder())
    rec.generate()
    pred_df = rec.recorder.load_object("pred.pkl")

print("=== pred_df type:", type(pred_df))
print("=== pred_df index type:", type(pred_df.index))
print("=== pred_df.head():")
print(pred_df.head(10))
print("\n=== pred_df.index names:", pred_df.index.names if hasattr(pred_df.index, 'names') else "N/A")

# Reset index
if isinstance(pred_df.index, pd.MultiIndex):
    pred_reset = pred_df.reset_index()
    print("\n=== After reset_index columns:", pred_reset.columns.tolist())
    print(pred_reset.head(5))

# Test filter test period
pred_reset.columns = ["datetime", "instrument", "score"]
pred_reset["datetime"] = pd.to_datetime(pred_reset["datetime"])
pred_test = pred_reset[pred_reset["datetime"] >= TEST_START]
print(f"\n=== pred_test rows: {len(pred_test)}")
print(f"=== date range: {pred_test['datetime'].min()} → {pred_test['datetime'].max()}")
print(f"=== symbols: {pred_test['instrument'].unique().tolist()}")

# Test load prices
symbols = pred_test["instrument"].unique().tolist()
raw = D.features(symbols, ["$close"], start_time=TEST_START, end_time=TEST_END)
print("\n=== raw price shape:", raw.shape)
print("=== raw price index:", raw.index[:3])
print("=== raw price columns:", raw.columns.tolist())
raw.columns = ["close"]
raw_r = raw.reset_index()
print("=== raw_r columns:", raw_r.columns.tolist())
print(raw_r.head(5))
