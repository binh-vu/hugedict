# Prerequisites:
# - install sem-desc: `pip install sem-desc`
# - data to test with in the ./data directory (e.g., ./data/wdentities/part-*.tsv.gz)
from functools import partial
import random
from loguru import logger
from matplotlib.style import available
import orjson
from dataclasses import dataclass
import multiprocessing
import shutil
from pathlib import Path
from typing import Optional

from hugedict.v1.loader import FileFormat, load
from rocksdb import DB, Options  # type: ignore
from sm.prelude import M

from hugedict.v1.rocksdb import RocksDBDict
from hugedict.hugedict.rocksdb import RocksDBDict as RustRocksDBDict, Options

bench_dir = Path(__file__).parent

if not (bench_dir / "tempdir" / "keys.txt.gz").exists():
    db = RocksDBDict(
        str(bench_dir / "tempdir" / "python-rocksdb.db"), deser_value=orjson.loads
    )

    keys = list(db.keys())
    M.serialize_lines(keys, bench_dir / "tempdir" / "keys.txt.gz")
    logger.info("Stop after creating list of keys. You need to rerun the script")
    exit(0)

keys = M.deserialize_lines(bench_dir / "tempdir" / "keys.txt.gz", trim=True)
random.shuffle(keys)
keys = keys[:3000]

db = RocksDBDict(
    str(bench_dir / "tempdir" / "python-rocksdb.db"), deser_value=orjson.loads
)
with M.Timer().watch_and_report("python-rocksdb"):
    count = 0
    for id in keys:
        count += len(db[id])

db2 = RustRocksDBDict(
    path=str(bench_dir / "tempdir" / "rust-rocksdb.db"),
    options=Options(),
    deser_key=partial(str, encoding="utf-8"),
    deser_value=orjson.loads,
    ser_value=orjson.dumps,
)
with M.Timer().watch_and_report("rust-rocksdb"):
    count = 0
    for id in keys:
        count += len(db2[id])

print("Done")
