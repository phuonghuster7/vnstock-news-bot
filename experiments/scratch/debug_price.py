import os, pandas as pd
os.environ['MLFLOW_ALLOW_FILE_STORE']='true'
import shutil; shutil.copy2=shutil.copyfile; shutil.copy=shutil.copyfile
import qlib
from qlib.data import D
from datetime import timedelta
qlib.init(provider_uri=os.path.expanduser('~/.qlib/qlib_data/vn_data'))
today = '2026-06-08'
start = '2026-05-28'
syms = ['BVH','VNM','MBB']
raw = D.features(syms, ['$close', '$volume'], start_time=start, end_time=today)
raw.columns=['close','volume']
raw = raw.reset_index()
raw['datetime'] = pd.to_datetime(raw['datetime'])
print(raw.tail(12).to_string())
print('dtypes:', raw.dtypes.to_dict())
print('close sample:', raw['close'].values[:5])
