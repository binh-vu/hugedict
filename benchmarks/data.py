# Prerequisites:
# - install sem-desc (for `sm`): `pip install sem-desc`
# - install kgdata: `pip install kgdata`
# - and other packages

import random
from pathlib import Path

import orjson
from kgdata.wikidata.db import get_entity_db
from sm.prelude import M
from tqdm import tqdm
from loguru import logger

data_dir = Path(__file__).parent / "data"

# generate benchmark data
random.seed(10)

db = get_entity_db("/workspace/sm-dev/data/wikidata/20211213/databases/wdentities.db")
n = 3000
part_size = 100
kvs = []

counter = 1
for i in tqdm(range(n), desc="load records"):
    for i in range(100):
        ent = db.get(f"Q{counter}", None)
        if ent is not None:
            break
        counter = counter + 1
    else:
        # we try it 100 times, if we don't find the entity, we hit the end of the db
        break

    kvs.append(ent.id.encode() + b"\t" + orjson.dumps(ent.to_dict()))
    counter += random.randint(1, 20)

random.shuffle(kvs)

logger.info("Creating wikidata dataset of {} records", len(kvs))

(data_dir / "wdentities").mkdir(exist_ok=True, parents=True)
counter = 0
for i in tqdm(range(0, n, part_size), desc="write records to disk"):
    file = data_dir / "wdentities" / f"part-{counter:04d}.tsv.gz"
    if len(kvs[i : i + part_size]) == 0:
        break
    M.serialize_byte_lines(kvs[i : i + part_size], file)
    counter += 1
