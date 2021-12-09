import functools
import gzip
import pickle
from typing import Any, Callable
from hugedict.types import T


def identity(x):
    return x


def compress_pyobject(x):
    return gzip.compress(pickle.dumps(x), mtime=0)


def decompress_pyobject(x):
    return pickle.loads(gzip.decompress(x))


def compress_custom(ser_fn: Callable[[T], bytes]) -> Callable[[T], bytes]:
    @functools.wraps(ser_fn)
    def wrapper(x):
        return gzip.compress(ser_fn(x), mtime=0)

    return wrapper


def decompress_custom(deser_fn: Callable[[bytes], T]) -> Callable[[bytes], T]:
    @functools.wraps(deser_fn)
    def wrapper(x):
        return deser_fn(gzip.decompress(x))

    return wrapper
