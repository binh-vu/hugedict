import time

from hugedict.parallel.parallel import Parallel


def heavy_computing(seconds: float):
    time.sleep(seconds)
    return seconds * 2


def test_parallel():
    pp = Parallel()

    fn = pp.cache_func("/tmp/hugedict/test.db")(heavy_computing)
    output = pp.map(fn, [0.5, 1, 0.7, 0.3, 0.6], n_processes=3)

    assert output == [1, 2, 1.4, 0.6, 1.2]
