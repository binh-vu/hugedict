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

class PrefixExtractor: ...

def fixed_prefix(*, type: Literal["fixed_prefix"], size: int) -> PrefixExtractor: ...
def fixed_prefix_alike(
    *, type: Literal["fixed_prefix_alike"], prefix: str
) -> PrefixExtractor: ...

# Compression options. See more:
# - http://rocksdb.org/blog/2021/05/31/dictionary-compression.html
# - https://github.com/facebook/rocksdb/wiki/Space-Tuning
@dataclass
class CompressionOptions:
    window_bits: int
    level: int
    strategy: int
    max_dict_bytes: int

# Checkout the list of options here:
# - https://github.com/facebook/rocksdb/blob/0e0a19832e5f1e3584590edf796abd05c484e649/include/rocksdb/options.h#L432
# - https://github.com/facebook/rocksdb/blob/main/include/rocksdb/advanced_options.h
# - https://docs.rs/rocksdb/latest/rocksdb/struct.Options.html
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
    compression_type: Optional[DBCompressionStyle] = "lz4"
    bottommost_compression_type: Optional[DBCompressionStyle] = None
    prefix_extractor: Optional[PrefixExtractor] = None
    compression_opts: Optional[CompressionOptions] = None
    bottommost_compression_opts: Optional[CompressionOptions] = None
    # in here: http://rocksdb.org/blog/2021/05/31/dictionary-compression.html
    # recommended to 100x of max_dict_bytes
    zstd_max_train_bytes: Optional[int] = None
    bottommost_zstd_max_train_bytes: Optional[int] = None

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
    bin_kv:
        binary data of key-value pairs concatenated in the following format <key_size><key><value_size><value>
        where <key_size> and <value_size> are 8-byte unsigned integers encoded in little-endian
    """

    type: Literal["tabsep", "ndjson", "tuple2", "bin_kv"]
    # object's attribute contains the key, None if key is the object itself.
    key: Optional[str]
    # object's attribute contains the value, None if value is the object itself.
    value: Optional[str]

class FileFormat(TypedDict):
    record_type: RecordType
    # whether the file is sorted or not.
    is_sorted: bool

def load(
    dbpath: str,
    dbopts: Options,
    files: List[str],
    format: FileFormat,
    verbose: bool,
    compact: bool,
) -> None:
    """Load files into rocksdb database by building SST files and ingesting them.

    Raised exception when no sst files are created (i.e., no input files).

    Args:
        dbpath: path to rocksdb database
        dbopts: rocksdb options
        files: list of input files
        format: file format
        verbose: whether to print progress
        compact: whether to compact the database after loading
    """

def build_sst_file(
    dbopts: Options,
    outfile: str,
    input_generator: Callable[[], Optional[Tuple[bytes, bytes]]],
) -> bool:
    """Build SST file from the input generator

    Args:
        dbopts: rocksdb options
        outfile: output file
        input_generator: when the function is called, it should return a new key-value pair. when it returns None, the input is exhausted.

    Returns:
        True if the output file is created, False otherwise.
    """

def ingest_sst_files(dbpath: str, dbopts: Options, sst_files: List[str], compact: bool):
    """Ingest SST files into rocksdb database.

    Args:
        dbpath: path to rocksdb database
        dbopts: rocksdb options
        sst_files: list of SST files
        compact: whether to compact the database after loading
    """

class RocksDBDict(HugeMutableMapping[KP, V]):
    """A mutable mapping backed by rocksdb.

    Args:
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
    @property
    def options(self) -> Options:
        """Get db's options"""
    def _put(self, k: bytes, v: bytes):
        """Put the raw (bytes) key and value into the database."""
    def _get(self, k: bytes) -> bytes:
        """Get raw (bytes) value from the database. Raise KeyError if not found."""
    def get_int_property(
        self,
        name: Literal[
            "rocksdb.num-immutable-mem-table",
            "rocksdb.mem-table-flush-pending",
            "rocksdb.compaction-pending",
            "rocksdb.background-errors",
            "rocksdb.cur-size-active-mem-table",
            "rocksdb.cur-size-all-mem-tables",
            "rocksdb.size-all-mem-tables",
            "rocksdb.num-entries-active-mem-table",
            "rocksdb.num-entries-imm-mem-tables",
            "rocksdb.num-deletes-active-mem-table",
            "rocksdb.num-deletes-imm-mem-tables",
            "rocksdb.estimate-num-keys",
            "rocksdb.estimate-table-readers-mem",
            "rocksdb.is-file-deletions-enabled",
            "rocksdb.num-snapshots",
            "rocksdb.oldest-snapshot-time",
            "rocksdb.num-live-versions",
            "rocksdb.current-super-version-number",
            "rocksdb.estimate-live-data-size",
            "rocksdb.min-log-number-to-keep",
            "rocksdb.min-obsolete-sst-number-to-keep",
            "rocksdb.total-sst-files-size",
            "rocksdb.live-sst-files-size",
            "rocksdb.base-level",
            "rocksdb.estimate-pending-compaction-bytes",
            "rocksdb.num-running-compactions",
            "rocksdb.num-running-flushes",
            "rocksdb.actual-delayed-write-rate",
            "rocksdb.is-write-stopped",
            "rocksdb.estimate-oldest-key-time",
            "rocksdb.block-cache-capacity",
            "rocksdb.block-cache-usage",
            "rocksdb.block-cache-pinned-usage",
        ],
    ) -> Optional[int]:
        """Retrieves a RocksDB property's value and cast it to an integer.

        Full list of properties that return int values could be find [here](https://github.com/facebook/rocksdb/blob/08809f5e6cd9cc4bc3958dd4d59457ae78c76660/include/rocksdb/db.h#L654-L689).
        """
    def seek_keys(self, prefix: KP) -> Iterator[KP]:
        """Seek to the first key that matches the *entire* prefix. From
        there, the itereator will continue to read pairs as long as the
        prefix extracted from `key` matches the prefix extracted from `prefix`.

        Note: for this function to always iterate over keys that match the *entire*
        prefix, set options.prefix_extractor to the length of the prefix.
        """
    def seek_items(self, prefix: KP) -> Iterator[Tuple[KP, V]]:
        """Seek to the first key that matches the *entire* prefix. From
        there, the itereator will continue to read pairs as long as the
        prefix extracted from `key` matches the prefix extracted from `prefix`.

        Note: for this function to always iterate over keys that match the *entire*
        prefix, set options.prefix_extractor to the length of the prefix.
        """
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
