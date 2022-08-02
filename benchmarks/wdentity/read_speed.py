from functools import partial
from pathlib import Path
import random
import orjson
import ray
from sm.prelude import M
from tap import Tap
from hugedict.misc import zstd6_compress_custom, zstd_decompress_custom
from hugedict.prelude import RocksDBDict
from wdentity.load_db import db_options


class ReadSpeedArgs(Tap):
    name: str
    option: str


data_dir = Path(__file__).parent.parent / "data"


if not (data_dir / "keys.txt").exists():
    ray.init()

    @ray.remote
    def read_keys(infile, rate: float, seed: int):
        random.seed(seed)

        keys = []
        with M.get_open_fn(infile)(infile, "rb") as f:
            for line in f:
                key = orjson.loads(line)["id"]
                if random.random() <= rate:
                    keys.append(key)
        return keys

    rate = 0.01
    refs = []
    for file in (data_dir / "entities").glob("*.gz"):
        refs.append(read_keys.remote(file, rate, 155))

    lst: list[str] = [k for ref in list(ray.get(refs)) for k in ref]
    M.serialize_lines(lst, data_dir / "keys.txt")


def test_runtime(name: str, option: str):
    cfg = db_options[option]
    dbpath = data_dir / "databases" / (name + cfg["name"])

    if name == "zstd-6":
        deser_value = zstd_decompress_custom(orjson.loads)
        ser_value = zstd6_compress_custom(orjson.dumps)
    else:
        deser_value = orjson.loads
        ser_value = orjson.dumps

    db = RocksDBDict(
        str(dbpath),
        options=cfg["opts"],
        deser_key=partial(str, encoding="utf-8"),
        deser_value=deser_value,
        ser_value=ser_value,
    )
    timer = M.Timer()
    keys = M.deserialize_lines(data_dir / "keys.txt", trim=True, n_lines=10000)
    with timer.watch():
        count = 0
        for key in keys:
            count += len(db[key])

    rows = []
    if not (data_dir / "runtime.txt").exists():
        rows = [["name", "type", "runtime"]]
    rows.append([name + cfg["name"], "read", timer.get_time()])

    with open(data_dir / "runtime.txt", "a") as f:
        for row in rows:
            f.write(",".join(map(str, row)) + "\n")

    return count


args = ReadSpeedArgs().parse_args()
test_runtime(args.name, args.option)
