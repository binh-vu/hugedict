import os
from typing import Dict, ItemsView, Iterator, KeysView, MutableMapping, ValuesView
from hugedict.types import K, V, HugeMutableMapping
from copy import copy


class CacheDict(HugeMutableMapping[K, V]):
    def __init__(self, mapping: HugeMutableMapping[K, V]) -> None:
        self.mapping = mapping
        self._cache: Dict[K, V] = {}

    def __getitem__(self, key: K) -> V:
        if key not in self._cache:
            self._cache[key] = self.mapping[key]
        return self._cache[key]

    def __setitem__(self, key: K, value: V):
        self.mapping[key] = value

    def __delitem__(self, key: K):
        if key in self._cache:
            del self._cache[key]
        del self.mapping[key]

    def __iter__(self) -> Iterator[K]:
        return iter(self.mapping)

    def __len__(self):
        return len(self.mapping)

    def __contains__(self, key):
        if key in self._cache:
            return True
        return key in self.mapping

    def keys(self) -> KeysView[K]:
        return self.mapping.keys()

    def values(self) -> ValuesView[V]:
        return self.mapping.values()

    def items(self) -> ItemsView[K, V]:
        return self.mapping.items()

    def get(self, key: K, default=None):
        if key in self._cache:
            return self._cache[key]
        return self.mapping.get(key, default)

    def cache(self) -> "CacheDict":
        cache = CacheDict(self.mapping)
        # Return a clone of this object so that subsequence cache won't affect this object.
        cache._cache = copy(self._cache)
        return cache
