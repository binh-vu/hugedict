import shutil
from hugedict.parallel import Parallel
from hugedict.parallel.parallel import Compressing
from loguru import logger
import orjson
import sm.misc as M

# Download the data in here: https://drive.google.com/file/d/1GPi19KEpBgf-AoQ2XFHXYEOUdFcg47tL/view?usp=sharing
# and put it to /tmp/test-break-syncmanager.jl.gz
logger.info("Loading data")
records = M.deserialize_jl("/tmp/test-break-syncmanager.jl.gz")
records = {orjson.dumps(r["key"]).decode(): r["value"] for r in records}
logger.info("Start testing")

pp = Parallel()

# shutil.rmtree("/tmp/hugedict/test2.db", ignore_errors=True)


@pp.cache_func("/tmp/hugedict/test2.db", compress=Compressing.NoCompression)
def run(q):
    global records
    return records[q]


def run2(q):
    run(q)
    return 5


output = pp.map(
    run2, sorted(records.keys()), n_processes=4, show_progress=True, is_parallel=True
)
