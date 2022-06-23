import os
from tempfile import TemporaryDirectory
import orjson

from multiprocessing import Process, Pipe
import pybloomfilter


def process1(conn):
    msg = orjson.loads(conn.recv())
    assert msg["status"] == "start"
    bloomfilter = pybloomfilter.BloomFilter(10000, 0.1, msg["bloomfile"])
    bloomfilter.add(msg["key1"])
    conn.send(orjson.dumps({"status": "done", "has_key": msg["key1"] in bloomfilter}))

    msg = orjson.loads(conn.recv())
    assert msg["status"] == "start"
    bloomfilter.add(msg["key2"])
    conn.send(orjson.dumps({"status": "done", "has_key": msg["key2"] in bloomfilter}))


def process2(conn):
    msg = orjson.loads(conn.recv())
    assert msg["status"] == "start"
    bloomfilter = pybloomfilter.BloomFilter.open(msg["bloomfile"], "r")
    conn.send(orjson.dumps({"status": "done", "has_key": msg["key1"] in bloomfilter}))

    msg = orjson.loads(conn.recv())
    assert msg["status"] == "start"
    conn.send(orjson.dumps({"status": "done", "has_key": msg["key2"] in bloomfilter}))


def test_bloomfilter_shared_data():
    with TemporaryDirectory() as tempdir:
        bloomfile = os.path.join(tempdir, "bloomfilter")

        p1conn_pp, p1conn_cc = Pipe()
        p2conn_pp, p2conn_cc = Pipe()

        p1 = Process(target=process1, args=(p1conn_cc,))
        p1.start()

        p2 = Process(target=process2, args=(p2conn_cc,))
        p2.start()

        key1 = '["heavy_computing",[0.365],{}]'
        key2 = '["heavy_computing",[0.476],{}]'

        p1conn_pp.send(
            orjson.dumps({"status": "start", "bloomfile": bloomfile, "key1": key1})
        )
        assert orjson.loads(p1conn_pp.recv()) == {"status": "done", "has_key": True}

        p2conn_pp.send(
            orjson.dumps({"status": "start", "bloomfile": bloomfile, "key1": key1})
        )
        assert orjson.loads(p2conn_pp.recv()) == {"status": "done", "has_key": True}

        p1conn_pp.send(orjson.dumps({"status": "start", "key2": key2}))
        assert orjson.loads(p1conn_pp.recv()) == {"status": "done", "has_key": True}

        p2conn_pp.send(orjson.dumps({"status": "start", "key2": key2}))
        assert orjson.loads(p2conn_pp.recv()) == {"status": "done", "has_key": True}
