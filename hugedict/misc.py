import functools
import gzip
import zstandard as zstd
import pickle
from typing import Any, Callable
from hugedict.types import T


zstd_3_compressor = zstd.ZstdCompressor(level=3)
zstd_6_compressor = zstd.ZstdCompressor(level=6)
zstd_decompressor = zstd.ZstdDecompressor()


def identity(x):
    return x


def compress_pyobject(x):
    return gzip.compress(pickle.dumps(x), mtime=0)


def decompress_pyobject(x):
    return pickle.loads(gzip.decompress(x))


def zstd3_compress(x):
    return zstd_3_compressor.compress(x)


def zstd6_compress(x):
    return zstd_6_compressor.compress(x)


def zstd_decompress(x):
    return zstd_decompressor.decompress(x)


def compress_zstd3_pyobject(x):
    return zstd_3_compressor.compress(pickle.dumps(x))


def compress_zstd6_pyobject(x):
    return zstd_6_compressor.compress(pickle.dumps(x))


def decompress_zstd_pyobject(x):
    return pickle.loads(zstd_decompressor.decompress(x))


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


def zstd3_compress_custom(ser_fn: Callable[[T], bytes]) -> Callable[[T], bytes]:
    @functools.wraps(ser_fn)
    def wrapper(x):
        return zstd_3_compressor.compress(ser_fn(x))

    return wrapper


def zstd6_compress_custom(ser_fn: Callable[[T], bytes]) -> Callable[[T], bytes]:
    @functools.wraps(ser_fn)
    def wrapper(x):
        return zstd_6_compressor.compress(ser_fn(x))

    return wrapper


def zstd_decompress_custom(deser_fn: Callable[[bytes], T]) -> Callable[[bytes], T]:
    @functools.wraps(deser_fn)
    def wrapper(x):
        return deser_fn(zstd_decompressor.decompress(x))

    return wrapper


class Chain2:
    def __init__(self, g, f):
        self.g = g
        self.f = f

    def exec(self, args):
        return self.g(self.f(args))
