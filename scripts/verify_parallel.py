from multiprocessing import freeze_support, set_start_method, get_start_method
import os
import time
import shutil

from hugedict.parallel import Parallel

shutil.rmtree("/tmp/hugedict/test.db", ignore_errors=True)


pp = Parallel()


@pp.cache_func("/tmp/hugedict/test.db")
def heavy_computing(seconds: float):
    time.sleep(seconds)
    return seconds * 2


def run(seconds: float):
    return heavy_computing(seconds)


if __name__ == "__main__":
    # print("@@", get_start_method())
    # set_start_method("fork")
    # freeze_support()

    output = pp.map(
        run,
        [0.5, 1, 0.7, 0.3, 0.6],
        n_processes=3,
        # use_threadpool=True,
        # is_parallel=False,
    )

    assert output == [1, 2, 1.4, 0.6, 1.2]
