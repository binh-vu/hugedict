from multiprocessing import Pool
from typing import Any, Callable, Optional, Type
import orjson
import inspect
from inspect import signature
from hugedict_v1.mrsw_rocksdb import SecondarySyncedRocksDBDict
from hugedict_v1.rocksdb import RocksDBDict
from hugedict.types import Fn
from loguru import logger


class ParallelFnWrapper:
    def __init__(self, fn: Fn, ignore_error=False):
        self.fn = fn
        # method of instances won't have `self` parameter, so we do not need to worry about it
        if hasattr(fn, "__self__") and isinstance(
            fn.__self__, (SecondaryRocksDBCacheFn, LazyRocksDBCacheFn)
        ):
            fn_params = signature(fn.__self__.fn).parameters
        else:
            fn_params = signature(fn).parameters
        self.spread_fn_args = len(fn_params) > 1
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

    def run_no_return(self, args):
        idx, r = args
        try:
            if self.spread_fn_args:
                r = self.fn(*r)
            else:
                r = self.fn(r)
            return idx, None
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
        self,
        db_class: Type[RocksDBDict],
        db_args: dict,
        fn: Fn,
        namespace: str = "",
        key: Optional[Callable[[str, tuple, dict], bytes]] = None,
    ):
        self.db_class = db_class
        self.db_args = db_args
        self.db: Optional[RocksDBDict] = None
        self.namespace = namespace

        self.fn = fn
        self.fn_name = (
            namespace + ":" + fn.__name__ if len(namespace) > 0 else fn.__name__
        )
        self.key = key or LazyRocksDBCacheFn.default_key

    def run(self, *args, **kwargs):
        key = self.key(self.fn_name, args, kwargs)
        if self.db is None:
            self.db = self.db_class(**self.db_args)

        if key not in self.db:
            output = self.fn(*args, **kwargs)
            self.db[key] = output
            return output

        return self.db[key]

    @staticmethod
    def default_key(fn_name, args, kwargs):
        return orjson.dumps((fn_name, args, kwargs))


class CacheFnKey:
    @staticmethod
    def single_str_arg(fn_name: str, args: tuple, kwargs: dict):
        return args[0].encode()
