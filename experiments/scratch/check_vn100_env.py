import os
import sys
import pandas as pd
import numpy as np
from vnstock import Listing, Quote

def check_libs():
    libs = {}
    try:
        import vnstock_ta
        libs['vnstock_ta'] = True
    except ImportError:
        libs['vnstock_ta'] = False
    
    try:
        import ta
        libs['ta'] = True
    except ImportError:
        libs['ta'] = False
        
    try:
        import pandas_ta
        libs['pandas_ta'] = True
    except ImportError:
        libs['pandas_ta'] = False
    return libs

def get_vn100_symbols():
    try:
        listing = Listing(source="vci")
        symbols = listing.symbols_by_group(group_name="VN100", to_df=False)
        if not symbols:
            # Fallback to kbs
            listing_kbs = Listing(source="kbs")
            symbols = listing_kbs.symbols_by_group(group_name="VN100", to_df=False)
        return symbols
    except Exception as e:
        print("Error getting VN100 symbols:", e)
        return []

print("Checking available libraries...")
print(check_libs())

symbols = get_vn100_symbols()
print(f"Total VN100 symbols retrieved: {len(symbols)}")
if symbols:
    print("Sample symbols:", symbols[:10])
