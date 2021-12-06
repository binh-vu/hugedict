import gzip
import pickle


def identity(x):
    return x


def compress_pyobject(x):
    return gzip.compress(pickle.dumps(x), mtime=0)


def decompress_pyobject(x):
    return pickle.loads(gzip.decompress(x))
