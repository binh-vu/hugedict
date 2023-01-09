import struct
from functools import partial
from pathlib import Path
from typing import List, Literal, Union

import orjson
from hugedict.prelude import (
    RocksDBCompressionOptions,
    RocksDBDict,
    RocksDBOptions,
)
from hugedict.types import HugeMutableMapping
from sm.prelude import M

EntAttr = Literal["label", "description", "aliases", "instanceof", "pagerank"]


def get_entity_attr_db(
    dbfile: Union[Path, str],
    attr: EntAttr,
    create_if_missing=False,
    read_only=True,
) -> Union[
    HugeMutableMapping[str, str],
    HugeMutableMapping[str, float],
    HugeMutableMapping[str, List[str]],
]:
    dbpath = Path(dbfile)
    realdbpath = dbpath.parent / dbpath.stem / f"{attr}.db"
    version = realdbpath / "_VERSION"

    if version.exists():
        ver = version.read_text()
        assert ver.strip() == "1", ver
    else:
        version.parent.mkdir(parents=True, exist_ok=True)
        version.write_text("1")

    if attr == "aliases" or attr == "instanceof":
        deser_value = orjson.loads
        ser_value = orjson.dumps
    elif attr == "pagerank":
        deser_value = partial(struct.unpack, "<d")
        ser_value = partial(struct.pack, "<d")
    else:
        deser_value = partial(str, encoding="utf-8")
        ser_value = str.encode

    db = RocksDBDict(
        path=str(realdbpath),
        options=RocksDBOptions(
            create_if_missing=create_if_missing,
            compression_type="zstd",
            compression_opts=RocksDBCompressionOptions(
                window_bits=-14, level=6, strategy=0, max_dict_bytes=16 * 1024
            ),
            zstd_max_train_bytes=100 * 16 * 1024,
        ),
        readonly=read_only,
        deser_key=partial(str, encoding="utf-8"),
        deser_value=deser_value,
        ser_value=ser_value,  # type: ignore
    )

    return db


db = get_entity_attr_db("/workspace/sm-dev/data/home/databases/wdentities_attr.db", "label")
db = get_entity_attr_db("/workspace/sm-dev/data/home/databases/wdentities_attr.db", "instanceof")

# Gather data from candidate generation in NED
# with open("/tmp/id.json.gz", "wb") as f:
#     ids = set()
#     for e in examples:
#         for link in e.gold_links.flat_iter():
#             if link is not None:
#                 ids.add(link.entity_id)
#                 for can in link.candidates:
#                     if can.entity_id is not None:
#                         ids.add(can.entity_id)
#     import orjson
#     f.write(orjson.dumps(list(ids.difference({None}))))

with open("/tmp/id.json.gz", "rb") as f:
    ids = orjson.loads(f.read())[:50000]

# with M.Timer().watch_and_report("single reads"):
#     res = {id: db[id + "_en"] for id in ids}
# print("single reads", len(res))

# with M.Timer().watch_and_report("batch reads"):
#     # res = {id: db[id] for id in ids}
#     res = dict(zip(ids, db._multi_get([(id + "_en").encode() for id in ids])))
# print("batch reads", len(res))
        
with M.Timer().watch_and_report("single reads"):
    res = {id: db[id] for id in ids}
print("single reads", len(res))

with M.Timer().watch_and_report("batch reads"):
    res = dict(zip(ids, db._multi_get([id.encode() for id in ids])))
print("batch reads", len(res))
