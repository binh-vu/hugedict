import enum, gc
import functools
import os
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4
from functools import partial
from multiprocessing.pool import Pool, ThreadPool
from multiprocessing.managers import BaseManager
from operator import itemgetter
import pickle
from typing import Any, List, Optional, Union
from hugedict.mrsw_rocksdb import PrimarySyncedRocksDBDict, SecondarySyncedRocksDBDict
from hugedict.parallel.fn_wrapper import ParallelFnWrapper, SecondaryRocksDBCacheFn
from hugedict.misc import identity, compress_pyobject, decompress_pyobject
from hugedict.rocksdb import RocksDBDict
from hugedict.types import Fn
from loguru import logger
from tqdm import tqdm


class Compressing(enum.Flag):
    NoCompression = enum.auto()
    # compress key won't work with gzip as it produce different keys everytime
    CompressValue = enum.auto()
    CompressAll = CompressValue


class MyManager(BaseManager):
    pass


MyManager.register("PrimarySyncedRocksDBDict", PrimarySyncedRocksDBDict)


class Parallel:
    def __init__(self, enable_bloomfilter=True):
        self._cache: List[SecondaryRocksDBCacheFn] = []
        self._cache_primary: list = []
        self.enable_bloomfilter = enable_bloomfilter

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
            for cache, db in zip(self._cache, dbs):
                cache.db = db
                cache.db.open()

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

        with self.pre_switch_cache() as dbargs:
            with self.switch_mrsw_cache(dbargs):

                if use_threadpool:
                    with ThreadPool(processes=n_processes) as pool:
                        iter = pool.imap_unordered(
                            ParallelFnWrapper(fn, ignore_error).run, enumerate(inputs)
                        )
                        if show_progress:
                            iter = tqdm(iter, total=len(inputs), desc=progress_desc)
                        results = list(iter)
                        results.sort(key=itemgetter(0))
                else:
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
        def wrapper_fn(func):
            if compress & Compressing.CompressValue:
                ser_value, deser_value = compress_pyobject, decompress_pyobject
            else:
                ser_value, deser_value = pickle.dumps, pickle.loads

            db = RocksDBDict(
                dbpath=dbpath,
                create_if_missing=True,
                deser_key=identity,
                ser_key=identity,
                deser_value=deser_value,
                ser_value=ser_value,
            )

            cache = SecondaryRocksDBCacheFn(
                db=db,  # type: ignore
                fn=func,
                namespace=namespace,
            )
            self._cache.append(cache)
            # return functools.update_wrapper(cache.run, func)
            return cache.run

        return wrapper_fn
