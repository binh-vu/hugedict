import os
import shutil
from typing import Generator
from glob import glob
from pathlib import Path

import pytest

from hugedict.hugedict.rocksdb import load, Options


@pytest.fixture()
def wdprops(resource_dir: Path, tmp_path: Path) -> Generator[Path, None, None]:
    dbpath = tmp_path / f"wdprops.db"

    load(
        str(dbpath),
        Options(create_if_missing=True),
        glob(f"{resource_dir}/wdprops/*.tsv"),
        {
            "record_type": {"type": "tabsep", "key": None, "value": None},
            "is_sorted": False,
        },
        verbose=False,
        compact=True,
    )

    yield dbpath

    shutil.rmtree(dbpath)
