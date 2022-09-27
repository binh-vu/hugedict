from os import read
import time
from loguru import logger
import ray
from typing import Callable, List, TypeVar, Any, Union
from tqdm import tqdm

R = TypeVar("R")


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
