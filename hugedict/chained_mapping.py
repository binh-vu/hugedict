from itertools import chain
import os
from typing import Iterator, KeysView, Mapping, MutableMapping, ValuesView
from hugedict.types import K, V


class ChainedMapping(Mapping[K, V]):
    def __init__(self, mapping1: Mapping[K, V], mapping2: Mapping[K, V]) -> None:
        self.mapping1 = mapping1
        self.mapping2 = mapping2

    def __getitem__(self, key: K) -> V:
        if key in self.mapping1:
            return self.mapping1[key]
        return self.mapping2[key]

    def __iter__(self) -> Iterator[K]:
        return chain(iter(self.mapping1), iter(self.mapping2))

    def __len__(self):
        return len(self.mapping1) + len(self.mapping2)

    def __contains__(self, key):
        if key in self.mapping1:
            return True
        return key in self.mapping2

    def get(self, key: K, default=None):
        if key in self.mapping1:
            return self.mapping1[key]
        return self.mapping2.get(key, default)
