from functools import partial
import time
from multiprocessing import Process, freeze_support
from pathlib import Path
from hugedict.hugedict.rocksdb import Options, SecondaryDB, primary_db, stop_primary_db
import sys


bench_dir = Path(__file__).parent.parent / "benchmarks"
dbpath = f"{bench_dir}/tempdir/rust-rocksdb.db"
url = "ipc:///tmp/test.ipc"
print(url)

if sys.argv[1] == "primary":
    primary_db(url, dbpath, Options())
elif sys.argv[1] == "stop":
    stop_primary_db(url)
else:
    db = SecondaryDB(
        url,
        dbpath,
        f"{dbpath}/secondaries/0",
        Options(),
        deser_value=partial(str, encoding="utf-8"),
        ser_value=str.encode,
    )
    db["P58"] = "screenwriter"
    print(db[sys.argv[1]])
