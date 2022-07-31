from multiprocessing import freeze_support, set_start_method, get_start_method
import os
import time
import shutil

from hugedict.parallel import Parallel

shutil.rmtree("/tmp/hugedict/test.db", ignore_errors=True)


def heavy_computing(seconds: float):
    time.sleep(seconds)
    return seconds * 2


if __name__ == "__main__":
    pp = Parallel()
    heavy_computing1 = pp.cache_func("/tmp/hugedict/test.db", url="ipc:///tmp/abc.ipc")(
        heavy_computing
    )

    output = pp.map(
        heavy_computing1,
        [0.5, 1, 0.7, 0.3, 0.6],
        n_processes=1,
        # use_threadpool=True,
        # is_parallel=False,
    )

    assert output == [1, 2, 1.4, 0.6, 1.2]
    print(">>> done")
    time.sleep(3)

    pp2 = Parallel()
    heavy_computing2 = pp2.cache_func(
        "/tmp/hugedict/test.db", url="ipc:///tmp/test22.ipc"
    )(heavy_computing)

    output = pp2.map(
        heavy_computing2,
        [0.5, 1, 0.7, 0.3, 0.6],
        n_processes=1,
        # use_threadpool=True,
        # is_parallel=False,
    )
