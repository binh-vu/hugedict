import pickle

from hugedict.core.rocksdb import Options, primary_db

pickle.dumps(Options())
pickle.dumps(primary_db)
pickle.dumps(Options)
