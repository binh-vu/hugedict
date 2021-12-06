from typing import Callable, TypeVar


K = TypeVar("K")
V = TypeVar("V")
Fn = Callable


class InvalidUsageError(Exception):
    pass
