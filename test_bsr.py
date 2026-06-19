import qlib
from qlib.data import D
from vnstock_qlib.features.alpha101 import VN_PRICE_FEATURES
qlib.init(provider_uri='/home/losbancos/.qlib/qlib_data/vn_data')
exprs = [f[0] for f in VN_PRICE_FEATURES]
for expr in exprs:
    try:
        df = D.features(['BSR'], [expr], start_time='2018-01-01', end_time='2026-06-01')
        print(f'[OK] {expr}')
    except Exception as e:
        print(f'[FAIL] {expr} -> {e}')
