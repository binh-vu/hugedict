from hugedict.hugedict.rocksdb import primary_db, Options
import pickle


pickle.dumps(Options())
pickle.dumps(primary_db)
pickle.dumps(Options)
