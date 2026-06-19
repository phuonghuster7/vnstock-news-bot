import os
import json
from vnstock import *

# Check home directory auth path
home_dir = os.path.expanduser("~")
auth_path = os.path.join(home_dir, ".vnstock", "auth_state.json")
print("Auth Path:", auth_path)
if os.path.exists(auth_path):
    try:
        with open(auth_path, "r", encoding="utf-8") as f:
            print("Auth data:", json.load(f))
    except Exception as e:
        print("Error reading auth file:", e)
else:
    print("Auth file does not exist")

# Try to get list of symbols
try:
    df_symbols = Listing().all_symbols()
    print("Number of symbols:", len(df_symbols))
    print(df_symbols.head())
except Exception as e:
    print("Error listing symbols:", e)
