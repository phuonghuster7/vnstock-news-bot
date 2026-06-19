import qlib
from qlib.data import D
import os
QLIB_DIR = os.path.expanduser("~/.qlib/qlib_data/vn_data")
qlib.init(provider_uri=QLIB_DIR)
try:
    df = D.features(["VNINDEX"], ["$close"], start_time="2020-01-01", end_time="2025-12-31")
    print("VNINDEX Qlib shape:", df.shape if df is not None else "None")
    if df is not None:
        print(df.head())
except Exception as e:
    print("Error:", e)
