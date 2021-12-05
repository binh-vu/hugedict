from pathlib import Path
import shutil
from multiprocessing import Process, Pipe
from loguru import logger
import pybloomfilter

tempdir = Path("/tmp/hugedict")
shutil.rmtree(tempdir, ignore_errors=True)
tempdir.mkdir(parents=True, exist_ok=True)

key = b'["heavy_computing",[0.365],{}]'
key2 = b'["heavy_computing",[0.476],{}]'


def process1(conn):
    assert conn.recv() == "start"

    logger.info("[process1] init bloom filter at: {}", str(tempdir / "bloomfilter"))

    bloomfilter = pybloomfilter.BloomFilter(10000, 0.1, str(tempdir / "bloomfilter"))
    bloomfilter.add(key)

    logger.info("[process1] has key: {}", key in bloomfilter)

    conn.send("done")

    assert conn.recv() == "start"
    bloomfilter.add(key2)
    logger.info("[process1] has key2: {}", key2 in bloomfilter)

    conn.send("done")


def process2(conn):
    assert conn.recv() == "start"

    logger.info("[process2] init bloom filter at: {}", str(tempdir / "bloomfilter"))
    # bloomfilter = pybloomfilter.BloomFilter(10000, 0.1, str(tempdir / "bloomfilter"))
    bloomfilter = pybloomfilter.BloomFilter.open(str(tempdir / "bloomfilter"), "r")
    logger.info("[process2] has key: {}", key in bloomfilter)

    conn.send("done")

    assert conn.recv() == "start"

    logger.info("[process1] has key2: {}", key2 in bloomfilter)

    conn.send("done")


logger.info("[main] time: t0")

p1conn_pp, p1conn_cc = Pipe()
p2conn_pp, p2conn_cc = Pipe()
p1 = Process(target=process1, args=(p1conn_cc,))
p1.start()

p2 = Process(target=process2, args=(p2conn_cc,))
p2.start()

p1conn_pp.send("start")
assert p1conn_pp.recv() == "done"

p2conn_pp.send("start")
assert p2conn_pp.recv() == "done"

p1conn_pp.send("start")
assert p1conn_pp.recv() == "done"
p2conn_pp.send("start")
assert p2conn_pp.recv() == "done"
