"""
Test IC delta of each extra feature individually against the V4 baseline.
Baseline V4 IC Mean: 0.028931
"""
import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
import shutil
shutil.copy2 = shutil.copyfile
shutil.copy = shutil.copyfile
import yaml

import pickle
import pandas as pd
import numpy as np
import qlib
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord
from vnstock_qlib.features.alpha101 import VN_PRICE_FEATURES

# Define the candidate extra features to test
CANDIDATES = {
    "sharpe_momentum_5d": ("(Ref($close,5)/$close-1) / (Std(Ref($close,1)/$close-1, 20) + 1e-8)", "sharpe_momentum_5d"),
    "sharpe_momentum_20d": ("(Ref($close,20)/$close-1) / (Std(Ref($close,1)/$close-1, 60) + 1e-8)", "sharpe_momentum_20d"),
    "momentum_accel_5d": ("(Ref($close,5)/$close-1) - (Ref($close,10)/Ref($close,5)-1)", "momentum_accel_5d"),
    "vol_weighted_mom_5d": ("($volume/Mean($volume,20)) * (Ref($close,5)/$close-1)", "vol_weighted_mom_5d")
}

V4_BASELINE_IC = 0.028931

def calc_ic_stats(pred: pd.DataFrame, label: pd.DataFrame) -> float:
    if isinstance(pred, pd.Series):
        pred = pred.to_frame("score")
    elif "score" not in pred.columns:
        pred.columns = ["score"]
    merged = pred.join(label, how="inner")
    daily_ic = (
        merged.groupby(level="datetime")
        .apply(lambda g: g["score"].corr(g["label"], method="spearman"))
        .dropna()
    )
    return daily_ic.mean()

def main():
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/vn_data")
    qlib.init(provider_uri=provider_uri)

    config_dir = os.path.join(os.path.dirname(__file__), "configs")
    with open(os.path.join(config_dir, "dataset_vn30_v5.yaml"), "r") as f:
        dataset_config = yaml.safe_load(f)

    with open(os.path.join(config_dir, "lgbm_vn30_tuned.yaml"), "r") as f:
        model_config = yaml.safe_load(f)

    # 1. Fetch labels once to calculate IC
    from qlib.data import D
    # Load actual forward returns (label)
    with open(os.path.join(config_dir, "dataset_vn30_v5.yaml"), "r") as f:
        c_temp = yaml.safe_load(f)
    print("Pre-fetching labels...")
    instruments = "vn30"
    start_time = "2024-01-01"
    end_time = "2026-06-01"
    
    # Resolve instruments list
    resolved_instruments = D.instruments(instruments)
    labels = D.features(resolved_instruments, ["Ref($close,-5)/$close-1"], start_time=start_time, end_time=end_time)
    labels.columns = ["label"]

    base_features = [f[0] for f in VN_PRICE_FEATURES]
    base_names = [f[1] for f in VN_PRICE_FEATURES]

    results = []

    for name, (expr, col_name) in CANDIDATES.items():
        print(f"\nEvaluating candidate feature: {name}...")
        
        # Build features for this experiment: base features + 1 candidate
        exp_features = base_features + [expr]
        exp_names = base_names + [col_name]
        
        # Clone dataset config
        run_config = yaml.safe_load(yaml.dump(dataset_config))
        # Ensure we remove 'label' key from handler kwargs to prevent DataHandler.__init__() unexpected keyword argument
        label_expr = run_config["kwargs"]["handler"]["kwargs"].pop("label", ["Ref($close,-5)/$close-1"])
        
        run_config["kwargs"]["handler"]["kwargs"]["data_loader"] = {
            "class": "QlibDataLoader",
            "kwargs": {
                "config": {
                    "feature": (exp_features, exp_names),
                    "label": (label_expr, ["LABEL0"])
                }
            }
        }

        
        # Load dataset
        dataset = init_instance_by_config(run_config, default_module='qlib.data.dataset')
        model = init_instance_by_config(model_config, default_module='qlib.contrib.model')
        
        exp_name = f"test_feat_{name}"
        with R.start(experiment_name=exp_name):
            model.fit(dataset)
            rec = SignalRecord(model=model, dataset=dataset, recorder=R.get_recorder())
            rec.generate()
            pred = rec.recorder.load_object("pred.pkl")
            
        ic_mean = calc_ic_stats(pred, labels)
        delta_ic = ic_mean - V4_BASELINE_IC
        decision = "KEEP" if delta_ic >= 0.005 else "DROP"
        
        print(f"-> {name} IC Mean: {ic_mean:.6f} | Delta IC: {delta_ic:+.6f} | Decision: {decision}")
        results.append({
            "Feature": name,
            "IC Mean": ic_mean,
            "Delta IC": delta_ic,
            "Decision": decision
        })

    print("\n" + "="*50)
    print("         SUMMARY OF INDIVIDUAL FEATURE TESTING")
    print("="*50)
    summary_df = pd.DataFrame(results)
    print(summary_df.to_string(index=False))
    print("="*50)

if __name__ == "__main__":
    main()
