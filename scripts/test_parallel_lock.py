import time
import shutil
import random

from hugedict.parallel.parallel import MyManager, Parallel

# shutil.rmtree("/tmp/hugedict/test.db", ignore_errors=True)

pp = Parallel()


@pp.cache_func("/tmp/hugedict/test.db")
def heavy_computing(seconds: float):
    time.sleep(seconds)
    return seconds * 2


def run(seconds: float):
    return heavy_computing(seconds)


random.seed(10)
inputs = []
for i in range(1000):
    inputs.append(round(random.random() * 2, 7))
# print(inputs[:100])
# inputs = [0.365, 0.365, 0.365]
output = pp.map(
    run,
    inputs,
    # n_processes=2,
    show_progress=True,
    # is_parallel=False,
)
print(">>>", len(output))
