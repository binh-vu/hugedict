# hugedict ![PyPI](https://img.shields.io/pypi/v/hugedict)

A dictionary-like object that is friendly with multiprocessing and uses key-value databases (e.g., RocksDB) as the underlying storage.

## Installation

```bash
pip install hugedict
```

## Usage

```python
from hugedict.rocksdb import RocksDBDict

# replace K and V for the types you are using
mapping: Dict[K, V] = RocksDBDict(
    dbpath,  # path to db file
    create_if_missing=create_if_missing,  # whether to create database if missing
    read_only=read_only,  # open database in read only mode
    deser_key=bytes.decode,  # decode the key from bytes
    ser_key=str.encode,  # encode the key to bytes
    deser_value=bytes.decode,  # decode the value from bytes
    ser_value=str.encode,  # encode the value from bytes
    db_options=db_options,  # other rocksdb options
)
```
