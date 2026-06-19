import qlib
from qlib.data import D
qlib.init(provider_uri='/home/losbancos/.qlib/qlib_data/vn_data')
try:
    df = D.features(['VCB'], [''], start_time='2018-01-01', end_time='2018-01-10')
    print('SUCCESS PE')
    print(df.head())
except Exception as e:
    import traceback
    traceback.print_exc()
