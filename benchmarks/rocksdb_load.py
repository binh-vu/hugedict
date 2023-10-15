# Prerequisites:
# - install sem-desc: `pip install sem-desc`
# - data to test with in the ./data directory (e.g., ./data/wdentities/part-*.tsv.gz)

import multiprocessing
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from hugedict_v1.loader import FileFormat, load
from sm.prelude import M

from rocksdb import DB, Options  # type: ignore

multiprocessing.set_start_method("fork")

bench_dir = Path(__file__).parent
shutil.rmtree(bench_dir / "tempdir", ignore_errors=True)
(bench_dir / "tempdir").mkdir(exist_ok=True)
(bench_dir / "tempdir" / "python-rocksdb.db").mkdir(exist_ok=True)

infiles = [str(x) for x in (bench_dir / "data/wdentities").glob("part-*.tsv.gz")]

with M.Timer().watch_and_report("python-rocksdb"):
    db = DB(
        str(bench_dir / "tempdir" / "python-rocksdb.db" / "primary"),
        Options(create_if_missing=True),
    )
    load(
        db,
        infiles,
        FileFormat.tabsep,
        key_fn=M.identity_func,
        value_fn=M.identity_func,
        verbose=False,
    )
    db.compact_range()


from hugedict.rocksdb import Options, load

with M.Timer().watch_and_report("rust-rocksdb"):
    load(
        str(bench_dir / "tempdir" / "rust-rocksdb.db"),
        Options(create_if_missing=True),
        infiles,
        format={
            "record_type": {"type": "tabsep", "key": None, "value": None},
            "is_sorted": False,
        },
        verbose=True,
        compact=True,
    )
