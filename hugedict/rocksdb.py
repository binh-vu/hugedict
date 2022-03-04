import os
from pathlib import Path
import pickle
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    Optional,
    TypeVar,
    Union,
    MutableMapping,
    cast,
)
from hugedict.cachedict import CacheDict
from rocksdb import DB, Options  # type: ignore
from pybloomfilter import BloomFilter
from hugedict.types import K, V


class RocksDBDict(MutableMapping[K, V]):
    """
    A dictionary-like object that uses RocksDB as the underlying storage.

    Args:
        dbpath: location to the rocksdb database folder.
        create_if_missing: If True, create the RocksDB file if it does not exist.
        secondary_name: If provided, open as a secondary instance
        read_only: If True, open the RocksDB file in read-only mode.
        deser_key: A function to deserialize a key from bytes.
        deser_value: A function to deserialize a value from bytes.
        ser_key: A function to serialize a key to bytes.
        ser_value: A function to serialize a value to bytes.
    """

    def __init__(
        self,
        dbpath: Union[Path, str],
        create_if_missing=False,
        secondary_name: Optional[str] = None,
        read_only=False,
        deser_key: Optional[Callable[[bytes], K]] = None,
        deser_value: Optional[Callable[[bytes], V]] = None,
        ser_key: Optional[Callable[[K], bytes]] = None,
        ser_value: Optional[Callable[[V], bytes]] = None,
        db_options: Optional[Dict[str, Any]] = None,
    ):
        if db_options is None:
            db_options = {}
        db_options["create_if_missing"] = create_if_missing
        kwargs: Dict[str, Any] = dict(read_only=read_only)

        if secondary_name is not None:
            if secondary_name == "primary":
                raise ValueError("secondary_name cannot be 'primary'")

            # required to open as secondary instance
            db_options["max_open_files"] = -1
            kwargs["secondary_name"] = os.path.join(dbpath, secondary_name)

        self.dbpath = dbpath
        Path(self.dbpath).mkdir(exist_ok=True, parents=True)
        self.db_options = db_options
        self.kwargs = kwargs
        self.db = DB(
            os.path.join(dbpath, "primary"), Options(**self.db_options), **kwargs
        )
        self.secondary_name = secondary_name
        self.is_primary = secondary_name is None

        self.deser_key = cast(Callable[[bytes], K], deser_key or bytes.decode)
        self.ser_key = cast(Callable[[K], bytes], ser_key or str.encode)

        self.deser_value = cast(Callable[[bytes], V], deser_value or pickle.loads)
        self.ser_value = cast(Callable[[V], bytes], ser_value or pickle.dumps)

    def __getitem__(self, key: K) -> V:
        item = self.db.get(self.ser_key(key))
        if item is None:
            raise KeyError(key)
        return self.deser_value(item)

    def __setitem__(self, key: K, value: V):
        self.db.put(self.ser_key(key), self.ser_value(value))

    def __delitem__(self, key: K):
        self.db.delete(self.ser_key(key))

    def __iter__(self) -> Iterator[K]:
        it = self.db.iterkeys()
        it.seek_to_first()
        return (self.deser_key(key) for key in it)

    def __len__(self):
        it = self.db.iterkeys()
        it.seek_to_first()
        return sum(1 for _ in it)

    def __contains__(self, key):
        return self.db.get(self.ser_key(key)) is not None

    def keys(self) -> Iterator[K]:
        it = self.db.iterkeys()
        it.seek_to_first()
        return (self.deser_key(key) for key in it)

    def values(self) -> Iterator[V]:
        it = self.db.itervalues()
        it.seek_to_first()
        return (self.deser_value(value) for value in it)

    def get(self, key: K, default: Optional[V] = None):
        item = self.db.get(self.ser_key(key))
        if item is None:
            return default
        return self.deser_value(item)

    def pop(self, key: K, default=None):
        serkey = self.ser_key(key)
        item = self.db.get(serkey)
        if item is None:
            return default
        self.db.delete(serkey)
        return self.deser_value(item)

    def close(self):
        self.db.close()
        del self.db

    def open(self):
        self.db = DB(
            os.path.join(self.dbpath, "primary"),
            Options(**self.db_options),
            **self.kwargs
        )

    def cache_dict(self):
        return CacheDict(self)
