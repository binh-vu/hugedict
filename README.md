# hugedict ![PyPI](https://img.shields.io/pypi/v/hugedict) ![Documentation](https://readthedocs.org/projects/hugedict/badge/?version=latest&style=flat)

hugedict provides a drop-in replacement for dictionary objects that are too big to fit in memory. hugedict's dictionary-like objects implement `typing.Mapping` and `typing.MutableMapping` interfaces using key-value databases (e.g., RocksDB) as the underlying storage. Moreover, they are friendly with Python's multiprocessing.

- [Documentation](https://hugedict.readthedocs.io/)

## Installation

From PyPI (using pre-built binaries):

```bash
pip install hugedict
```

To compile the source, run: `maturin build -r` inside the project directory. You need [Rust](https://www.rust-lang.org/), [Maturin](https://github.com/PyO3/maturin), CMake and CLang (to build [Rust-RocksDB](https://github.com/rust-rocksdb/rust-rocksdb)).

## Features

1. Create a mutable mapping backed by RocksDB

```python
from functools import partial
from hugedict.prelude import RocksDBDict, RocksDBOptions

# replace [str, str] for the types of keys and values you want
# as well as deser_key, deser_value, ser_value
mapping: MutableMapping[str, str] = RocksDBDict(
    path=dbpath,  # path (str) to db file
    options=RocksDBOptions(create_if_missing=create_if_missing),  # whether to create database if missing, check other options
    deser_key=partial(str, encoding="utf-8"),  # decode the key from memoryview
    deser_value=partial(str, encoding="utf-8"),  # decode the value from memoryview
    ser_value=str.encode,  # encode the value to bytes
    readonly=False,  # open database in read only mode
    secondary_mode=False,  # open database in secondary mode
    secondary_path=None,  # when secondary_mode is True, it's a string pointing to a directory for storing data required to operate in secondary mode
)
```

2. Load huge data from files into RocksDB in parallel: `from hugedict.prelude import rocksdb_load`. This function creates SST files in parallel, ingests into the db and (optionally) compacts them.

3. Cache a function when doing parallel processing

```python
from hugedict.prelude import Parallel

pp = Parallel()

@pp.cache_func("/tmp/test.db")
def heavy_computing(seconds: float):
    time.sleep(seconds)
    return seconds * 2


output = pp.map(heavy_computing, [0.5, 1, 0.7, 0.3, 0.6], n_processes=3)
```
