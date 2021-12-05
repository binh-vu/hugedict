import time
import shutil

from hugedict.parallel.parallel import MyManager, Parallel

shutil.rmtree("/tmp/hugedict/test.db", ignore_errors=True)

pp = Parallel()


@pp.cache_func("/tmp/hugedict/test.db")
def heavy_computing(seconds: float):
    time.sleep(seconds)
    return seconds * 2


def run(seconds: float):
    return heavy_computing(seconds)


output = pp.map(run, [0.5, 1, 0.7, 0.3, 0.6], n_processes=3)

assert output == [1, 2, 1.4, 0.6, 1.2]
