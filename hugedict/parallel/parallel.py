import enum, gc
import functools
from logging import disable
import os
from contextlib import contextmanager
from pathlib import Path
import shutil
from uuid import uuid4
from functools import partial
from multiprocessing.pool import Pool, ThreadPool
from multiprocessing.managers import BaseManager, SharedMemoryManager, SyncManager
from operator import itemgetter
import pickle
from typing import Any, Callable, List, Optional, Union
from hugedict.mrsw_rocksdb import SecondarySyncedRocksDBDict
from hugedict.parallel.fn_wrapper import (
    LazyRocksDBCacheFn,
    ParallelFnWrapper,
)
from hugedict.misc import identity, compress_pyobject, decompress_pyobject
from hugedict.parallel.manager import (
    MB,
    MyManager,
    SharedMemoryDictClient,
)
from hugedict.rocksdb import RocksDBDict
from hugedict.types import Fn
from loguru import logger
from tqdm import tqdm


class Compressing(enum.Flag):
    NoCompression = enum.auto()
    CompressKey = enum.auto()
    CompressValue = enum.auto()
    CompressAll = CompressValue | CompressKey


class Parallel:
    def __init__(
        self,
        enable_bloomfilter=True,
        enable_shared_memory=False,
        min_increase_shm_mb_size=2,
    ):
        self._cache: List[LazyRocksDBCacheFn] = []
        self._cache_primary: list = []
        self.enable_shared_memory = enable_shared_memory
        self.enable_bloomfilter = enable_bloomfilter
        self.min_increase_shm_size = int(min_increase_shm_mb_size * MB)

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
    def switch_mrsw_cache(self):
        with MyManager() as manager:
            lst_db_args = []
            servers = []
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

                    if self.enable_shared_memory:
                        server = manager.SharedMemoryPrimarySyncedRocksDBDict(  # type: ignore
                            enable_bloomfilter=self.enable_bloomfilter, **cache.db_args
                        )
                        servers.append(server)
                        primary = SharedMemoryDictClient(
                            server, min_increase_size=self.min_increase_shm_size
                        )
                    else:
                        primary = manager.PrimarySyncedRocksDBDict(  # type: ignore
                            enable_bloomfilter=self.enable_bloomfilter, **cache.db_args
                        )
                    cache.db_class = SecondarySyncedRocksDBDict
                    lst_db_args.append(cache.db_args.copy())
                    del cache.db_args["create_if_missing"]
                    cache.db_args["primary"] = primary
                    cache.db_args["enable_bloomfilter"] = self.enable_bloomfilter
                    cache.db_args["secondary_name"] = str(uuid4()).replace("-", "")
                yield
            finally:
                for server in servers:
                    server.unlink_all_shared_memories()
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
        """Execute a map function over each input in parallel"""
        with self.init_cache():
            if not is_parallel:
                return [
                    fn(item)
                    for item in tqdm(
                        inputs,
                        total=len(inputs),
                        desc=progress_desc,
                        disable=not show_progress,
                    )
                ]

            if use_threadpool:
                # it won't break rocksdb when using threadpool because of GIL.
                with ThreadPool(processes=n_processes) as pool:
                    iter = pool.imap_unordered(
                        ParallelFnWrapper(fn, ignore_error).run,
                        enumerate(
                            tqdm(
                                inputs,
                                total=len(inputs),
                                desc=progress_desc,
                                disable=not show_progress,
                            )
                        ),
                    )
                    results = list(iter)
                    results.sort(key=itemgetter(0))
            else:
                # have to switch to multi read single write mode
                with self.switch_mrsw_cache():
                    # start a pool of processes
                    with Pool(processes=n_processes) as pool:
                        iter = pool.imap_unordered(
                            ParallelFnWrapper(fn, ignore_error).run,
                            enumerate(
                                tqdm(
                                    inputs,
                                    total=len(inputs),
                                    desc=progress_desc,
                                    disable=not show_progress,
                                )
                            ),
                        )
                        results = list(iter)
                        results.sort(key=itemgetter(0))

        return [v for i, v in results]

    def foreach(
        self,
        fn: Fn,
        inputs: list,
        show_progress=False,
        progress_desc="",
        is_parallel=True,
        use_threadpool=False,
        n_processes: Optional[int] = None,
        ignore_error: bool = False,
    ) -> None:
        """Execute a map function over each input in parallel"""
        with self.init_cache():
            if not is_parallel:
                for item in tqdm(
                    inputs,
                    total=len(inputs),
                    desc=progress_desc,
                    disable=not show_progress,
                ):
                    fn(item)
                return

            if use_threadpool:
                # it won't break rocksdb when using threadpool because of GIL.
                with ThreadPool(processes=n_processes) as pool:
                    iter = pool.imap_unordered(
                        ParallelFnWrapper(fn, ignore_error).run_no_return,
                        enumerate(
                            tqdm(
                                inputs,
                                total=len(inputs),
                                desc=progress_desc,
                                disable=not show_progress,
                            )
                        ),
                    )
                    results = list(iter)
                    return

            # have to switch to multi read single write mode
            with self.switch_mrsw_cache():
                # start a pool of processes
                with Pool(processes=n_processes) as pool:
                    iter = pool.imap_unordered(
                        ParallelFnWrapper(fn, ignore_error).run_no_return,
                        enumerate(
                            tqdm(
                                inputs,
                                total=len(inputs),
                                desc=progress_desc,
                                disable=not show_progress,
                            )
                        ),
                    )
                    results = list(iter)
                    return

    def cache_func(
        self,
        dbpath: Union[Path, str],
        namespace: str = "",
        compress=Compressing.NoCompression,
        key: Callable[[str, tuple, dict], bytes] = None,
    ):
        """Cache a function (only work when using with Parallel object)"""
        for cache in self._cache:
            assert cache.db_args["dbpath"] != dbpath, "dbpath must be unique"

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
                key=key,
            )

            self._cache.append(cache)
            return cache.run

        return wrapper_fn
