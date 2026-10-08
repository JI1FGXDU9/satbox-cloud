#!/home/lily2004/ji1fgx.com/satbox-cloud/.venv/bin/python
import sys
import os
# Limit BLAS startup threads before any NumPy/Skyfield import.
for _name in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '1'
import traceback
sys.dont_write_bytecode=True
sys.path.insert(0,'/home/lily2004/ji1fgx.com/satbox-cloud')
try:
    from satbox_web.cgi_entry import main
    main()
except Exception:
    traceback.print_exc(file=sys.stderr)
    sys.stdout.write('Status: 500 Internal Server Error\r\nContent-Type: text/plain; charset=utf-8\r\nCache-Control: no-store\r\n\r\nSatBox startup failed. Check the server error log.\n')
