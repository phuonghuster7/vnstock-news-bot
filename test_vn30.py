import qlib
from qlib.data import D
from vnstock_qlib.features.alpha101 import VN_PRICE_FEATURES
qlib.init(provider_uri='/home/losbancos/.qlib/qlib_data/vn_data')
exprs = [f[0] for f in VN_PRICE_FEATURES]
instruments = D.instruments('vn30')
symbols = D.list_instruments(instruments=instruments, start_time='2018-01-01', end_time='2026-06-01', as_list=True)
for sym in symbols:
    try:
        df = D.features([sym], exprs, start_time='2018-01-01', end_time='2026-06-01')
        print(f'[OK] {sym}')
    except Exception as e:
        print(f'[FAIL] {sym} -> {e}')
