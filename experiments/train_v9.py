"""
Train Model V9: Tuned LightGBM on VN100 clean universe.
"""
import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
import shutil
shutil.copy2 = shutil.copyfile
shutil.copy = shutil.copyfile

import yaml
import pickle
import qlib
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord
from vnstock_qlib.features.alpha101 import VN_PRICE_FEATURES

def main():
    # Sử dụng vn_data mặc định vì build_data đã build vào vn_data
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/vn_data")
    qlib.init(provider_uri=provider_uri)

    config_dir = os.path.join(os.path.dirname(__file__), "configs")
    with open(os.path.join(config_dir, "dataset_vn100_v9.yaml"), "r") as f:
        dataset_config = yaml.safe_load(f)

    tuned_model_path = os.path.join(config_dir, "lgbm_vn30_tuned.yaml")
    model_path = tuned_model_path if os.path.exists(tuned_model_path) else os.path.join(config_dir, "lgbm_vn30.yaml")
    print(f"Using model config: {os.path.basename(model_path)}")
    with open(model_path, "r") as f:
        model_config = yaml.safe_load(f)

    features = [f[0] for f in VN_PRICE_FEATURES]
    names    = [f[1] for f in VN_PRICE_FEATURES]
    
    print(f"Base features: {len(features)} (SectorMomentumProcessor will add sector_ret_5d + sector_rel_ret)")

    dataset_config["kwargs"]["handler"]["kwargs"]["data_loader"] = {
        "class": "QlibDataLoader",
        "kwargs": {
            "config": {
                "feature": (features, names),
                "label": (dataset_config["kwargs"]["handler"]["kwargs"].pop("label"), ["LABEL0"])
            }
        }
    }

    print("Preparing dataset V9 (VN100)...")
    dataset = init_instance_by_config(dataset_config, default_module='qlib.data.dataset')
    print("Initializing model...")
    model = init_instance_by_config(model_config, default_module='qlib.contrib.model')

    with R.start(experiment_name="train_lgbm_vn100_v9"):
        print("Training model V9 (VN100)...")
        model.fit(dataset)
        R.save_objects(trained_model=model)

        print("Generating predictions...")
        rec = SignalRecord(model=model, dataset=dataset, recorder=R.get_recorder())
        rec.generate()
        pred = rec.recorder.load_object("pred.pkl")

        out_dir = "results/v9_vn100"
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "pred.pkl"), "wb") as f:
            pickle.dump(pred, f)

        print("\n" + "="*40)
        print("TRAINING V9 COMPLETE (VN100)")
        print(f"Predictions saved to {out_dir}/pred.pkl")
        print("="*40)

if __name__ == "__main__":
    main()
