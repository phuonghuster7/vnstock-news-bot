"""
Optuna hyperparameter tuning for LightGBM on validation set to maximize IC/ICIR.
"""
import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
import yaml
import numpy as np
import pandas as pd
import optuna
import qlib
from qlib.utils import init_instance_by_config
from vnstock_qlib.features.alpha101 import VN_PRICE_FEATURES

def calc_icir(pred: pd.DataFrame, label: pd.DataFrame) -> float:
    # Handle Series or DataFrame inputs
    if isinstance(pred, pd.Series):
        pred = pred.to_frame("score")
    elif "score" not in pred.columns:
        pred.columns = ["score"]
        
    if isinstance(label, pd.Series):
        label = label.to_frame("label")
    else:
        label.columns = ["label"]
        
    merged = pred.join(label, how="inner")
    if len(merged) == 0:
        return -1.0
        
    daily_ic = (
        merged.groupby(level="datetime")
        .apply(lambda g: g["score"].corr(g["label"], method="spearman"))
        .dropna()
    )
    if len(daily_ic) < 5 or daily_ic.std() == 0:
        return -1.0
        
    icir = daily_ic.mean() / daily_ic.std()
    return float(icir)

def main():
    # 1. Initialize Qlib
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/vn_data")
    qlib.init(provider_uri=provider_uri)
    
    # 2. Load dataset config
    config_dir = os.path.join(os.path.dirname(__file__), "configs")
    with open(os.path.join(config_dir, "dataset_vn30_v4.yaml"), "r") as f:
        dataset_config = yaml.safe_load(f)
        
    features = [f[0] for f in VN_PRICE_FEATURES]
    names = [f[1] for f in VN_PRICE_FEATURES]
    
    dataset_config["kwargs"]["handler"]["kwargs"]["data_loader"] = {
        "class": "QlibDataLoader",
        "kwargs": {
            "config": {
                "feature": (features, names),
                "label": (dataset_config["kwargs"]["handler"]["kwargs"].pop("label"), ["LABEL0"])
            }
        }
    }
    
    print("Loading and preparing dataset (once)...")
    dataset = init_instance_by_config(dataset_config, default_module='qlib.data.dataset')
    
    # Pre-load labels for validation set to save time
    print("Preparing validation labels...")
    valid_label = dataset.prepare("valid", col_set="label")
    
    # 3. Define Optuna objective
    def objective(trial):
        # Suggest parameters
        params = {
            "loss": "mse",
            "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.05, log=True),
            "num_leaves": trial.suggest_int("num_leaves", 15, 63),
            "min_data_in_leaf": trial.suggest_int("min_data_in_leaf", 10, 50),
            "num_boost_round": 1000,
            "early_stopping_rounds": 100,
            "feature_fraction": trial.suggest_float("feature_fraction", 0.6, 1.0),
            "bagging_fraction": trial.suggest_float("bagging_fraction", 0.6, 1.0),
            "lambda_l1": trial.suggest_float("lambda_l1", 1e-3, 5.0, log=True),
            "lambda_l2": trial.suggest_float("lambda_l2", 1e-3, 5.0, log=True),
            "verbose": -1,
        }
        
        model_config = {
            "class": "LGBModel",
            "kwargs": params
        }
        
        # Instantiate and fit
        model = init_instance_by_config(model_config, default_module='qlib.contrib.model')
        model.fit(dataset)
        
        # Predict on validation set
        pred = model.predict(dataset, segment="valid")
        
        # Calculate ICIR
        icir = calc_icir(pred, valid_label)
        
        return icir

    # 4. Run Study
    # Set verbose off for optuna to avoid messy logs
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    
    print("Starting Optuna optimization study (20 trials)...")
    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=20)
    
    print("\n" + "=" * 50)
    print("           OPTUNA TUNING COMPLETED")
    print("=" * 50)
    print(f"Best Trial Value (Valid ICIR): {study.best_value:.6f}")
    print("Best Parameters:")
    for k, v in study.best_params.items():
        print(f"  {k}: {v}")
    print("=" * 50)
    
    # Save best parameters to yaml
    best_params = study.best_params
    best_params["loss"] = "mse"
    best_params["num_boost_round"] = 1000
    best_params["early_stopping_rounds"] = 100
    best_params["verbose"] = -1
    
    best_config = {
        "class": "LGBModel",
        "kwargs": best_params
    }
    
    out_path = os.path.join(os.path.dirname(__file__), "configs", "lgbm_vn30_tuned.yaml")
    with open(out_path, "w") as f:
        yaml.safe_dump(best_config, f, default_flow_style=False)
    print(f"Saved tuned config to {out_path}")

if __name__ == "__main__":
    main()
