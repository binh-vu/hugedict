from dataclasses import dataclass
from typing import (
    Callable,
    Generic,
    Literal,
    Optional,
    List,
    TypedDict,
)

from hugedict.types import KP, V, HugeMutableMapping

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
    compaction_style: Optional[Literal["level", "universal", "fifo"]] = None
    disable_auto_compactions: Optional[bool] = None
    max_background_jobs: Optional[int] = None
    max_subcompactions: Optional[int] = None

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
    """

    def __init__(
        self,
        path: str,
        options: Options,
        deser_key: Callable[[memoryview], KP],
        deser_value: Callable[[memoryview], V],
        ser_value: Callable[[V], bytes],
        readonly: bool = False,
    ): ...
    def cache(self) -> HugeMutableMapping[KP, V]: ...

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
