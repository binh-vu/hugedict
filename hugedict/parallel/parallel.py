import enum, gc
import functools
import os
from contextlib import contextmanager
from pathlib import Path
import shutil
from uuid import uuid4
from functools import partial
from multiprocessing.pool import Pool, ThreadPool
from multiprocessing.managers import BaseManager, SyncManager
from operator import itemgetter
import pickle
from typing import Any, List, Optional, Union
from hugedict.mrsw_rocksdb import PrimarySyncedRocksDBDict, SecondarySyncedRocksDBDict
from hugedict.parallel.fn_wrapper import (
    LazyRocksDBCacheFn,
    ParallelFnWrapper,
    SecondaryRocksDBCacheFn,
)
from hugedict.misc import identity, compress_pyobject, decompress_pyobject
from hugedict.rocksdb import RocksDBDict
from hugedict.types import Fn
from loguru import logger
from tqdm import tqdm


class Compressing(enum.Flag):
    NoCompression = enum.auto()
    CompressKey = enum.auto()
    CompressValue = enum.auto()
    CompressAll = CompressValue | CompressKey


class MyManager(SyncManager):
    pass


MyManager.register("PrimarySyncedRocksDBDict", PrimarySyncedRocksDBDict)


class Parallel:
    def __init__(self, enable_bloomfilter=True):
        self._cache: List[LazyRocksDBCacheFn] = []
        self._cache_primary: list = []
        self.enable_bloomfilter = enable_bloomfilter

    @contextmanager
    def init_cache(self):
        try:
            for cache in self._cache:
                if cache.db is not None:
                    cache.db.close()
                    cache.db = None
            yield
        finally:
            for cache in self._cache:
                if cache.db is not None:
                    cache.db.close()
                    cache.db = None

    @contextmanager
    def pre_switch_cache(self):
        dbs = []
        for cache in self._cache:
            dbs.append(cache.db)
        try:
            db_args = []
            for cache, db in zip(self._cache, dbs):
                cache.db = None  # type: ignore
                db_args.append(
                    dict(
                        dbpath=db.dbpath,
                        create_if_missing=True,
                        deser_key=db.deser_key,
                        ser_key=db.ser_key,
                        deser_value=db.deser_value,
                        ser_value=db.ser_value,
                    )
                )
                db.close()
            yield db_args
        finally:
            pass
            # for cache, db in zip(self._cache, dbs):
            #     cache.db = db
            #     cache.db.open()

    @contextmanager
    def switch_mrsw_cache(self, db_args: List[dict]):
        with MyManager() as manager:
            for cache, db_arg in zip(self._cache, db_args):
                # remove previous bloom filter if exists
                bloomfilter = os.path.join(db_arg["dbpath"], "bloomfilter")
                if os.path.exists(bloomfilter):
                    os.remove(bloomfilter)

                primary = manager.PrimarySyncedRocksDBDict(enable_bloomfilter=self.enable_bloomfilter, **db_arg)  # type: ignore
                cache.db = SecondarySyncedRocksDBDict(
                    primary=primary,
                    dbpath=db_arg["dbpath"],
                    secondary_name=str(uuid4()).replace("-", ""),
                    deser_key=db_arg["deser_key"],
                    ser_key=db_arg["ser_key"],
                    deser_value=db_arg["deser_value"],
                    ser_value=db_arg["ser_value"],
                    enable_bloomfilter=self.enable_bloomfilter,
                )
            yield

    @contextmanager
    def switch_mrsw_cache2(self):
        with MyManager() as manager:
            lst_db_args = []
            try:
                for cache in self._cache:
                    assert cache.db is None, "Freshly start db"
                    # clean previous files except primary db
                    dbpath = cache.db_args["dbpath"]
                    if dbpath.exists():
                        for file in dbpath.iterdir():
                            if file.name != "primary":
                                if file.is_dir():
                                    shutil.rmtree(file)
                                else:
                                    file.unlink()

                    primary = manager.PrimarySyncedRocksDBDict(  # type: ignore
                        enable_bloomfilter=self.enable_bloomfilter, **cache.db_args
                    )
                    cache.db_class = SecondarySyncedRocksDBDict
                    lst_db_args.append(cache.db_args.copy())
                    del cache.db_args["create_if_missing"]
                    cache.db_args["enable_bloomfilter"] = self.enable_bloomfilter
                    cache.db_args["primary"] = primary
                    cache.db_args["secondary_name"] = str(uuid4()).replace("-", "")
                    cache.db = cache.db_class(**cache.db_args)
                yield
            finally:
                for cache, db_args in zip(self._cache, lst_db_args):
                    cache.db_args = db_args

    def map(
        self,
        fn: Fn,
        inputs: list,
        show_progress=False,
        progress_desc="",
        is_parallel=True,
        use_threadpool=False,
        n_processes: Optional[int] = None,
        ignore_error: bool = False,
    ) -> List[Any]:
        if not is_parallel:
            iter = (fn(item) for item in inputs)
            if show_progress:
                iter = tqdm(iter, total=len(inputs), desc=progress_desc)
            return list(iter)

        if use_threadpool:
            # it won't break rocksdb when using threadpool because of GIL.
            with ThreadPool(processes=n_processes) as pool:
                iter = pool.imap_unordered(
                    ParallelFnWrapper(fn, ignore_error).run, enumerate(inputs)
                )
                if show_progress:
                    iter = tqdm(iter, total=len(inputs), desc=progress_desc)
                results = list(iter)
                results.sort(key=itemgetter(0))
        else:
            # have to switch to multi read single write mode
            # with self.pre_switch_cache() as x:
            #     with self.switch_mrsw_cache(x):
            with self.init_cache():
                with self.switch_mrsw_cache2():
                    # start a pool of processes
                    with Pool(processes=n_processes) as pool:
                        iter = pool.imap_unordered(
                            ParallelFnWrapper(fn, ignore_error).run, enumerate(inputs)
                        )
                        if show_progress:
                            iter = tqdm(iter, total=len(inputs), desc=progress_desc)
                        results = list(iter)
                        results.sort(key=itemgetter(0))

        return [v for i, v in results]

    def cache_func(
        self,
        dbpath: Union[Path, str],
        namespace: str = "",
        compress=Compressing.NoCompression,
    ):
        """Cache a function (only work when using with Parallel object)"""

        def wrapper_fn(func):
            if compress & Compressing.CompressKey:
                ser_key, deser_key = compress_pyobject, decompress_pyobject
            else:
                ser_key, deser_key = identity, identity

            if compress & Compressing.CompressValue:
                ser_value, deser_value = compress_pyobject, decompress_pyobject
            else:
                ser_value, deser_value = pickle.dumps, pickle.loads

            cache = LazyRocksDBCacheFn(
                db_class=RocksDBDict,
                db_args=dict(
                    dbpath=Path(dbpath),
                    create_if_missing=True,
                    deser_key=deser_key,
                    ser_key=ser_key,
                    deser_value=deser_value,
                    ser_value=ser_value,
                ),
                fn=func,
                namespace=namespace,
            )
            # db = RocksDBDict(
            #     dbpath=dbpath,
            #     create_if_missing=True,
            #     deser_key=identity,
            #     ser_key=identity,
            #     deser_value=deser_value,
            #     ser_value=ser_value,
            # )

            # cache = SecondaryRocksDBCacheFn(
            #     db=db,  # type: ignore
            #     fn=func,
            #     namespace=namespace,
            # )

            self._cache.append(cache)
            # return functools.update_wrapper(cache.run, func)
            return cache.run

        return wrapper_fn
