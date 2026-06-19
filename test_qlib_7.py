import qlib
from qlib.data import D
from qlib.data.dataset import DatasetH
from qlib.data.dataset.handler import DataHandlerLP
qlib.init(provider_uri='/home/losbancos/.qlib/qlib_data/vn_data')
dh = DataHandlerLP(
    instruments='vn30',
    start_time='2018-01-01',
    end_time='2026-06-01',
    infer_processors=[],
    learn_processors=[],
    data_loader={
        'class': 'QlibDataLoader',
        'kwargs': {
            'config': {
                'feature': ([''], ['close']),
                'label': (['Ref(,-5)/-1'], ['LABEL0'])
            }
        }
    }
)
print('SUCCESS HANDLER')
