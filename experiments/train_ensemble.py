import qlib
from qlib.data import D
import pandas as pd
import numpy as np
import pickle
from pathlib import Path
import os
import yaml

# Initialize Qlib
import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
import shutil
shutil.copy2 = shutil.copyfile
shutil.copy = shutil.copyfile

QLIB_DIR = os.path.expanduser("~/.qlib/qlib_data/vn_data")
qlib.init(provider_uri=QLIB_DIR)

# ── Regime Classification ─────────────────────────────────────────

def classify_market_regime(vnindex_path: str) -> pd.Series:
    """
    Phân loại regime từng ngày dựa trên VN-Index.
    
    Bull:     ret_20d > +5%  AND vol_20d thấp
    Bear:     ret_20d < -5%  AND vol_20d cao
    Recovery: ret_20d > 0%   sau Bear period
    Sideways: còn lại
    
    Returns: pd.Series index=date, values=regime string
    """
    vnindex = pd.read_csv(vnindex_path, index_col=0, parse_dates=True)
    # Sắp xếp index tăng dần theo thời gian
    vnindex = vnindex.sort_index()
    c = vnindex["close"]
    
    ret_20d  = c.pct_change(20)
    vol_20d  = c.pct_change().rolling(20).std()
    vol_mean = vol_20d.rolling(60).mean()
    high_vol = vol_20d > vol_mean * 1.2
    
    regime = pd.Series("sideways", index=c.index)
    regime[ret_20d >  0.05]                   = "bull"
    regime[(ret_20d < -0.05) & high_vol]      = "bear"
    
    # Recovery: ret_20d > 0 sau bear period
    # Sử dụng numeric mask (1 cho bear, 0 cho loại khác) để dùng rolling
    is_bear_numeric = (regime == "bear").astype(int)
    has_bear_in_20d = is_bear_numeric.shift(1).rolling(20).max().fillna(0).astype(bool)
    is_recovery = (ret_20d > 0.0) & has_bear_in_20d
    regime[is_recovery] = "recovery"
    
    # Smooth: tránh flip liên tục
    # Giữ regime ít nhất 5 ngày trước khi switch
    smoothed = regime.copy()
    for i in range(5, len(regime)):
        window = regime.iloc[i-5:i]
        if (window == regime.iloc[i]).sum() < 3:
            smoothed.iloc[i] = smoothed.iloc[i-1]
    
    return smoothed


# ── Train specialist models ────────────────────────────────────────

LGBM_PARAMS = {
    "learning_rate":      0.0337,
    "num_leaves":         59,
    "min_data_in_leaf":   41,
    "feature_fraction":   0.6004,
    "bagging_fraction":   0.9260,
    "lambda_l1":          0.0313,
    "lambda_l2":          0.0325,
    "num_boost_round":    1000,
    "early_stopping_rounds": 100,
}

def train_specialist(name: str,
                     target_regimes: list,
                     regime_series: pd.Series,
                     output_dir: str = "results/ensemble"):
    """
    Train một specialist model cho subset regime.
    
    name: "bull" hoặc "bear"
    target_regimes: list regime strings để train trên
    """
    from qlib.utils import init_instance_by_config
    from vnstock_qlib.features.alpha101 import VN_PRICE_FEATURES
    
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*50}")
    print(f"  Training {name.upper()} specialist model")
    print(f"  Regimes: {target_regimes}")
    
    # Lấy dates thuộc regime này
    regime_dates = regime_series[
        regime_series.isin(target_regimes)
    ].index
    
    # Đọc config dataset cơ bản
    config_path = "experiments/configs/dataset_vn100_v9.yaml"
    with open(config_path) as f:
        dataset_config = yaml.safe_load(f)
        
    features = [f[0] for f in VN_PRICE_FEATURES]
    names    = [f[1] for f in VN_PRICE_FEATURES]
    features.extend(["$sector_ret_5d", "$sector_rel_ret"])
    names.extend(["sector_ret_5d", "sector_rel_ret"])
    
    label_expr = dataset_config["kwargs"]["handler"]["kwargs"].pop("label")
    dataset_config["kwargs"]["handler"]["kwargs"]["data_loader"] = {
        "class": "QlibDataLoader",
        "kwargs": {"config": {
            "feature": (features, names),
            "label":   (label_expr, ["LABEL0"]),
        }},
    }
    
    # Filter chỉ regime dates trong training/validation
    train_dates = [d for d in regime_dates if d <= pd.Timestamp("2022-12-31")]
    valid_dates = [d for d in regime_dates if pd.Timestamp("2023-01-01") <= d <= pd.Timestamp("2023-12-31")]
    
    # Đảm bảo có đủ ngày
    if not train_dates:
        train_start = "2018-01-01"
        train_end = "2022-12-31"
    else:
        train_start = min(train_dates).strftime("%Y-%m-%d")
        train_end = max(train_dates).strftime("%Y-%m-%d")
        
    if not valid_dates:
        valid_start = "2023-01-01"
        valid_end = "2023-12-31"
    else:
        valid_start = min(valid_dates).strftime("%Y-%m-%d")
        valid_end = max(valid_dates).strftime("%Y-%m-%d")

    print(f"  Training segment: {train_start} to {train_end} ({len(train_dates)} regime days)")
    print(f"  Validation segment: {valid_start} to {valid_end} ({len(valid_dates)} regime days)")
    
    dataset_config["kwargs"]["handler"]["kwargs"]["start_time"] = "2018-01-01"
    dataset_config["kwargs"]["handler"]["kwargs"]["end_time"]   = "2026-06-01"
    dataset_config["kwargs"]["segments"] = {
        "train": [train_start, train_end],
        "valid": [valid_start, valid_end],
        "test":  ["2024-01-01", "2026-06-01"],
    }
    
    dataset = init_instance_by_config(dataset_config, default_module="qlib.data.dataset")
    
    # Cấu hình LGBModel
    model_config = {
        "class": "LGBModel",
        "module_path": "qlib.contrib.model.gbdt",
        "kwargs": LGBM_PARAMS
    }
    model = init_instance_by_config(model_config, default_module="qlib.contrib.model")
    
    # Train model
    model.fit(dataset)
    
    # Save model
    model_path = f"{output_dir}/{name}_model.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"  Saved: {model_path}")
    
    # Eval IC trên test set
    pred = model.predict(dataset, segment="test")
    # pred index: (datetime, instrument), columns: [score] hoặc là pd.Series
    if isinstance(pred, pd.Series):
        pred = pred.to_frame("score")
    else:
        pred.columns = ["score"]
        
    # Lấy label trực tiếp từ dataset.prepare
    test_label = dataset.prepare(segments="test", col_set="label")
    pred["label"] = test_label["LABEL0"]
    
    # Tính IC theo từng ngày
    daily_ic = pred.groupby(level="datetime").apply(
        lambda g: g["score"].corr(g["label"], method="spearman")
    )
    ic_val = daily_ic.mean()
    print(f"  Test IC ({name}): {ic_val:.4f}")
    
    return model, ic_val


# ── Ensemble Predictor ─────────────────────────────────────────────

class EnsemblePredictor:
    """
    Runtime: dùng đúng model theo regime hiện tại.
    
    Bull/Recovery → bull_model.pkl
    Bear/Sideways → bear_model.pkl
    
    Transition zone (regime mới < 3 ngày):
      blend 50/50 để tránh sudden switch
    """
    
    def __init__(self, ensemble_dir: str = "results/ensemble"):
        with open(f"{ensemble_dir}/bull_model.pkl", "rb") as f:
            self.bull_model = pickle.load(f)
        with open(f"{ensemble_dir}/bear_model.pkl", "rb") as f:
            self.bear_model = pickle.load(f)
        
        self.regime_history = []
    
    def predict(self, features: pd.DataFrame, current_regime: str) -> pd.Series:
        self.regime_history.append(current_regime)
        
        # Qlib models predict nhận values hoặc DataFrame
        try:
            bull_score = self.bull_model.model.predict(features.values)
            bear_score = self.bear_model.model.predict(features.values)
        except AttributeError:
            bull_score = self.bull_model.predict(features)
            bear_score = self.bear_model.predict(features)
            
        bull_series = pd.Series(bull_score, index=features.index)
        bear_series = pd.Series(bear_score, index=features.index)
        
        # Xác định weight blend
        bull_weight = self._get_bull_weight(current_regime)
        bear_weight = 1.0 - bull_weight
        
        blended = bull_series * bull_weight + bear_series * bear_weight
        print(f"  Regime: {current_regime} → bull×{bull_weight:.1f} + bear×{bear_weight:.1f}")
        return blended
    
    def _get_bull_weight(self, regime: str) -> float:
        base = 1.0 if regime in ["bull", "recovery"] else 0.0
        
        # Check transition: nếu regime vừa đổi → blend
        if len(self.regime_history) >= 2:
            prev = self.regime_history[-2]
            curr = self.regime_history[-1]
            if prev != curr:
                # Ngày đầu transition → 50/50
                return 0.5
        return base
    
    def get_current_regime(self, vnindex_path: str, date: str) -> str:
        regime = classify_market_regime(vnindex_path)
        try:
            return regime.loc[date]
        except KeyError:
            return regime.iloc[-1]


if __name__ == "__main__":
    vnindex_csv = "cache/VNINDEX_price.csv"
    regimes = classify_market_regime(vnindex_csv)
    print("\nRegime distribution (2018-2026):")
    print(regimes.value_counts(normalize=True).round(3))
    
    # Train
    train_specialist("bull", ["bull", "recovery"], regimes)
    train_specialist("bear", ["bear", "sideways"], regimes)
