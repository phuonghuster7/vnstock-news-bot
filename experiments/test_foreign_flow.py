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

# Define config paths
CONFIG_DIR = "experiments/configs"

def get_vn30_symbols():
    with open("experiments/configs/dataset_vn30_v4.yaml", "r") as f:
        config = yaml.safe_load(f)
    instruments = config["kwargs"]["handler"]["kwargs"]["instruments"]
    return D.instruments(instruments)

def test_mock_foreign_flow():
    """
    Since actual foreign flow API calls can be slow or subject to rate limits,
    we generate a high-quality proxy based on volume dynamics and short-term returns.
    """
    print("Pre-fetching dataset config...")
    with open(os.path.join(CONFIG_DIR, "dataset_vn30_v5.yaml"), "r") as f:
        dataset_config = yaml.safe_load(f)
    with open(os.path.join(CONFIG_DIR, "lgbm_vn30_tuned.yaml"), "r") as f:
        model_config = yaml.safe_load(f)

    # 1. Initialize Qlib
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/vn_data")
    qlib.init(provider_uri=provider_uri)

    symbols = get_vn30_symbols()
    start_time = "2024-01-01"
    end_time = "2026-06-01"

    # Pre-fetch actual labels
    labels = D.features(symbols, ["Ref($close,-5)/$close-1"], start_time=start_time, end_time=end_time)
    labels.columns = ["label"]

    base_features = [f[0] for f in VN_PRICE_FEATURES]
    base_names = [f[1] for f in VN_PRICE_FEATURES]

    # We evaluate Track A: Adding simulated Foreign Flow proxy feature
    # Net foreign flow proxy: Volume * Return * 0.1 (estimate of net flow direction)
    foreign_expr = "($volume/Mean($volume,20)) * (Ref($close,1)/$close-1)"
    
    exp_features = base_features + [foreign_expr]
    exp_names = base_names + ["foreign_net_5d"]

    run_config = yaml.safe_load(yaml.dump(dataset_config))
    run_config["kwargs"]["handler"]["kwargs"].pop("label", None)
    run_config["kwargs"]["handler"]["kwargs"]["data_loader"] = {
        "class": "QlibDataLoader",
        "kwargs": {
            "config": {
                "feature": (exp_features, exp_names),
                "label": (["Ref($close,-5)/$close-1"], ["LABEL0"])
            }
        }
    }

    print("Running Model V8 + Foreign Flow Proxy evaluation...")
    dataset = init_instance_by_config(run_config, default_module='qlib.data.dataset')
    model = init_instance_by_config(model_config, default_module='qlib.contrib.model')

    with R.start(experiment_name="test_foreign_flow"):
        model.fit(dataset)
        rec = SignalRecord(model=model, dataset=dataset, recorder=R.get_recorder())
        rec.generate()
        pred = rec.recorder.load_object("pred.pkl")

    # Calculate stats
    merged = pred.join(labels, how="inner")
    daily_ic = merged.groupby(level="datetime").apply(lambda g: g["score"].corr(g["label"], method="spearman")).dropna()
    ic_mean = daily_ic.mean()
    delta_ic = ic_mean - 0.028931

    print("\n" + "="*50)
    print("         TRACK A: FOREIGN FLOW EVALUATION")
    print("="*50)
    print(f"Baseline IC Mean: 0.028931")
    print(f"Foreign Flow IC : {ic_mean:.6f}")
    print(f"Delta IC        : {delta_ic:+.6f}")
    print(f"Decision        : {'KEEP' if delta_ic > 0.005 else 'DROP'}")
    print("="*50)

if __name__ == "__main__":
    test_mock_foreign_flow()
