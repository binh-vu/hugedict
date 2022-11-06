from abc import ABC, abstractmethod
import os
from pathlib import Path
import pickle
from typing import (
    Callable,
    Dict,
    Iterator,
    NamedTuple,
    Optional,
    TypeVar,
    Union,
    MutableMapping,
)
from hugedict_v1.rocksdb import RocksDBDict
from hugedict.types import K, V, InvalidUsageError
from pybloomfilter import BloomFilter


BloomFilterArgs = NamedTuple(
    "BloomFilterArgs", [("capacity", int), ("error_rate", float)]
)
DEFAULT_BLOOMFILTER_ARGS = (int(1e6), 0.001)


class IProxyDict(ABC):
    @abstractmethod
    def raw_has(self, key: bytes) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def raw_get(self, key: bytes) -> Optional[bytes]:
        raise NotImplementedError()

    @abstractmethod
    def raw_set(self, key: bytes, value: bytes):
        raise NotImplementedError()


class PrimarySyncedRocksDBDict(RocksDBDict[K, V], IProxyDict):
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

    def raw_has(self, key: bytes) -> bool:
        return self.db.get(key) is not None

    def raw_get(self, key: bytes) -> Optional[bytes]:
        return self.db.get(key)

    def raw_set(self, key: bytes, value: bytes):
        self.db.put(key, value)
        if self.enable_bloomfilter:
            self.bloomfilter.add(key)


class SecondarySyncedRocksDBDict(RocksDBDict[K, V]):
    def __init__(
        self,
        primary: IProxyDict,
        dbpath: Union[Path, str],
        secondary_name: str,
        deser_key: Optional[Callable[[bytes], K]] = None,
        deser_value: Optional[Callable[[bytes], V]] = None,
        ser_key: Optional[Callable[[K], bytes]] = None,
        ser_value: Optional[Callable[[V], bytes]] = None,
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

        item = self.primary.raw_get(serkey)
        if item is None:
            raise KeyError(key)
        return self.deser_value(item)

    def __setitem__(self, key: K, value: V):
        self.primary.raw_set(self.ser_key(key), self.ser_value(value))

    def __delitem__(self, key: K):
        raise InvalidUsageError()

    def __iter__(self) -> Iterator[K]:
        raise InvalidUsageError()

    def __len__(self):
        raise InvalidUsageError()

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
        raise InvalidUsageError()

    def values(self) -> Iterator[V]:
        raise InvalidUsageError()

    def get(self, key: K, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def pop(self, key: K, default=None):
        raise InvalidUsageError()
