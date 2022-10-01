from os import read
import time
from loguru import logger
import ray
from typing import Callable, List, Optional, TypeVar, Any, Union
from tqdm import tqdm

R = TypeVar("R")
OBJECTS = {}


def ray_map(
    remote_fn: Callable[..., "ray.ObjectRef[R]"],
    args_lst: List[Union[list, tuple]],
    verbose: bool = False,
    poll_interval: float = 0.1,
) -> List[R]:
    with tqdm(total=len(args_lst), disable=not verbose) as pbar:
        refs = []
        ref2index = {}
        for args in args_lst:
            refs.append(remote_fn(*args))
            ref2index[refs[-1]] = len(refs) - 1

        output: List[R] = [None] * len(refs)  # type: ignore
        notready_refs = refs

        while True:
            ready_refs, notready_refs = ray.wait(notready_refs, timeout=poll_interval)
            pbar.update(len(ready_refs))

            for ref in ready_refs:
                output[ref2index[ref]] = ray.get(ref)

            if len(notready_refs) == 0:
                return output


def get_instance(constructor: Callable[[], R], name: Optional[str] = None) -> R:
    """A utility function to get a singleton, which can be created from the given constructor.

    One use case of this function is we have a big object that is expensive to send
    to individual task repeatedly. As ray executes multiple tasks in a reusable worker,
    this allows us to create the object per worker instead of per task.

    Reference: https://docs.ray.io/en/latest/ray-core/actors.html#faq-actors-workers-and-resources
    """
    global OBJECTS

    if name is None:
        assert (
            constructor.__name__ != "<lambda>"
        ), "Cannot use lambda as a name because it will keep changing"
        name = constructor  # type: ignore

    if name not in OBJECTS:
        logger.trace("Create a new instance of {}", name)
        OBJECTS[name] = constructor()
    return OBJECTS[name]
