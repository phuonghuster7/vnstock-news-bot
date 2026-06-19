import qlib
from qlib.data import D
qlib.init(provider_uri='/home/losbancos/.qlib/qlib_data/vn_data')
print(D.calendar(start_time='2018-01-01', end_time='2018-01-10'))
