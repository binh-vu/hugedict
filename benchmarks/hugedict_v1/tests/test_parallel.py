from pathlib import Path
import time, tempfile, pytest

from hugedict_v1.parallel import Parallel


def heavy_computing(seconds: float):
    time.sleep(seconds)
    return seconds * 2


@pytest.mark.parametrize(
    "enable_bloomfilter,enable_shared_memory",
    [
        (enable_bloomfilter, enable_shared_memory)
        for enable_bloomfilter in [True, False]
        for enable_shared_memory in [True, False]
    ],
)
@pytest.mark.skip()
def test_parallel(enable_bloomfilter: bool, enable_shared_memory: bool):
    pp = Parallel(
        enable_bloomfilter=enable_bloomfilter, enable_shared_memory=enable_shared_memory
    )

    with tempfile.TemporaryDirectory() as tempdir:
        tempdir = Path(tempdir)
        fn = pp.cache_func(tempdir / "test.db")(heavy_computing)
        output = pp.map(fn, [0.5, 1, 0.7, 0.3, 0.6], n_processes=3)

        assert output == [1, 2, 1.4, 0.6, 1.2]
