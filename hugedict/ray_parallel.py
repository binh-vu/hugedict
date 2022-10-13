import math
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
    concurrent_submissions: int = 3000,
    desc: Optional[str] = None,
) -> List[R]:
    n_jobs = len(args_lst)

    with tqdm(total=n_jobs, desc=desc, disable=not verbose) as pbar:
        output: List[R] = [None] * n_jobs  # type: ignore

        notready_refs = []
        ref2index = {}
        for i, args in enumerate(args_lst):
            # submit a task and add it to not ready queue and ref2index
            ref = remote_fn(*args)
            notready_refs.append(ref)
            ref2index[ref] = i

            # when the not ready queue is full, wait for some tasks to finish
            while len(notready_refs) >= concurrent_submissions:
                ready_refs, notready_refs = ray.wait(
                    notready_refs, timeout=poll_interval
                )
                pbar.update(len(ready_refs))
                for ref in ready_refs:
                    output[ref2index[ref]] = ray.get(ref)

        while len(notready_refs) > 0:
            ready_refs, notready_refs = ray.wait(notready_refs, timeout=poll_interval)
            pbar.update(len(ready_refs))
            for ref in ready_refs:
                output[ref2index[ref]] = ray.get(ref)

        return output


def ray_map_v1(
    remote_fn: Callable[..., "ray.ObjectRef[R]"],
    args_lst: List[Union[list, tuple]],
    verbose: bool = False,
    poll_interval: float = 0.1,
) -> List[R]:
    with tqdm(total=len(args_lst), disable=not verbose) as pbar:
        pbar.set_description("initializing")
        interval = math.floor(len(args_lst) / 1000)
        refs = []
        ref2index = {}
        for i, args in enumerate(args_lst):
            refs.append(remote_fn(*args))
            ref2index[refs[-1]] = len(refs) - 1

            if i % interval == 0:
                pbar.set_postfix(
                    {"initializing progress": percentage(len(refs), len(args_lst))}
                )

        output: List[R] = [None] * len(refs)  # type: ignore
        notready_refs = refs

        pbar.set_description("processing")
        pbar.set_postfix({})

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


def percentage(a: Union[float, int], b: Union[float, int]) -> str:
    return "%.2f%% (%d/%d)" % (a * 100 / b, a, b)
