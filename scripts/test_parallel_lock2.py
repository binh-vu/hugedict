import random
import shutil
import time
from hugedict.parallel import Parallel
from loguru import logger
import orjson
import redis
import sm.misc as M
from ned.candidate_generation.table_linker import TableLinker
from tqdm import tqdm

# redisdb = redis.Redis.from_url("redis://localhost:6379")
# queries = M.deserialize_jl("/tmp/binhvu/keys.jl.gz")

# records = []
# for q in tqdm(queries):
#     value = orjson.loads(redisdb.get(orjson.dumps(q)))
#     records.append({"key": q, "value": value})
# M.serialize_jl(records, "/tmp/binhvu/testdata.jl.gz")
# exit(0)

es_url = "http://ckg07:9200"
es_index = "wikidatadwd-augmented-09"

logger.info("Loading data")
records = M.deserialize_jl("/tmp/binhvu/testdata.jl.gz", n_lines=400)
records = {orjson.dumps(r["key"]).decode(): r["value"] for r in records}
logger.info("Start testing")

# print(type(list(records.values())[0]))
# exit(0)
# tl = TableLinker(
#     es_url,
#     es_index,
# )

pp = Parallel()


shutil.rmtree("/tmp/hugedict/test2.db")


@pp.cache_func("/tmp/hugedict/test2.db")
def run(q):
    global records
    return records[q]


def run2(q):
    return run(q)


output = pp.map(
    run2, sorted(records.keys()), n_processes=2, show_progress=True, is_parallel=False
)
