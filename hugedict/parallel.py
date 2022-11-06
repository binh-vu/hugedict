from __future__ import annotations
from contextlib import contextmanager
import enum
from functools import partial
import gc
import gzip
from inspect import signature
from multiprocessing import get_context
from multiprocessing.pool import ThreadPool
from operator import itemgetter
import subprocess
from pathlib import Path
import pickle
import shutil
import sys
from typing import Any, Callable, List, Literal, Optional, Union, MutableMapping, cast
from uuid import uuid4
import base64

from loguru import logger
import orjson
from tqdm import tqdm
from hugedict.types import F, Fn
from hugedict.misc import (
    Chain2,
    compress_zstd6_pyobject,
    decompress_zstd_pyobject,
    compress_pyobject,
)
from hugedict.hugedict.rocksdb import (
    Options,
    RocksDBDict,
    SecondaryDB,
    stop_primary_db,
)


class Compressing(enum.Flag):
    NoCompression = enum.auto()
    CompressKey = enum.auto()
    CompressValue = enum.auto()
    CompressAll = CompressValue | CompressKey


class Parallel:
    SWITCHED_MRSW_CACHE = False

    """Utility to execute a function over a list of inputs in parallel. It is useful
    when you have an expensive function and want to cache it results.

    Arguments:
        start_method: method used to start the process. Using fork is recommended if
            the code do not involve any lock (you may encounter deadlock).
            Note: spawn mode is currently not working.
    """

    def __init__(self, start_method: Literal["fork", "spawn", "forkserver"] = "fork"):
        self.start_method = start_method
        self.caches: List[LazyDBCacheFn] = []

    @contextmanager
    def init_cache(self):
        try:
            for cache in self.caches:
                if cache.db is not None:
                    del cache.db
                    cache.db = None
            gc.collect()
            yield
        finally:
            for cache in self.caches:
                if cache.db is not None:
                    del cache.db
                    cache.db = None
            gc.collect()

    @contextmanager
    def switch_mrsw_cache(self):
        primaries: List[subprocess.Popen] = []
        for cache in self.caches:
            primaries.append(cache.start_primary())

        yield

        for cache, primary in zip(self.caches, primaries):
            if primary is not None:
                cache.stop_primary()

        for primary in primaries:
            primary.wait(30)
            assert primary.returncode == 0, primary.returncode

        for cache in self.caches:
            cache.cleanup()

    @staticmethod
    def spawn_init_cache(enable_mrsw: bool):
        Parallel.SWITCHED_MRSW_CACHE = enable_mrsw

    def cache_func(
        self,
        dbpath: Union[Path, str],
        namespace: str = "",
        compress=Compressing.NoCompression,
        key: Optional[Callable[[str, tuple, dict], bytes]] = None,
        url: Optional[str] = None,
    ) -> Callable[[F], F]:
        """Cache a function (only work when using with Parallel object)"""
        for cache in self.caches:
            assert cache.dbpath != Path(dbpath), "dbpath must be unique"

        def wrapper_fn(func: F) -> F:
            if compress & Compressing.CompressKey:
                if key is None:
                    keyfn = compress_pyobject
                else:
                    keyfn = Chain2(partial(gzip.compress, mtime=0), key)
            else:
                keyfn = key

            if compress & Compressing.CompressValue:
                ser_value, deser_value = (
                    compress_zstd6_pyobject,
                    decompress_zstd_pyobject,
                )
            else:
                ser_value, deser_value = pickle.dumps, pickle.loads

            cache = LazyDBCacheFn(
                dbpath=Path(dbpath),
                dbopts=Options(create_if_missing=True),
                deser_value=deser_value,
                ser_value=ser_value,
                fn=func,
                namespace=namespace,
                key=keyfn,  # type: ignore
                url=url,
            )

            self.caches.append(cache)
            return cache.run  # type: ignore

        return wrapper_fn

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
                wrapped_fn = ParallelFnWrapper(fn, ignore_error=False).run
                return [
                    wrapped_fn((i, item))[1]
                    for i, item in tqdm(
                        enumerate(inputs),
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
                        enumerate(inputs),
                    )
                    results = []
                    for result in tqdm(
                        iter,
                        total=len(inputs),
                        desc=progress_desc,
                        disable=not show_progress,
                    ):
                        results.append(result)
                    results.sort(key=itemgetter(0))
            else:
                # have to switch to multi read single write mode
                with self.switch_mrsw_cache():
                    if self.start_method == "fork":
                        initializer = None
                        initargs = ()
                    else:
                        initializer = Parallel.spawn_init_cache
                        initargs = (True,)

                    # start a pool of processes
                    with get_context(self.start_method).Pool(
                        processes=n_processes,
                        initializer=initializer,
                        initargs=initargs,
                    ) as pool:
                        iter = pool.imap_unordered(
                            ParallelFnWrapper(fn, ignore_error).run,
                            enumerate(inputs),
                        )
                        results = []
                        for result in tqdm(
                            iter,
                            total=len(inputs),
                            desc=progress_desc,
                            disable=not show_progress,
                        ):
                            results.append(result)
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
                        enumerate(inputs),
                    )
                    results = []
                    for result in tqdm(
                        iter,
                        total=len(inputs),
                        desc=progress_desc,
                        disable=not show_progress,
                    ):
                        results.append(result)
                    return

            # have to switch to multi read single write mode
            with self.switch_mrsw_cache():
                # start a pool of processes
                if self.start_method == "fork":
                    initializer = None
                    initargs = ()
                else:
                    initializer = Parallel.spawn_init_cache
                    initargs = (True,)

                # start a pool of processes
                with get_context(self.start_method).Pool(
                    processes=n_processes,
                    initializer=initializer,
                    initargs=initargs,
                ) as pool:
                    iter = pool.imap_unordered(
                        ParallelFnWrapper(fn, ignore_error).run_no_return,
                        enumerate(inputs),
                    )
                    results = []
                    for result in tqdm(
                        iter,
                        total=len(inputs),
                        desc=progress_desc,
                        disable=not show_progress,
                    ):
                        results.append(result)
                    return


class ParallelFnWrapper:
    def __init__(self, fn: Fn, ignore_error=False):
        self.fn = fn
        # method of instances won't have `self` parameter, so we do not need to worry about it
        if hasattr(fn, "__self__") and isinstance(fn.__self__, LazyDBCacheFn):
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


class LazyDBCacheFn:
    SECONDARY_DIR = "secondaries"

    def __init__(
        self,
        dbpath: Path,
        dbopts: Options,
        deser_value: Callable[[memoryview], Any],
        ser_value: Callable[[Any], bytes],
        fn: Fn,
        key: Optional[Callable[[str, tuple, dict], bytes]] = None,
        namespace: str = "",
        url: Optional[str] = None,
    ):
        self.dbopts = dbopts
        self.dbpath = dbpath
        self.deser_value = deser_value
        self.ser_value = ser_value
        self.db: Optional[MutableMapping[bytes, Any]] = None
        self.is_mrsw = False
        self.namespace = namespace

        self.fn = fn
        self.fn_name = (
            namespace + ":" + fn.__name__ if len(namespace) > 0 else fn.__name__
        )
        self.key = key or CacheFnKey.default_key

        if url is not None:
            self.url = url
            self.socket_file = None
        else:
            self.socket_file = Path(f"/tmp/hugedict/{str(uuid4())}.ipc")
            self.socket_file.parent.mkdir(parents=True, exist_ok=True)
            self.url = f"ipc://{self.socket_file}"

    def run(self, *args, **kwargs):
        key = self.key(self.fn_name, args, kwargs)
        if self.db is None:
            if not self.is_mrsw and not Parallel.SWITCHED_MRSW_CACHE:
                self.db = RocksDBDict(
                    str(self.dbpath),
                    self.dbopts,
                    bytes,
                    self.deser_value,
                    self.ser_value,
                )
            else:
                (self.dbpath / self.SECONDARY_DIR).mkdir(parents=True, exist_ok=True)
                self.db = cast(
                    MutableMapping,
                    SecondaryDB(
                        self.url,
                        str(self.dbpath),
                        str(self.dbpath / self.SECONDARY_DIR / str(uuid4())),
                        self.dbopts,
                        self.deser_value,
                        self.ser_value,
                    ),
                )

        if key not in self.db:
            output = self.fn(*args, **kwargs)
            self.db[key] = output
            return output

        return self.db[key]

    def start_primary(self) -> subprocess.Popen:
        assert (
            self.db is None
        ), "Switching to Multi-read single-write mode must done before starting a primary instance"
        self.is_mrsw = True
        self.cleanup()

        return self._start_primary_db(self.url, self.dbpath, self.dbopts)

    def stop_primary(self):
        self.is_mrsw = False
        stop_primary_db(self.url)

    def cleanup(self):
        # clean previous directory if exists
        if (self.dbpath / self.SECONDARY_DIR).exists():
            shutil.rmtree(self.dbpath / self.SECONDARY_DIR)

        if self.socket_file is not None and self.socket_file.exists():
            self.socket_file.unlink()
            self.socket_file = None

        if self.db is not None:
            self.db = None
            gc.collect()

    @staticmethod
    def _start_primary_db(
        url: str, dbpath: Union[str, Path], opts: Options
    ) -> subprocess.Popen:
        commands = [
            "import sys, json, base64, pickle",
            "from hugedict.hugedict.rocksdb import primary_db",
            "o = json.loads(sys.argv[1])",
            'primary_db(o["url"], o["dbpath"], pickle.loads(base64.b64decode(o["dbopts"])))',
        ]
        command = ";".join(commands)
        input = orjson.dumps(
            {
                "url": url,
                "dbpath": str(dbpath),
                "dbopts": base64.b64encode(pickle.dumps(opts)).decode(),
            }
        ).decode()

        assert sys.executable is not None and len(sys.executable) > 0
        p = subprocess.Popen([sys.executable, "-c", command, input])
        return p


class CacheFnKey:
    @staticmethod
    def default_key(fn_name, args: tuple, kwargs: dict):
        return orjson.dumps((fn_name, args, kwargs))

    @staticmethod
    def single_str_arg(fn_name: str, args: tuple, kwargs: dict):
        return args[0].encode()
