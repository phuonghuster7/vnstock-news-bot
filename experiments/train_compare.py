import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
import shutil
shutil.copy2 = shutil.copyfile
shutil.copy = shutil.copyfile

import yaml
import qlib
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord
from vnstock_qlib.features.alpha101 import VN_PRICE_FEATURES
import pickle

def run_experiment(dataset_yaml, output_dir):
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/vn_data")
    qlib.init(provider_uri=provider_uri)

    config_dir = os.path.join(os.path.dirname(__file__), "configs")
    with open(os.path.join(config_dir, dataset_yaml), "r") as f:
        dataset_config = yaml.safe_load(f)
    with open(os.path.join(config_dir, "lgbm_vn30.yaml"), "r") as f:
        model_config = yaml.safe_load(f)

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

    dataset = init_instance_by_config(dataset_config, default_module='qlib.data.dataset')
    model = init_instance_by_config(model_config, default_module='qlib.contrib.model')

    with R.start(experiment_name=f"train_{dataset_yaml}"):
        model.fit(dataset)
        rec = SignalRecord(model=model, dataset=dataset, recorder=R.get_recorder())
        rec.generate()
        pred = rec.recorder.load_object("pred.pkl")
        
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, "pred.pkl"), "wb") as f:
            pickle.dump(pred, f)
            
    print(f"Saved {dataset_yaml} predictions to {output_dir}/pred.pkl")

if __name__ == "__main__":
    run_experiment("dataset_vn30.yaml", "results/v3")
    run_experiment("dataset_vn30_v4.yaml", "results/v4")
