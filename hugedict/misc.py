from functools import partial
import gzip
import pickle

from hugedict.rocksdb import RocksDBDict


def identity(x):
    return x


def compress_pyobject(x):
    return gzip.compress(pickle.dumps(x))


def decompress_pyobject(x):
    return pickle.loads(gzip.decompress(x))
