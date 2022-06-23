from __future__ import annotations
from typing import Callable, Mapping, MutableMapping, TypeVar, Union
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


class HugeMutableMapping(MutableMapping[K, V]):
    @abstractmethod
    def cache(self) -> HugeMutableMapping[K, V]:
        """Return a new mapping that will cache the results to
        avoid calling to an external mapping
        """
        pass
