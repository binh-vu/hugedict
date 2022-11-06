import time
from pathlib import Path


from hugedict.parallel import Parallel


def heavy_computing(seconds: float):
    time.sleep(seconds)
    return seconds * 2


def test_parallel(tmp_path: Path, url: str):
    pp = Parallel(start_method="spawn")

    fn = pp.cache_func(tmp_path / "test.db", url=url)(heavy_computing)
    output = pp.map(fn, [0.5, 1, 0.7, 0.3, 0.6], n_processes=3)
    assert output == [1, 2, 1.4, 0.6, 1.2]

    output = pp.map(fn, [0.5, 1, 0.7, 0.3, 0.6], n_processes=3)
    assert output == [1, 2, 1.4, 0.6, 1.2]


def test_parallel_new_url(tmp_path: Path):
    pp = Parallel(start_method="spawn")

    fn = pp.cache_func(tmp_path / "test.db")(heavy_computing)
    output = pp.map(fn, [0.5, 1, 0.7, 0.3, 0.6], n_processes=3)

    assert output == [1, 2, 1.4, 0.6, 1.2]
