## PyWasp - Python bindings for [WASP](https://dtspedia.intel.com/Conduit-data-warehouse) REST API
[![pipeline](https://github.com/intel-innersource/libraries.python.py-wasp/actions/workflows/status.yml/badge.svg)](https://github.com/intel-innersource/libraries.python.py-wasp/actions)

Tested for Windows with:
    Python 3.6
and Linux:
    /p/dpg/arch/perfhome/python/miniconda

Linux install path:
    /p/dpg/arch/perfhome/py_wasp

Examples
========

Reading a record
================
```python
from py_wasp import Wasp

server_url = "http://iapp405.iil.intel.com:2232"
collection = "wsiv_traces"

api = Wasp(server_urls=[server_url])

# get list of records
records = api.find_records(collection)
print(records[0])

# access file data:
record = records[0]
file = record['raw_data']['etl']

content = file.read()
# or
file.to_file("/path/to/output/directory")

```

Adding a record
===============
```python
from pyconduit import Wasp, FileValue

server_url = "http://iapp405.iil.intel.com:2232"
collection = "wsiv_traces"
socwatch_file = 'C:/my/data.csv'
log_file 'C:/my/log.txt'

api = Wasp(server_urls=[server_url])

# a record is JSON object (represented by dict)
# FileValue() is used to specify files to be uploaded to Wasp
record = {
  'platform': 'SKL',
  'cpu_num_cores': 4,
  'cpu_freq': 1.8,
  'files': {
    'socwatch': FileValue(socwatch_file)
    'log_file': FileValue(log_file)
  }
}

record_with_id = api.add_record(collection, record)
print("Record ID in conduit:", record_with_id['_id'])

```