import os
import yaml
import pandas as pd
import numpy as np
import qlib
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord
import pickle

def main():
    os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
    import shutil
    shutil.copy2 = shutil.copyfile
    shutil.copy = shutil.copyfile

    qlib.init(provider_uri=os.path.expanduser("~/.qlib/qlib_data/vn_data"))

    config_dir = os.path.join(os.path.dirname(__file__), "configs")
    
    with open(os.path.join(config_dir, "dataset_vn30_v5.yaml"), "r") as f:
        dataset_config = yaml.safe_load(f)
        
    with open(os.path.join(config_dir, "lgbm_vn30.yaml"), "r") as f:
        model_config = yaml.safe_load(f)

    # Dynamic features loading
    from vnstock_qlib.features.alpha101 import VN_PRICE_FEATURES
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

    print(f"Features: {names}")

    dataset = init_instance_by_config(dataset_config, default_module='qlib.data.dataset')
    model = init_instance_by_config(model_config, default_module='qlib.contrib.model')

    exp_name = "train_v5"
    with R.start(experiment_name=exp_name):
        model.fit(dataset)
        rec = SignalRecord(model=model, dataset=dataset, recorder=R.get_recorder())
        rec.generate()
        pred = rec.recorder.load_object("pred.pkl")
        
        out_dir = os.path.join(os.path.dirname(__file__), "..", "results", "v5")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "pred.pkl")
        with open(out_path, "wb") as f:
            pickle.dump(pred, f)
            
        print(f"Predictions saved to {out_path}")

if __name__ == "__main__":
    main()
