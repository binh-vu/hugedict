from __future__ import annotations
from typing import (
    Callable,
    Iterator,
    Mapping,
    MutableMapping,
    Sequence,
    Tuple,
    TypeVar,
    Union,
)
from abc import abstractmethod


# generic parameters
K = TypeVar("K")
KP = TypeVar("KP", bound=Union[str, bytes, int, None])
V = TypeVar("V")
T = TypeVar("T")
F = TypeVar("F", bound=Callable)
Fn = Callable


class InvalidUsageError(Exception):
    pass


class HugeMapping(Mapping[K, V]):
    @abstractmethod
    def cache(self) -> HugeMapping[K, V]:
        """Return a new mapping that will cache the results to
        avoid calling to an external mapping
        """
        pass

    @abstractmethod
    def update_cache(
        self, o: Union[Mapping[K, V], Sequence[Tuple[K, V]]]
    ) -> HugeMapping[K, V]:
        """Update the cache with the given mapping or iterator"""
        pass


class HugeMutableMapping(MutableMapping[K, V]):
    @abstractmethod
    def cache(self) -> HugeMutableMapping[K, V]:
        """Return a new mapping that will cache the results to
        avoid calling to an external mapping
        """
        pass

    @abstractmethod
    def update_cache(
        self, o: Union[Mapping[K, V], Sequence[Tuple[K, V]]]
    ) -> HugeMapping[K, V]:
        """Update the cache with the given mapping or iterator"""
        pass
