from multiprocessing import Pool
from typing import Optional, Type
import orjson
import gzip
from inspect import signature
from hugedict.mrsw_rocksdb import SecondarySyncedRocksDBDict
from hugedict.rocksdb import RocksDBDict
from hugedict.types import Fn
from loguru import logger


class ParallelFnWrapper:
    def __init__(self, fn: Fn, ignore_error=False):
        self.fn = fn
        # method of instances won't have `self` parameter, so we do not need to worry about it
        self.spread_fn_args = len(signature(fn).parameters) > 1
        self.ignore_error = ignore_error

    def run(self, args):
        idx, r = args
        try:
            if self.spread_fn_args:
                r = self.fn(*r)
            else:
                r = self.fn(r)
            return idx, r
        except:
            logger.error(f"[ParallelMap] Error while process item {idx}")
            if self.ignore_error:
                return idx, None
            raise


class SecondaryRocksDBCacheFn:
    def __init__(
        self,
        db: SecondarySyncedRocksDBDict[bytes, bytes],
        fn: Fn,
        namespace: str = "",
    ):
        self.db = db
        self.namespace = namespace

        self.fn = fn
        self.fn_name = fn.__name__

    def run(self, *args, **kwargs):
        key = orjson.dumps((self.fn_name, args, kwargs))

        if key not in self.db:
            output = self.fn(*args, **kwargs)
            self.db[key] = output
            return output

        return self.db[key]


class LazyRocksDBCacheFn:
    def __init__(
        self, db_class: Type[RocksDBDict], db_args: dict, fn: Fn, namespace: str = ""
    ):
        self.db_class = db_class
        self.db_args = db_args
        self.db: Optional[RocksDBDict] = None
        self.namespace = namespace

        self.fn = fn
        self.fn_name = fn.__name__

    def run(self, *args, **kwargs):
        key = orjson.dumps((self.fn_name, args, kwargs))
        if self.db is None:
            self.db = self.db_class(**self.db_args)

        if key not in self.db:
            output = self.fn(*args, **kwargs)
            self.db[key] = output
            return output

        return self.db[key]
