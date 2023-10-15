import warnings

from hugedict.sqlite import SqliteDict, SqliteDictFieldType, SqliteKey

warnings.warn(
    "Module hugedict.sqlitedict has been renamed to hugedict.sqlite. Will be removed in 3.X",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = ["SqliteDict", "SqliteDictFieldType", "SqliteKey"]
