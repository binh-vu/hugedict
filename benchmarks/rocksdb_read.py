# Prerequisites:
# - install sem-desc: `pip install sem-desc`
# - data to test with in the ./data directory (e.g., ./data/wdentities/part-*.tsv.gz)
import random
from functools import partial
from pathlib import Path

import orjson
import serde.textline
from hugedict_v1.rocksdb import RocksDBDict
from loguru import logger
from timer import Timer

from hugedict.rocksdb import Options as RustOptions
from hugedict.rocksdb import RocksDBDict as RustRocksDBDict
from rocksdb import DB, Options  # type: ignore

bench_dir = Path(__file__).parent

if not (bench_dir / "tempdir" / "keys.txt.gz").exists():
    db = RocksDBDict(
        str(bench_dir / "tempdir" / "python-rocksdb.db"), deser_value=orjson.loads
    )

    keys = list(db.keys())
    serde.textline.ser(keys, bench_dir / "tempdir" / "keys.txt.gz")
    logger.info("Stop after creating list of keys. You need to rerun the script")
    exit(0)

keys = serde.textline.deser(bench_dir / "tempdir" / "keys.txt.gz", trim=True)
random.shuffle(keys)
keys = keys[:3000]

db = RocksDBDict(
    str(bench_dir / "tempdir" / "python-rocksdb.db"), deser_value=orjson.loads
)
with Timer().watch_and_report("python-rocksdb"):
    count = 0
    for id in keys:
        count += len(db[id])

db2 = RustRocksDBDict(
    path=str(bench_dir / "tempdir" / "rust-rocksdb.db"),
    options=RustOptions(),
    deser_key=partial(str, encoding="utf-8"),
    deser_value=orjson.loads,
    ser_value=orjson.dumps,
)
with Timer().watch_and_report("rust-rocksdb"):
    count = 0
    for id in keys:
        count += len(db2[id])

print("Done")
