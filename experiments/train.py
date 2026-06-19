import os
os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
import shutil
shutil.copy2 = shutil.copyfile
shutil.copy = shutil.copyfile
import yaml
import qlib
from qlib.utils import init_instance_by_config
from qlib.workflow import R
from qlib.workflow.record_temp import SignalRecord, PortAnaRecord
from vnstock_qlib.features.alpha101 import VN_PRICE_FEATURES
from vnstock_qlib.features.fundamental import VN_FUNDAMENTAL_FEATURES

def main():
    # 1. Initialize Qlib
    provider_uri = os.path.expanduser("~/.qlib/qlib_data/vn_data")
    qlib.init(provider_uri=provider_uri)

    # 2. Load configs
    config_dir = os.path.dirname(__file__)
    with open(os.path.join(config_dir, "configs", "dataset_vn30.yaml"), "r") as f:
        dataset_config = yaml.safe_load(f)
    with open(os.path.join(config_dir, "configs", "lgbm_vn30.yaml"), "r") as f:
        model_config = yaml.safe_load(f)

    # Inject features dynamically
    features = [f[0] for f in VN_PRICE_FEATURES]
    names = [f[1] for f in VN_PRICE_FEATURES]
    
    # Update DataHandler config
    dataset_config["kwargs"]["handler"]["kwargs"]["data_loader"] = {
        "class": "QlibDataLoader",
        "kwargs": {
            "config": {
                "feature": (features, names),
                "label": (dataset_config["kwargs"]["handler"]["kwargs"].pop("label"), ["LABEL0"])
            }
        }
    }

    # 3. Instantiate Dataset and Model
    print("Preparing dataset...")
    dataset = init_instance_by_config(dataset_config, default_module='qlib.data.dataset')
    print("Initializing model...")
    model = init_instance_by_config(model_config, default_module='qlib.contrib.model')

    # 4. Train Model
    with R.start(experiment_name="train_lgbm_vn30"):
        print("Training model...")
        model.fit(dataset)
        R.save_objects(trained_model=model)

        print("Generating predictions...")
        # Record signal (predictions)
        rec = SignalRecord(model=model, dataset=dataset, recorder=R.get_recorder())
        rec.generate()
        
        print("\n" + "="*40)
        print("TRAINING RESULT")
        print("Model trained and predictions generated successfully!")
        print("="*40)
        print("Model saved to MLflow tracking / Qlib records")

if __name__ == "__main__":
    main()
