from typing import Callable, TypeVar


K = TypeVar("K")
V = TypeVar("V")
T = TypeVar("T")
Fn = Callable


class InvalidUsageError(Exception):
    pass
