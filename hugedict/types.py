from typing import Callable, TypeVar


K = TypeVar("K")
V = TypeVar("V")
T = TypeVar("T")
Fn = Callable
F = TypeVar("F", bound=Callable)


class InvalidUsageError(Exception):
    pass
