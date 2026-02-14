import importlib, traceback
try:
    m = importlib.import_module('protocol')
    print('imported protocol:', hasattr(m, 'get_ack_timeout'))
except Exception as e:
    print('ERR', type(e), e)
    traceback.print_exc()

try:
    m2 = importlib.import_module('akita_vmail.protocol')
    print('imported akita_vmail.protocol:', hasattr(m2, 'get_ack_timeout'))
except Exception as e:
    print('ERR2', type(e), e)
    traceback.print_exc()
