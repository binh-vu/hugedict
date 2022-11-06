import shutil
from hugedict.parallel import Parallel
from hugedict_v1.parallel.manager import MB
from hugedict_v1.parallel.parallel import Compressing
from loguru import logger
import orjson
import sm.misc as M

# Download the data in here: https://drive.google.com/file/d/1GPi19KEpBgf-AoQ2XFHXYEOUdFcg47tL/view?usp=sharing
# and put it to /tmp/test-break-syncmanager.jl.gz
logger.info("Loading data")
records = M.deserialize_jl("/tmp/test-break-syncmanager.jl.gz", n_lines=100)
records = {orjson.dumps(r["key"]).decode(): r["value"] for r in records}
logger.info("Start testing")

pp = Parallel(enable_shared_memory=True, min_increase_shm_mb_size=5)

shutil.rmtree("/tmp/hugedict/test2.db", ignore_errors=True)


@pp.cache_func("/tmp/hugedict/test2.db", compress=Compressing.NoCompression)
def run(q):
    global records
    return records[q]


def run2(q):
    run(q)
    return 5


output = pp.foreach(run2, sorted(records.keys()), show_progress=True, is_parallel=True)
print("FINISH!!")
