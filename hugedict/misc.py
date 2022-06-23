import functools
import gzip
import threading
import zstandard as zstd
import pickle
from typing import Any, Callable
from hugedict.types import T


container = threading.local()
container.zstd_3_compressor = zstd.ZstdCompressor(level=3)
container.zstd_6_compressor = zstd.ZstdCompressor(level=6)
container.zstd_decompressor = zstd.ZstdDecompressor()


def init_container(container):
    if not hasattr(container, "zstd_decompressor"):
        container.zstd_3_compressor = zstd.ZstdCompressor(level=3)
        container.zstd_6_compressor = zstd.ZstdCompressor(level=6)
        container.zstd_decompressor = zstd.ZstdDecompressor()


def identity(x):
    return x


def compress_pyobject(x):
    return gzip.compress(pickle.dumps(x), mtime=0)


def decompress_pyobject(x):
    return pickle.loads(gzip.decompress(x))


def zstd3_compress(x):
    global container
    init_container(container)
    return container.zstd_3_compressor.compress(x)


def zstd6_compress(x):
    global container
    init_container(container)
    return container.zstd_6_compressor.compress(x)


def zstd_decompress(x):
    global container
    init_container(container)
    return container.zstd_decompressor.decompress(x)


def compress_zstd3_pyobject(x):
    global container
    init_container(container)
    return container.zstd_3_compressor.compress(pickle.dumps(x))


def compress_zstd6_pyobject(x):
    global container
    init_container(container)
    return container.zstd_6_compressor.compress(pickle.dumps(x))


def decompress_zstd_pyobject(x):
    global container
    init_container(container)
    return pickle.loads(container.zstd_decompressor.decompress(x))


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
        global container
        init_container(container)
        return container.zstd_3_compressor.compress(ser_fn(x))

    return wrapper


def zstd6_compress_custom(ser_fn: Callable[[T], bytes]) -> Callable[[T], bytes]:
    @functools.wraps(ser_fn)
    def wrapper(x):
        global container
        init_container(container)
        return container.zstd_6_compressor.compress(ser_fn(x))

    return wrapper


def zstd_decompress_custom(deser_fn: Callable[[bytes], T]) -> Callable[[bytes], T]:
    @functools.wraps(deser_fn)
    def wrapper(x):
        global container
        init_container(container)
        return deser_fn(container.zstd_decompressor.decompress(x))

    return wrapper


class Chain2:
    def __init__(self, g, f):
        self.g = g
        self.f = f

    def exec(self, args):
        return self.g(self.f(args))

    def __call__(self, args):
        return self.g(self.f(args))


class Chain3:
    def __init__(self, h, g, f):
        self.h = h
        self.g = g
        self.f = f

    def exec(self, args):
        return self.h(self.g(self.f(args)))
