from __future__ import annotations

import functools
import pickle
import sqlite3
from dataclasses import dataclass
from enum import Enum
from inspect import signature
from pathlib import Path
from typing import (
    Any,
    Callable,
    Generic,
    Iterable,
    Iterator,
    Optional,
    Tuple,
    TypeVar,
    Union,
    overload,
)

import orjson
from timer import Timer

from hugedict.cachedict import CacheDict
from hugedict.types import F, HugeMutableMapping, V

SqliteKey = TypeVar("SqliteKey", bound=Union[str, int, bytes])
V1 = TypeVar("V1")
V2 = TypeVar("V2")
V3 = TypeVar("V3")

DEFAULT_TIMEOUT = 5.0


class SqliteDictFieldType(str, Enum):
    str = "TEXT"
    int = "INTEGER"
    bytes = "BLOB"


@dataclass
class SqliteDictArgs(Generic[V]):
    tablename: str
    keytype: SqliteDictFieldType
    ser_value: Callable[[V], bytes]
    deser_value: Callable[[bytes], V]
    valuetype: SqliteDictFieldType = SqliteDictFieldType.bytes
    timeout: float = DEFAULT_TIMEOUT


class SqliteDict(HugeMutableMapping[SqliteKey, V]):
    """A mutable mapping backed by sqlite. This mapping is slower than key-value db but offers
    concurrency read-write operators.

    Args:
        path: path to the sqlite database
        deser_key: deserialize key from bytes
        deser_value: deserialize value from bytes
        ser_value: serialize value to bytes
    """

    def __init__(
        self,
        path: Union[str, Path, sqlite3.Connection],
        keytype: SqliteDictFieldType,
        ser_value: Callable[[V], bytes],
        deser_value: Callable[[bytes], V],
        valuetype: SqliteDictFieldType = SqliteDictFieldType.bytes,
        timeout: float = DEFAULT_TIMEOUT,
        table_name: str = "data",
    ):
        if isinstance(path, (str, Path)):
            self.dbfile = Path(path)
            self.table_name = table_name
            need_init = not self.dbfile.exists()
            self.db = sqlite3.connect(str(self.dbfile), timeout=timeout)
            if need_init:
                with self.db:
                    self.db.execute(
                        f"CREATE TABLE {self.table_name}(key {keytype.value} PRIMARY KEY, value {valuetype.value})"
                    )
        else:
            assert isinstance(
                path, sqlite3.Connection
            ), f"path must be a str, Path, or Connection but get {type(path)}"
            self.db = path

        self.ser_value = ser_value
        self.deser_value = deser_value

    @staticmethod
    def str(
        path: Union[str, Path],
        ser_value: Callable[[V], bytes],
        deser_value: Callable[[bytes], V],
    ) -> SqliteDict[str, V]:
        return SqliteDict(path, SqliteDictFieldType.str, ser_value, deser_value)

    @staticmethod
    def int(
        path: Union[str, Path],
        ser_value: Callable[[V], bytes],
        deser_value: Callable[[bytes], V],
    ) -> SqliteDict[str, V]:
        return SqliteDict(path, SqliteDictFieldType.int, ser_value, deser_value)

    @staticmethod
    def mul2(
        path: Union[str, Path],
        args1: SqliteDictArgs[V1],
        args2: SqliteDictArgs[V2],
    ) -> tuple[SqliteDict[str, V1], SqliteDict[str, V2]]:
        d1, d2 = SqliteDict.multiple(path, args1, args2)
        return d1, d2

    @staticmethod
    def mul3(
        path: Union[str, Path],
        args1: SqliteDictArgs[V1],
        args2: SqliteDictArgs[V2],
        args3: SqliteDictArgs[V3],
    ) -> tuple[SqliteDict[str, V1], SqliteDict[str, V2], SqliteDict[str, V3]]:
        d1, d2, d3 = SqliteDict.multiple(path, args1, args2, args3)
        return d1, d2, d3

    @staticmethod
    def multiple(
        path: Union[str, Path],
        *args: SqliteDictArgs[Any],
    ) -> tuple[SqliteDict[str, Any], ...]:
        dbfile = Path(path)
        need_init = not dbfile.exists()
        timeout = max(a.timeout for a in args)
        db = sqlite3.connect(str(dbfile), timeout=timeout)
        if need_init:
            with db:
                for a in args:
                    db.execute(
                        f"CREATE TABLE {a.tablename}(key {a.keytype.value} PRIMARY KEY, value {a.valuetype.value})"
                    )

        out = []
        for a in args:
            out.append(
                SqliteDict(
                    path=db,
                    keytype=a.keytype,
                    ser_value=a.ser_value,
                    deser_value=a.deser_value,
                    valuetype=a.valuetype,
                    timeout=a.timeout,
                    table_name=a.tablename,
                )
            )
        return tuple(out)

    def __contains__(self, key: SqliteKey):
        return (
            self.db.execute(
                f"SELECT EXISTS ( SELECT 1 FROM {self.table_name} WHERE key = ? LIMIT 1)",
                (key,),
            ).fetchone()[0]
            == 1
        )

    def __getitem__(self, key: SqliteKey) -> V:
        record = self.db.execute(
            f"SELECT value FROM {self.table_name} WHERE key = ?", (key,)
        ).fetchone()
        if record is None:
            raise KeyError(key)
        return self.deser_value(record[0])

    def __setitem__(self, key: SqliteKey, value: V):
        with self.db:
            self.db.execute(
                f"INSERT INTO {self.table_name} VALUES (:key, :value) ON CONFLICT(key) DO UPDATE SET value = :value",
                {"key": key, "value": self.ser_value(value)},
            )

    def __delitem__(self, key: SqliteKey) -> None:
        with self.db:
            self.db.execute(f"DELETE FROM {self.table_name} WHERE key = ?", (key,))

    def __iter__(self) -> Iterator[SqliteKey]:
        return (key[0] for key in self.db.execute(f"SELECT key FROM {self.table_name}"))

    def __len__(self) -> int:
        return self.db.execute(f"SELECT COUNT(*) FROM {self.table_name}").fetchone()[0]

    def keys(self) -> Iterator[SqliteKey]:
        return (key[0] for key in self.db.execute(f"SELECT key FROM {self.table_name}"))

    def values(self) -> Iterator[V]:
        return (
            self.deser_value(value[0])
            for value in self.db.execute(f"SELECT value FROM {self.table_name}")
        )

    def items(self) -> Iterator[Tuple[SqliteKey, V]]:
        return (
            (key, self.deser_value(value))
            for key, value in self.db.execute(
                f"SELECT key, value FROM {self.table_name}"
            )
        )

    def get(self, key: SqliteKey, default=None):
        record = self.db.execute(
            f"SELECT value FROM {self.table_name} WHERE key = ?", (key,)
        ).fetchone()
        if record is None:
            return default
        return self.deser_value(record[0])

    def batch_insert(self, items: Iterable[Tuple[SqliteKey, V]]):
        with self.db:
            self.db.executemany(
                f"INSERT INTO {self.table_name} VALUES (:key, :value) ON CONFLICT(key) DO UPDATE SET value = :value",
                [{"key": key, "value": self.ser_value(value)} for key, value in items],
            )

    def cache(self) -> CacheDict:
        return CacheDict(self)

    @staticmethod
    def cache_fn(
        ser: Callable[[Any], bytes] = pickle.dumps,
        deser: Callable[[bytes], Any] = pickle.loads,
        cache_args: Optional[list[str]] = None,
        cache_key: Optional[Callable[..., bytes]] = None,
        outfile: Optional[Union[str, Path]] = None,
        log_serde_time: bool = False,
        disable: bool = False,
    ) -> Callable[[F], F]:
        """Decorator to cache the result of a function to a file using sqlitedict.
        Note: It does not support function with variable number of arguments.

        Args:
            ser: A function to serialize the output of the function to bytes.
            deser: A function to deserialize the output of the function from bytes.
            cache_args: list of arguments to use for the default cache key function. If None, all arguments are used. If cache_key is provided
                this argument is ignored.
            cache_key: Function to use to generate the cache key. If None, the default is used. The default function
                only support arguments of types str, int, bool, and None.
            outfile: where to store the cache file. If None, the name of the function is used and the location of the file is in /tmp. If it is a function,
                it will be called with the arguments of the function to generate the filename.
            log_serde_time: if True, will log the time it takes to deserialize the cache file.
            disable: if True, the cache is disabled.
        """
        if isinstance(disable, bool) and disable:
            return lambda x: x

        def wrapper_fn(func):
            if outfile is None:
                dbpath = Path("/tmp") / f"{func.__name__}.sqlite"
            else:
                dbpath = outfile

            keyfn = cache_key
            if keyfn is None:
                fnargs = {}
                for name, param in signature(func).parameters.items():
                    fnargs[name] = param
                fnargnames = list(fnargs.keys())

                def default_keyfn(*args, **kwargs):
                    out = {name: value for name, value in zip(fnargs, args)}
                    out.update(
                        [
                            (name, kwargs.get(name, fnargs[name].default))
                            for name in fnargnames[len(args) :]
                        ]
                    )
                    if cache_args is not None and len(cache_args) != len(fnargnames):
                        out = {name: out[name] for name in cache_args}
                    return orjson.dumps(out)

                keyfn = default_keyfn

            sqlitedict: SqliteDict[bytes, bytes] = SqliteDict(
                dbpath,
                SqliteDictFieldType.bytes,
                lambda x: x,
                lambda x: x,
                timeout=30,
            )

            @functools.wraps(func)
            def fn(*args, **kwargs):
                key = keyfn(*args, **kwargs)
                if key not in sqlitedict:
                    output = func(*args, **kwargs)
                    if log_serde_time:
                        with Timer().watch_and_report("serialize value"):
                            sqlitedict[key] = ser(output)
                    else:
                        sqlitedict[key] = ser(output)
                else:
                    if log_serde_time:
                        with Timer().watch_and_report(
                            "deserialize value",
                        ):
                            output = deser(sqlitedict[key])
                    else:
                        output = deser(sqlitedict[key])
                return output

            return fn

        return wrapper_fn  # type: ignore
