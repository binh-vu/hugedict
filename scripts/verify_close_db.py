import shutil
from hugedict_v1.rocksdb import RocksDBDict
from hugedict_v1.mrsw_rocksdb import *
from multiprocessing.pool import *
from hugedict_v1.parallel import MyManager

shutil.rmtree("/tmp/hugedict/test.db", ignore_errors=True)

db = RocksDBDict("/tmp/hugedict/test.db", create_if_missing=True)
db["a"] = "b"

print(">>> 1", db["a"])

# input("enter to close")

# input("enter to continue")
# with MyManager() as manager:
#     db.close()

#     db2 = manager.PrimarySyncedRocksDBDict(  # type: ignore
#         db.dbpath,
#         create_if_missing=True,
#     )
manager = MyManager()
try:
    db.close()
    manager.start()

    db2 = manager.PrimarySyncedRocksDBDict(  # type: ignore
        db.dbpath,
        create_if_missing=True,
    )
finally:
    manager.shutdown()
# db2 = RocksDBDict("/tmp/hugedict/test.db", create_if_missing=True)

# db2["a"] = "b"
# print(">>> 2", db2.get("a"))
