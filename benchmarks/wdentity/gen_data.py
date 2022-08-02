from genericpath import exists
from multiprocessing import parent_process
import ray, glob, orjson
from pathlib import Path
from sm.prelude import M

from hugedict.misc import zstd6_compress_custom

ray.init()


@ray.remote
def generate_data(infile: Path, outdir: Path, name: str):
    (outdir / name).mkdir(exist_ok=True, parents=True)

    if name == "default":
        value_fn = orjson.dumps
    elif name == "zstd-6":
        value_fn = zstd6_compress_custom(orjson.dumps)
    else:
        assert False, name

    with M.get_open_fn(outdir / name / infile.name)(
        outdir / name / infile.name, "wb"
    ) as f:
        with M.get_open_fn(infile)(infile, "rb") as g:
            for line in g:
                object = orjson.loads(line)
                key = object["id"].encode()
                value = value_fn(object)

                f.write(len(key).to_bytes(8, byteorder="little"))
                f.write(key)
                f.write(len(value).to_bytes(8, byteorder="little"))
                f.write(value)


def run(name: str):
    data_dir = Path(__file__).parent.parent / "data"
    refs = []
    for file in (data_dir / "entities").glob("*.gz"):
        refs.append(generate_data.remote(file, data_dir, name))
    ray.get(refs)


# run("default")
# run("zstd-6")
