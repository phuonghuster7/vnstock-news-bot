import qlib
import yaml
import os
from qlib.utils import init_instance_by_config
from vnstock_qlib.features.alpha101 import VN_PRICE_FEATURES

provider_uri = os.path.expanduser("~/.qlib/qlib_data/vn_data")
qlib.init(provider_uri=provider_uri)

with open("experiments/configs/dataset_vn30_v8.yaml", "r") as f:
    dataset_config = yaml.safe_load(f)

features = [f[0] for f in VN_PRICE_FEATURES]
names    = [f[1] for f in VN_PRICE_FEATURES]

# Append sector features
features.extend(["$sector_ret_5d", "$sector_rel_ret"])
names.extend(["sector_ret_5d", "sector_rel_ret"])

dataset_config["kwargs"]["handler"]["kwargs"]["data_loader"] = {
    "class": "QlibDataLoader",
    "kwargs": {
        "config": {
            "feature": (features, names),
            "label": (dataset_config["kwargs"]["handler"]["kwargs"].pop("label"), ["LABEL0"])
        }
    }
}

dataset = init_instance_by_config(dataset_config, default_module='qlib.data.dataset')
df = dataset.prepare("test")
print("Columns in test:")
print(df.columns.tolist())
print("Head values for sector features:")
print(df[["sector_ret_5d", "sector_rel_ret"]].head())
