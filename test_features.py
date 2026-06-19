import qlib
from qlib.data import D
from vnstock_qlib.features.alpha101 import VN_PRICE_FEATURES

qlib.init(provider_uri='/home/losbancos/.qlib/qlib_data/vn_data')

instruments = ['VCB']
for expr, name in VN_PRICE_FEATURES:
    try:
        df = D.features(instruments, [expr], start_time='2018-01-01', end_time='2018-01-10')
        print(f'[OK] {name}: {expr}')
    except Exception as e:
        print(f'[FAIL] {name}: {expr} -> {e}')

try:
    df = D.features(instruments, ['Ref(,-5)/-1'], start_time='2018-01-01', end_time='2018-01-10')
    print(f'[OK] LABEL: Ref(,-5)/-1')
except Exception as e:
    print(f'[FAIL] LABEL: Ref(,-5)/-1 -> {e}')
