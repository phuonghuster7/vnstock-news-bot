import qlib
import yaml
import os
import pandas as pd
from qlib.utils import init_instance_by_config
from vnstock_qlib.features.alpha101 import VN_PRICE_FEATURES

provider_uri = os.path.expanduser("~/.qlib/qlib_data/vn_data")
qlib.init(provider_uri=provider_uri)

with open("experiments/configs/dataset_vn30_v8.yaml", "r") as f:
    dataset_config = yaml.safe_load(f)

features = [f[0] for f in VN_PRICE_FEATURES]
names    = [f[1] for f in VN_PRICE_FEATURES]

dataset_config["kwargs"]["handler"]["kwargs"]["data_loader"] = {
    "class": "QlibDataLoader",
    "kwargs": {
        "config": {
            "feature": (features, names),
            "label": (dataset_config["kwargs"]["handler"]["kwargs"].pop("label"), ["LABEL0"])
        }
    }
}

print("Raw loader init...")
dataset = init_instance_by_config(dataset_config, default_module='qlib.data.dataset')
handler = dataset.handler
print("handler type:", type(handler))

# Let's inspect df before and after SectorMomentumProcessor in handler.infer_processors
df = handler._data
print("Fetched df columns:", df.columns.tolist() if hasattr(df, "columns") else "No columns")


# Call processor 1
p1 = handler.infer_processors[0]
df_p1 = p1(df)
print("After RobustZScoreNorm columns:", df_p1.columns.tolist())

# Call processor 2 (SectorMomentumProcessor)
p2 = handler.infer_processors[1]
df_p2 = p2(df_p1)
print("After SectorMomentumProcessor columns:", df_p2.columns.tolist())
print("Head values:")
print(df_p2[[("feature", "ret_5d"), ("feature", "sector_ret_5d"), ("feature", "sector_rel_ret")]].head())
