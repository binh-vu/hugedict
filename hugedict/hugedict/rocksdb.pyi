from dataclasses import dataclass
from typing import (
    Callable,
    Generic,
    Iterator,
    Literal,
    Optional,
    List,
    Tuple,
    TypedDict,
)

from hugedict.types import KP, V, HugeMutableMapping

DBCompactionStyle = Literal["level", "universal", "fifo"]
DBCompressionStyle = Literal[
    "none",
    "snappy",
    "zlib",
    "bz2",
    "lz4",
    "lz4hc",
    "zstd",
]

@dataclass
class Options:
    create_if_missing: Optional[bool] = None
    max_open_files: Optional[int] = None
    use_fsync: Optional[bool] = None
    bytes_per_sync: Optional[int] = None
    optimize_for_point_lookup: Optional[int] = None
    table_cache_numshardbits: Optional[int] = None
    max_write_buffer_number: Optional[int] = None
    write_buffer_size: Optional[int] = None
    target_file_size_base: Optional[int] = None
    min_write_buffer_number_to_merge: Optional[int] = None
    level_zero_stop_writes_trigger: Optional[int] = None
    level_zero_slowdown_writes_trigger: Optional[int] = None
    compaction_style: Optional[DBCompactionStyle] = None
    disable_auto_compactions: Optional[bool] = None
    max_background_jobs: Optional[int] = None
    max_subcompactions: Optional[int] = None
    compression_type: Optional[DBCompressionStyle] = None
    bottommost_compression_type: Optional[DBCompressionStyle] = None

class FileFormat(TypedDict):
    record_type: RecordType
    # whether the file is sorted or not.
    is_sorted: bool

class RecordType(TypedDict):
    """
    tabsep:
        tab separated format of serialized byte key and value
        serialized key must not contain tab character
        serialized value must not contain newline character such as \r\n.
        no key or value
    ndjson:
        each line is a json object, key is required but value is optional
    tuple2:
        each line is a json list of two items key and value, key and value are optional
    """

    type: Literal["tabsep", "ndjson", "tuple2"]
    # object's attribute contains the key, None if key is the object itself.
    key: Optional[str]
    # object's attribute contains the value, None if value is the object itself.
    value: Optional[str]

def load(
    dbpath: str,
    dbopts: Options,
    infiles: List[str],
    format: FileFormat,
    verbose: bool,
    compact: bool,
) -> None:
    """Load files into rocksdb database by building SST files and ingesting them.

    Arguments:
        dbpath: path to rocksdb database
        dbopts: rocksdb options
        infiles: list of input files
        format: file format
        verbose: whether to print progress
        compact: whether to compact the database after loading
    """

class RocksDBDict(HugeMutableMapping[KP, V]):
    """A mutable mapping backed by rocksdb.

    Arguments:
        path: path to rocksdb database
        opts: rocksdb options
        deser_key: deserialize key from a memoryview
        deser_value: deserialize value from a memoryview
        ser_value: serialize value to bytes
        readonly: whether to open the database in readonly mode (can open many times)
        secondary_mode: whether to open the database in secondary mode
        secondary_path: path to secondary rocksdb database
    """

    def __init__(
        self,
        path: str,
        options: Options,
        deser_key: Callable[[memoryview], KP],
        deser_value: Callable[[memoryview], V],
        ser_value: Callable[[V], bytes],
        readonly: bool = False,
        secondary_mode: bool = False,
        secondary_path: Optional[str] = None,
    ): ...
    @property
    def deser_value(self) -> Callable[[memoryview], V]:
        """Deserialize value from a memoryview."""
    @property
    def ser_value(self) -> Callable[[V], bytes]:
        """Serialize value to bytes."""
    def _put(self, k: bytes, v: bytes):
        """Put the raw (bytes) key and value into the database."""
    # RocksDB seems only provide prefix seek (https://github.com/facebook/rocksdb/wiki/Prefix-Seek)
    # currently, I haven't got any idea or do research to find an efficient implementation.
    # def prefix_keys(self, prefix: KP) -> Iterator[KP]:
    #     """Iterate over keys that have the given prefix."""
    # def prefix_items(self, prefix: KP) -> Iterator[Tuple[KP, V]]:
    #     """Iterate over items which keys have the given prefix"""
    def compact(self, start: Optional[KP], end: Optional[KP]):
        """Compact the database on the range of keys"""
    def try_catch_up_with_primary(self):
        """For secondary mode. Tries to catch up with the primary by reading as much as possible from the log files."""

def primary_db(url: str, path: str, opts: Options):
    """Start a primary rocksdb. Should be in a separated process."""

def stop_primary_db(url: str):
    """Stop the primary rocksdb."""

class SecondaryDB(Generic[KP, V]):
    """A secondary instance of rocksdb that falled back to primary if not found.

    It communicates with primary instance using nng.

    Arguments:
        url: url of the socket
        primary_path: path to primary rocksdb
        secondary_path: path to secondary rocksdb
        opts: rocksdb options
        deser_value: deserialize value from a memoryview
        ser_value: serialize value to bytes
    """

    def __init__(
        self,
        url: str,
        primary_path: str,
        secondary_path: str,
        opts: Options,
        deser_value: Callable[[memoryview], V],
        ser_value: Callable[[V], bytes],
    ): ...
    def __getitem__(self, key: KP) -> V:
        """Get key from database"""
        ...
    def __setitem__(self, key: KP, value: V) -> None:
        """Put key and value to database"""
        ...
    def __contains__(self, key: KP) -> bool:
        """Check if key is in database"""
        ...
