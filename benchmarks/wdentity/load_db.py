from operator import itemgetter
import orjson
import ray
import glob
from pathlib import Path
import shutil
from hugedict.misc import zstd6_compress_custom, zstd_decompress_custom
from hugedict.prelude import (
    rocksdb_load,
    rocksdb_build_sst_file,
    rocksdb_ingest_sst_files,
    RocksDBOptions,
    RocksDBCompressionOptions,
)
from tap import Tap
from sm.prelude import M


class LoadDBArgs(Tap):
    name: str
    option: str


db_options = {
    "default": {"name": "", "opts": RocksDBOptions(create_if_missing=True)},
    "compress-1": {
        "name": "--compress-type=zstd",
        "opts": RocksDBOptions(create_if_missing=True, compression_type="zstd"),
    },
    "compress-2": {
        "name": "--compress-type=lz4",
        "opts": RocksDBOptions(create_if_missing=True, compression_type="lz4"),
    },
    "compress-3": {
        "name": "--compress-type=zstd-6",
        "opts": RocksDBOptions(
            create_if_missing=True,
            compression_type="zstd",
            compression_opts=RocksDBCompressionOptions(
                window_bits=15,
                level=6,
                strategy=0,
                max_dict_bytes=0,
                # max_dict_bytes=16 * 1024,
            ),
            # zstd_max_train_bytes=100 * 16 * 1024,
        ),
    },
    "compress-4": {
        "name": "--compress-type=zstd-6-rem",
        "opts": RocksDBOptions(
            create_if_missing=True,
            compression_type="zstd",
            compression_opts=RocksDBCompressionOptions(
                window_bits=15,
                level=6,
                strategy=0,
                max_dict_bytes=16 * 1024,
            ),
            zstd_max_train_bytes=100 * 16 * 1024,
        ),
    },
    "compress-5": {
        "name": "--compress-type=zstd-6-w14",
        "opts": RocksDBOptions(
            create_if_missing=True,
            compression_type="zstd",
            compression_opts=RocksDBCompressionOptions(
                window_bits=14,
                level=6,
                strategy=0,
                max_dict_bytes=0,
            ),
        ),
    },
    "compress-6": {
        "name": "--compress-type=zstd-6-w14-rem",
        "opts": RocksDBOptions(
            create_if_missing=True,
            compression_type="zstd",
            compression_opts=RocksDBCompressionOptions(
                window_bits=14,
                level=6,
                strategy=0,
                max_dict_bytes=16 * 1024,
            ),
            zstd_max_train_bytes=100 * 16 * 1024,
        ),
    },
    "compress-7": {
        "name": "--compress-type=bottom-zstd-6-w14-rem",
        "opts": RocksDBOptions(
            create_if_missing=True,
            compression_type="lz4",
            bottommost_compression_type="zstd",
            bottommost_compression_opts=RocksDBCompressionOptions(
                window_bits=14,
                level=6,
                strategy=0,
                max_dict_bytes=16 * 1024,
            ),
            bottommost_zstd_max_train_bytes=100 * 16 * 1024,
        ),
    },
    "compress-8": {
        "name": "--compress-type=zstd-6-w14-d10-rem",
        "opts": RocksDBOptions(
            create_if_missing=True,
            compression_type="zstd",
            compression_opts=RocksDBCompressionOptions(
                window_bits=14,
                level=6,
                strategy=0,
                max_dict_bytes=16 * 1024,
            ),
            zstd_max_train_bytes=10 * 16 * 1024,
        ),
    },
    "compress-9": {
        "name": "--compress-type=zstd-3-w14-rem",
        "opts": RocksDBOptions(
            create_if_missing=True,
            compression_type="zstd",
            compression_opts=RocksDBCompressionOptions(
                window_bits=14,
                level=3,
                strategy=0,
                max_dict_bytes=16 * 1024,
            ),
            zstd_max_train_bytes=100 * 16 * 1024,
        ),
    },
    "compress-10": {
        "name": "--compress-type=zstd-3-w-14-rem",
        "opts": RocksDBOptions(
            create_if_missing=True,
            compression_type="zstd",
            compression_opts=RocksDBCompressionOptions(
                window_bits=-14,
                level=3,
                strategy=0,
                max_dict_bytes=16 * 1024,
            ),
            zstd_max_train_bytes=100 * 16 * 1024,
        ),
    },
    "compress-11": {
        "name": "--compress-type=zstd-3-w-14-d10-rem",
        "opts": RocksDBOptions(
            create_if_missing=True,
            compression_type="zstd",
            compression_opts=RocksDBCompressionOptions(
                window_bits=-14,
                level=3,
                strategy=0,
                max_dict_bytes=16 * 1024,
            ),
            zstd_max_train_bytes=10 * 16 * 1024,
        ),
    },
    "compress-12": {
        "name": "--compress-type=zstd-6-w-14",
        "opts": RocksDBOptions(
            create_if_missing=True,
            compression_type="zstd",
            compression_opts=RocksDBCompressionOptions(
                window_bits=-14,
                level=6,
                strategy=0,
                max_dict_bytes=16 * 1024,
            ),
            zstd_max_train_bytes=100 * 16 * 1024,
        ),
    },
}


def load(data_dir: Path, name: str, opt_name: str, opts):
    dbpath = data_dir / "databases" / (name + opt_name)
    if dbpath.exists():
        shutil.rmtree(dbpath)

    rocksdb_load(
        str(dbpath),
        opts,
        glob.glob(str(data_dir / name / "part-*.gz")),
        {
            "record_type": {"type": "bin_kv", "key": None, "value": None},
            "is_sorted": False,
        },
        True,
        True,
    )


def load_new(data_dir: Path, name: str, opt_name: str, opts):
    dbpath = data_dir / "databases" / (name + opt_name)
    tempdir = data_dir / "temporary" / (name + opt_name)

    if dbpath.exists():
        shutil.rmtree(dbpath)

    if tempdir.exists():
        shutil.rmtree(tempdir)
    tempdir.mkdir(parents=True)

    @ray.remote
    def build_sst(name: str, infile: str, outfile: str, opts):
        if name == "default":
            value_fn = orjson.dumps
        elif name == "zstd-6":
            value_fn = zstd6_compress_custom(orjson.dumps)
        else:
            assert False, name

        kvs = sorted(
            [(obj["id"].encode(), value_fn(obj)) for obj in M.deserialize_jl(infile)],
            key=itemgetter(0),
        )
        tmp = {"counter": 0}

        def input_gen():
            if tmp["counter"] == len(kvs):
                return None
            obj = kvs[tmp["counter"]]
            tmp["counter"] += 1
            return obj

        rocksdb_build_sst_file(opts, outfile, input_gen)

        return outfile

    ray_opts = ray.put(opts)
    with M.Timer().watch_and_report(
        f"{name}-{opt_name}", append_to_file=data_dir / "runtime.load.csv"
    ):
        refs = []
        for file in (data_dir / "entities").glob("*.gz"):
            refs.append(
                build_sst.remote(
                    name, str(file), str(tempdir / (file.stem + ".sst")), ray_opts
                )
            )
        sst_files = ray.get(refs)
        rocksdb_ingest_sst_files(str(dbpath), opts, sst_files, True)


if __name__ == "__main__":
    data_dir = Path(__file__).parent.parent / "data"

    args = LoadDBArgs().parse_args()
    # load(
    #     data_dir,
    #     args.name,
    #     db_options[args.option]["name"],
    #     db_options[args.option]["opts"],
    # )

    ray.init(num_cpus=8)
    load_new(
        data_dir,
        args.name,
        db_options[args.option]["name"],
        db_options[args.option]["opts"],
    )
