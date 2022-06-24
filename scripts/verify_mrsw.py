from functools import partial
import time
from multiprocessing import Process, freeze_support
from pathlib import Path
from hugedict.hugedict.rocksdb import Options, SecondaryDB, primary_db, stop_primary_db
import sys


dbpath = "/Users/rook/workspace/hugedict/benchmarks/tempdir/rust-rocksdb.db"
url = "ipc:///tmp/test.ipc"
print(url)

if __name__ == "__main__":
    freeze_support()
    p = Process(target=primary_db, args=(url, dbpath, Options()))
    p.start()
    assert p.exitcode is None

    # stop it
    stop_primary_db(url)

    # wait max 3 seconds
    p.join(3)
    assert p.exitcode == 0

# if sys.argv[1] == "primary":
#     primary_db(url, dbpath, Options())
# else:
#     db = SecondaryDB(
#         url,
#         dbpath,
#         f"{dbpath}/secondaries/0",
#         Options(),
#         deser_value=partial(str, encoding="utf-8"),
#         ser_value=str.encode,
#     )
#     db["P58"] = "screenwriter"
#     print(db["P59"])
#     # stop_primary_db(url)
