from functools import partial
from pathlib import Path

from hugedict.hugedict.rocksdb import Options, SecondaryDB, primary_db, stop_primary_db
from hugedict.parallel import LazyDBCacheFn


def test_start_and_close_primary_db(wdprops: Path, url: str):
    p = LazyDBCacheFn._start_primary_db(url, str(wdprops), Options())
    assert p.returncode is None

    # stop it
    stop_primary_db(url)

    # wait 3 seconds
    p.wait(3)

    assert p.returncode == 0


def test_primary_secondary_db(wdprops: Path, url: str):
    p = LazyDBCacheFn._start_primary_db(url, str(wdprops), Options())

    db0 = SecondaryDB(
        url,
        str(wdprops),
        str(wdprops / "secondaries/0"),
        Options(),
        deser_value=partial(str, encoding="utf-8"),
        ser_value=str.encode,
    )

    db1 = SecondaryDB(
        url,
        str(wdprops),
        str(wdprops / "secondaries/1"),
        Options(),
        deser_value=partial(str, encoding="utf-8"),
        ser_value=str.encode,
    )

    assert "P58" not in db0
    assert "P58" not in db1

    # setting P58 on a secondary db will make it available to other db through the primary db
    db1["P58"] = "screenwriter"
    assert "P58" in db0
    assert "P58" in db1

    stop_primary_db(url)
    p.wait(3)
    assert p.returncode == 0
