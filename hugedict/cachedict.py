import os
from typing import Iterator, KeysView, MutableMapping, ValuesView
from hugedict.types import K, V
from copy import copy


class CacheDict(MutableMapping[K, V]):
    def __init__(self, mapping: MutableMapping[K, V]) -> None:
        self.mapping = mapping
        self.cache = {}

    def __getitem__(self, key: K) -> V:
        if key not in self.cache:
            self.cache[key] = self.mapping[key]
        return self.cache[key]

    def __setitem__(self, key: K, value: V):
        self.mapping[key] = value

    def __delitem__(self, key: K):
        if key in self.cache:
            del self.cache[key]
        del self.mapping[key]

    def __iter__(self) -> Iterator[K]:
        return iter(self.mapping)

    def __len__(self):
        return len(self.mapping)

    def __contains__(self, key):
        if key in self.cache:
            return True
        return key in self.mapping

    def keys(self) -> KeysView[K]:
        return self.mapping.keys()

    def values(self) -> ValuesView[V]:
        return self.mapping.values()

    def get(self, key: K, default=None):
        if key in self.cache:
            return self.cache[key]
        return self.mapping.get(key, default)

    def cache_dict(self) -> "CacheDict":
        """Return a clone of this object so that subsequence cache won't affect this object.
        Using the name cache_dict, so that it can be mixed with existing object providing cache_dict such as RocksDBDict
        """
        cache = CacheDict(self.mapping)
        cache.cache = copy(self.cache)
        return cache
