from pathlib import Path
import shutil
from hugedict.deprecated.rocksdb import RocksDBDict
from multiprocessing import Process, Queue, Pipe
from loguru import logger


tempdir = Path("/tmp/hugedict_test")
shutil.rmtree(tempdir, ignore_errors=True)
tempdir.mkdir(parents=True, exist_ok=True)

db = RocksDBDict(dbpath="/tmp/hugedict_test/test.db", create_if_missing=True)
db["aaa"] = "10"


def process1(conn):
    assert conn.recv() == "t0"

    logger.info("[process1] online")
    logger.info("[process1] see key aaa = {}", db.get("aaa", None))

    db["bbb"] = "20"
    logger.info("[process1] see key bbb = {}", db.get("bbb", None))
    logger.info("[process1] time: t1")
    conn.send("t1")


def process2(conn):
    assert conn.recv() == "t0"

    logger.info("[process2] online")
    logger.info("[process2] see key aaa = {}", db.get("aaa", None))

    assert conn.recv() == "t1"

    logger.info("[process2] see key bbb = {}", db.get("bbb", None))


logger.info("[main] time: t0")

p1conn_pp, p1conn_cc = Pipe()
p2conn_pp, p2conn_cc = Pipe()
p1 = Process(target=process1, args=(p1conn_cc,))
p1.start()

p2 = Process(target=process2, args=(p2conn_cc,))
p2.start()

p1conn_pp.send("t0")
p2conn_pp.send("t0")

assert p1conn_pp.recv() == "t1"
p2conn_pp.send("t1")

p1.join()
p2.join()
