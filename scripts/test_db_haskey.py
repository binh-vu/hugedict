from hugedict.misc import identity
from hugedict.rocksdb import RocksDBDict


db = RocksDBDict("/tmp/hugedict/test.db", ser_key=identity, deser_key=identity)

keys = [
    b'["heavy_computing",[0.3204591],{}]',
    b'["heavy_computing",[0.4121965],{}]',
    b'["heavy_computing",[0.6555456],{}]',
    b'["heavy_computing",[0.8577781],{}]',
    b'["heavy_computing",[1.0413387],{}]',
    b'["heavy_computing",[1.1428052],{}]',
    b'["heavy_computing",[1.1561826],{}]',
    b'["heavy_computing",[1.3069451],{}]',
    b'["heavy_computing",[1.6266425],{}]',
    b'["heavy_computing",[1.6471777],{}]',
]

for key in keys:
    print("key in db:", key in db)
