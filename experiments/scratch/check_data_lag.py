import qlib, pandas as pd, os, shutil
os.environ['MLFLOW_ALLOW_FILE_STORE']='true'
shutil.copy2 = shutil.copyfile
shutil.copy  = shutil.copyfile
qlib.init(provider_uri=os.path.expanduser('~/.qlib/qlib_data/vn_data'))
from qlib.data import D
raw = D.features(['VCB','FPT','MBB'], ['$close'], start_time='2026-05-20', end_time='2026-06-09')
raw.columns = ['close']
raw = raw.reset_index()
raw['datetime'] = pd.to_datetime(raw['datetime'])
last = raw.dropna().groupby('instrument')['datetime'].max()
print("Last data date per symbol:")
print(last.to_string())
print("\nAll rows for VCB:")
print(raw[raw['instrument']=='VCB'].tail(10).to_string())
