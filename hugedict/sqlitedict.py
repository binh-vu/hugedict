from __future__ import annotations

from enum import Enum
import sqlite3
from pathlib import Path
from typing import (
    Callable,
    Iterator,
    Union,
    TypeVar,
    Tuple,
)
from hugedict.cachedict import CacheDict
from hugedict.types import HugeMutableMapping, V


SqliteKey = TypeVar("SqliteKey", bound=Union[str, int])


class SqliteDictKeyType(str, Enum):
    str = "TEXT"
    int = "INTEGER"


class SqliteDict(HugeMutableMapping[SqliteKey, V]):
    """A mutable mapping backed by sqlite. This mapping is slower than key-value db but offers
    concurrency read-write operators.

    Args:
        path: path to the sqlite database
        deser_key: deserialize key from a memoryview
        deser_value: deserialize value from a memoryview
        ser_value: serialize value to bytes
    """

    def __init__(
        self,
        path: Union[str, Path],
        keytype: SqliteDictKeyType,
        ser_value: Callable[[V], bytes],
        deser_value: Callable[[bytes], V],
    ):
        self.dbfile = Path(path)
        need_init = not self.dbfile.exists()
        self.db = sqlite3.connect(str(self.dbfile))
        if need_init:
            with self.db:
                self.db.execute(
                    f"CREATE TABLE data(key {keytype.value} PRIMARY KEY, value BLOB)"
                )

        self.ser_value = ser_value
        self.deser_value = deser_value

    @staticmethod
    def str(
        path: Union[str, Path],
        ser_value: Callable[[V], bytes],
        deser_value: Callable[[bytes], V],
    ) -> SqliteDict[str, V]:
        return SqliteDict(path, SqliteDictKeyType.str, ser_value, deser_value)

    @staticmethod
    def int(
        path: Union[str, Path],
        ser_value: Callable[[V], bytes],
        deser_value: Callable[[bytes], V],
    ) -> SqliteDict[str, V]:
        return SqliteDict(path, SqliteDictKeyType.int, ser_value, deser_value)

    def __contains__(self, key):
        return (
            self.db.execute(
                "SELECT EXISTS ( SELECT 1 FROM data WHERE key = ? LIMIT 1)", (key,)
            ).fetchone()[0]
            == 1
        )

    def __getitem__(self, key: SqliteKey) -> V:
        record = self.db.execute(
            "SELECT value FROM data WHERE key = ?", (key,)
        ).fetchone()
        if record is None:
            raise KeyError(key)
        return self.deser_value(record[0])

    def __setitem__(self, key: SqliteKey, value: V):
        with self.db:
            self.db.execute(
                "INSERT INTO data VALUES (:key, :value) ON CONFLICT(key) DO UPDATE SET value = :value",
                {"key": key, "value": self.ser_value(value)},
            )

    def __delitem__(self, key: SqliteKey) -> None:
        with self.db:
            self.db.execute("DELETE FROM data WHERE key = ?", (key,))

    def __iter__(self) -> Iterator[SqliteKey]:
        return (key[0] for key in self.db.execute("SELECT key FROM data"))

    def __len__(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM data").fetchone()[0]

    def keys(self) -> Iterator[SqliteKey]:
        return (key[0] for key in self.db.execute("SELECT key FROM data"))

    def values(self) -> Iterator[V]:
        return (
            self.deser_value(value[0])
            for value in self.db.execute("SELECT value FROM data")
        )

    def items(self) -> Iterator[Tuple[SqliteKey, V]]:
        return (
            (key, self.deser_value(value))
            for key, value in self.db.execute("SELECT key, value FROM data")
        )

    def get(self, key: SqliteKey, default=None):
        record = self.db.execute(
            "SELECT value FROM data WHERE key = ?", (key,)
        ).fetchone()
        if record is None:
            return default
        return self.deser_value(record[0])

    def cache(self) -> CacheDict:
        return CacheDict(self)
