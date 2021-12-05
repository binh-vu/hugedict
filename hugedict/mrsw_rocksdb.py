import os
from pathlib import Path
import pickle
from typing import Callable, Dict, Iterator, NamedTuple, TypeVar, Union, MutableMapping
from hugedict.rocksdb import RocksDBDict
from hugedict.types import K, V
from pybloomfilter import BloomFilter


BloomFilterArgs = NamedTuple(
    "BloomFilterArgs", [("capacity", int), ("error_rate", float)]
)
DEFAULT_BLOOMFILTER_ARGS = (int(1e6), 0.001)


class PrimarySyncedRocksDBDict(RocksDBDict[K, V]):
    def __init__(
        self,
        dbpath: Union[Path, str],
        create_if_missing=False,
        deser_key: Callable[[bytes], K] = None,
        deser_value: Callable[[bytes], V] = None,
        ser_key: Callable[[K], bytes] = None,
        ser_value: Callable[[V], bytes] = None,
        bloomfilter_args: BloomFilterArgs = None,
        enable_bloomfilter: bool = True,
    ) -> None:
        super().__init__(
            dbpath=dbpath,
            create_if_missing=create_if_missing,
            deser_key=deser_key,
            deser_value=deser_value,
            ser_key=ser_key,
            ser_value=ser_value,
        )

        # create a default of 1M keys
        self.bloomfilter_args = bloomfilter_args or DEFAULT_BLOOMFILTER_ARGS
        self.enable_bloomfilter = enable_bloomfilter
        if self.enable_bloomfilter:
            self.bloomfilter = BloomFilter(
                *self.bloomfilter_args, os.path.join(self.dbpath, "bloomfilter")
            )

    def __setitem__(self, key: K, value: V):
        serkey = self.ser_key(key)
        self.db.put(serkey, self.ser_value(value))
        if self.enable_bloomfilter:
            self.bloomfilter.add(serkey)

    def __delitem__(self, key: K):
        serkey = self.ser_key(key)
        self.db.delete(serkey)
        if self.enable_bloomfilter:
            self.bloomfilter.remove(serkey)

    def pop(self, key: K, default=None):
        serkey = self.ser_key(key)
        item = self.db.get(serkey)
        if item is None:
            return default
        self.db.delete(serkey)
        if self.enable_bloomfilter:
            self.bloomfilter.remove(serkey)
        return self.deser_value(item)

    # extra method for proxy & secondary
    def raw_has(self, key: bytes) -> bool:
        return self.db.get(key) is not None

    def raw_get(self, key: bytes) -> V:
        item = self.db.get(key)
        if item is None:
            raise KeyError(key)
        return self.deser_value(item)

    def raw_set(self, key: bytes, value: bytes):
        self.db.put(key, value)
        if self.enable_bloomfilter:
            self.bloomfilter.add(key)


class SecondarySyncedRocksDBDict(RocksDBDict[K, V]):
    def __init__(
        self,
        primary: PrimarySyncedRocksDBDict[K, V],
        dbpath: Union[Path, str],
        secondary_name: str,
        deser_key: Callable[[bytes], K] = None,
        deser_value: Callable[[bytes], V] = None,
        ser_key: Callable[[K], bytes] = None,
        ser_value: Callable[[V], bytes] = None,
        bloomfilter_args: BloomFilterArgs = None,
        enable_bloomfilter: bool = True,
    ):
        super().__init__(
            dbpath=dbpath,
            secondary_name=secondary_name,
            create_if_missing=False,
            read_only=False,
            deser_key=deser_key,
            deser_value=deser_value,
            ser_key=ser_key,
            ser_value=ser_value,
        )

        self.primary = primary

        # create a default of 1M keys
        self.bloomfilter_args = bloomfilter_args or DEFAULT_BLOOMFILTER_ARGS
        self.enable_bloomfilter = enable_bloomfilter
        if self.enable_bloomfilter:
            self.bloomfilter = BloomFilter.open(
                os.path.join(self.dbpath, "bloomfilter"), "r"
            )

    def __getitem__(self, key: K) -> V:
        serkey = self.ser_key(key)
        item = self.db.get(serkey)

        if item is not None:
            return self.deser_value(item)

        if self.enable_bloomfilter and serkey not in self.bloomfilter:  # type: ignore
            # can't find the key anywhere
            raise KeyError(key)

        return self.primary.raw_get(serkey)

    def __setitem__(self, key: K, value: V):
        self.primary.raw_set(self.ser_key(key), self.ser_value(value))

    def __delitem__(self, key: K):
        raise NotImplementedError(
            "SecondarySyncedRocksDBDict does not support __delitem__"
        )

    def __iter__(self) -> Iterator[K]:
        return iter(self.primary)

    def __len__(self):
        return len(self.primary)

    def __contains__(self, key):
        serkey = self.ser_key(key)
        return (
            (self.db.get(serkey) is not None)
            or (
                self.enable_bloomfilter and (serkey in self.bloomfilter) and self.primary.raw_has(serkey)  # type: ignore
            )
            or (not self.enable_bloomfilter and self.primary.raw_has(serkey))
        )

    def keys(self) -> Iterator[K]:
        return self.primary.keys()

    def values(self) -> Iterator[V]:
        return self.primary.values()

    def get(self, key: K, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def pop(self, key: K, default=None):
        raise NotImplementedError(
            "SecondarySyncedRocksDBDict does not support __delitem__"
        )
