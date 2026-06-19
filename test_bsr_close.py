import qlib
from qlib.data import D
qlib.init(provider_uri='/home/losbancos/.qlib/qlib_data/vn_data')
try:
    df = D.features(['BSR'], ['$close'], start_time='2018-01-01', end_time='2026-06-01')
    print('SUCCESS BSR $close')
except Exception as e:
    import traceback
    traceback.print_exc()
